"""
YOLOv9 珊瑚个体计数 —— 训练与评估（P3 第 4–5 步）
============================================================
数据集由 build_yolo_coral_dataset.py 从 Coralscapes 掩膜生成：
    data/yolo_coral/{images,labels}/{train,val}  +  data.yaml
    · train = Coralscapes 官方 train split（已下载分片）
    · val   = Coralscapes 官方 validation split（166 张，与分割 mIoU 同一份数据）
    · 1 类：coral（只回答"这里有一个珊瑚个体"）

验收标准（方案 v5 · P3）：**mAP@0.5 ≥ 0.35**，且现有分割指标不下降
（分割不下降由 eval_segmentation_miou.py 单独复核，本脚本不碰分割权重）。

用法：
    python train_yolo_coral.py                       # 训练 + 评估（幂等）
    python train_yolo_coral.py --epochs 50 --batch 8 --imgsz 640
    python train_yolo_coral.py --eval-only           # 只重新评估已有权重
    python train_yolo_coral.py --force               # 忽略已有权重重新训练

8GB 显存约束：imgsz 640 / batch ≤ 8（原文 §6 提示）。
"""
import argparse
import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "yolo_coral" / "data.yaml"
W_DIR = ROOT / "weights" / "yolo_coral"
REPORTS = ROOT / "reports"
ACCEPT_MAP50 = 0.35


def pick_device():
    import torch
    return "0" if torch.cuda.is_available() else "cpu"


def resolve_model(name: str) -> str:
    """预训练权重优先用仓库内副本，避免训练中途联网。"""
    cand = W_DIR / name
    if cand.exists():
        return str(cand)
    return name


def out_weights(weights_dir):
    """权重的落盘位置（烟雾测试可用 --weights-dir 改到别处，避免污染生产权重）。"""
    return Path(weights_dir) / "best.pt"


def rel(p) -> str:
    """相对 ROOT 的展示路径；不在 ROOT 下就原样返回。"""
    try:
        return str(Path(p).relative_to(ROOT))
    except ValueError:
        return str(p)


def train(args):
    from ultralytics import YOLO, settings
    settings.update({"sync": False, "tensorboard": False, "clearml": False, "comet": False})

    if not DATA.exists():
        raise SystemExit(f"缺少数据集 {DATA}\n请先运行: python build_yolo_coral_dataset.py")

    model = YOLO(resolve_model(args.model))
    t0 = time.time()
    kwargs = dict(
        data=str(DATA),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=pick_device(),
        project=str(ROOT / "runs"), name=args.name, exist_ok=True,
        workers=args.workers,
        patience=args.patience,
        plots=False, val=True, seed=0, deterministic=True,
        resume=args.resume,
        optimizer=args.optimizer,
        close_mosaic=args.close_mosaic,
        pretrained=True,
    )
    if args.lr0 is not None:
        kwargs["lr0"] = args.lr0
    if args.lrf is not None:
        kwargs["lrf"] = args.lrf
    if args.mosaic is not None:
        kwargs["mosaic"] = args.mosaic
    res = model.train(**kwargs)
    train_sec = time.time() - t0
    save_dir = Path(res.save_dir) if getattr(res, "save_dir", None) else ROOT / "runs" / args.name
    best = save_dir / "weights" / "best.pt"
    if not best.exists():
        raise SystemExit(f"训练未产出 best.pt：{best}")
    best_out = out_weights(args.weights_dir)
    best_out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, best_out)
    print(f"[训练] 完成 {train_sec/60:.1f} 分钟 → {best_out}")
    return train_sec, str(save_dir)


