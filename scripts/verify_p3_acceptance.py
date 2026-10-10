"""
P3 验收一键自检（把「验收标准」变成可执行检查）
============================================================
方案 v5 · P3 的验收标准有两条，外加用户追加的两条工程要求，共四项：

  ① 计数质量：mAP@0.5 ≥ 0.35          （reports/yolo_coral_metrics.json）
  ② 不伤现有：分割 mIoU 不下降          （before/after 两份 mIoU JSON）
  ③ 只新增字段：既有输出逐键未变        （serve_before_p3.json vs serve_after_p3.json）
  ④ 链路可用：端到端自检全通过          （实跑 e2e_check.py 并解析通过数）

用法（服务需已启动）：
    python verify_p3_acceptance.py
    python verify_p3_acceptance.py --skip-e2e     # 服务没起时跳过第 ④ 项

输出：reports/p3_verification.json（可直接进报告，未人工誊抄）
退码：全部通过 0，否则 1
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "reports"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_serve_additive import diff  # noqa: E402


def load(name):
    p = R / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def check_counting():
    m = load("yolo_coral_metrics.json")
    if not m:
        return False, "缺少 reports/yolo_coral_metrics.json（先跑 train_yolo_coral.py）", {}
    det = m["detection"]
    ok = det["mAP50"] >= 0.35
    return ok, f"mAP@0.5 = {det['mAP50']}（阈值 0.35）", {
        "mAP50": det["mAP50"], "mAP50_95": det["mAP50_95"],
        "precision": det["precision"], "recall": det["recall"],
        "valImages": m["valImages"], "epochs": m["epochs"], "imgsz": m["imgsz"],
        "trainMinutes": m["trainMinutes"], "counting": m["counting"],
    }


def check_segmentation():
    b = load("segmentation_miou_1024.json")
    a = load("segmentation_miou_1024_after_p3.json")
    if not b or not a:
        return False, "缺少分割 mIoU 的 before/after 文件", {}
    dm = a["mIoU"] - b["mIoU"]
    dp = a["pixelAccuracy"] - b["pixelAccuracy"]
    ok = dm >= -1e-9 and dp >= -1e-9
    return ok, (f"mIoU {b['mIoU']} → {a['mIoU']}（Δ {dm:+.6f}）；"
                f"像素准确率 {b['pixelAccuracy']} → {a['pixelAccuracy']}（Δ {dp:+.6f}）"), {
        "mIoUBefore": b["mIoU"], "mIoUAfter": a["mIoU"], "mIoUDelta": round(dm, 8),
        "pixelAccBefore": b["pixelAccuracy"], "pixelAccAfter": a["pixelAccuracy"],
        "nImages": a["nImages"], "inputSize": a["inputSize"],
    }


def check_additive():
    b, a = load("serve_before_p3.json"), load("serve_after_p3.json")
    if not b or not a:
        return False, "缺少 serve_before/after_p3.json（先跑 verify_serve_additive.py --capture）", {}
    problems, added, maxdiff = [], [], [0.0]
    for case in b:
        if case not in a:
            problems.append(f"缺少用例 {case}")
            continue
        p, ad = diff(b[case], a[case], case, maxdiff=maxdiff)
        problems += p
        added += ad
    ok = not problems
    detail = (f"既有键最大数值变化 {maxdiff[0]:.3g}；新增键 {sorted(set(added))}"
              if ok else f"{len(problems)} 处既有输出被改动：" + "; ".join(problems[:5]))
    return ok, detail, {"existingKeysMaxChange": maxdiff[0], "addedKeys": sorted(set(added)),
                        "problems": problems}


def check_e2e(skip=False):
    if skip:
        return True, "已跳过（--skip-e2e）", {"skipped": True}
    p = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "e2e_check.py")],
                       cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    m = re.search(r"通过\s+(\d+)/(\d+)", out)
    if not m:
        return False, f"无法解析 e2e_check 输出（退出码 {p.returncode}）", {"tail": out[-400:]}
    ok_n, tot = int(m.group(1)), int(m.group(2))
    ok = ok_n == tot and p.returncode == 0
    return ok, f"端到端自检 {ok_n}/{tot}", {"passed": ok_n, "total": tot, "returncode": p.returncode}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-e2e", action="store_true")
    args = ap.parse_args()

    checks = [
        ("① 计数质量：mAP@0.5 ≥ 0.35", check_counting),
        ("② 不伤现有：分割指标不下降", check_segmentation),
        ("③ 只新增字段：既有输出不变", check_additive),
        ("④ 链路可用：端到端自检", lambda: check_e2e(args.skip_e2e)),
    ]
    results, all_ok = {}, True
    print("=" * 74)
    print("P3 验收自检（YOLOv9 珊瑚个体计数）")
    print("=" * 74)
    for name, fn in checks:
        ok, detail, data = fn()
        all_ok &= ok
        results[name] = {"passed": bool(ok), "detail": detail, **data}
        print(f"  {'✅' if ok else '❌'} {name}\n      {detail}")

    out = R / "p3_verification.json"
    out.write_text(json.dumps({
        "task": "P3 acceptance self-check",
        "allPassed": bool(all_ok),
        "checks": results,
        "criteria": {
            "counting": "mAP@0.5 >= 0.35（Coralscapes 官方 validation split，166 张，单类 coral）",
            "segmentation": "分割 mIoU / 逐像素准确率不下降（同口径 1024px 复跑）",
            "additive": "serve_fusion.py 既有输出逐键未变，只新增 coralCount / coralCounter / POST /count",
            "e2e": "e2e_check.py 全项通过",
        },
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=" * 74)
    print(f"{'✅ 全部通过' if all_ok else '❌ 存在未通过项'}   证据：{out}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
