"""
近重复审计（E10）：跨 train/val/test 检测近似重复图片
================================================================
目的：iNaturalist 上同一张照片可能被多次上传（不同观察/不同用户），
      若它们被分到不同 split，就构成**数据泄漏**，会虚高测试指标。

方法：感知哈希（dHash + aHash）
      · dHash：缩放到 9×8 灰度 → 比较相邻像素 → 64 bit
      · aHash：缩放到 8×8 灰度 → 与均值比较 → 64 bit
      · 汉明距离 ≤ 阈值（默认 6）判为近似重复

输出：
  · 跨 split 的重复对清单
  · 若存在泄漏，报告「剔除后的干净测试集规模」

用法：
    python phash_audit.py --root data/inat_dataset/images --threshold 6
    python phash_audit.py --root data/inat_dataset/images --report-only
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
IMG_EXT = {".jpg", ".jpeg", ".png"}


def dhash(img: Image.Image, size=8) -> int:
    g = img.convert("L").resize((size + 1, size), Image.BILINEAR)
    a = np.asarray(g, dtype=np.int16)
    diff = a[:, 1:] > a[:, :-1]
    bits = 0
    for b in diff.flatten():
        bits = (bits << 1) | int(b)
    return bits


def ahash(img: Image.Image, size=8) -> int:
    g = img.convert("L").resize((size, size), Image.BILINEAR)
    a = np.asarray(g, dtype=np.float32)
    bits = 0
    for b in (a > a.mean()).flatten():
        bits = (bits << 1) | int(b)
    return bits


def hamming(x: int, y: int) -> int:
    return bin(x ^ y).count("1")


def collect(root: Path):
    out = defaultdict(list)
    for split in ("train", "val", "test", "test_ip"):
        d = root / split
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if f.suffix.lower() in IMG_EXT:
                out[split].append(f)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT / "data" / "inat_dataset" / "images"))
    ap.add_argument("--threshold", type=int, default=6)
    ap.add_argument("--limit-per-split", type=int, default=0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    root = Path(args.root)
    if not root.is_absolute():
        root = ROOT / root
    files = collect(root)
    print("各 split 图片数:", {k: len(v) for k, v in files.items()})

    # 计算哈希
    hashes = {}
    for split, fs in files.items():
        if args.limit_per_split:
            fs = fs[: args.limit_per_split]
        for f in fs:
            try:
                img = Image.open(f)
                hashes[(split, f)] = (dhash(img), ahash(img))
            except Exception:
                continue
    print(f"已计算哈希: {len(hashes)} 张")

    # 分桶加速：按 dHash 前 16 位分桶
    buckets = defaultdict(list)
    for key, (dh, ah) in hashes.items():
        buckets[dh >> 48].append(key)

    # 找跨 split 的近似重复
    cross = []
    keys = list(hashes.keys())
    checked = 0
    for key in keys:
        split, f = key
        dh, ah = hashes[key]
        base = dh >> 48
        cand = []
        for b in (base - 1, base, base + 1):        # 只比相邻桶
            cand += buckets.get(b & 0xFFFF, [])
        for other in cand:
            if other <= key:
                continue
            osplit, of = other
            if osplit == split:
                continue
            odh, oah = hashes[other]
            d1, d2 = hamming(dh, odh), hamming(ah, oah)
            if d1 <= args.threshold or d2 <= args.threshold:
                cross.append({"a": f"{split}/{f.name}", "b": f"{osplit}/{of.name}",
                              "dHashDist": d1, "aHashDist": d2})
            checked += 1

    print(f"\n跨 split 近似重复对: {len(cross)}")
    for c in cross[:20]:
        print(f"  {c['a']}  <->  {c['b']}   (d={c['dHashDist']}, a={c['aHashDist']})")

    # 统计每个 split 涉及泄漏的图片数
    leak = defaultdict(set)
    for c in cross:
        leak[c["a"].split("/")[0]].add(c["a"])
        leak[c["b"].split("/")[0]].add(c["b"])
    print("\n各 split 涉及的重复图片数:")
    for s, v in leak.items():
        print(f"  {s}: {len(v)} / {len(files.get(s, []))}")

    out = Path(args.out) if args.out else (ROOT / "reports" / "phash_audit.json")
    out.write_text(json.dumps({
        "root": str(root), "threshold": args.threshold,
        "counts": {k: len(v) for k, v in files.items()},
        "hashed": len(hashes), "crossDuplicates": len(cross),
        "leakPerSplit": {k: len(v) for k, v in leak.items()},
        "pairs": cross[:2000],
        "note": "跨 split 近似重复构成数据泄漏；若数量显著，需从训练集剔除这些图片后重测",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告: {out}")


if __name__ == "__main__":
    main()