def evaluate(args, train_sec=None, save_dir=None):
    from ultralytics import YOLO
    best_out = out_weights(args.weights_dir)
    metrics_out = Path(args.metrics_out)
    if not best_out.exists():
        raise SystemExit(f"缺少权重 {best_out}，先运行训练（不加 --eval-only）")

    model = YOLO(str(best_out))
    m = model.val(data=str(DATA), imgsz=args.imgsz, batch=args.batch, device=pick_device(),
                  split="val", plots=False, verbose=False)

    mAP50 = float(m.box.map50)
    mAP5095 = float(m.box.map)
    prec = float(m.box.mp)
    rec = float(m.box.mr)

    # ---- 个体计数口径：逐图预测框数 vs GT 框数 ----
    # val 目录由 data.yaml 所在目录派生，避免硬编码（§8.2 #13 的教训）
    val_dir = Path(DATA).parent / "images" / "val"
    val_lab = Path(DATA).parent / "labels" / "val"
    gt_counts, pred_counts, rows = [], [], []
    jpgs = sorted(val_dir.glob("*.jpg"))
    for jpg in jpgs:
        lab = val_lab / f"{jpg.stem}.txt"
        gt = sum(1 for line in lab.read_text(encoding="utf-8").splitlines() if line.strip()) if lab.exists() else 0
        r = model.predict(source=str(jpg), imgsz=args.imgsz, conf=args.conf, iou=args.iou,
                          device=pick_device(), verbose=False, plots=False)[0]
        pc = int(len(r.boxes)) if r.boxes is not None else 0
        gt_counts.append(gt)
        pred_counts.append(pc)
        rows.append({"image": jpg.name, "gtCount": gt, "predCount": pc})
        if len(rows) % 25 == 0:
            print(f"  计数评估 {len(rows)}/{len(jpgs)}", flush=True)

    n = max(len(gt_counts), 1)
    mae = sum(abs(a - b) for a, b in zip(gt_counts, pred_counts)) / n
    exact = sum(1 for a, b in zip(gt_counts, pred_counts) if a == b) / n
    tot_gt, tot_pred = sum(gt_counts), sum(pred_counts)
    bias = (tot_pred - tot_gt) / max(tot_gt, 1)

    # ---- 生产工作点单独统计（conf = 服务/CLI 默认值，可能不同于 --conf）----
    work_point = None
    try:
        from count_coral_yolo import DEFAULT_CONF as WORK_CONF, DEFAULT_IOU as WORK_IOU
    except Exception:
        WORK_CONF, WORK_IOU = 0.20, 0.7
    if abs(WORK_CONF - args.conf) > 1e-9:
        print(f"  另计生产工作点 conf={WORK_CONF}（服务与 CLI 默认）…", flush=True)
        wp_pred, wp_gt = [], []
        for i, jpg in enumerate(jpgs):
            lab = val_lab / f"{jpg.stem}.txt"
            g = sum(1 for line in lab.read_text(encoding="utf-8").splitlines() if line.strip()) if lab.exists() else 0
            r2 = model.predict(source=str(jpg), imgsz=args.imgsz, conf=WORK_CONF, iou=WORK_IOU,
                               device=pick_device(), verbose=False, plots=False)[0]
            wp_gt.append(g)
            wp_pred.append(int(len(r2.boxes)) if r2.boxes is not None else 0)
            if (i + 1) % 50 == 0:
                print(f"    工作点计数 {i + 1}/{len(jpgs)}", flush=True)
        n2 = max(len(wp_gt), 1)
        wp_tot_gt, wp_tot_pred = sum(wp_gt), sum(wp_pred)
        work_point = {
            "conf": WORK_CONF, "iou": WORK_IOU, "imgsz": args.imgsz,
            "gtTotal": wp_tot_gt, "predTotal": wp_tot_pred,
            "countBias": round((wp_tot_pred - wp_tot_gt) / max(wp_tot_gt, 1), 4),
            "maePerImage": round(sum(abs(a - b) for a, b in zip(wp_gt, wp_pred)) / n2, 4),
            "exactMatchRate": round(sum(1 for a, b in zip(wp_gt, wp_pred) if a == b) / n2, 4),
            "note": "服务 /analyze 与 count_coral_yolo.py 的默认阈值（生产工作点）",
        }
        print(f"  工作点计数（conf={WORK_CONF}）: GT {wp_tot_gt} / 预测 {wp_tot_pred}"
              f"（偏差 {work_point['countBias']:+.1%}）", flush=True)
    else:
        work_point = dict(report_counting := {
            "conf": args.conf, "iou": args.iou, "imgsz": args.imgsz,
            "gtTotal": tot_gt, "predTotal": tot_pred,
            "countBias": round(bias, 4), "maePerImage": round(mae, 4),
            "exactMatchRate": round(exact, 4),
            "note": "与 --conf 相同，故即工作点",
        })

    passed = mAP50 >= ACCEPT_MAP50
    report = {
        "task": "YOLOv9 coral individual counting (P3)",
        "acceptance": {"criterion": "mAP@0.5 >= 0.35", "value": round(mAP50, 6), "passed": bool(passed)},
        "weights": rel(best_out),
        "runDir": rel(save_dir) if save_dir else None,
        "imgsz": args.imgsz, "epochs": args.epochs, "batch": args.batch,
        "trainMinutes": round(train_sec / 60, 2) if train_sec else None,
        "trainingArgs": {
            "initModel": resolve_model(args.model), "optimizer": args.optimizer,
            "lr0": args.lr0, "lrf": args.lrf, "mosaic": args.mosaic,
            "closeMosaic": args.close_mosaic, "patience": args.patience,
            "fineTuneFrom": rel(resolve_model(args.model)) if Path(resolve_model(args.model)).exists() else None,
        },
        "valImages": len(gt_counts),
        "detection": {
            "mAP50": round(mAP50, 6),
            "mAP50_95": round(mAP5095, 6),
            "precision": round(prec, 6),
            "recall": round(rec, 6),
            "confThreshold": args.conf, "iouThreshold": args.iou,
        },
        "counting": {
            "conf": args.conf, "iou": args.iou,
            "gtTotal": tot_gt, "predTotal": tot_pred,
            "countBias": round(bias, 4),
            "maePerImage": round(mae, 4),
            "exactMatchRate": round(exact, 4),
            "note": "计数在 conf/iou 阈值下统计；MAE 为逐图 |预测框数-真值框数| 的均值",
        },
        # ⚠️ 生产工作点（服务 /analyze 与 CLI 的默认 conf）单独记一遍：
        #    此前只记 --conf（默认 0.25），验收证据因此与服务实际工作点不一致（+2.3% vs −15.7%）
        "countingWorkPoint": work_point,
        "perImage": rows,
        "device": pick_device(),
        "note": ("val = Coralscapes 官方 validation split（与分割 mIoU 同源，无训练泄漏）；"
                 "1 类 coral；真值框 = 掩膜连通域外接矩形"),
    }
    out = metrics_out
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 70)
    print("YOLOv9 珊瑚个体计数 —— 验证集结果（Coralscapes 官方 validation split）")
    print("=" * 70)
    print(f"  mAP@0.5      : {mAP50:.4f}   （阈值 0.35 → {'✅ 达标' if passed else '❌ 未达标'}）")
    print(f"  mAP@0.5:0.95 : {mAP5095:.4f}")
    print(f"  precision    : {prec:.4f}    recall: {rec:.4f}")
    print(f"  计数（conf={args.conf}）: GT {tot_gt} / 预测 {tot_pred}（偏差 {bias:+.1%}）")
    print(f"  逐图计数 MAE : {mae:.2f} 个   完全命中率: {exact:.1%}")
    print(f"  结果 JSON    : {out}")
    return report


