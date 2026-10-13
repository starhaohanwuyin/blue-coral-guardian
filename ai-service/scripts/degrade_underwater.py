"""
水下图像物理降质（构造「真实拍摄条件」测试集）
================================================================
公开数据里的珊瑚照片多是潜水员**近距离、打灯、构图好**拍的，
与真实使用场景（志愿者**远距离、自然光、浑浊、低对比**拍整片礁区）差距很大。
没有实地照片时，用**物理成像模型**合成降质是唯一严谨的替代方案。

采用的模型（Akkaynak & Treibitz 2019 修订版水下成像模型，简化实用形式）：

    I_c(x) = J_c(x) · exp(-β_c · z)  +  B_c · (1 - exp(-β_c · z))
             └── 直接透射（颜色随深度衰减）──┘  └── 后向散射（雾化/对比度下降）──┘

其中 c ∈ {R,G,B}，红光衰减最快（这正是水下照片偏蓝绿的根本原因）。

参数依据（Jerlov 水体分类，单位 1/m）：
    清澈大洋 I   : β_R=0.35  β_G=0.10  β_B=0.05
    沿岸 1C–3C   : β_R=0.55  β_G=0.16  β_B=0.09
    浑浊沿岸 5C  : β_R=0.85  β_G=0.30  β_B=0.18

再叠加真实拍摄中常见的其它退化：
    · 目标变小（分辨率损失 + 缩放）
    · JPEG 压缩
    · 传感器噪声（弱光）
    · 轻微运动模糊

用法：
    python degrade_underwater.py --src <目录> --dst <目录> --level all
    python degrade_underwater.py --image a.jpg --depth 10 --water coastal --out b.jpg
"""
import argparse
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent

# Jerlov 水体类型 → (β_R, β_G, β_B) 单位 1/m
WATER = {
    "clear":   (0.35, 0.10, 0.05),   # 清澈大洋
    "coastal": (0.55, 0.16, 0.09),   # 沿岸
    "turbid":  (0.85, 0.30, 0.18),   # 浑浊沿岸
}

# 后向散射（无穷远veiling light）强度的通道比例：蓝>绿>红
BACKSCATTER_RGB = (0.10, 0.28, 0.40)

# 预置的降质档位（模拟不同拍摄条件）
# (名称, 水体, 深度m, 目标缩放, jpeg质量, 噪声σ, 运动模糊核)
LEVELS = {
    "L0_clean":    ("clear",   0.0, 1.00, 95, 0.000, 0),
    "L1_near":     ("coastal", 3.0, 0.80, 85, 0.004, 0),   # 近距拍摄（较好条件）
    "L2_typical":  ("coastal", 8.0, 0.55, 72, 0.008, 1),   # 典型潜水拍摄
    "L3_far":      ("turbid", 15.0, 0.35, 60, 0.014, 2),   # 远距/浑浊/弱光（现场志愿者常见）
    "L4_harsh":    ("turbid", 20.0, 0.22, 45, 0.020, 3),   # 恶劣条件（浑浊 + 远距 + 手抖）
}


def degrade_array(rgb: np.ndarray, water="coastal", depth=8.0,
                  backscatter_scale=1.0, seed=0) -> np.ndarray:
    """对 float32 [0,1] RGB 数组施加物理水下退化。"""
    rng = np.random.default_rng(seed)
    beta = np.array(WATER[water], dtype=np.float32)      # (3,)
    B = np.array(BACKSCATTER_RGB, dtype=np.float32) * backscatter_scale

    T = np.exp(-beta * depth)                            # 直接透射率 (3,)
    veil = B * (1.0 - np.exp(-beta * depth))             # 后向散射 veil (3,)

    out = rgb * T[None, None, :] + veil[None, None, :]
    return np.clip(out, 0.0, 1.0)


def add_noise(rgb: np.ndarray, sigma: float, seed=0) -> np.ndarray:
    if sigma <= 0:
        return rgb
    rng = np.random.default_rng(seed + 1)
    return np.clip(rgb + rng.normal(0, sigma, rgb.shape).astype(np.float32), 0, 1)


