"""
测试时增强（TTA）对比评估
================================================================
对比 无TTA / 水平翻转TTA / 四视图TTA 在测试集上的表现，
给出 Top-1、宏F1 与选择性预测曲线，结果写入 reports/<task>/tta_eval.json

用法：
    python eval_tta.py --task species
    python eval_tta.py --task bleaching
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train import build_model, macro_f1, selective_report  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def load(task, device):
    ck = torch.load(ROOT / "weights" / task / "best.pt", map_location=device, weights_only=False)
    m = build_model(ck["backbone"], len(ck["classes"])).to(device)
    m.load_state_dict(ck["model"])
    m.eval()
    return m, ck


def make_loader(task, img_size, batch=32, workers=4):
    tf = transforms.Compose([
        transforms.Resize(int(img_size * 1.14)),
        transforms.CenterCrop(img_size),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    ds = datasets.ImageFolder(ROOT / "data" / "processed" / task / "test", transform=tf)
    return DataLoader(ds, batch_size=batch, shuffle=False, num_workers=workers), ds


@torch.no_grad()
def logits_of(model, loader, device, mode):
    """mode: none | hflip | quad（原图+水平翻转+垂直翻转+180°旋转）"""
    out, ys = [], []
    for x, y in loader:
        x = x.to(device)
        with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
            z = model(x).float()
            if mode in ("hflip", "quad"):
                z = z + model(torch.flip(x, dims=[3])).float()
            if mode == "quad":
                z = z + model(torch.flip(x, dims=[2])).float()
                z = z + model(torch.flip(x, dims=[2, 3])).float()
        n = {"none": 1, "hflip": 2, "quad": 4}[mode]
        out.append((z / n).cpu())
        ys.append(y)
    return torch.cat(out), torch.cat(ys)


def score(logits, y, T, n_cls, target=0.999):
    probs = torch.softmax(logits / T, dim=1).numpy()
    yy = y.numpy()
    pred = probs.argmax(1)
    top1 = float((pred == yy).mean())
    conf = np.zeros((n_cls, n_cls), dtype=np.int64)
    for t, p in zip(yy, pred):
        conf[t, p] += 1
    return {"top1": round(top1, 6), "macro_f1": round(macro_f1(conf), 6),
            "selective": selective_report(probs, yy, target)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=["bleaching", "species"])
    ap.add_argument("--modes", default="none,hflip,quad")
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, ck = load(args.task, device)
    classes = ck["classes"]
    img_size = ck.get("img_size", 224)
    loader, ds = make_loader(args.task, img_size)

    # 温度（若已有报告）
    mp = ROOT / "reports" / args.task / "metrics.json"
    T = 1.0
    if mp.exists():
        T = float(json.loads(mp.read_text(encoding="utf-8")).get("temperature", 1.0))

    print(f"任务={args.task}  类别={len(classes)}  输入={img_size}  测试样本={len(ds)}  温度T={T:.4f}")
    print("-" * 62)
    results = {}
    for mode in args.modes.split(","):
        logits, y = logits_of(model, loader, device, mode)
        s = score(logits, y, T, len(classes))
        b = s["selective"]["best_meeting_target"]
        results[mode] = s
        got = (f"覆盖率 {b['coverage']:.1%} @阈值{b['threshold']}"
               if b else "未达标")
        print(f"  {mode:<6} Top-1={s['top1']:.4%}  宏F1={s['macro_f1']:.4f}   "
              f"99.9%需: {got}")

    best = max(results.items(), key=lambda kv: kv[1]["top1"])
    print("-" * 62)
    print(f"最佳模式: {best[0]}  Top-1={best[1]['top1']:.4%}")

    out = ROOT / "reports" / args.task / "tta_eval.json"
    out.write_text(json.dumps({"best_mode": best[0], "temperature": T, "results": results},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入: {out}")


if __name__ == "__main__":
    main()
