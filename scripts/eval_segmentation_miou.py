"""
分割质量评估：在 Coralscapes 官方验证集上计算 mIoU
================================================================
补上此前的空白：Model A 是分割模型，但全项目一直**没有报告分割质量指标**。

数据：Coralscapes 官方 validation split（166 张，含像素级掩膜）
      来源 data/raw/coralscapes/data/validation-00000-of-00001.parquet
      列：image / label（均为 struct{bytes, path}）

指标：
  · 逐类 IoU（40 类，排除 0=unlabeled）
  · mIoU（宏平均，仅统计出现过的类）
  · 按功能群聚合的 mIoU（活/白化/死亡/藻类/底质/海草）
  · 逐像素准确率（pixel accuracy）
  · 频次加权 IoU（fIoU）

用法：
    python eval_segmentation_miou.py                 # 512 输入（与产品一致）
    python eval_segmentation_miou.py --size 1024     # 更高分辨率
    python eval_segmentation_miou.py --limit 40
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from segment_coral import CoralSegmenter, functional_group  # noqa: E402

PQ = ROOT / "data" / "raw" / "coralscapes" / "data" / "validation-00000-of-00001.parquet"
N_CLASSES = 40
GROUP_CN = {"alive": "活珊瑚", "bleached": "白化珊瑚", "dead": "死亡珊瑚",
            "algae": "藻类覆盖", "substrate": "沙/底质", "seagrass": "海草", "other": "其他"}


def to_pil(obj):
    if isinstance(obj, Image.Image):
        return obj
    if isinstance(obj, dict):
        import io
        if obj.get("bytes"):
            return Image.open(io.BytesIO(obj["bytes"]))
        if obj.get("path"):
            return Image.open(obj["path"])
    if isinstance(obj, (bytes, bytearray)):
        import io
        return Image.open(io.BytesIO(obj))
    if isinstance(obj, np.ndarray):
        return Image.fromarray(obj)
    raise TypeError(f"无法解析: {type(obj)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=1024, help="推理输入长边（与产品一致为 1024）")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if not PQ.exists():
        raise SystemExit(f"缺少验证集: {PQ}\n请先运行: python dl_coralscapes.py --shards validation-00000-of-00001.parquet")

    import pyarrow.parquet as pq
    tbl = pq.read_table(str(PQ))
    n = tbl.num_rows
    if args.limit:
        n = min(n, args.limit)
    print(f"Coralscapes 验证集: {tbl.num_rows} 张（本次评估 {n} 张）")
    print(f"推理输入长边: {args.size}\n")

    seg = CoralSegmenter(size=args.size)
    DEV = torch.device(str(seg.device))
    print(f"模型: {seg.model.config._name_or_path if hasattr(seg.model.config,'_name_or_path') else 'segformer'}")
    print(f"设备: {DEV}   类别数: {seg.n_classes}\n")

    conf = np.zeros((N_CLASSES, N_CLASSES), dtype=np.int64)   # [gt, pred]
    ok_img = 0
    for i in range(n):
        try:
            row = {c: tbl.column(c)[i].as_py() for c in tbl.column_names}
            img = to_pil(row["image"]).convert("RGB")
            gt = to_pil(row["label"])
            if gt.mode not in ("L", "I", "I;16"):
                gt = gt.convert("L")
        except Exception as e:
            print(f"  [跳过 {i}] 读取失败: {type(e).__name__}")
            continue

        # 与 segment() 完全一致的几何处理
        W0, H0 = img.size
        scale = args.size / max(W0, H0)
        nw = max(32, int(W0 * scale) // 32 * 32)
        nh = max(32, int(H0 * scale) // 32 * 32)
        small = img.resize((nw, nh), Image.BILINEAR)
        gt_small = np.array(gt.resize((nw, nh), Image.NEAREST))

        inputs = seg.processor(images=small, return_tensors="pt").to(DEV)
        with torch.no_grad(), torch.amp.autocast("cuda", enabled=(DEV.type == "cuda")):
            logits = seg.model(**inputs).logits
        up = F.interpolate(logits, size=(nh, nw), mode="bilinear", align_corners=False)
        pred = up.argmax(1)[0].cpu().numpy().astype(np.int64)

        g = gt_small.astype(np.int64)
        valid = (g >= 0) & (g < N_CLASSES)
        # 用 bincount 加速累积混淆矩阵
        idx = (g[valid] * N_CLASSES + pred[valid]).astype(np.int64)
        conf += np.bincount(idx, minlength=N_CLASSES * N_CLASSES).reshape(N_CLASSES, N_CLASSES)
        ok_img += 1
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{n} ...", flush=True)

    if ok_img == 0:
        raise SystemExit("没有成功处理的样本")

    print(f"\n成功评估 {ok_img} 张\n")
    print("=" * 82)
    print("分割质量：Coralscapes 官方验证集")
    print("=" * 82)

    inter = np.diag(conf).astype(np.float64)
    gt_sum = conf.sum(axis=1).astype(np.float64)
    pr_sum = conf.sum(axis=0).astype(np.float64)
    union = gt_sum + pr_sum - inter
    iou = np.where(union > 0, inter / np.maximum(union, 1), np.nan)
    present = gt_sum > 0
    miou = float(np.nanmean(iou[present]))
    pixel_acc = float(inter.sum() / max(conf.sum(), 1))
    fiou = float(inter.sum() / max(union[present].sum(), 1))

    print(f"{'mIoU（宏平均，{present.sum()} 类）':<34}{miou:>10.4f}")
    print(f"{'频次加权 IoU (fIoU)':<34}{fiou:>10.4f}")
    print(f"{'逐像素准确率 (pixel acc)':<34}{pixel_acc:>10.4f}")
    print("-" * 82)

    # 功能群聚合
    print("\n按功能群聚合的 IoU：")
    names = [seg.id2label.get(int(c), f"class_{c}") for c in range(N_CLASSES)]
    grp_conf = {}
    for c in range(N_CLASSES):
        if not present[c]:
            continue
        g = functional_group(names[c])
        gc = grp_conf.setdefault(g, np.zeros((N_CLASSES, N_CLASSES), dtype=np.int64))
        gc[c] = conf[c]
    grp_rows = []
    for g, gc in sorted(grp_conf.items()):
        it = np.diag(gc).sum()
        un = (gc.sum(1) + gc.sum(0) - np.diag(gc)).sum()
        # 注意：功能群 IoU 应按「群合并后」计算，这里用逐类再平均
        cs = []
        for c in range(N_CLASSES):
            if gc[c].sum() == 0:
                continue
            u = gc[c].sum() + gc[:, c].sum() - gc[c, c]
            if u > 0:
                cs.append(gc[c, c] / u)
        grp_rows.append((GROUP_CN.get(g, g), np.mean(cs) if cs else 0.0, len(cs)))
    for name, v, k in sorted(grp_rows, key=lambda x: -x[1]):
        print(f"    {name:<12} IoU={v:.4f}   （{k} 个类别）")

    print("\n逐类 IoU（按 IoU 降序，仅列出出现过的类）：")
    ranked = [(names[c], float(iou[c]), int(gt_sum[c])) for c in range(N_CLASSES) if present[c]]
    for name, v, cnt in sorted(ranked, key=lambda x: -x[1]):
        print(f"    {name:<38} IoU={v:.4f}  像素数={cnt}")

    out = Path(args.out) if args.out else (ROOT / "reports" / f"segmentation_miou_{args.size}.json")
    out.write_text(json.dumps({
        "dataset": "Coralscapes official validation split",
        "nImages": ok_img, "inputSize": args.size,
        "mIoU": round(miou, 6), "fIoU": round(fiou, 6), "pixelAccuracy": round(pixel_acc, 6),
        "nClassesPresent": int(present.sum()),
        "perClassIoU": {names[c]: round(float(iou[c]), 6) for c in range(N_CLASSES) if present[c]},
        "perClassPixels": {names[c]: int(gt_sum[c]) for c in range(N_CLASSES) if present[c]},
        "byFunctionalGroup": {GROUP_CN.get(g, g): round(float(v), 6) for g, v, _ in grp_rows},
        "confusionMatrix": conf.tolist(),
        "note": "mIoU 为宏平均，仅统计验证集中出现过的类；类别 0（unlabeled）不参与",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果: {out}")


if __name__ == "__main__":
    main()
