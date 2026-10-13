"""
退化不变性自蒸馏（无需任何新数据即可修复 Model A 的降质崩溃）
================================================================
背景（实测）：
    Coralscapes 预训练分割模型在物理降质 L3(15m)/L4(20m) 下
    活珊瑚估计从 39.7% 崩到 0.00%。而 Coralscapes 原始数据集
    因为镜像重定向被墙、速度仅 41KB/s，实际下不下来。

思路（自蒸馏 / 一致性训练，无需真值掩膜）：
    对同一张**真实礁区照片**：
        教师分支 = 模型在【原图】上的输出（argmax 掩膜）
        学生分支 = 模型在【物理降质图】上的输出
        损失     = CE(学生, 教师) + KL(学生‖教师)
    → 强迫模型在退化条件下仍复现清晰条件下的判断，即"退化不变性"

    这正是项目简介里「CNN 增强 + 色偏修正」要做的事，
    但用**模型级一致性**实现，比图像级滤波更端到端。

数据（全部已有，无需下载）：
    · CORAL_INDO 印尼珊瑚礁 patch（4256 张，印太域）
    · 仙本那 iNaturalist 照片（180 张，目标域）

用法：
    python finetune_degradinv_distill.py --epochs 4 --crop 384 --batch 6
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

from degrade_underwater import degrade_image  # noqa: E402
from uw_enhance import enhance  # noqa: E402

BASE_CKPT = ROOT / "weights" / "segformer_coralscapes"
OUT_DIR = ROOT / "weights" / "segformer_coralscapes_degradinv"

# 训练时采样的退化档位（含 L0，保证清晰条件下不掉点）
TRAIN_LEVELS = ["L0_clean", "L1_near", "L2_typical", "L2_typical", "L3_far", "L3_far", "L4_harsh"]

TRAIN_SOURCES = [
    ROOT / "data" / "raw" / "coral_indo" / "dataset_preparation_output",
    ROOT / "data" / "semporna_photos",
]
IMG_EXT = {".jpg", ".jpeg", ".png"}


def collect_images(limit_per_site=900):
    files = []
    for src in TRAIN_SOURCES:
        if not src.exists():
            continue
        if src.name == "dataset_preparation_output":
            for site in sorted(src.iterdir()):
                if not site.is_dir():
                    continue
                d = site / "1_original_patches"
                if not d.exists():
                    d = site / "2_yolo_filtered"
                if d.exists():
                    fs = sorted(f for f in d.rglob("*") if f.suffix.lower() in IMG_EXT)
                    files += fs[:limit_per_site]
        else:
            files += sorted(f for f in src.rglob("*") if f.suffix.lower() in IMG_EXT)
    return files


class DistillDataset(torch.utils.data.Dataset):
    """返回 (clean_tensor, degraded_tensor)：同一图的两个视图。

    ⚠️ 关于「裁剪 vs 缩放」——这是第一次实验失败的关键：
       前次用**随机裁剪 384×384**，对 1024×684 的整景照片只是一个小局部，
       若该局部恰好珊瑚密集，教师（清晰分支）就给出很高的珊瑚占比，
       学生因此学到「珊瑚偏多」的先验 → L0 基准从 39.66% 漂到 53.07%。
       改为 **整图缩放**后，训练视图与推理时的整景输入分布一致，
       教师输出自然回到 ~40%，先验偏差随之消失。
    """

    def __init__(self, files, crop=384, train=True, use_enhance=False, resize_mode=False):
        self.files = files
        self.crop = crop
        self.train = train
        self.use_enhance = use_enhance
        self.resize_mode = resize_mode
        self.mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
        self.std = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)

    def __len__(self):
        return len(self.files)

    def _norm(self, img):
        x = torch.from_numpy(np.array(img).astype(np.float32).transpose(2, 0, 1) / 255.0)
        return (x - self.mean) / self.std

    def __getitem__(self, i):
        img = Image.open(self.files[i]).convert("RGB")
        c = self.crop
        W, H = img.size
        if self.resize_mode:
            # 整图缩放：保留整景构图与珊瑚/底质比例
            # ⚠️ 不同照片宽高比不同，若只缩放到长边=crop 会得到**变尺寸张量**，
            #    DataLoader 无法拼批（RuntimeError: resize storage that is not resizable）。
            #    故缩放后**居中填充到固定 c×c**，填充色取该图自身均值色以减小边界影响。
            if W >= H:
                nw, nh = c, max(32, int(round(c * H / W)))
            else:
                nh, nw = c, max(32, int(round(c * W / H)))
            small = img.resize((nw, nh), Image.BILINEAR)
            arr = np.asarray(small).astype(np.float32)
            fill = tuple(int(v) for v in arr.reshape(-1, 3).mean(axis=0))
            canvas = Image.new("RGB", (c, c), fill)
            canvas.paste(small, ((c - nw) // 2, (c - nh) // 2))
            clean = canvas
        else:
            # 随机裁剪（旧行为：已证明会引入珊瑚中心偏差）
            if W < c or H < c:
                s = max(c / W, c / H)
                img = img.resize((max(c, int(W * s)), max(c, int(H * s))), Image.BILINEAR)
                W, H = img.size
            if self.train:
                x0, y0 = random.randint(0, W - c), random.randint(0, H - c)
            else:
                x0, y0 = max(0, (W - c) // 2), max(0, (H - c) // 2)
            clean = img.crop((x0, y0, x0 + c, y0 + c))

        lv = random.choice(TRAIN_LEVELS) if self.train else "L2_typical"
        deg = clean if lv == "L0_clean" else degrade_image(clean, lv, seed=random.randint(0, 10**6))
        if self.use_enhance:
            deg = enhance(deg, clahe=True)
        return self._norm(clean), self._norm(deg), lv


@torch.no_grad()
def teacher_mask(model, x, size):
    logits = model(pixel_values=x).logits
    up = F.interpolate(logits, size=size, mode="bilinear", align_corners=False)
    return up.argmax(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--crop", type=int, default=384)
    ap.add_argument("--batch", type=int, default=6)
    ap.add_argument("--lr", type=float, default=4e-5)
    ap.add_argument("--limit", type=int, default=1500, help="训练图片上限（控制时长）")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--use-enhance", action="store_true", help="降质分支先过色彩还原前端")
    ap.add_argument("--init", default=None, help="起点权重目录（默认原始预训练）")
    ap.add_argument("--anchor-w", type=float, default=1.0,
                    help="锚定损失权重：约束清晰分支不漂移（0=关闭，实测会退化）")
    ap.add_argument("--resize-mode", action="store_true",
                    help="整图缩放而非随机裁剪（修复珊瑚中心偏差导致的基准漂移）")
    ap.add_argument("--out-suffix", default="", help="输出目录后缀，便于保留多组实验")
    args = ap.parse_args()

    from transformers import SegformerForSemanticSegmentation

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"设备: {device}")

    files = collect_images()
    random.seed(42)
    random.shuffle(files)
    if args.limit:
        files = files[: args.limit]
    print(f"训练图片: {len(files)} 张（印尼 CORAL_INDO + 仙本那）")

    out_dir = OUT_DIR if not args.out_suffix else OUT_DIR.parent / (OUT_DIR.name + args.out_suffix)
    print(f"输出目录: {out_dir.name}   视图模式: "
          f"{'整图缩放(修复中心偏差)' if args.resize_mode else '随机裁剪'}")

    init = Path(args.init) if args.init else (
        out_dir if (out_dir / "config.json").exists() else BASE_CKPT)
    print(f"起点权重: {init}")
    model = SegformerForSemanticSegmentation.from_pretrained(str(init)).to(device)

    ds = DistillDataset(files, crop=args.crop, train=True, use_enhance=args.use_enhance,
                        resize_mode=args.resize_mode)
    dl = torch.utils.data.DataLoader(ds, batch_size=args.batch, shuffle=True,
                                     num_workers=args.workers, pin_memory=True, drop_last=True)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, args.epochs * len(dl)))
    scaler = torch.amp.GradScaler("cuda", enabled=(device.type == "cuda"))

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n开始自蒸馏：{len(dl)} 步/轮 × {args.epochs} 轮")
    hist = []
    t_all = time.time()
    for ep in range(1, args.epochs + 1):
        model.train()
        t0, tot_ce, tot_kl, nb = time.time(), 0.0, 0.0, 0
        for clean, deg, lv in dl:
            clean = clean.to(device, non_blocking=True)
            deg = deg.to(device, non_blocking=True)
            with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                with torch.no_grad():
                    tlogits = model(pixel_values=clean).logits
                    tlogits = F.interpolate(tlogits, size=deg.shape[-2:], mode="bilinear",
                                            align_corners=False)
                    tmask = tlogits.argmax(1)
                    tprob = F.softmax(tlogits, dim=1)
                slogits = model(pixel_values=deg).logits
                slogits = F.interpolate(slogits, size=deg.shape[-2:], mode="bilinear",
                                        align_corners=False)
                # ✅ 锚定损失：约束【学生(清晰图)】仍贴近教师(清晰图)，
                #    否则清晰分支会自由漂移 —— 实测不加锚定时 L0 基准从
                #    39.66% 漂到 75.73%（退化解：到处判成珊瑚）。
                clogits = model(pixel_values=clean).logits
                clogits = F.interpolate(clogits, size=deg.shape[-2:], mode="bilinear",
                                        align_corners=False)
                anchor = F.cross_entropy(clogits, tmask)

                # CE（硬标签）+ KL（软标签）：保留教师的不确定性信息
                ce = F.cross_entropy(slogits, tmask)
                npix = deg.shape[-2] * deg.shape[-1]
                kl = F.kl_div(F.log_softmax(slogits, 1), tprob,
                              reduction="batchmean") / npix
                loss = ce + 0.5 * kl + args.anchor_w * anchor
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            sched.step()
            tot_ce += ce.item(); tot_kl += kl.item(); nb += 1
            if nb % 40 == 0:
                print(f"    ep{ep} {nb}/{len(dl)} ce={tot_ce/nb:.4f} kl={tot_kl/nb:.4f} "
                      f"{time.time()-t0:.0f}s", flush=True)
        hist.append({"epoch": ep, "ce": tot_ce / max(nb, 1), "kl": tot_kl / max(nb, 1)})
        print(f"[{ep}/{args.epochs}] ce={tot_ce/max(nb,1):.4f} kl={tot_kl/max(nb,1):.4f} "
              f"{time.time()-t0:.0f}s", flush=True)
        # 每轮都存，便于中断续训
        model.save_pretrained(str(out_dir))
        for extra in ("id2label.json", "preprocessor_config.json"):
            src = BASE_CKPT / extra
            if src.exists():
                (out_dir / extra).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"    <- 已保存（含 preprocessor_config.json）", flush=True)

    (ROOT / "reports" / "finetune_distill.json").write_text(json.dumps({
        "method": "degradation-invariant self-distillation",
        "n_images": len(files), "crop": args.crop, "batch": args.batch,
        "train_levels": TRAIN_LEVELS, "use_enhance": args.use_enhance,
        "history": hist, "total_seconds": round(time.time() - t_all, 1),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成。权重: {out_dir}  用时 {time.time()-t_all:.0f}s")


if __name__ == "__main__":
    main()
