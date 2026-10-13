"""
数据整理与划分 —— 防泄漏版
================================================================
作用：把原始数据集（各种目录结构）整理成统一的 ImageFolder 结构：

    data/processed/<task>/{train,val,test}/<class_name>/*.jpg

关键设计（很重要，直接决定指标是否可信）：
  1. MD5 去重：Kaggle 上几个珊瑚数据集同源（比如 aneeshdighe 与
     vencerlanz09 的图片文件名完全相同），合并前必须去重，
     否则同一张图既在训练集又在测试集 → 准确率虚高。
  2. 分层划分：按类别比例划分 train/val/test，避免小类别全被分到一边。
  3. 固定随机种子 + 写出 splits.json：保证结果可复现。

用法：
    python split_data.py --task bleaching --src <目录> [--src <目录2> ...]
    python split_data.py --task species   --src <目录>
"""
import argparse
import hashlib
import json
import random
import shutil
import sys
from collections import defaultdict
from pathlib import Path

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def md5_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def collect(src_dirs):
    """从多个源目录收集 {class_name: [paths]}，自动兼容多种目录结构。

    兼容：
      - <src>/<class>/*.jpg                （标准 ImageFolder）
      - <src>/Dataset/<class>/*.png        （bhd-corals）
      - <src>/Train/<class>/*.png          （bleached-corals-detection）
      - <src>/Testing/<class>/*.jpg        （aneeshdighe）
    """
    by_class = defaultdict(list)
    for src in src_dirs:
        src = Path(src)
        if not src.exists():
            print(f"  [跳过] 不存在: {src}")
            continue
        # 找出所有"直接包含图片"的目录
        for d in [src] + [p for p in src.rglob("*") if p.is_dir()]:
            imgs = [p for p in d.iterdir() if p.is_file() and p.suffix.lower() in IMG_EXT]
            if not imgs:
                continue
            cls = d.name
            # 跳过 Data/Dataset/Train/Testing 这类容器目录名
            if cls.lower() in {"data", "dataset", "train", "test", "testing", "images", "val", "valid"}:
                continue
            by_class[cls].extend(imgs)
    return by_class


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, help="任务名，如 bleaching / species")
    ap.add_argument("--src", action="append", required=True, help="源目录（可重复传多个）")
    ap.add_argument("--out", default=None, help="输出根目录，默认 data/processed")
    ap.add_argument("--val-ratio", type=float, default=0.15)
    ap.add_argument("--test-ratio", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--min-per-class", type=int, default=20,
                    help="少于该数量的类别会被丢弃（样本太少无法训练/评估）")
    ap.add_argument("--map", default=None,
                    help='类别名映射（JSON），如 \'{"Bleached":"bleached","healthy_corals":"healthy"}\'。'
                         '多个数据集类名不一致时必须用它归并')
    ap.add_argument("--map-file", default=None,
                    help="类别名映射 JSON 文件路径（Windows 下推荐用这个，避免引号被 shell 吞掉）")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    out_root = Path(args.out) if args.out else root / "data" / "processed"
    out_dir = out_root / args.task

    print("=" * 62)
    print(f"任务: {args.task}")
    print(f"源目录: {args.src}")
    print("=" * 62)

    by_class = collect(args.src)
    print(f"\n[1/5] 收集到 {len(by_class)} 个类别目录，共 {sum(len(v) for v in by_class.values())} 张图")

    # ---- 类别名归一化（多数据集类名不一致时归并）----
    if args.map_file:
        with open(args.map_file, "r", encoding="utf-8") as f:
            args.map = f.read()
    if args.map:
        mapping = json.loads(args.map)
        merged = defaultdict(list)
        for cls, paths in by_class.items():
            merged[mapping.get(cls, cls)].extend(paths)
        print(f"      原始类别: {sorted(by_class.keys())}")
        print(f"      映射规则: {mapping}")
        by_class = merged
        print(f"      归并后类别: {sorted(by_class.keys())}")

    # ---- 去重（全局 MD5，跨类别也去重，防止同一图被标成两类）----
    print("[2/5] MD5 去重中...")
    seen = {}
    dedup = defaultdict(list)
    dup_in_class = 0
    dup_cross = 0
    for cls, paths in sorted(by_class.items()):
        for p in paths:
            try:
                h = md5_of(p)
            except OSError:
                continue
            if h in seen:
                if seen[h] == cls:
                    dup_in_class += 1
                else:
                    dup_cross += 1
                continue
            seen[h] = cls
            dedup[cls].append(p)
    print(f"      类别内重复: {dup_in_class} 张 | 跨类别重复: {dup_cross} 张")
    print(f"      去重后剩余: {sum(len(v) for v in dedup.values())} 张")

    # ---- 过滤小类别 ----
    kept, dropped = {}, {}
    for cls, paths in dedup.items():
        if len(paths) >= args.min_per_class:
            kept[cls] = paths
        else:
            dropped[cls] = len(paths)
    if dropped:
        print(f"[3/5] 丢弃样本过少的类别（<{args.min_per_class}）: {dropped}")
    else:
        print("[3/5] 无需丢弃类别")

    # ---- 分层划分 ----
    print("[4/5] 分层划分 train/val/test ...")
    rng = random.Random(args.seed)
    splits = {"train": [], "val": [], "test": []}
    summary = {}
    for cls, paths in sorted(kept.items()):
        paths = sorted(paths)
        rng.shuffle(paths)
        n = len(paths)
        n_test = max(1, int(round(n * args.test_ratio)))
        n_val = max(1, int(round(n * args.val_ratio)))
        if n - n_val - n_test < 1:  # 极小类别兜底
            n_val = n_test = 1 if n >= 3 else 0
        part = {
            "test": paths[:n_test],
            "val": paths[n_test:n_test + n_val],
            "train": paths[n_test + n_val:],
        }
        summary[cls] = {k: len(v) for k, v in part.items()}
        for k, v in part.items():
            splits[k].extend((str(p), cls) for p in v)

    # ---- 落盘 ----
    print("[5/5] 写入目标结构 ...")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    for split in ("train", "val", "test"):
        for src_path, cls in splits[split]:
            dst = out_dir / split / cls / Path(src_path).name
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():  # 同名不同内容，加后缀
                dst = dst.with_name(f"{dst.stem}_{abs(hash(src_path)) % 10000}{dst.suffix}")
            shutil.copy2(src_path, dst)

    with open(out_dir / "splits.json", "w", encoding="utf-8") as f:
        json.dump({
            "task": args.task, "seed": args.seed,
            "val_ratio": args.val_ratio, "test_ratio": args.test_ratio,
            "classes": sorted(kept.keys()),
            "per_class": summary,
            "counts": {k: len(v) for k, v in splits.items()},
        }, f, ensure_ascii=False, indent=2)

    # ---- 报告 ----
    print("\n" + "=" * 62)
    print(f"完成 → {out_dir}")
    print(f"类别数: {len(kept)}")
    print(f"train/val/test = {len(splits['train'])}/{len(splits['val'])}/{len(splits['test'])}")
    print("-" * 62)
    print(f"{'类别':<26}{'train':>7}{'val':>6}{'test':>6}{'合计':>7}")
    for cls in sorted(summary):
        s = summary[cls]
        print(f"{cls:<26}{s['train']:>7}{s['val']:>6}{s['test']:>6}{sum(s.values()):>7}")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
