"""
CNN 水下图像增强（原方案点名的 "CNN 增强"）
================================================================
原方案技术栈为「CNN 增强 → 目标检测/分割」。本项目此前用的是**传统 CV 增强**
（红通道补偿 + 灰度世界 + CLAHE），本脚本补上**学习式增强**并做**可量化对比**。

任务：degraded → clean 的图像到图像翻译（轻量 U-Net）
数据：用 degrade_underwater.py 的物理模型，从 clean 图合成 degraded 图（自监督配对）

评估：
    在**降质图**上比较三种前置处理对下游分割覆盖率的影响
      ① none（不做增强）
      ② 传统 CV 增强（uw_enhance.py）
      ③ CNN 增强（本脚本训练）
    指标：活珊瑚覆盖率相对 clean 基准的偏差

用法：
    python train_enhance.py --train                 # 训练
    python train_enhance.py --compare               # 三方对比评估
"""
import argparse
import json
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

W_DIR = ROOT / "weights" / "enhance_unet"
R_DIR = ROOT / "reports"
SIZE = 256


# ---------------------------------------------------------------- 轻量 U-Net
class ConvBlock(nn.Module):
    def __init__(self, i, o):
        super().__init__()
        self.b = nn.Sequential(
            nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True),
            nn.Conv2d(o, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True))

    def forward(self, x):
        return self.b(x)


class EnhanceUNet(nn.Module):
    """degraded → clean。残差学习：输出 = 输入 + 网络预测的残差。"""

    def __init__(self, base=24):
        super().__init__()
        self.e1 = ConvBlock(3, base)
        self.e2 = ConvBlock(base, base * 2)
        self.e3 = ConvBlock(base * 2, base * 4)
        self.pool = nn.MaxPool2d(2)
        self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
        self.d2 = ConvBlock(base * 4, base * 2)
        self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.d1 = ConvBlock(base * 2, base)
        self.out = nn.Conv2d(base, 3, 1)

    def forward(self, x):
        s1 = self.e1(x)
        s2 = self.e2(self.pool(s1))
        s3 = self.e3(self.pool(s2))
        u2 = self.d2(torch.cat([self.up2(s3), s2], 1))
        u1 = self.d1(torch.cat([self.up1(u2), s1], 1))
        return torch.clamp(x + self.out(u1), 0, 1)   # 残差 + 截断到 [0,1]


# ---------------------------------------------------------------- 数据
def _clean_files(limit=None):
    """用仙本那照片作为 clean 域（真实水下但未合成降质）。"""
    fs = sorted((ROOT / "data" / "semporna_photos").glob("*.jpg"))
    return fs[:limit] if limit else fs


def _to_tensor(img):
    a = np.asarray(img.convert("RGB").resize((SIZE, SIZE), Image.BILINEAR),
                   dtype=np.float32) / 255.0
    return torch.from_numpy(a).permute(2, 0, 1)


def _degrade_batch(imgs, levels=("L1_near", "L2_typical")):
    """随机挑一个降质档位合成 degraded 图（自监督配对）。"""
    import random
    from degrade_underwater import LEVELS, degrade_image
    out = []
    for im in imgs:
        lv = random.choice(levels)
        out.append(_to_tensor(degrade_image(im, lv)))
    return torch.stack(out)