def main():
    global DATA
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="yolov9c.pt")
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--patience", type=int, default=15)
    ap.add_argument("--optimizer", default="auto", help="auto / AdamW / SGD …")
    ap.add_argument("--lr0", type=float, default=None, help="初始学习率（微调时建议调低）")
    ap.add_argument("--lrf", type=float, default=None, help="末端学习率比例")
    ap.add_argument("--mosaic", type=float, default=None, help="mosaic 概率（默认 1.0）")
    ap.add_argument("--close-mosaic", type=int, default=10, help="最后 N 个 epoch 关闭 mosaic")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--name", default="coral_yolov9c")
    ap.add_argument("--weights-dir", default=str(W_DIR), help="best.pt 落盘目录（烟雾测试改到别处）")
    ap.add_argument("--metrics-out", default=str(REPORTS / "yolo_coral_metrics.json"))
    ap.add_argument("--force", action="store_true", help="已有 best.pt 也重新训练")
    ap.add_argument("--resume", action="store_true", help="从上次中断处续训")
    ap.add_argument("--eval-only", action="store_true")
    args = ap.parse_args()

    DATA = Path(args.data)
    # 统一成绝对路径：否则 report 里的相对路径换算会失败（烟雾测试踩过）
    if not Path(args.weights_dir).is_absolute():
        args.weights_dir = str(ROOT / args.weights_dir)
    best_out = out_weights(args.weights_dir)

    if args.eval_only:
        evaluate(args)
        return
    if best_out.exists() and not args.force and not args.resume:
        print(f"[跳过] 已有权重 {best_out}（--force 可重训）")
        evaluate(args)
        return
    train_sec, save_dir = train(args)
    evaluate(args, train_sec, save_dir)


if __name__ == "__main__":
    main()
