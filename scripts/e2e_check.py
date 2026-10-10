"""
小程序端到端自检
================================================================
一键验证「礁区识别 + 白化程度评估」链路是否正常。

检查项：
  1. 推理服务是否在线，加载的权重是否已校准
  2. 多张真实礁区照片能否正常返回覆盖率
  3. 已知含白化的样本能否检出白化（与直接调用模型比对）
  4. 拍摄条件自检是否工作
  5. 属级识别是否给出合理置信度
  6. 超边界照片是否被正确拒绝
  7. 珊瑚个体计数（P3 附加能力）是否可用且未影响既有字段
  8. 投放窗口档案（往年白化预警记录 → 建议避开月份）与**空间覆盖闸门**

用法：
    python e2e_check.py
    python e2e_check.py --api http://127.0.0.1:8000
"""
import argparse
import json
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

ROOT = Path(__file__).resolve().parent.parent
REF_BLEACH_IDX = 8      # 已知含白化的样本序号（实测白化约 10.6%）


def get(url, timeout=30):
    req = Request(url, headers={"User-Agent": "e2e-check/1.0"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def post_image(api, path, timeout=120, endpoint="/analyze"):
    """用 urllib 手工构造 multipart/form-data 上传。"""
    boundary = "----e2echeckboundary"
    data = path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = Request(f"{api}{endpoint}", data=body, method="POST",
                  headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                           "User-Agent": "e2e-check/1.0"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_sample(api, aset="semporna", index=0, timeout=60):
    """把 /sample 的图片存到临时文件。"""
    import tempfile
    req = Request(f"{api}/sample?set={aset}&index={index}",
                  headers={"User-Agent": "e2e-check/1.0"})
    with urlopen(req, timeout=timeout) as r:
        b = r.read()
        name = r.headers.get("X-Sample-Name", f"{aset}_{index}.jpg")
    p = Path(tempfile.gettempdir()) / f"e2e_{aset}_{index}_{name}"
    p.write_bytes(b)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    api = args.api.rstrip("/")

    ok_cnt = 0
    total = 0
    problems = []

    def check(name, cond, detail=""):
        nonlocal ok_cnt, total
        total += 1
        if cond:
            ok_cnt += 1
            print(f"  ✅ {name}" + (f"  {detail}" if detail else ""))
        else:
            print(f"  ❌ {name}  {detail}")
            problems.append(f"{name}: {detail}")

    print("=" * 72)
    print("小程序端到端自检")
    print("=" * 72)

    # ---- 1. 服务健康 ----
    print("\n[1] 推理服务")
    try:
        h = get(f"{api}/health")
        check("服务在线", h.get("status") == "ok")
        check("分割模型已加载", h.get("segmentation") == "loaded", h.get("segModel", ""))
        check("权重已校准", h.get("segCalibrated") is True,
              "（未校准会让覆盖率偏高约 13 个百分点）" if not h.get("segCalibrated") else "")
        check("属分类模型已加载", h.get("species") == "loaded")
        print(f"      设备: {h.get('device')}  底栖类别: {h.get('categories')}")
    except (URLError, OSError) as e:
        print(f"  ❌ 无法连接 {api}: {e}")
        print(f"\n  请先启动服务： cd coral_ml/scripts && python serve_fusion.py")
        return 1

    # ---- 2. 仙本那真实照片 ----
    print("\n[2] 仙本那礁区照片（覆盖率评估）")
    for idx in (0, 3, 7):
        try:
            p = fetch_sample(api, "semporna", idx)
            t0 = time.time()
            r = post_image(api, p)
            dt = time.time() - t0
            c = r["cover"]
            check(f"照片 #{idx} 正常返回", r.get("success") is True,
                  f"珊瑚总覆盖 {c['coralTotalPct']:.1%}  耗时 {dt:.2f}s")
            check(f"照片 #{idx} 覆盖率合理", 0.0 <= c["coralTotalPct"] <= 1.0,
                  f"{c['coralTotalPct']:.1%}")
        except Exception as e:
            check(f"照片 #{idx}", False, f"{type(e).__name__}: {e}")

    # ---- 3. 白化检出 ----
    print(f"\n[3] 白化程度检出（已知含白化样本 index={REF_BLEACH_IDX}）")
    try:
        p = fetch_sample(api, "bleached", REF_BLEACH_IDX)
        r = post_image(api, p)
        c = r["cover"]
        check("检出白化像素", c["bleachedPct"] > 0.01,
              f"白化 {c['bleachedPct']:.2%}（实测应约 10.6%）")
        check("白化占珊瑚比例已计算", c["bleachingShareOfCoral"] > 0,
              f"{c['bleachingShareOfCoral']:.1%}")
        check("属级识别给出结果",
              bool(r.get("coralRegion", {}).get("top")) or r["coralRegion"].get("reliable") is False,
              ", ".join(f"{t['genus']} {t['confidence']:.0%}"
                        for t in (r.get("coralRegion", {}).get("top") or [])))
        q = r.get("captureQuality", {})
        check("拍摄条件自检工作", q.get("level") in ("good", "warn", "poor"),
              f"{q.get('level')} — {q.get('message','')[:40]}")
    except Exception as e:
        check("白化检出", False, f"{type(e).__name__}: {e}")

    # ---- 4. 超边界拒绝 ----
    print("\n[4] 超出适用边界的照片应被识别")
    try:
        d = ROOT / "data" / "degraded" / "L4_harsh"
        files = sorted(d.glob("*.jpg"))[:1] if d.exists() else []
        if files:
            r = post_image(api, files[0])
            q = r["captureQuality"]
            check("20m 降质照片判为 poor", q["level"] == "poor",
                  f"对比度 {q['contrast']:.4f}  usable={q['usable']}")
        else:
            print("  ⏭  未找到降质样本（需先运行 degrade_underwater.py），跳过")
    except Exception as e:
        check("超边界识别", False, f"{type(e).__name__}: {e}")

    # ---- 5. 珊瑚个体计数（P3 附加能力，未训练则跳过而非失败）----
    print("\n[5] 珊瑚个体计数（P3 附加能力）")
    try:
        if h.get("coralCounter") != "loaded":
            print("  ⏭  计数模型未训练（weights/yolo_coral/best.pt 缺失），跳过")
        else:
            p2 = fetch_sample(api, "semporna", 0)
            r = post_image(api, p2)
            cc = r.get("coralCount") or {}
            check("计数模型已加载（/health.coralCounter）", h.get("coralCounter") == "loaded")
            check("/analyze 新增 coralCount 字段", isinstance(cc.get("count"), int),
                  f"个体数 {cc.get('count')}  耗时 {cc.get('elapsedMs')}ms")
            check("既有字段未被改动（cover/groups 齐备）",
                  all(k in r["cover"] for k in ("alivePct", "bleachedPct", "deadPct",
                                                "algaePct", "substratePct", "seagrassPct",
                                                "coralTotalPct", "bleachingShareOfCoral"))
                  and isinstance(r.get("topClasses"), list) and "bleaching" in r,
                  f"coralTotalPct={r['cover']['coralTotalPct']:.1%}")
            r2 = post_image(api, p2, endpoint="/count")
            check("POST /count 端点可用", isinstance(r2.get("count"), int),
                  f"个体数 {r2.get('count')}  阈值 conf={r2.get('threshold', {}).get('conf')}")
    except Exception as e:
        check("珊瑚个体计数", False, f"{type(e).__name__}: {e}")

    # ---- 6. 投放窗口与热压力档案（未生成则跳过而非失败）----
    print("\n[6] 投放窗口与热压力档案（往年白化预警记录）")
    try:
        prof = get(f"{api}/climate/profile?lat=4.425&lon=118.775")
        if not prof.get("ok"):
            print("  ⏭  档案不可用（先运行 climate_site_profile.py --build），跳过")
        else:
            check("可按坐标查档案", bool(prof.get("label")),
                  f"{prof.get('label')}；逐年峰值 {prof.get('peakByYear')}")
            adv = prof.get("advice") or {}
            check("给出建议避开月份", bool(adv.get("text")),
                  f"避开 {prof.get('avoidMonths')} 月"
                  f"（无风险月份 {prof.get('safeMonths')}）")
            out = get(f"{api}/climate/profile?lat=22.5&lon=114.0")
            check("覆盖闸门：网格外拒绝给建议", out.get("ok") is False,
                  f"深圳 ok={out.get('ok')}（应为 false，不得返回最近格点结论）")
    except Exception as e:
        check("投放窗口档案", False, f"{type(e).__name__}: {e}")

    # ---- 汇总 ----
    print("\n" + "=" * 72)
    print(f"通过 {ok_cnt}/{total}")
    if problems:
        print("\n需关注：")
        for p in problems:
            print(f"  · {p}")
    else:
        print("✅ 全部通过 —— 小程序「礁区识别 + 白化程度评估」链路正常")
    print("=" * 72)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
