"""
白化类召回提升实验（E11）
================================================================
问题（实测）：
    印太域测试中白化类召回仅 42.3%（26 张只对 11 张），
    而健康类召回 92.7%。argmax 决策在类别不平衡时严重偏向多数类。

原理：
    当测试集先验与训练集先验不一致时，argmax 不是最优决策。
    标准修正手段是 **先验校正（logit adjustment / prior correction）**：
        p'(y|x) ∝ p(y|x) / p_train(y)^τ · p_test(y)^τ
    取 τ=1、p_test 为均匀先验时，等价于按训练先验的倒数给各类加权，
    可显著提升少数类召回。

本脚本对比三种决策规则，并给出「召回–精确率」权衡曲线：
    A. argmax（基线）
    B. 先验校正（logit adjustment）
    C. 白化类阈值扫描（推荐给保育场景：宁可多报，不可漏报）

用法：
    python eval_decision_rules.py --task bleaching_ip --split test_ip
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train import build_model  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="bleaching_ip")
    ap.add_argument("--split", default="test_ip")
    ap.add_argument("--tau", type=float, default=1.0, help="先验校正强度")
    args = ap.parse_args()

    data_dir = ROOT / "data" / "processed" / args.task
    wpath = ROOT / "weights" / args.task / "best.pt"
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(wpath, map_location=device, weights_only=False)
    classes = ck["classes"]
    size = ck.get("img_size", 224)
    model = build_model(ck["backbone"], len(classes)).to(device)
    model.load_state_dict(ck["model"]); model.eval()
    T = 1.0
    mp = ROOT / "reports" / args.task / "metrics.json"
    if mp.exists():
        T = float(json.loads(mp.read_text(encoding="utf-8")).get("temperature", 1.0))

    tf = transforms.Compose([
        transforms.Resize(int(size * 1.14)), transforms.CenterCrop(size), transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
    ds = datasets.ImageFolder(data_dir / args.split, transform=tf)
    remap = np.array([classes.index(c) for c in ds.classes])
    loader = DataLoader(ds, batch_size=32, shuffle=False, num_workers=4)

    probs, ys = [], []
    with torch.no_grad():
        for x, y in loader:
            with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                lg = model(x.to(device)).float()
            probs.append(F.softmax(lg / T, 1).cpu().numpy())
            ys.append(remap[y.numpy()])
    probs = np.concatenate(probs)
    y = np.concatenate(ys)
    n_cls = len(classes)

    # 训练集先验（用于校正）
    tr_dir = data_dir / "train"
    prior = np.zeros(n_cls)
    for c in tr_dir.iterdir():
        if c.is_dir() and c.name in classes:
            prior[classes.index(c.name)] = len(list(c.glob("*")))
    prior = prior / max(prior.sum(), 1)
    print(f"任务={args.task} split={args.split} 样本={len(y)} 类别={classes}")
    print(f"训练先验: {dict(zip(classes, np.round(prior,3).tolist()))}")
    print(f"测试分布: {dict(zip(classes, np.bincount(y, minlength=n_cls).tolist()))}")

    def report(tag, pred):
        print("-" * 62)
        print(f"[{tag}] 总体准确率 {np.mean(pred==y):.4f}")
        out = {"accuracy": float(np.mean(pred == y)),
               "perClass": {}, "recall": {}, "precision": {}}
        for i, c in enumerate(classes):
            m = (y == i)
            if m.sum() == 0:
                continue
            rec = float(np.mean(pred[m] == i))
            pr = float(np.sum((pred == i) & (y == i)) / max(np.sum(pred == i), 1))
            print(f"   {c:<10} n={m.sum():<4} 召回={rec:.3f}  精确={pr:.3f}")
            out["perClass"][c] = {"n": int(m.sum()), "recall": round(rec, 4),
                                  "precision": round(pr, 4)}
            out["recall"][c] = round(rec, 4)
            out["precision"][c] = round(pr, 4)
        return out

    results = {}
    # A. 基线 argmax
    results["A_argmax"] = report("A. argmax（基线）", probs.argmax(1))

    # B. 先验校正
    adj = probs / np.power(np.maximum(prior, 1e-6), args.tau)[None, :]
    adj = adj / adj.sum(1, keepdims=True)
    results["B_prior_corrected"] = report(f"B. 先验校正 τ={args.tau}", adj.argmax(1))

    # C. 白化类阈值扫描
    if "bleached" in classes:
        bi = classes.index("bleached")
        print("-" * 62)
        print("C. 白化类阈值扫描（降低白化判定门槛 → 提升召回，牺牲精确）")
        print(f"   {'β':>6}{'白化召回':>10}{'白化精确':>10}{'总体准确':>10}")
        best = None
        for beta in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0):
            p2 = probs.copy()
            p2[:, bi] *= beta
            pred = p2.argmax(1)
            m = (y == bi)
            rec = float(np.mean(pred[m] == bi)) if m.sum() else 0.0
            pr = float(np.sum((pred == bi) & (y == bi)) / max(np.sum(pred == bi), 1))
            acc = float(np.mean(pred == y))
            print(f"   {beta:>6.1f}{rec:>10.3f}{pr:>10.3f}{acc:>10.3f}")
            if best is None or rec > best[1]:
                best = (beta, rec, pr, acc)
        results["C_bleached_boost"] = {"best_beta": best[0], "recall": best[1],
                                       "precision": best[2], "accuracy": best[3]}

    out = ROOT / "reports" / f"decision_rules_{args.task}_{args.split}.json"
    out.write_text(json.dumps({"task": args.task, "split": args.split, "n": int(len(y)),
                               "classes": classes, "prior": prior.tolist(),
                               "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果: {out}")
    print("\n结论：保育场景应**优先保召回**（漏报白化珊瑚的代价远大于误报），")
    print("      建议采用 C 方案的白化类阈值提升，并在报告中同时给出召回/精确率。")


if __name__ == "__main__":
    main()