def degrade_image(img: Image.Image, level: str, seed=0) -> Image.Image:
    water, depth, scale, jpeg_q, sigma, blur_k = LEVELS[level]
    img = img.convert("RGB")

    # 1) 物理退化
    arr = np.asarray(img).astype(np.float32) / 255.0
    arr = degrade_array(arr, water, depth, seed=seed)
    img = Image.fromarray((arr * 255).astype(np.uint8))

    # 2) 目标变小：先降采样再回原尺寸（模拟远距离/低分辨率损失）
    if scale < 1.0:
        w, h = img.size
        small = img.resize((max(16, int(w * scale)), max(16, int(h * scale))), Image.BILINEAR)
        img = small.resize((w, h), Image.BICUBIC)

    # 3) 运动模糊
    if blur_k > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=blur_k * 0.6))

    # 4) 传感器噪声
    if sigma > 0:
        a = np.asarray(img).astype(np.float32) / 255.0
        a = add_noise(a, sigma, seed=seed)
        img = Image.fromarray((a * 255).astype(np.uint8))

    # 5) JPEG 压缩
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=int(jpeg_q))
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=None, help="源目录")
    ap.add_argument("--dst", default=None, help="输出目录")
    ap.add_argument("--image", default=None, help="单张图片")
    ap.add_argument("--out", default=None)
    ap.add_argument("--depth", type=float, default=8.0)
    ap.add_argument("--water", default="coastal", choices=list(WATER))
    ap.add_argument("--level", default="all", choices=list(LEVELS) + ["all"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if args.image:
        img = Image.open(args.image)
        levels = list(LEVELS) if args.level == "all" else [args.level]
        for lv in levels:
            if args.level != "all" and args.depth != 8.0:
                water, _, scale, jq, sigma, bk = LEVELS[lv]
                out_img = degrade_array(np.asarray(img.convert("RGB")).astype(np.float32) / 255.0,
                                        args.water, args.depth)
                out_img = Image.fromarray((out_img * 255).astype(np.uint8))
            else:
                out_img = degrade_image(img, lv, seed=args.seed)
            p = Path(args.out) if args.out else (ROOT / "reports" / f"degrade_{lv}.jpg")
            if args.level == "all":
                p = p.with_name(f"{p.stem}_{lv}{p.suffix}")
            out_img.save(p, quality=95)
            print(f"  {lv:<12} → {p}")
        return

    src = Path(args.src)
    if not src.is_absolute():
        src = ROOT / src
    dst = Path(args.dst) if args.dst else (ROOT / "data" / "degraded")
    if not dst.is_absolute():
        dst = ROOT / dst

    IMG = {".jpg", ".jpeg", ".png"}
    files = sorted(f for f in src.rglob("*") if f.suffix.lower() in IMG)
    if args.limit:
        files = files[: args.limit]

    levels = list(LEVELS) if args.level == "all" else [args.level]
    print(f"源: {src}  ({len(files)} 张)")
    for lv in levels:
        outdir = dst / lv
        outdir.mkdir(parents=True, exist_ok=True)
        for i, f in enumerate(files):
            try:
                img = Image.open(f)
                degrade_image(img, lv, seed=args.seed + i).save(outdir / f"{f.stem}.jpg", quality=95)
            except Exception as e:
                print(f"  [跳过] {f.name}: {type(e).__name__}")
        print(f"  {lv:<12} → {outdir}  ({len(list(outdir.glob('*.jpg')))} 张)")

    (dst / "degrade_config.json").write_text(json.dumps({
        "note": "物理水下降质（Akkaynak-Treibitz 模型简化形式）",
        "water_types": {k: list(v) for k, v in WATER.items()},
        "levels": {k: {"water": v[0], "depth_m": v[1], "target_scale": v[2],
                       "jpeg_quality": v[3], "noise_sigma": v[4], "blur_kernel": v[5]}
                   for k, v in LEVELS.items()},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n配置: {dst/'degrade_config.json'}")


if __name__ == "__main__":
    main()
