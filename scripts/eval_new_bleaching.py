"""
在新数据集（AI4Climate_data）上的独立评估
================================================================
该数据集为 Roboflow 导出的**二分类**白化数据（Bleached / Healthy），
共 10,382 张，与我原有训练数据**哈希零重叠** —— 是干净的独立测试集。

本脚本用现有模型（3 类：bleached/dead/healthy）在其 valid/test 上评估：
  · 白化召回 / 精确率（核心指标）
  · 健康召回
  · 二分类准确率（把 dead 视为非白化）
  · 置信度分布

用法：
    python eval_new_bleaching.py
    python eval_new_bleaching.py --task bleaching_ip --split test
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torchvision import transforms
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from train import build_model  # noqa: E402

NEW_ROOT = Path(r"D:\大学作业\广东海洋大学的珊瑚评测小程序\competition_data"
                r"\AI4Climate_data\Kaggle_coral_images\Coral Reef Images")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="bleaching_ip")
    ap.add_argument("--split", default="test", choices=["train", "valid", "test"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    wpath = ROOT / "weights" / args.task / "best.pt"
    if not wpath.exists():
        raise SystemExit(f"找不到权重 {wpath}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(wpath, map_location=device, weights_only=False)
    classes = ck["classes"]
    size = ck.get("img_size", 224)
    model = build_model(ck["backbone"], len(classes)).to(device)
    model.load_state_dict(ck["model"])
    model.eval()
    mp = ROOT / "reports" / args.task / "metrics.json"
    T = float(json.loads(mp.read_text(encoding="utf-8")).get("temperature", 1.0)) if mp.exists() else 1.0

    tf = transforms.Compose([
        transforms.Resize(int(size * 1.14)), transforms.CenterCrop(size),
        transforms.ToTensor(), transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

    print(f"模型: {args.task}  权重={ck['backbone']}  类别={classes}  T={T:.4f}")
    print(f"数据: {NEW_ROOT.name}/{args.split}\n")

    bi = classes.index("bleached") if "bleached" in classes else None
    if bi is None:
        raise SystemExit("模型无 bleached 类")

    rows = []
    for cls in ("Bleached", "Healthy"):
        d = NEW_ROOT / args.split / cls
        if not d.exists():
            print(f"  [跳过] {d} 不存在"); continue
        files = sorted(d.glob("*.jpg"))
        if args.limit:
            files = files[: args.limit]
        for f in files:
            try:
                x = tf(Image.open(f).convert("RGB")).unsqueeze(0).to(device)
                with torch.no_grad(), torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                    p = F.softmax(model(x).float() / T, 1)[0].cpu().numpy()
            except Exception:
                continue
            pred = int(p.argmax())
            rows.append({"cls": cls, "pred": classes[pred], "pBleach": float(p[bi]),
                         "conf": float(p.max()), "file": f.name})

    if not rows:
        raise SystemExit("无样本")

    n_ble = sum(1 for r in rows if r["cls"] == "Bleached")
    n_hea = len(rows) - n_ble
    print("=" * 76)
    print(f"独立测试集结果（{args.task} / {args.split}，n={len(rows)}）")
    print("=" * 76)
    print(f"{'指标':<26}{'数值':>12}")
    print("-" * 76)

    # 白化召回：真白化中被判为 bleached 的比例
    ble_rec = sum(1 for r in rows if r["cls"] == "Bleached" and r["pred"] == "bleached") / max(n_ble, 1)
    ble_pred_n = sum(1 for r in rows if r["pred"] == "bleached")
    ble_prec = (sum(1 for r in rows if r["cls"] == "Bleached" and r["pred"] == "bleached")
                / max(ble_pred_n, 1))
    # 健康召回：真健康中未被判为 bleached 的比例（判为 healthy 或 dead 都算"非白化"）
    hea_rec = sum(1 for r in rows if r["cls"] == "Healthy" and r["pred"] != "bleached") / max(n_hea, 1)
    # 二分类准确率
    acc2 = (sum(1 for r in rows if (r["cls"] == "Bleached") == (r["pred"] == "bleached"))) / len(rows)

    print(f"{'白化类召回 (Recall)':<26}{ble_rec:>12.2%}   ← 核心指标")
    print(f"{'白化类精确 (Precision)':<26}{ble_prec:>12.2%}")
    print(f"{'健康类召回':<26}{hea_rec:>12.2%}")
    print(f"{'二分类准确率':<26}{acc2:>12.2%}")
    print(f"{'样本数 (白化/健康)':<26}{f'{n_ble}/{n_hea}':>12}")
    print("-" * 76)

    # 类分布
    dist = defaultdict(int)
    for r in rows:
        dist[f"{r['cls']}→{r['pred']}"] += 1
    print("\n混淆明细:")
    for k in sorted(dist):
        print(f"  {k:<26}{dist[k]:>6}")

    # 按预测类别的置信度
    print("\n置信度分布:")
    for c in classes:
        g = [r["conf"] for r in rows if r["pred"] == c]
        if g:
            print(f"  {c:<12} n={len(g):<5} 平均置信度={np.mean(g):.3f}  "
                  f"P25={np.percentile(g,25):.3f}  P75={np.percentile(g,75):.3f}")

    # 阈值扫描（提升白化召回的代价）
    print("\n白化判定阈值扫描（降低阈值 → 提升召回，牺牲精确）:")
    print(f"  {'阈值':>7}{'白化召回':>10}{'白化精确':>10}{'二分类准确':>12}")
    best = None
    for th in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        pred_b = [r["pBleach"] >= th for r in rows]
        rec = sum(1 for r, pb in zip(rows, pred_b) if r["cls"] == "Bleached" and pb) / max(n_ble, 1)
        pr = (sum(1 for r, pb in zip(rows, pred_b) if r["cls"] == "Bleached" and pb)
              / max(sum(pred_b), 1))
        a2 = sum(1 for r, pb in zip(rows, pred_b) if (r["cls"] == "Bleached") == pb) / len(rows)
        print(f"  {th:>7.2f}{rec:>10.2%}{pr:>10.2%}{a2:>12.2%}")
        if best is None or rec > best[1]:
            best = (th, rec, pr, a2)

    out = Path(args.out) if args.out else (ROOT / "reports" / f"new_bleaching_{args.task}_{args.split}.json")
    out.write_text(json.dumps({
        "model": args.task, "split": args.split, "n": len(rows),
        "nBleached": n_ble, "nHealthy": n_hea,
        "bleachedRecall": round(ble_rec, 6), "bleachedPrecision": round(ble_prec, 6),
        "healthyRecall": round(hea_rec, 6), "binaryAccuracy": round(acc2, 6),
        "bestThreshold": {"th": best[0], "recall": best[1], "precision": best[2], "acc2": best[3]},
        "confusion": dict(dist),
        "note": "该数据集与本项目原训练数据哈希零重叠，属独立测试集",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果: {out}")


if __name__ == "__main__":
    main()
