"""
构建「印太域」白化数据集（用于白化模型的域适配）
================================================================
来源：
  A. 现有 3 类白化数据（Kaggle bhd-corals 等）     —— 基础训练
  B. CORAL_INDO V2（印尼 Bunaken/Karimunjawa/Wakatobi）—— 目标域

⚠️ 重要声明：CORAL_INDO 的白化标签来自 `3_bleaching_predictions`
   目录，即 **NOAA ViT 分类器的伪标签（pseudo-label）**，不是人工标注。
   因此它只用于「域适配」与「域内评估参考」，不得用于对外宣称的精度指标。

实验设计：
  train  = A_train  + B_train(80%)
  val    = A_val
  test   = A_test                    → 原域测试（与历史结果可比）
  test_ip= B_holdout(20%)            → **印太域测试（新增，反映目标域表现）**

用法：
    python build_bleaching_ip.py
"""
import json
import random
import shutil
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
OUT = PROC / "bleaching_ip"
INDO = RAW / "coral_indo" / "dataset_preparation_output"
SEED = 42

IMG_EXT = {".jpg", ".jpeg", ".png"}
# 印尼伪标签目录 → 统一类别名
INDO_MAP = {"CORAL": "healthy", "CORAL_BL": "bleached"}


def main():
    rng = random.Random(SEED)
    if OUT.exists():
        shutil.rmtree(OUT)

    plan = {s: {} for s in ("train", "val", "test", "test_ip")}

    # ---------- A. 现有 3 类数据 ----------
    src = PROC / "bleaching"
    if not src.exists():
        raise SystemExit(f"缺少 {src}，请先运行 split_data.py --task bleaching")
    for split in ("train", "val", "test"):
        for cls_dir in (src / split).iterdir():
            if not cls_dir.is_dir():
                continue
            dst = OUT / split / cls_dir.name
            dst.mkdir(parents=True, exist_ok=True)
            n = 0
            for f in cls_dir.iterdir():
                if f.suffix.lower() in IMG_EXT:
                    shutil.copy2(f, dst / f.name)
                    n += 1
            plan[split][cls_dir.name] = n

    # ---------- B. 印尼数据（80% 进 train，20% 进 test_ip）----------
    indo_alloc = Counter()
    if INDO.exists():
        for site_dir in sorted(INDO.iterdir()):
            if not site_dir.is_dir():
                continue
            bl_dir = site_dir / "3_bleaching_predictions"
            if not bl_dir.exists():
                continue
            for sub, cls in INDO_MAP.items():
                d = bl_dir / sub
                if not d.exists():
                    continue
                files = sorted(f for f in d.iterdir() if f.suffix.lower() in IMG_EXT)
                rng.shuffle(files)
                k = max(1, int(round(len(files) * 0.2)))
                hold, train = files[:k], files[k:]
                for split, group in (("train", train), ("test_ip", hold)):
                    dst = OUT / split / cls
                    dst.mkdir(parents=True, exist_ok=True)
                    for f in group:
                        shutil.copy2(f, dst / f"{site_dir.name}_{f.name}")
                    indo_alloc[(split, cls)] += len(group)
    else:
        print(f"⚠ 未找到印尼数据目录 {INDO}")

    # ---------- 报告 ----------
    print("=" * 66)
    print("数据集构建完成:", OUT)
    print("=" * 66)
    print(f"{'split':<10}{'类别':<14}{'数量':>8}")
    print("-" * 66)
    for split in ("train", "val", "test", "test_ip"):
        if not (OUT / split).exists():
            continue
        for cls_dir in sorted((OUT / split).iterdir()):
            if cls_dir.is_dir():
                n = sum(1 for f in cls_dir.iterdir() if f.suffix.lower() in IMG_EXT)
                print(f"{split:<10}{cls_dir.name:<14}{n:>8}")
    print("-" * 66)

    meta = {
        "note": "test_ip 使用 CORAL_INDO 伪标签，仅作目标域参考，不得作为对外精度声明",
        "indo_pseudo_labels_from": "NOAA ViT classifier (3_bleaching_predictions)",
        "plan": {k: dict(v) for k, v in plan.items()},
        "indo_alloc": {f"{a}/{b}": c for (a, b), c in indo_alloc.items()},
        "seed": SEED,
    }
    (OUT / "dataset_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n元信息: {OUT/'dataset_meta.json'}")


if __name__ == "__main__":
    main()
