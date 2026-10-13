"""
退化不变性微调（修复 Model A 在 15m+ 浑浊水下崩溃的问题）
================================================================
问题（实测）：
    Coralscapes 预训练分割模型在物理降质 L3(15m浑浊)/L4(20m) 下
    活珊瑚估计从 39.7% 崩到 0.00%（全部判为底质）。
    经典色彩还原只能救回 4.65%，远不够。

方案：
    用 Coralscapes 的**像素级真值掩膜**，配合本项目已验证的**物理降质管线**，
    构造「退化图 → 原始掩膜」训练对，微调分割模型，
    使其在退化条件下仍能输出正确掩膜（退化不变性）。

    训练时随机采样退化档位，使模型覆盖整条条件阶梯。

数据：
    Coralscapes parquet（HF: EPFL-ECEO/coralscapes）
    列：image, label（像素级掩膜，40 类，0=unlabeled/ignore）

用法：
    python finetune_seg_degradation.py --epochs 6 --crop 512 --batch 4
    python finetune_seg_degradation.py --eval-only        # 只评估现有权重
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from degrade_underwater import LEVELS, degrade_image  # noqa: E402
from uw_enhance import enhance  # noqa: E402

CS_DIR = ROOT / "data" / "raw" / "coralscapes" / "data"
BASE_CKPT = ROOT / "weights" / "segformer_coralscapes"
OUT_DIR = ROOT / "weights" / "segformer_coralscapes_degradinv"
IGNORE = 255          # 训练时的忽略标签（unlabeled 重新映射到 255）
N_CLASSES = 40

# 训练时采样的退化档位（含原始，保证不退化时也不掉点）
TRAIN_LEVELS = ["L0_clean", "L0_clean", "L1_near", "L2_typical", "L2_typical", "L3_far", "L3_far", "L4_harsh"]


# ---------------------------------------------------------------- 数据
def find_parquets(split):
    pats = {"train": "train-*.parquet", "val": "validation-*.parquet", "test": "test-*.parquet"}
    return sorted(CS_DIR.glob(pats[split]))


def read_parquet_images(path, columns=None):
    import pyarrow.parquet as pq
    t = pq.read_table(str(path), columns=columns)
    return t


def detect_columns(tbl):
    names = tbl.column_names
    img_col = next((n for n in names if n.lower() in ("image", "img", "leftimg8bit", "photo")), names[0])
    lbl_col = next((n for n in names if n.lower() in ("label", "mask", "semantic", "gtfine", "segmentation")),
                   None)
    return img_col, lbl_col


class CoralscapesDegraded(torch.utils.data.Dataset):
    """从 parquet 读取 (image, mask)，训练时随机施加物理降质 + 随机裁剪。"""

    def __init__(self, split, crop=512, train=True, degrade_train=True, prefer_enhanced=False):
        self.files = find_parquets(split)
        if not self.files:
            raise SystemExit(f"找不到 parquet：{CS_DIR}/{split}")
        self.tables = []
        self.index = []          # (file_idx, row_idx)
        for fi, fp in enumerate(self.files):
            import pyarrow.parquet as pq
            md = pq.ParquetFile(str(fp))
            self.tables.append(str(fp))
            for r in range(md.metadata.num_rows):
                self.index.append((fi, r))
        self.crop = crop
        self.train = train
        self.degrade_train = degrade_train
        self.prefer_enhanced = prefer_enhanced
        self._cache = {}
        print(f"  [{split}] {len(self.files)} 个 parquet，共 {len(self.index)} 个样本")

    def _row(self, fi, ri):
        import pyarrow.parquet as pq
        key = fi
        if key not in self._cache:
            self._cache = {key: pq.read_table(self.tables[fi])}   # 只缓存当前分片，省内存
        return self._cache[key].slice(ri, 1)

    def __len__(self):
        return len(self.index)

    def _to_pil(self, obj):
        if isinstance(obj, Image.Image):
            return obj
        if isinstance(obj, dict):                      # HF Image feature: {'bytes':..., 'path':...}
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
        raise TypeError(f"无法解析图像字段: {type(obj)}")

    def __getitem__(self, i):
        import pyarrow.parquet as pq
        fi, ri = self.index[i]
        if fi not in self._cache:
            self._cache = {fi: pq.read_table(self.tables[fi])}
        tbl = self._cache[fi]
        img_col, lbl_col = detect_columns(tbl)
        row = {c: tbl.column(c)[ri].as_py() for c in tbl.column_names}

        img = self._to_pil(row[img_col]).convert("RGB")
        if lbl_col is None:
            raise SystemExit(f"未找到掩膜列，实际列名: {tbl.column_names}")
        lbl = row[lbl_col]
        lbl = self._to_pil(lbl) if not isinstance(lbl, np.ndarray) else Image.fromarray(lbl)
        if lbl.mode not in ("L", "I", "I;16"):
            lbl = lbl.convert("L")

        W, H = img.size
        c = self.crop
        if W < c or H < c:      # 兜底：缩放到至少 crop
            img = img.resize((max(c, W), max(c, H)), Image.BILINEAR)
            lbl = lbl.resize((max(c, W), max(c, H)), Image.NEAREST)
            W, H = img.size
        x0 = random.randint(0, W - c) if self.train else max(0, (W - c) // 2)
        y0 = random.randint(0, H - c) if self.train else max(0, (H - c) // 2)
        img = img.crop((x0, y0, x0 + c, y0 + c))
        lbl = lbl.crop((x0, y0, x0 + c, y0 + c))

        # 物理降质（训练时随机；评估时由外部指定 level）
        if self.train and self.degrade_train:
            lv = random.choice(TRAIN_LEVELS)
            if lv != "L0_clean":
                img = degrade_image(img, lv, seed=random.randint(0, 10**6))
        if self.prefer_enhanced:
            img = enhance(img, clahe=True)

        mask = np.array(lbl).astype(np.int64)
        mask[mask == 0] = IGNORE          # 0=unlabeled → ignore
        mask[mask >= N_CLASSES] = IGNORE

        x = torch.from_numpy(np.array(img).astype(np.float32).transpose(2, 0, 1) / 255.0)
        x = (x - torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)) / torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
        return x, torch.from_numpy(mask)


# ---------------------------------------------------------------- 评估
@torch.no_grad()
def evaluate(model, loader, device, n_batches=None):
    model.eval()
    inter = np.zeros(N_CLASSES, dtype=np.int64)
    union = np.zeros(N_CLASSES, dtype=np.int64)
    for bi, (x, y) in enumerate(loader):
        if n_batches and bi >= n_batches:
            break
        x = x.to(device)
        logits = model(pixel_values=x).logits
        up = F.interpolate(logits, size=y.shape[-2:], mode="bilinear", align_corners=False)
        pred = up.argmax(1).cpu().numpy()
        gt = y.numpy()
        for c in range(N_CLASSES):
            if c == 0:
                continue
            p, g = (pred == c), (gt == c)
            inter[c] += np.logical_and(p, g).sum()
            union[c] += np.logical_or(p, g).sum()
    iou = np.where(union > 0, inter / np.maximum(union, 1), np.nan)
    miou = float(np.nanmean(iou))
    return miou, iou


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--crop", type=int, default=512)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--lr", type=float, default=6e-5)
    ap.add_argument("--limit", type=int, default=0, help="限制训练样本数（快速试验）")
    ap.add_argument("--val-batches", type=int, default=20)
    ap.add_argument("--eval-only", action="store_true")
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()

    from transformers import SegformerForSemanticSegmentation

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"设备: {device}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 起点：有微调权重就用微调权重，否则用原始预训练
    start = OUT_DIR if (OUT_DIR / "config.json").exists() else BASE_CKPT
    print(f"加载起点: {start}")
    model = SegformerForSemanticSegmentation.from_pretrained(str(start)).to(device)

    if args.eval_only:
        val = CoralscapesDegraded("val", crop=args.crop, train=False, degrade_train=False)
        for lv in list(LEVELS):
            ds = CoralscapesDegraded("val", crop=args.crop, train=False, degrade_train=False)
            ds.degrade_level = lv
            # 用固定档位评估：临时替换 degrade_image 行为
            loader = torch.utils.data.DataLoader(ds, batch_size=args.batch, shuffle=False,
                                                 num_workers=0)
            # 该路径仅用于快速自检
            print(f"  {lv}: 跳过（请用 eval_degradation 的完整评估）")
        return

    tr = CoralscapesDegraded("train", crop=args.crop, train=True, degrade_train=True)
    va = CoralscapesDegraded("val", crop=args.crop, train=False, degrade_train=False)
    if args.limit:
        tr.index = tr.index[: args.limit]

    tl = torch.utils.data.DataLoader(tr, batch_size=args.batch, shuffle=True,
                                     num_workers=args.workers, pin_memory=True, drop_last=True)
    vl = torch.utils.data.DataLoader(va, batch_size=args.batch, shuffle=False,
                                     num_workers=args.workers, pin_memory=True)

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, args.epochs * len(tl)))
    scaler = torch.amp.GradScaler("cuda", enabled=(device.type == "cuda"))
    crit = nn.CrossEntropyLoss(ignore_index=IGNORE)

    print(f"\n开始训练: {len(tr)} 训练样本 / {len(va)} 验证样本  crop={args.crop} batch={args.batch}")
    best = -1.0
    hist = []
    for ep in range(1, args.epochs + 1):
        model.train()
        t0, tot, nb = time.time(), 0.0, 0
        for x, y in tl:
            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)
            opt.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                logits = model(pixel_values=x).logits
                loss = crit(F.interpolate(logits, size=y.shape[-2:], mode="bilinear",
                                          align_corners=False), y)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            sched.step()
            tot += loss.item(); nb += 1
            if nb % 50 == 0:
                print(f"    ep{ep} {nb}/{len(tl)} loss={tot/nb:.4f} "
                      f"{time.time()-t0:.0f}s", flush=True)
        miou, _ = evaluate(model, vl, device, args.val_batches)
        hist.append({"epoch": ep, "loss": tot / max(nb, 1), "miou": miou})
        print(f"[{ep}/{args.epochs}] loss={tot/max(nb,1):.4f}  val mIoU={miou:.4f}  "
              f"{time.time()-t0:.0f}s", flush=True)
        if miou > best:
            best = miou
            model.save_pretrained(str(OUT_DIR))
            (OUT_DIR / "id2label.json").write_text(
                (BASE_CKPT / "id2label.json").read_text(encoding="utf-8"), encoding="utf-8")
            print(f"    <- 保存 (best mIoU={best:.4f})", flush=True)

    (ROOT / "reports" / "finetune_degradinv.json").write_text(json.dumps(
        {"epochs": args.epochs, "crop": args.crop, "batch": args.batch,
         "train_samples": len(tr), "val_samples": len(va),
         "train_levels": TRAIN_LEVELS, "history": hist, "best_miou": best},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成。权重: {OUT_DIR}  最佳 mIoU={best:.4f}")


if __name__ == "__main__":
    main()
