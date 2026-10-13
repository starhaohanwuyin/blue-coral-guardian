"""
个体计数的**推理分辨率**扫描（P3 后续优化）
============================================================
为什么需要它：Coralscapes 图像是 **2:1**（2048×1024），而 YOLO 默认把方图
letterbox 到 imgsz×imgsz —— **一半画布被灰边浪费**，个体只拿到 imgsz/2 的短边像素。
分辨率是否值得提高，必须实测，而不是拍脑袋。

本脚本在同一权重、同一验证集上扫 imgsz，输出 mAP 与耗时，并写
`reports/yolo_coral_resolution.json`。

用法：
    python eval_yolo_resolution.py                      # 默认 640/800/1024/1280
    python eval_yolo_resolution.py --sizes 640 896 1152
"""
import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEIGHTS = ROOT / "weights" / "yolo_coral" / "best.pt"
DATA = ROOT / "data" / "yolo_coral" / "data.yaml"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default=str(WEIGHTS))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--sizes", type=int, nargs="*", default=[640, 800, 1024, 1280])
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--workers", type=int, default=0, help="0 = 不用多进程（否则脚本必须在真实文件里）")
    ap.add_argument("--out", default=str(ROOT / "reports" / "yolo_coral_resolution.json"))
    args = ap.parse_args()

    if not Path(args.weights).exists():
        raise SystemExit(f"缺少权重 {args.weights}，先运行 train_yolo_coral.py")

    # 统一成绝对路径：否则 report 里的相对路径换算会抛 ValueError
    # （`Path('weights/…').relative_to(ROOT)` —— 与 train_yolo_coral 踩过的同一类坑）
    w_abs = Path(args.weights)
    if not w_abs.is_absolute():
        w_abs = (ROOT / w_abs).resolve()
    try:
        w_rel = str(w_abs.relative_to(ROOT))
    except ValueError:
        w_rel = str(w_abs)

    from ultralytics import YOLO
    model = YOLO(str(w_abs))

    rows = []
    for sz in args.sizes:
        t0 = time.time()
        r = model.val(data=args.data, imgsz=sz, batch=args.batch, workers=args.workers,
                      split="val", plots=False, verbose=False)
        dt = time.time() - t0
        rows.append({
            "imgsz": sz,
            "mAP50": round(float(r.box.map50), 6),
            "mAP50_95": round(float(r.box.map), 6),
            "precision": round(float(r.box.mp), 6),
            "recall": round(float(r.box.mr), 6),
            "valSeconds": round(dt, 1),
        })
        print(f"imgsz={sz:<6} mAP50={rows[-1]['mAP50']:.4f}  mAP50-95={rows[-1]['mAP50_95']:.4f}  "
              f"P={rows[-1]['precision']:.4f}  R={rows[-1]['recall']:.4f}  ({dt:.0f}s)", flush=True)

    best = max(rows, key=lambda r: r["mAP50"])
    out = {
        "task": "P3 counting inference-resolution sweep",
        "weights": w_rel,
        "valImages": 166,
        "rows": rows,
        "bestImgsz": best["imgsz"],
        "note": ("同一权重只改推理长边。训练用的是 imgsz 640（方图 letterbox，2:1 图像有 50% 灰边），"
                 "因此高分辨率推理可看作「训练分辨率 vs 测试分辨率」的差异度量。"),
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n最佳 imgsz={best['imgsz']}（mAP50 {best['mAP50']}）→ {args.out}")


if __name__ == "__main__":
    main()
