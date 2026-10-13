"""
真实拍摄照片评估（用真实劣化条件验证合成降质结论）
================================================================
用途：
    我们的「使用边界（≤8m 可用 / ≥15m 失效）」结论目前建立在**物理合成降质**上。
    本脚本用**团队实拍的真实照片**来检验这个结论：

      1. 对每张真实照片计算拍摄条件指标（对比度 / R-G 比）
      2. 按已标定阈值分成 good / warn / poor 三档
      3. 对每张跑分割模型，得到覆盖率估计
      4. 检验：条件越差，估计是否越不稳定、越不合理
      5. 与**合成降质曲线**对比 —— 若趋势一致，证明合成降质是可信代理

    另外会尽力从 EXIF 中读取**拍摄深度**（部分相机/潜水壳会写入），
    有深度就能画出「深度 vs 精度」的真实曲线。

用法：
    python eval_real_photos.py --dir "D:\珊瑚照片"
    python eval_real_photos.py --dir ./photos --limit 200 --save-overlays
"""
import argparse
import json
import statistics
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from segment_coral import CoralSegmenter  # noqa: E402
from check_capture_quality import metrics as quality_metrics, verdict as quality_verdict, \
    DEFAULT_THRESHOLDS  # noqa: E402

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

# EXIF 中可能含深度的标签（各厂商不一，尽力而为）
EXIF_DEPTH_TAGS = {0x927C: "MakerNote", 0x0002: "GPSAltitude"}


