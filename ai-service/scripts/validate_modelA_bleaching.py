"""
Model A（分割）白化检测能力验证
================================================================
背景：
  Model A（Coralscapes SegFormer）输出「白化珊瑚像素占比」，
  在项目中被推荐为主力白化评估手段（白化类别来自专业标注）。
  但此前**缺少带白化标注的独立数据集**来验证它。

本脚本用 Roboflow 白化数据集（10,382 张，Bleached / Healthy 标签，
与本项目训练数据哈希零重叠）来验证：
  · 模型输出的「白化像素占比」能否区分 Bleached / Healthy
  · 用少量真实标签拟合一个阈值后的分类表现（precision / recall / AUC）
  · 与二分类模型（bleaching_new）的表现对比

⚠️ 注意：该数据集划分存在 Roboflow 泄漏（相邻视频帧跨 split），
   因此评估时**按图像自身标签**统计，不依赖其 split 划分的可信度。

用法：
    python validate_modelA_bleaching.py --split test
    python validate_modelA_bleaching.py --limit 600
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from segment_coral import CoralSegmenter  # noqa: E402

# ⚠️ 不硬编码主机绝对路径（换机器即失效，且会把本机目录名带进仓库）。
#    优先取环境变量 CORAL_COMPETITION_DATA，否则按仓库同级目录推导。
NEW_ROOT = Path(os.environ.get(
    "CORAL_COMPETITION_DATA",
    str(ROOT.parent / "competition_data"
        / "AI4Climate_data" / "Kaggle_coral_images" / "Coral Reef Images")))


def auc(y_true, scores):
    """AUC（Mann-Whitney U 形式），无需 sklearn。"""
    y = np.asarray(y_true)
    s = np.asarray(scores)
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]))
    ranks = np.empty(len(order), dtype=float)
    ranks[order] = np.arange(1, len(order) + 1)
    r_pos = ranks[: len(pos)].sum()
    return float((r_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test", choices=["train", "valid", "test"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    seg = CoralSegmenter(size=args.size)
    print(f"Model A: Coralscapes SegFormer-B2  设备={seg.device}")
    print(f"数据: {NEW_ROOT.name}/{args.split}\n")

    rows = []
    for label, cls, y in (("Bleached", "Bleached", 1), ("Healthy", "Healthy", 0)):
        d = NEW_ROOT / args.split / cls
        if not d.exists():
            print(f"  [跳过] {d}")
            continue
        files = sorted(d.glob("*.jpg"))
        if args.limit:
            files = files[: args.limit // 2]
        print(f"  处理 {label}: {len(files)} 张 ...", flush=True)
        for f in files:
            try:
                _, _, grp = seg.segment(Image.open(f))
            except Exception:
                continue
            coral = grp.get("alive", 0) + grp.get("bleached", 0) + grp.get("dead", 0)
            rows.append({
                "file": f.name, "label": label, "y": y,
                "bleached": grp.get("bleached", 0.0),
                "alive": grp.get("alive", 0.0),
                "dead": grp.get("dead", 0.0),
                "coralTotal": coral,
                # 白化占珊瑚比例：更贴近"白化程度"的语义
                "bleachShare": (grp.get("bleached", 0.0) / coral) if coral > 0 else 0.0,
            })

    if not rows:
        raise SystemExit("无样本")

    y = np.array([r["y"] for r in rows])
    print(f"\n样本: 白化 {int(y.sum())} / 健康 {int((1-y).sum())}  共 {len(y)}")

    print("\n" + "=" * 76)
    print("Model A 输出的白化指标分布")
    print("=" * 76)
    print(f"{'指标':<24}{'白化组均值':>12}{'健康组均值':>12}{'AUC':>10}")
    print("-" * 76)
    metrics = {}
    for key, cn in (("bleached", "白化像素占比"), ("bleachShare", "白化占珊瑚比例"),
                    ("alive", "活珊瑚占比"), ("coralTotal", "珊瑚总覆盖")):
        v = np.array([r[key] for r in rows])
        a = auc(y, v)
        m1, m0 = v[y == 1].mean(), v[y == 0].mean()
        metrics[key] = {"auc": round(a, 4), "bleachedMean": round(float(m1), 4),
                        "healthyMean": round(float(m0), 4)}
        print(f"{cn:<24}{m1:>12.4f}{m0:>12.4f}{a:>10.4f}")
    print("-" * 76)

    # 最佳阈值搜索（Youden's J）
    score = np.array([r["bleachShare"] for r in rows])
    best = None
    for th in np.linspace(0.01, 0.6, 60):
        pred = score >= th
        tp = int(((pred == 1) & (y == 1)).sum())
        fn = int(((pred == 0) & (y == 1)).sum())
        fp = int(((pred == 1) & (y == 0)).sum())
        tn = int(((pred == 0) & (y == 0)).sum())
        rec = tp / max(tp + fn, 1)
        prec = tp / max(tp + fp, 1)
        spec = tn / max(tn + fp, 1)
        j = rec + spec - 1
        if best is None or j > best["j"]:
            best = {"th": float(th), "recall": rec, "precision": prec, "specificity": spec,
                    "accuracy": (tp + tn) / len(y), "j": j}
    print("\n最佳阈值（以「白化占珊瑚比例」为判据，Youden's J）:")
    print(f"  阈值      : {best['th']:.3f}")
    print(f"  召回      : {best['recall']:.2%}")
    print(f"  精确      : {best['precision']:.2%}")
    print(f"  特异度    : {best['specificity']:.2%}")
    print(f"  总体准确  : {best['accuracy']:.2%}")

    print("\n阈值扫描:")
    print(f"  {'阈值':>7}{'召回':>10}{'精确':>10}{'特异度':>10}{'准确':>10}")
    for th in (0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40):
        pred = score >= th
        tp = int(((pred) & (y == 1)).sum()); fn = int((~pred & (y == 1)).sum())
        fp = int((pred & (y == 0)).sum()); tn = int((~pred & (y == 0)).sum())
        print(f"  {th:>7.2f}{tp/max(tp+fn,1):>10.2%}{tp/max(tp+fp,1):>10.2%}"
              f"{tn/max(tn+fp,1):>10.2%}{(tp+tn)/len(y):>10.2%}")

    out = Path(args.out) if args.out else (ROOT / "reports" / f"modelA_bleaching_{args.split}.json")
    out.write_text(json.dumps({
        "model": "coralscapes-segformer-b2", "split": args.split, "n": len(rows),
        "nBleached": int(y.sum()), "nHealthy": int((1 - y).sum()),
        "metrics": metrics, "bestThreshold": best,
        "note": "用第三方 Roboflow 白化数据集验证 Model A 的白化检测能力；"
                "该数据集划分存在泄漏，故按图像自身标签统计",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果: {out}")


if __name__ == "__main__":
    main()