def train(epochs=12, limit=180, bs=8, lr=2e-4):
    torch.manual_seed(0)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    files = _clean_files(limit)
    if not files:
        raise SystemExit("没有 clean 图（data/semporna_photos）")
    print(f"  训练样本 {len(files)} 张  设备 {dev}  分辨率 {SIZE}")

    net = EnhanceUNet().to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
    n_par = sum(p.numel() for p in net.parameters())
    print(f"  参数量 {n_par/1e6:.2f} M")

    W_DIR.mkdir(parents=True, exist_ok=True)
    best = 1e9
    for ep in range(1, epochs + 1):
        net.train()
        rng = np.random.default_rng(ep)
        order = rng.permutation(len(files))
        tot, nb = 0.0, 0
        t0 = time.time()
        for i in range(0, len(order), bs):
            idx = order[i:i + bs]
            imgs = [Image.open(files[j]) for j in idx]
            clean = torch.stack([_to_tensor(im) for im in imgs]).to(dev)
            deg = _degrade_batch(imgs).to(dev)
            pred = net(deg)
            # 像素 L1 + 结构项（梯度差）
            l1 = F.l1_loss(pred, clean)
            gx = F.l1_loss(pred[..., 1:, :] - pred[..., :-1, :],
                           clean[..., 1:, :] - clean[..., :-1, :])
            gy = F.l1_loss(pred[..., :, 1:] - pred[..., :, :-1],
                           clean[..., :, 1:] - clean[..., :, :-1])
            loss = l1 + 0.5 * (gx + gy)
            opt.zero_grad(); loss.backward(); opt.step()
            tot += float(loss); nb += 1
        sched.step()
        avg = tot / max(nb, 1)
        print(f"  [{ep:>2}/{epochs}] loss={avg:.4f}  {time.time()-t0:.0f}s")
        if avg < best:
            best = avg
            torch.save({"model": net.state_dict(), "size": SIZE, "base": 24},
                       W_DIR / "best.pt")
    print(f"  最优 loss {best:.4f}  权重: {W_DIR/'best.pt'}")
    return net


def load_enhancer():
    p = W_DIR / "best.pt"
    if not p.exists():
        return None
    ck = torch.load(p, map_location="cpu", weights_only=False)
    net = EnhanceUNet(base=ck.get("base", 24))
    net.load_state_dict(ck["model"])
    net.eval()
    return net


@torch.no_grad()
def cnn_enhance(img, net, dev):
    x = _to_tensor(img).unsqueeze(0).to(dev)
    y = net(x)[0].clamp(0, 1).permute(1, 2, 0).cpu().numpy()
    # 恢复到原分辨率
    out = Image.fromarray((y * 255).astype(np.uint8))
    return out.resize(img.size, Image.BILINEAR)


# ---------------------------------------------------------------- 三方对比
def compare(limit=60):
    from segment_coral import CoralSegmenter
    from uw_enhance import enhance as cv_enhance
    from degrade_underwater import LEVELS, degrade_image

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net = load_enhancer()
    if net is None:
        raise SystemExit("未找到 CNN 增强权重，请先 --train")
    net = net.to(dev)

    files = _clean_files(limit)
    seg = CoralSegmenter(size=1024)
    rows = []
    for lv in ("L1_near", "L2_typical", "L3_far"):
        acc = {"none": [], "cv": [], "cnn": [], "clean": []}
        for f in files:
            im = Image.open(f)
            clean_im = im
            deg = degrade_image(im, lv)
            for tag, src in (("clean", clean_im), ("none", deg),
                             ("cv", cv_enhance(deg, clahe=True)),
                             ("cnn", cnn_enhance(deg, net, dev))):
                try:
                    _, _, g = seg.segment(src)
                    acc[tag].append(g.get("alive", 0.0))
                except Exception:
                    pass
        base = float(np.mean(acc["clean"])) if acc["clean"] else 0.0
        row = {"level": lv, "n": len(acc["clean"]), "cleanBase": round(base, 4)}
        for tag in ("none", "cv", "cnn"):
            m = float(np.mean(acc[tag])) if acc[tag] else 0.0
            row[tag] = round(m, 4)
            row[tag + "Err"] = round(m - base, 4)
        rows.append(row)
        print(f"  {lv:<12} clean={base:.2%}  none={row['none']:.2%}({row['noneErr']:+.2%})  "
              f"cv={row['cv']:.2%}({row['cvErr']:+.2%})  cnn={row['cnn']:.2%}({row['cnnErr']:+.2%})")

    out = {"task": "CNN 增强 vs 传统 CV 增强 vs 不增强（下游分割覆盖率偏差）",
           "nPerLevel": len(files), "rows": rows,
           "note": "误差 = 该处理下的活珊瑚覆盖率 − clean 基准；越接近 0 越好"}
    (R_DIR / "enhance_compare.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  结果: {R_DIR/'enhance_compare.json'}")
    return out


def main():
    ap = argparse.ArgumentParser(description="CNN 水下图像增强")
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--limit", type=int, default=180)
    args = ap.parse_args()
    if args.train:
        train(epochs=args.epochs, limit=args.limit)
    if args.compare:
        compare()
    if not (args.train or args.compare):
        ap.print_help()


if __name__ == "__main__":
    main()