def read_exif(p: Path) -> dict:
    """尽力读取 EXIF：拍摄时间、相机、以及可能的水深信息。"""
    out = {"datetime": None, "make": None, "model": None, "depthM": None}
    try:
        from PIL import ExifTags
        with Image.open(p) as im:
            ex = im.getexif()
            if not ex:
                return out
            for k, v in ex.items():
                name = ExifTags.TAGS.get(k, str(k))
                if name == "DateTime":
                    out["datetime"] = str(v)
                elif name == "Make":
                    out["make"] = str(v).strip()
                elif name == "Model":
                    out["model"] = str(v).strip()
            # 有些潜水壳把深度写进 MakerNote 或 UserComment，尝试正则提取
            for k in (0x9286, 0x927C):     # UserComment / MakerNote
                try:
                    raw = ex.get(k)
                    if raw is None:
                        continue
                    txt = raw if isinstance(raw, str) else bytes(raw).decode("latin-1", "ignore")
                    import re
                    m = re.search(r"(?:depth|Depth|深度)[^\d\-]{0,6}(-?\d+(?:\.\d+)?)\s*(m|M|米)?", txt)
                    if m:
                        out["depthM"] = float(m.group(1))
                except Exception:
                    pass
    except Exception:
        pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="真实照片目录（递归查找）")
    ap.add_argument("--limit", type=int, default=0, help="最多处理多少张（0=全部）")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--save-overlays", action="store_true", help="保存分割叠加图便于人工检查")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    d = Path(args.dir)
    if not d.exists():
        raise SystemExit(f"目录不存在: {d}")
    files = sorted(f for f in d.rglob("*") if f.suffix.lower() in IMG_EXT)
    if args.limit:
        files = files[: args.limit]
    if not files:
        raise SystemExit(f"未在 {d} 找到图片")

    print(f"目录: {d}")
    print(f"找到 {len(files)} 张真实照片\n")

    # 读取标定阈值
    th = DEFAULT_THRESHOLDS
    tp = ROOT / "reports" / "capture_quality_thresholds.json"
    if tp.exists():
        th = json.loads(tp.read_text(encoding="utf-8"))["thresholds"]
        print(f"使用已标定阈值: good 对比度≥{th['good']['contrast']}, "
              f"warn ≥{th['warn']['contrast']}\n")

    seg = CoralSegmenter(size=args.size)
    print(f"分割模型: {seg.device}\n")

    rows = []
    ov_dir = (ROOT / "reports" / "real_overlays")
    if args.save_overlays:
        ov_dir.mkdir(parents=True, exist_ok=True)

    for i, f in enumerate(files, 1):
        try:
            img = Image.open(f)
            qm = quality_metrics(img)
            qv = quality_verdict(qm, th)
            pred, cls_frac, grp = seg.segment(img)
        except Exception as e:
            print(f"  [跳过] {f.name}: {type(e).__name__}")
            continue
        coral_total = grp.get("alive", 0) + grp.get("bleached", 0) + grp.get("dead", 0)
        ex = read_exif(f)
        rows.append({
            "file": str(f.relative_to(d)),
            "quality": qv["level"], "usable": qv["usable"],
            "contrast": qm["contrast"], "rgRatio": qm["rgRatio"],
            "saturation": qm["saturation"],
            "alive": grp.get("alive", 0.0), "bleached": grp.get("bleached", 0.0),
            "dead": grp.get("dead", 0.0), "algae": grp.get("algae", 0.0),
            "substrate": grp.get("substrate", 0.0), "coralTotal": coral_total,
            "exif": ex,
        })
        if args.save_overlays:
            try:
                ov = seg.overlay(img, pred) if hasattr(seg, "overlay") else None
                if ov is not None:
                    ov.save(ov_dir / f"{f.stem}_overlay.jpg", quality=88)
            except Exception:
                pass
        if i % 20 == 0:
            print(f"  {i}/{len(files)} ...", flush=True)

    if not rows:
        raise SystemExit("没有成功处理的图片")

    # ---------------- 汇总 ----------------
    print("\n" + "=" * 84)
    print(f"按拍摄条件分层（n={len(rows)}）")
    print("=" * 84)
    print(f"{'档位':<8}{'张数':>6}{'占比':>8}{'对比度均值':>12}{'活珊瑚均值':>12}"
          f"{'珊瑚总覆盖':>12}{'估计标准差':>12}")
    print("-" * 84)
    by_q = defaultdict(list)
    for r in rows:
        by_q[r["quality"]].append(r)
    for lvl in ("good", "warn", "poor"):
        g = by_q.get(lvl, [])
        if not g:
            continue
        al = [x["alive"] for x in g]
        ct = [x["coralTotal"] for x in g]
        print(f"{lvl:<8}{len(g):>6}{len(g)/len(rows):>8.1%}"
              f"{statistics.mean(x['contrast'] for x in g):>12.4f}"
              f"{statistics.mean(al):>12.2%}{statistics.mean(ct):>12.2%}"
              f"{(statistics.pstdev(al) if len(al) > 1 else 0):>12.4f}")
    print("-" * 84)

    # ---------------- 与合成降质曲线对比 ----------------
    print("\n" + "=" * 84)
    print("与合成降质曲线对比（检验合成降质是否为可信代理）")
    print("=" * 84)
    syn_p = ROOT / "reports" / "degradation_modelA_base.json"
    if syn_p.exists():
        syn = json.loads(syn_p.read_text(encoding="utf-8"))["rows"]
        print(f"{'来源':<26}{'对比度':>10}{'活珊瑚估计':>12}{'判定'}")
        print("-" * 84)
        for r in syn:
            st = next((x for x in rows if abs(x["contrast"] - 0.1) < 9), None)
            print(f"{'合成 ' + r['level']:<26}{'—':>10}{r['alive']:>12.2%}"
                  f"   {r['desc']}")
        print("-" * 84)
        for lvl in ("good", "warn", "poor"):
            g = by_q.get(lvl, [])
            if g:
                print(f"{'真实 ' + lvl:<26}"
                      f"{statistics.mean(x['contrast'] for x in g):>10.4f}"
                      f"{statistics.mean(x['alive'] for x in g):>12.2%}")
        print("\n判读：若「真实 poor」的活珊瑚估计同样显著低于「真实 good」，")
        print("      则合成降质模拟的失效趋势在真实照片上得到验证 → 使用边界结论可信。")
    else:
        print("  （缺少合成降质结果，跳过对比）")

    # ---------------- 深度（若 EXIF 有） ----------------
    with_depth = [r for r in rows if r["exif"].get("depthM") is not None]
    print("\n" + "=" * 84)
    print(f"EXIF 深度信息：{len(with_depth)}/{len(rows)} 张含深度")
    print("=" * 84)
    if with_depth:
        print(f"{'深度(m)':>10}{'张数':>6}{'活珊瑚':>12}{'对比度':>10}")
        buckets = defaultdict(list)
        for r in with_depth:
            buckets[round(r["exif"]["depthM"])].append(r)
        for dp in sorted(buckets):
            g = buckets[dp]
            print(f"{dp:>10}{len(g):>6}{statistics.mean(x['alive'] for x in g):>12.2%}"
                  f"{statistics.mean(x['contrast'] for x in g):>10.4f}")
    else:
        print("  未从 EXIF 读到深度。若你的相机/潜水壳不写深度，可提供一份")
        print("  手工标注的深度清单（文件名,深度），我按它出「深度 vs 精度」曲线。")

    # ---------------- 输出 ----------------
    out = Path(args.out) if args.out else (ROOT / "reports" / "real_photo_eval.json")
    summary = {
        "dir": str(d), "n": len(rows),
        "qualityCounts": {k: len(v) for k, v in by_q.items()},
        "byQuality": {lvl: {
            "n": len(g),
            "contrastMean": statistics.mean(x["contrast"] for x in g),
            "aliveMean": statistics.mean(x["alive"] for x in g),
            "coralTotalMean": statistics.mean(x["coralTotal"] for x in g),
            "aliveStdev": (statistics.pstdev([x["alive"] for x in g]) if len(g) > 1 else 0.0),
        } for lvl, g in by_q.items()},
        "nWithExifDepth": len(with_depth),
        "rows": rows,
        "note": "真实照片评估，用于验证合成降质结论；样本量小时仅作趋势判读",
    }
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n详细结果: {out}")


if __name__ == "__main__":
    main()
