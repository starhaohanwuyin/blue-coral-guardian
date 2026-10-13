"""人工标注工具链：为「个体计数在真实照片上的核验」（P3 的已知缺口）铺路。

背景：当前计数的**真值来自 Coralscapes 掩膜连通域（自动标注）**，紧贴的个体会被合并，
所以"偏少"是必然的。要量化这个偏差，只能在**真实照片**上人工标一批框再比。
标注本身需要约 1 人天，但剩下的都可以脚本化 —— 本脚本就是那部分。

用法：
    # 1) 准备抽样与目录（生成 images/ + 空 labels/ + data.yaml + 标注说明）
    python yolo_manual_annotation_kit.py --prepare 60
    # 2) 用 labelImg / CVAT 在 data/yolo_manual/images 上画框（单类 coral），
    #    标注存成 YOLO txt 到 data/yolo_manual/labels/<同名>.txt
    # 3) 标注完做核验（真实照片上的 mAP + 计数偏差/MAE）
    python yolo_manual_annotation_kit.py --eval
"""
import argparse
import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "data" / "yolo_manual"
IMG_DIR = KIT / "images"
LBL_DIR = KIT / "labels"
SOURCE = ROOT / "data" / "semporna_photos"
WEIGHTS = ROOT / "weights" / "yolo_coral" / "best.pt"
REPORT = ROOT / "reports" / "yolo_manual_verify.json"
CLASSES = ["coral"]

README = """# 人工实例标注（个体计数核验）

## 为什么要做
现有真值是 Coralscapes 掩膜连通域（**自动标注**），紧贴的个体会被合并 → 计数偏少。
要量化偏差，必须在**真实照片**上人工标一批框再比。

## 怎么标（约 1 人天 / 60 张）
1. 装 labelImg（`pip install labelImg`）或直接用 CVAT。
2. labelImg 打开 `data/yolo_manual/images`，格式选 **YOLO**，类别只写一个：`coral`。
3. **框住每一个可分辨的珊瑚个体**（含紧贴的个体，各画各的框）；实在分不开的合并成一个框并在备注里说明。
4. 标签自动存到 `labels/`（与图片同名 `.txt`）。classes.txt 已给出。

## 标注完
    python scripts/yolo_manual_annotation_kit.py --eval
→ 输出真实照片上的 mAP@0.5、总计数偏差、逐图 MAE，写入 `reports/yolo_manual_verify.json`。

⚠️ 这批图与训练集**同域**（都是仙本那照片），所以它验证的是"真值标注方式带来的偏差"，
不是跨海域泛化。跨域核验还需要别的海域的照片。
"""


def prepare(n: int, seed: int = 42):
    if not SOURCE.exists():
        print(f"❌ 找不到源图目录 {SOURCE}")
        return 1
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    LBL_DIR.mkdir(parents=True, exist_ok=True)
    pool = sorted([p for p in SOURCE.rglob("*.jpg")] + [p for p in SOURCE.rglob("*.jpeg")])
    if not pool:
        print(f"❌ {SOURCE} 下没有 jpg")
        return 1
    random.seed(seed)
    picked = random.sample(pool, min(n, len(pool)))
    for i, src in enumerate(picked):
        dst = IMG_DIR / f"manual_{i + 1:03d}{src.suffix.lower()}"
        if not dst.exists():
            shutil.copy2(src, dst)
    (KIT / "classes.txt").write_text("\n".join(CLASSES) + "\n", encoding="utf-8")
    (KIT / "README.md").write_text(README, encoding="utf-8")
    (KIT / "data.yaml").write_text(
        f"path: {KIT.as_posix()}\ntrain: images\nval: images\nnames:\n  0: coral\n", encoding="utf-8")
    print(f"✅ 已抽样 {len(picked)} 张 → {IMG_DIR}")
    print(f"   标签目录（先为空）：{LBL_DIR}")
    print(f"   说明：{KIT / 'README.md'}")
    print(f"   下一步：用 labelImg 画框（单类 coral），再跑 --eval")
    return 0


def eval_kit():
    imgs = sorted(IMG_DIR.glob("*.jpg")) + sorted(IMG_DIR.glob("*.jpeg"))
    labeled = [p for p in imgs if (LBL_DIR / f"{p.stem}.txt").exists()]
    if not imgs:
        print("❌ 还没有图片：先跑 `--prepare 60`")
        return 1
    if not labeled:
        print(f"⚠️ 共 {len(imgs)} 张图，但 labels/ 里还没有标注（0 个 .txt）")
        print("   请先用 labelImg/CVAT 标注（详见 data/yolo_manual/README.md），再跑 --eval")
        return 1

    from ultralytics import YOLO
    try:
        import yaml  # noqa: F401
    except ImportError:
        print("⚠️ 需要 pyyaml（ultralytics 自带）：pip install pyyaml")
        return 1

    print(f"用 {len(labeled)}/{len(imgs)} 张有标注的图核验（权重 {WEIGHTS.name}）…")
    model = YOLO(str(WEIGHTS))
    r = model.val(data=str(KIT / "data.yaml"), split="val", imgsz=896, conf=0.20, iou=0.5,
                  plots=False, verbose=False, device=None)

    # 计数统计（与训练评估同口径：conf=0.20）
    gt_counts, pred_counts = [], []
    for p in labeled:
        n_gt = sum(1 for ln in (LBL_DIR / f"{p.stem}.txt").read_text(encoding="utf-8").splitlines() if ln.strip())
        res = model.predict(source=str(p), imgsz=896, conf=0.20, iou=0.5, verbose=False, plots=False)[0]
        gt_counts.append(n_gt)
        pred_counts.append(0 if res.boxes is None else len(res.boxes))
    tot_gt, tot_pred = sum(gt_counts), sum(pred_counts)
    n = max(len(gt_counts), 1)
    mae = sum(abs(a - b) for a, b in zip(gt_counts, pred_counts)) / n
    out = {
        "task": "个体计数：真实照片人工标注核验",
        "images": len(labeled), "imgsz": 896, "conf": 0.20, "iou": 0.5,
        "mAP50": round(float(r.box.map50), 4), "mAP50_95": round(float(r.box.map), 4),
        "precision": round(float(r.box.mp), 4), "recall": round(float(r.box.mr), 4),
        "counting": {"gtTotal": tot_gt, "predTotal": tot_pred,
                     "countBias": round((tot_pred - tot_gt) / max(tot_gt, 1), 4),
                     "maePerImage": round(mae, 3)},
        "note": ("真值 = 人工在真实照片上标的个体框；与训练真值（掩膜连通域）不同，"
                 "差值即「自动标注造成的合并偏差」。同域图片，不代表跨海域泛化。"),
        "kitDir": KIT.relative_to(ROOT).as_posix(),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  手工真值 {tot_gt} / 模型预测 {tot_pred} → 偏差 {out['counting']['countBias']:+.1%}，"
          f"MAE {out['counting']['maePerImage']}")
    print(f"  mAP@0.5 = {out['mAP50']}  mAP@0.5:0.95 = {out['mAP50_95']}")
    print(f"  结果写入 {REPORT}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="人工实例标注工具链（计数核验）")
    ap.add_argument("--prepare", type=int, default=0, help="抽样 N 张待标注图片并生成目录结构")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--eval", action="store_true", help="对已标注图片做核验")
    a = ap.parse_args()
    if a.prepare:
        return prepare(a.prepare, a.seed)
    if a.eval:
        return eval_kit()
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
