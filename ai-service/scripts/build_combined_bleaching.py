"""
合并数据集构建：旧白化集 + 新 Roboflow 白化集
================================================================
背景（实测）：
  · 旧模型 bleaching_ip  ：印尼域 85.23%，新域仅 75.56% 召回
  · 新模型 bleaching_new ：新域 99.40%，印尼域仅 21.02%
  → 两者各有优势域，说明单靠任一数据源都不够。

本脚本把两者合并为统一的 3 类结构（bleached / healthy / dead）：
  · 旧集：bleached / healthy / dead
  · 新集：Bleached → bleached，Healthy → healthy
  · 用目录 junction 嵌套，避免复制 1 GB 图片
    （torchvision.ImageFolder 会递归遍历类目录，因此嵌套目录可用）

用法：
    python build_combined_bleaching.py
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "processed" / "bleaching_all"

# (来源目录, 该来源的类别名 → 目标类别名)
SOURCES = [
    (ROOT / "data" / "processed" / "bleaching",
     {"bleached": "bleached", "healthy": "healthy", "dead": "dead"}, "old"),
    (ROOT / "data" / "processed" / "bleaching_ip",
     {"bleached": "bleached", "healthy": "healthy", "dead": "dead"}, "oldip"),
    (ROOT / "data" / "processed" / "bleaching_new",
     {"Bleached": "bleached", "Healthy": "healthy"}, "new"),
]
SPLITS = {"train": ["train"], "val": ["val"], "test": ["test"]}
# 统一的评估集：保留旧集的 test / test_ip 供跨域评估
EXTRA_TESTS = {"test_ip": ROOT / "data" / "processed" / "bleaching_ip" / "test_ip"}


def junction(link: Path, target: Path):
    if link.exists():
        return False
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                   capture_output=True, text=True)
    return link.exists()


def main():
    if sys.platform != "win32":
        raise SystemExit("本脚本用 Windows junction，需在 Windows 上运行")
    OUT.mkdir(parents=True, exist_ok=True)
    counts = {}
    made = 0

    for split, src_splits in SPLITS.items():
        for dst_cls in ("bleached", "healthy", "dead"):
            (OUT / split / dst_cls).mkdir(parents=True, exist_ok=True)
        for src_dir, cls_map, tag in SOURCES:
            for s in src_splits:
                for src_cls, dst_cls in cls_map.items():
                    d = src_dir / s / src_cls
                    if not d.exists():
                        continue
                    link = OUT / split / dst_cls / f"{tag}_{src_cls}"
                    if junction(link, d):
                        made += 1
                    n = len(list(d.glob("*")))
                    counts[f"{split}/{dst_cls}"] = counts.get(f"{split}/{dst_cls}", 0) + n

    # 额外的跨域测试集
    for name, src in EXTRA_TESTS.items():
        if not src.exists():
            continue
        for cls in ("bleached", "healthy", "dead"):
            t = src / cls
            if not t.exists():
                continue
            (OUT / name / cls).mkdir(parents=True, exist_ok=True)
            junction(OUT / name / cls / "oldip", t)

    print(f"建立 junction: {made} 个")
    print(f"输出目录: {OUT}\n")
    print(f"{'split/类别':<22}{'图片数':>8}")
    print("-" * 32)
    for k in sorted(counts):
        print(f"{k:<22}{counts[k]:>8}")

    # 验证读入
    from torchvision import datasets
    print("\n验证 ImageFolder:")
    ok = True
    for split in ("train", "val", "test", "test_ip"):
        d = OUT / split
        if not d.exists():
            continue
        ds = datasets.ImageFolder(d)
        n_per = {c: 0 for c in ds.classes}
        for _, ci in ds.samples:
            n_per[ds.classes[ci]] += 1
        print(f"  {split:<8} 共 {len(ds):>6} 张  {n_per}")
        if len(ds) == 0:
            ok = False
    print("\n" + ("✅ 合并数据集可用" if ok else "❌ 有问题"))

    (ROOT / "reports" / "combined_dataset.json").write_text(json.dumps({
        "path": str(OUT), "counts": counts, "junctions": made,
        "classes": ["bleached", "healthy", "dead"],
        "note": "旧集 + 新 Roboflow 集的合并；用 junction 嵌套避免复制",
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
