"""
错误归因分析
================================================================
回答："什么情况下模型会错？"

分析维度：
  1. **类别维度**：哪些属/类错得多？与样本量、类内形态相似度有关吗？
  2. **图像质量维度**：错判样本的对比度/亮度/饱和度是否异常？
  3. **置信度维度**：错误是否集中在低置信区间？（决定拒识阈值是否有效）
  4. **易混淆对**：哪些类互相混淆？是否生物学上相近？
  5. **错误代价**：分类错误 vs 高置信错误（后者更危险）

用法：
    python error_attribution.py --task species_ip --split test \
        --data-dir data/inat_dataset/images
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import datasets, transforms

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from train import build_model  # noqa: E402


def img_stats(p: Path):
    """图像质量统计（用于错误归因）。"""
    try:
        import numpy as np
        a = np.asarray(Image.open(p).convert("RGB")).astype(np.float32) / 255.0
        gray = a @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
        return {"contrast": float(gray.std()), "brightness": float(gray.mean()),
                "saturation": float((a.max(2) - a.min(2)).mean()),
                "rgRatio": float(a[..., 0].mean() / max(a[..., 1].mean(), 1e-6))}
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--weights", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir
    wpath = Path(args.weights) if args.weights else (ROOT / "weights" / args.task / "best.pt")
    ck = torch.load(wpath, map_location="cpu", weights_only=False)
    classes = ck["classes"]
    size = ck.get("img_size", 224)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model(ck["backbone"], len(classes)).to(device)
    model.load_state_dict(ck["model"]); model.eval()
    mp = ROOT / "reports" / args.task / "metrics.json"
    T = float(json.loads(mp.read_text(encoding="utf-8")).get("temperature", 1.0)) if mp.exists() else 1.0

    ds = datasets.ImageFolder(data_dir / args.split)
    missing = [c for c in ds.classes if c not in classes]
    if missing:
        raise SystemExit(f"含未知类别 {missing}")
    remap = [classes.index(c) for c in ds.classes]
    tf = transforms.Compose([
        transforms.Resize(int(size * 1.14)), transforms.CenterCrop(size), transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

    print(f"[{args.task}/{args.split}] {len(ds)} 张  类别 {len(ds.classes)}  T={T:.4f}")
    rows = []
    with torch.no_grad():
        for i, (p, ci) in enumerate(ds.samples):
            try:
                x = tf(Image.open(p).convert("RGB")).unsqueeze(0).to(device)
                with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                    lg = model(x).float()
                prob = F.softmax(lg / T, 1)[0].cpu().numpy()
            except Exception:
                continue
            pred = int(prob.argmax())
            gt = remap[ci]
            st = img_stats(Path(p))
            rows.append({"file": Path(p).name, "gt": classes[gt], "pred": classes[pred],
                         "correct": pred == gt, "conf": float(prob.max()),
                         "pGt": float(prob[gt]), **({"img": st} if st else {})})
    if not rows:
        raise SystemExit("无样本")

    n = len(rows)
    n_err = sum(1 for r in rows if not r["correct"])
    print(f"\n总错误: {n_err}/{n} = {n_err/n:.2%}\n")

    # ---------- 1. 类别维度 ----------
    per_cls = defaultdict(lambda: {"n": 0, "err": 0, "confs": []})
    for r in rows:
        c = per_cls[r["gt"]]
        c["n"] += 1
        c["err"] += (not r["correct"])
        if not r["correct"]:
            c["confs"].append(r["conf"])
    print("=" * 76)
    print("类别维度：错误率最高的类 Top10")
    print("=" * 76)
    print(f"{'类别':<22}{'样本':>6}{'错误':>6}{'错误率':>10}{'错误样本平均置信':>18}")
    print("-" * 76)
    ranked = sorted(per_cls.items(), key=lambda kv: -(kv[1]["err"] / max(kv[1]["n"], 1)))
    for c, v in ranked[:10]:
        avgc = np.mean(v["confs"]) if v["confs"] else 0
        print(f"{c:<22}{v['n']:>6}{v['err']:>6}{v['err']/max(v['n'],1):>10.1%}{avgc:>18.3f}")
    print("-" * 76)

    # 错误率 vs 样本量
    ns = np.array([v["n"] for _, v in ranked])
    es = np.array([v["err"] / max(v["n"], 1) for _, v in ranked])
    if len(ns) > 3 and ns.std() > 0 and es.std() > 0:
        rr = float(np.corrcoef(ns, es)[0, 1])
        print(f"\n  错误率 vs 样本量的相关: r = {rr:+.3f}"
              f"  ({'样本少的类更容易错' if rr < -0.2 else '与样本量关系不明显'})")

    # ---------- 2. 图像质量维度 ----------
    if all("img" in r for r in rows):
        print("\n" + "=" * 76)
        print("图像质量维度：正确 vs 错误样本")
        print("=" * 76)
        print(f"{'指标':<16}{'正确样本均值':>14}{'错误样本均值':>14}{'差异':>12}")
        print("-" * 76)
        for k, cn in (("contrast", "对比度"), ("brightness", "亮度"),
                      ("saturation", "饱和度"), ("rgRatio", "R/G 比")):
            ok = np.mean([r["img"][k] for r in rows if r["correct"]])
            er = np.mean([r["img"][k] for r in rows if not r["correct"]])
            print(f"{cn:<16}{ok:>14.4f}{er:>14.4f}{er-ok:>+12.4f}")
        print("-" * 76)

    # ---------- 3. 置信度维度 ----------
    print("\n" + "=" * 76)
    print("置信度维度：错误是否集中在低置信区？")
    print("=" * 76)
    bins = [(0, .3), (.3, .5), (.5, .7), (.7, .9), (.9, 1.01)]
    print(f"{'置信度区间':<14}{'样本数':>8}{'错误数':>8}{'错误率':>10}")
    print("-" * 76)
    for lo, hi in bins:
        g = [r for r in rows if lo <= r["conf"] < hi]
        if not g:
            continue
        e = sum(1 for r in g if not r["correct"])
        print(f"{f'[{lo:.1f},{hi:.1f})':<14}{len(g):>8}{e:>8}{e/len(g):>10.1%}")
    print("-" * 76)

    # 高置信错误（最危险）
    hc_err = [r for r in rows if not r["correct"] and r["conf"] >= 0.9]
    print(f"\n  ⚠️ 高置信错误（conf ≥ 0.9 但判错）: {len(hc_err)} 个"
          f"（占全部错误 {len(hc_err)/max(n_err,1):.1%}）")
    for r in sorted(hc_err, key=lambda x: -x["conf"])[:5]:
        print(f"     {r['gt']:<20} → {r['pred']:<20} conf={r['conf']:.3f}")

    # ---------- 4. 易混淆对 ----------
    print("\n" + "=" * 76)
    print("易混淆对 Top10（真实 → 预测）")
    print("=" * 76)
    pairs = Counter((r["gt"], r["pred"]) for r in rows if not r["correct"])
    for (a, b), c in pairs.most_common(10):
        print(f"  {a:<22} → {b:<22} {c:>4} 次")

    # ---------- 5. 拒识策略效果 ----------
    print("\n" + "=" * 76)
    print("拒识策略效果（若低置信样本交人工）")
    print("=" * 76)
    print(f"{'置信度阈值':<12}{'自动化率':>10}{'自动部分准确率':>16}{'拦截的错误占比':>16}")
    print("-" * 76)
    for th in (0.0, 0.5, 0.7, 0.8, 0.9, 0.95):
        keep = [r for r in rows if r["conf"] >= th]
        if not keep:
            continue
        kc = sum(1 for r in keep if r["correct"])
        caught = sum(1 for r in rows if not r["correct"] and r["conf"] < th)
        print(f"{th:<12.2f}{len(keep)/n:>10.1%}{kc/len(keep):>16.2%}"
              f"{caught/max(n_err,1):>16.1%}")
    print("-" * 76)

    out = Path(args.out) if args.out else (ROOT / "reports" / f"error_attribution_{args.task}_{args.split}.json")
    out.write_text(json.dumps({
        "task": args.task, "split": args.split, "n": n, "nError": n_err,
        "errorRate": n_err / n,
        "perClassError": {c: {"n": v["n"], "err": v["err"],
                              "rate": v["err"] / max(v["n"], 1)}
                          for c, v in per_cls.items()},
        "topConfusions": [{"true": a, "pred": b, "count": c} for (a, b), c in pairs.most_common(20)],
        "highConfidenceErrors": len(hc_err),
        "rejectionCurve": [{"threshold": th,
                            "automation": (sum(1 for r in rows if r["conf"] >= th) / n),
                            "autoAccuracy": (sum(1 for r in rows if r["conf"] >= th and r["correct"])
                                             / max(sum(1 for r in rows if r["conf"] >= th), 1))}
                           for th in (0.0, 0.5, 0.7, 0.8, 0.9, 0.95)],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果: {out}")


if __name__ == "__main__":
    main()
