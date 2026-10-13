"""
个体计数的置信度阈值扫描（P3）
============================================================
mAP **不依赖**置信度阈值（它是 PR 曲线下的面积），但**「数出来有几株」依赖阈值**。
所以验收指标用 mAP，而**产品要报的个体数**必须先把阈值选对。

本脚本在官方 validation split（166 张）上逐阈值统计：
    预测总数 / 相对真值的偏差 / 逐图 MAE / 完全命中率
并给出「偏差最小」的推荐阈值 → `reports/yolo_coral_count_thresholds.json`

用法：
    python tune_yolo_counting_threshold.py
    python tune_yolo_counting_threshold.py --confs 0.05 0.1 0.15 0.2 0.25 0.3 0.4
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEIGHTS = ROOT / "weights" / "yolo_coral" / "best.pt"
DATA = ROOT / "data" / "yolo_coral"
DEFAULT_CONFS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default=str(WEIGHTS))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--confs", type=float, nargs="*", default=DEFAULT_CONFS)
    ap.add_argument("--out", default=str(ROOT / "reports" / "yolo_coral_count_thresholds.json"))
    args = ap.parse_args()

    if not Path(args.weights).exists():
        raise SystemExit(f"缺少权重 {args.weights}，先运行 train_yolo_coral.py")

    from ultralytics import YOLO
    import torch

    data_dir = Path(args.data)
    val_dir = data_dir / "images" / "val"
    lab_dir = data_dir / "labels" / "val"
    jpgs = sorted(val_dir.glob("*.jpg"))
    if not jpgs:
        raise SystemExit(f"找不到验证集图片: {val_dir}")

    gt = {}
    for jpg in jpgs:
        lab = lab_dir / f"{jpg.stem}.txt"
        gt[jpg.stem] = sum(1 for ln in lab.read_text(encoding="utf-8").splitlines() if ln.strip())
    gt_total = sum(gt.values())
    print(f"验证集 {len(jpgs)} 张，真值个体总数 {gt_total}")

    model = YOLO(str(args.weights))
    device = "0" if torch.cuda.is_available() else "cpu"
    gt_list = [gt[j.stem] for j in jpgs]

    rows = []
    for conf in args.confs:
        preds = []
        for jpg in jpgs:
            r = model.predict(source=str(jpg), imgsz=args.imgsz, conf=conf, iou=args.iou,
                              device=device, verbose=False, plots=False)[0]
            preds.append(int(len(r.boxes)) if r.boxes is not None else 0)
        tot = sum(preds)
        n = len(preds)
        rows.append({
            "conf": conf,
            "predTotal": tot,
            "bias": round((tot - gt_total) / gt_total, 4),
            "maePerImage": round(sum(abs(a - b) for a, b in zip(gt_list, preds)) / n, 4),
            "exactMatchRate": round(sum(1 for a, b in zip(gt_list, preds) if a == b) / n, 4),
        })
        print(f"  conf={conf:<5} 预测 {tot:>5}  偏差 {rows[-1]['bias']:+.1%}  "
              f"MAE {rows[-1]['maePerImage']:.2f}  完全命中 {rows[-1]['exactMatchRate']:.1%}", flush=True)

    best = min(rows, key=lambda r: (abs(r["bias"]), r["maePerImage"]))
    out = {
        "task": "P3 counting confidence-threshold sweep",
        "weights": str(Path(args.weights).relative_to(ROOT)),
        "valImages": len(jpgs), "gtTotal": gt_total,
        "imgsz": args.imgsz, "iou": args.iou,
        "rows": rows,
        "recommendedConf": best["conf"],
        "recommendedBias": best["bias"],
        "note": ("mAP 与阈值无关，但计数与阈值强相关；"
                 "推荐值 = |总量偏差| 最小者。真值为掩膜连通域（自动标注）。"),
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 68)
    print("个体计数阈值扫描（Coralscapes 官方 validation split）")
    print("=" * 68)
    print(f"{'conf':>6}{'预测总数':>10}{'偏差':>10}{'MAE/图':>10}{'完全命中':>10}")
    for r in rows:
        print(f"{r['conf']:>6}{r['predTotal']:>10}{r['bias']:>+10.1%}"
              f"{r['maePerImage']:>10.2f}{r['exactMatchRate']:>10.1%}")
    print(f"\n推荐阈值 conf = {best['conf']}（偏差 {best['bias']:+.1%}）")
    print(f"结果 JSON: {args.out}")


if __name__ == "__main__":
    main()
