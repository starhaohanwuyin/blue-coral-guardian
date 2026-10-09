"""
跨域评估：新白化模型在旧域 / 印尼域 / 仙本那域上的表现
================================================================
bleaching_new 在它自己的测试集上达到 99.40%（剔除泄漏后），
但那只是**同域**结果。本脚本回答两个关键问题：

  1. 换成旧域（原 Kaggle 白化集）表现如何？
  2. **印尼域（之前的短板，召回仅 42%）有没有改善？**
  3. 仙本那真实照片上表现如何？

模型为二分类（Bleached/Healthy），旧数据为三分类，
评估时把 dead 并入「非白化」处理，并同时给出三分类视角。

用法：
    python eval_cross_domain.py --task bleaching_new
    python eval_cross_domain.py --task bleaching_new --weights weights/bleaching_new/best.pt
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from train import build_model  # noqa: E402

# 待评估的目标域：(名称, 目录, 说明)
TARGETS = [
    ("旧域 test", ROOT / "data/processed/bleaching/test", "原 Kaggle 白化测试集"),
    ("印尼域 test_ip", ROOT / "data/processed/bleaching_ip/test_ip", "印太域，此前召回仅 42%"),
    ("旧域IP test", ROOT / "data/processed/bleaching_ip/test", "bleaching_ip 的测试集"),
    ("仙本那照片", ROOT / "data/semporna_photos", "真实目标域（无白化标注，仅看预测分布）"),
]

IMG_EXT = {".jpg", ".jpeg", ".png"}


def load_model(wpath, device):
    ck = torch.load(wpath, map_location=device, weights_only=False)
    classes = ck["classes"]
    size = ck.get("img_size", 224)
    m = build_model(ck["backbone"], len(classes)).to(device)
    m.load_state_dict(ck["model"])
    m.eval()
    T = 1.0
    mp = wpath.parent.parent.parent / "reports" / wpath.parent.name / "metrics.json"
    if mp.exists():
        T = float(json.loads(mp.read_text(encoding="utf-8")).get("temperature", 1.0))
    return m, classes, size, T, ck["backbone"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="bleaching_new")
    ap.add_argument("--weights", default=None)
    ap.add_argument("--batch", type=int, default=32)
    args = ap.parse_args()

    wpath = Path(args.weights) if args.weights else (ROOT / "weights" / args.task / "best.pt")
    if not wpath.exists():
        raise SystemExit(f"找不到权重 {wpath}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, classes, size, T, backbone = load_model(wpath, device)
    print(f"模型: {args.task}  骨干={backbone}  类别={classes}  T={T:.4f}\n")
    tf = transforms.Compose([
        transforms.Resize(int(size * 1.14)), transforms.CenterCrop(size), transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

    # 白化类在模型输出中的索引
    bi = None
    for cand in ("Bleached", "bleached"):
        if cand in classes:
            bi = classes.index(cand)
            break
    if bi is None:
        raise SystemExit("模型无白化类")

    results = {}
    for name, d, desc in TARGETS:
        if not d.exists():
            print(f"[跳过] {name}: 目录不存在")
            continue
        print("=" * 74)
        print(f"【{name}】{desc}")
        print(f"  目录: {d}")
        print("=" * 74)

        if name == "仙本那照片":
            # 无标注：只看白化概率分布
            files = sorted(f for f in d.rglob("*") if f.suffix.lower() in IMG_EXT)
            ps = []
            for f in files:
                try:
                    x = tf(Image.open(f).convert("RGB")).unsqueeze(0).to(device)
                    with torch.no_grad(), torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                        p = F.softmax(model(x).float() / T, 1)[0].cpu().numpy()
                    ps.append(float(p[bi]))
                except Exception:
                    continue
            if ps:
                ps = np.array(ps)
                print(f"  样本 {len(ps)} 张")
                print(f"  白化概率：均值 {ps.mean():.3f}  中位 {np.median(ps):.3f}  "
                      f"P75 {np.percentile(ps,75):.3f}  P90 {np.percentile(ps,90):.3f}")
                for th in (0.5, 0.7, 0.9):
                    print(f"    判为白化(阈值{th})：{(ps>=th).mean():.1%}")
                results[name] = {"n": len(ps), "meanP": float(ps.mean()),
                                 "medianP": float(np.median(ps)),
                                 "fracAt50": float((ps >= 0.5).mean()),
                                 "fracAt90": float((ps >= 0.9).mean())}
            print()
            continue

        # 有标注：按子目录类别评估
        by_cls = defaultdict(list)
        for sub in sorted(d.iterdir()):
            if not sub.is_dir():
                continue
            for f in sub.rglob("*"):
                if f.suffix.lower() in IMG_EXT:
                    by_cls[sub.name.lower()].append(f)
        if not by_cls:
            print("  未找到类别子目录，跳过\n")
            continue

        n_ble = len(by_cls.get("bleached", []))
        n_hea = len(by_cls.get("healthy", []))
        n_dead = len(by_cls.get("dead", []))
        rows = []
        for cls_name, files in by_cls.items():
            for f in files:
                try:
                    x = tf(Image.open(f).convert("RGB")).unsqueeze(0).to(device)
                    with torch.no_grad(), torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                        p = F.softmax(model(x).float() / T, 1)[0].cpu().numpy()
                    rows.append({"gt": cls_name, "pB": float(p[bi]), "pred": classes[int(p.argmax())]})
                except Exception:
                    continue
        if not rows:
            print("  无有效样本\n"); continue

        # 二分类视角：Bleached vs 非白化
        tb = [r for r in rows if r["gt"] == "bleached"]
        tn = [r for r in rows if r["gt"] != "bleached"]
        rec = (sum(1 for r in tb if r["pB"] >= 0.5) / len(tb)) if tb else 0.0
        prec_den = sum(1 for r in rows if r["pB"] >= 0.5)
        prec = (sum(1 for r in tb if r["pB"] >= 0.5) / prec_den) if prec_den else 0.0
        acc2 = sum(1 for r in rows if (r["gt"] == "bleached") == (r["pB"] >= 0.5)) / len(rows)

        print(f"  样本: 白化 {n_ble} / 健康 {n_hea}" + (f" / 死亡 {n_dead}" if n_dead else ""))
        print(f"  {'白化召回':<14}{rec:>9.2%}   ← 关键")
        print(f"  {'白化精确':<14}{prec:>9.2%}")
        print(f"  {'二分类准确率':<14}{acc2:>9.2%}")
        if n_hea:
            hrec = sum(1 for r in rows if r["gt"] == "healthy" and r["pB"] < 0.5) / n_hea
            print(f"  {'健康召回':<14}{hrec:>9.2%}")
        results[name] = {"n": len(rows), "nBleached": n_ble, "nHealthy": n_hea, "nDead": n_dead,
                         "bleachedRecall": round(rec, 4), "bleachedPrecision": round(prec, 4),
                         "binaryAccuracy": round(acc2, 4)}
        print()

    out = ROOT / "reports" / f"cross_domain_{args.task}.json"
    out.write_text(json.dumps({"model": args.task, "classes": classes,
                               "note": "二分类视角：dead 并入非白化", "targets": results},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print("=" * 74)
    print("汇总")
    print("=" * 74)
    print(f"{'目标域':<20}{'白化召回':>10}{'白化精确':>10}{'二分类准确':>12}")
    print("-" * 74)
    for k, v in results.items():
        if "bleachedRecall" in v:
            print(f"{k:<20}{v['bleachedRecall']:>10.2%}{v['bleachedPrecision']:>10.2%}"
                  f"{v['binaryAccuracy']:>12.2%}")
        else:
            print(f"{k:<20}{'（无标注）':>10}{'':>10}{'均值P=%.3f' % v['meanP']:>12}")
    print(f"\n结果: {out}")


if __name__ == "__main__":
    main()
