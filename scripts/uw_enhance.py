"""
水下图像色彩还原前端（对应项目简介里的「CNN 增强修正色偏」）
================================================================
动机：降质鲁棒性实验发现，Coralscapes 分割模型在 15m 浑浊水下
      活珊瑚估计从 39.7% 崩到 0%（全部判为底质）。
      原因是红光/绿光被海水强烈吸收，图像退化为近单色蓝，模型失效。

本模块提供一个**零训练、可解释**的色彩还原前端，用经典水下图像复原方法：

  1. 红通道补偿 (Galdran et al. 2015)
        R' = R + (mean(G) - mean(R)) · (1 - R) · G
  2. 灰度世界白平衡（去除蓝绿偏）
  3. 逐通道百分位拉伸（恢复对比度）
  4. 可选 CLAHE 局部对比度增强

用法（作为模块）：
    from uw_enhance import enhance
    img2 = enhance(img)

用法（命令行对比）：
    python uw_enhance.py --src data/degraded/L3_far --dst data/enhanced/L3_far
    python uw_enhance.py --image a.jpg --out b.jpg
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def _red_compensate(arr: np.ndarray) -> np.ndarray:
    """Galdran 红通道补偿：用 G 的均值补回 R 的缺失。"""
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    delta = max(0.0, float(g.mean() - r.mean()))
    r2 = r + delta * (1.0 - r) * g
    return np.clip(np.stack([r2, g, b], axis=-1), 0, 1)


def _gray_world(arr: np.ndarray) -> np.ndarray:
    means = arr.reshape(-1, 3).mean(axis=0)
    target = float(means.mean())
    gain = target / np.maximum(means, 1e-6)
    # 限制增益幅度，避免过度校正
    gain = np.clip(gain, 0.6, 2.2)
    return np.clip(arr * gain[None, None, :], 0, 1)


def _stretch(arr: np.ndarray, lo=1.0, hi=99.0) -> np.ndarray:
    out = np.empty_like(arr)
    for c in range(3):
        ch = arr[..., c]
        a, b = np.percentile(ch, lo), np.percentile(ch, hi)
        if b - a < 1e-6:
            out[..., c] = ch
        else:
            out[..., c] = np.clip((ch - a) / (b - a), 0, 1)
    return out


def _clahe_like(arr: np.ndarray, grid=8, clip=2.0) -> np.ndarray:
    """简化的分块直方图均衡（近似 CLAHE，无需 cv2）。"""
    h, w, _ = arr.shape
    gh, gw = max(1, h // grid), max(1, w // grid)
    out = arr.copy()
    for c in range(3):
        ch = out[..., c]
        for y in range(0, h, gh):
            for x in range(0, w, gw):
                blk = ch[y:y + gh, x:x + gw]
                if blk.size < 16:
                    continue
                hist, _ = np.histogram(blk, bins=64, range=(0, 1))
                # 直方图裁剪
                excess = np.maximum(hist - clip * blk.size / 64, 0).sum()
                hist = np.minimum(hist, clip * blk.size / 64) + excess / 64
                cdf = np.cumsum(hist) / hist.sum()
                out[y:y + gh, x:x + gw, c] = np.interp(blk, np.linspace(0, 1, 64), cdf)
    return np.clip(out, 0, 1)


def enhance(img: Image.Image, clahe=True, verbose=False) -> Image.Image:
    """完整色彩还原流程。输入/输出均为 PIL Image。"""
    arr = np.asarray(img.convert("RGB")).astype(np.float32) / 255.0
    before = arr.reshape(-1, 3).mean(axis=0)
    arr = _red_compensate(arr)
    arr = _gray_world(arr)
    arr = _stretch(arr)
    if clahe:
        arr = _clahe_like(arr)
    if verbose:
        after = arr.reshape(-1, 3).mean(axis=0)
        print(f"    通道均值 R/G/B: {before[0]:.3f}/{before[1]:.3f}/{before[2]:.3f}"
              f"  →  {after[0]:.3f}/{after[1]:.3f}/{after[2]:.3f}")
    return Image.fromarray((arr * 255).astype(np.uint8))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    ap.add_argument("--dst")
    ap.add_argument("--image")
    ap.add_argument("--out")
    ap.add_argument("--no-clahe", action="store_true")
    args = ap.parse_args()

    if args.image:
        img = Image.open(args.image)
        out = enhance(img, clahe=not args.no_clahe, verbose=True)
        p = Path(args.out) if args.out else (ROOT / "reports" / "enhanced_demo.jpg")
        out.save(p, quality=95)
        print(f"  → {p}")
        return

    src = Path(args.src)
    if not src.is_absolute():
        src = ROOT / src
    dst = Path(args.dst)
    if not dst.is_absolute():
        dst = ROOT / dst
    dst.mkdir(parents=True, exist_ok=True)
    IMG = {".jpg", ".jpeg", ".png"}
    files = sorted(f for f in src.rglob("*") if f.suffix.lower() in IMG)
    for i, f in enumerate(files):
        try:
            enhance(Image.open(f), clahe=not args.no_clahe).save(dst / f"{f.stem}.jpg", quality=95)
        except Exception as e:
            print(f"  [跳过] {f.name}: {type(e).__name__}")
    print(f"增强完成: {src} → {dst}  ({len(list(dst.glob('*.jpg')))} 张)")


if __name__ == "__main__":
    main()
