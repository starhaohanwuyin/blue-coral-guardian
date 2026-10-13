"""
模型比较的显著性检验（McNemar 检验）
================================================================
问题：
    我们报告过「旧模型在印尼域 85.23%，新模型仅 21.02%」。
    但**差异是否统计显著**？还是小样本波动？

方法：McNemar 检验（配对分类器比较的标准方法）
    在同一测试集上跑两个模型，构造 2×2 列联表：

                    模型B 正确    模型B 错误
        模型A 正确      a             b
        模型A 错误      c             d

    关注的只有 b 与 c（两模型判断不一致的样本）：
      · 小样本用**精确二项检验**：b ~ Binomial(b+c, 0.5)
      · 大样本用连续校正 χ² = (|b-c|-1)² / (b+c)
    再叠加 **cluster bootstrap**（按观察聚类）给出准确率差的置信区间。

用法：
    # 比较两个模型在同一测试集上的表现
    python mcnemar_test.py --model-a bleaching_ip --model-b bleaching_new \
        --data-dir data/processed/bleaching_ip --split test_ip

    # 比较新旧属级模型
    python mcnemar_test.py --model-a species_ip --weights-b weights/species_ip/best.pt ...
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from train import build_model  # noqa: E402

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}
RNG = np.random.default_rng(2026)


def load_model(wpath, device):
    ck = torch.load(wpath, map_location=device, weights_only=False)
    classes = ck["classes"]
    size = ck.get("img_size", 224)
    m = build_model(ck["backbone"], len(classes)).to(device)
    m.load_state_dict(ck["model"]); m.eval()
    mp = ROOT / "reports" / wpath.parent.name / "metrics.json"
    T = float(json.loads(mp.read_text(encoding="utf-8")).get("temperature", 1.0)) if mp.exists() else 1.0
    return m, classes, size, T


def collect(data_dir, split):
    """收集 (路径, 真类名) 列表。"""
    d = data_dir / split
    out = []
    for sub in sorted(d.iterdir()):
        if not sub.is_dir():
            continue
        for f in sub.rglob("*"):
            if f.suffix.lower() in IMG_EXT:
                out.append((f, sub.name.lower()))
    return out


@torch.no_grad()
def predict_all(model, classes, size, T, items, device):
    tf = transforms.Compose([
        transforms.Resize(int(size * 1.14)), transforms.CenterCrop(size), transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
    preds, probs = [], []
    for f, _ in items:
        try:
            x = tf(Image.open(f).convert("RGB")).unsqueeze(0).to(device)
            with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                lg = model(x).float()
            p = F.softmax(lg / T, 1)[0].cpu().numpy()
            preds.append(classes[int(p.argmax())])
            probs.append(p)
        except Exception:
            preds.append(None); probs.append(None)
    return preds, probs


def mcnemar(correct_a, correct_b):
    """返回 McNemar 检验结果（精确二项 + 连续校正 χ²）。"""
    b = int(np.sum(correct_a & ~correct_b))     # A 对 B 错
    c = int(np.sum(~correct_a & correct_b))     # A 错 B 对
    n = b + c
    if n == 0:
        return {"b": 0, "c": 0, "n_discordant": 0, "p_exact": 1.0, "p_chi2": 1.0,
                "note": "两模型判断完全一致，无差异"}
    # 精确二项检验（双侧）
    p_exact = float(sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) * 2 / (2 ** n))
    p_exact = min(p_exact, 1.0)
    chi2 = (abs(b - c) - 1) ** 2 / n
    # χ²(1) 的 p 值：p = erfc(sqrt(chi2/2))
    p_chi2 = float(math.erfc(math.sqrt(max(chi2, 0) / 2)))
    return {"b": b, "c": c, "n_discordant": n,
            "chi2": round(chi2, 4), "p_chi2": round(p_chi2, 6),
            "p_exact": round(p_exact, 6),
            "significant_0.05": bool(p_exact < 0.05),
            "note": "p<0.05 表示两模型差异统计显著"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-a", required=True)
    ap.add_argument("--weights-a", default=None)
    ap.add_argument("--model-b", required=True)
    ap.add_argument("--weights-b", default=None)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir
    wa = Path(args.weights_a) if args.weights_a else (ROOT / "weights" / args.model_a / "best.pt")
    wb = Path(args.weights_b) if args.weights_b else (ROOT / "weights" / args.model_b / "best.pt")
    for w in (wa, wb):
        if not w.exists():
            raise SystemExit(f"找不到权重 {w}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ma, ca, sa, Ta = load_model(wa, device)
    mb, cb, sb, Tb = load_model(wb, device)
    print(f"模型A: {args.model_a}  类别={ca}")
    print(f"模型B: {args.model_b}  类别={cb}\n")

    items = collect(data_dir, args.split)
    print(f"测试集: {data_dir.name}/{args.split}  共 {len(items)} 张")

    # 统一到「白化/非白化」二分类口径（两模型类别数可能不同）
    def to_binary(pred, gt):
        if pred is None:
            return None
        pb = pred.lower() in ("bleached", "bleached.")
        gb = gt.lower() == "bleached"
        return pb == gb

    pa, _ = predict_all(ma, ca, sa, Ta, items, device)
    pb_, _ = predict_all(mb, cb, sb, Tb, items, device)

    ok = [i for i in range(len(items)) if pa[i] is not None and pb_[i] is not None]
    gts = [items[i][1] for i in ok]
    A = np.array([to_binary(pa[i], gts[j]) for j, i in enumerate(ok)])
    B = np.array([to_binary(pb_[i], gts[j]) for j, i in enumerate(ok)])
    obs = np.array([Path(items[i][0]).stem.split("_")[0] for i in ok])

    print(f"\n有效样本: {len(ok)}")
    print(f"模型A 二分类准确率: {A.mean():.4%}")
    print(f"模型B 二分类准确率: {B.mean():.4%}")
    print(f"准确率差 (B-A)   : {(B.mean()-A.mean()):+.4%}")

    res = mcnemar(A, B)
    print("\n" + "=" * 70)
    print("McNemar 检验（配对比较）")
    print("=" * 70)
    print(f"  A对B错 (b)      : {res['b']}")
    print(f"  A错B对 (c)      : {res['c']}")
    print(f"  不一致样本数    : {res['n_discordant']}")
    if res["n_discordant"]:
        print(f"  精确二项 p 值   : {res['p_exact']:.6f}")
        print(f"  χ²(连续校正)    : {res['chi2']:.4f}   p = {res['p_chi2']:.6f}")
        sig = "✅ 显著" if res["significant_0.05"] else "❌ 不显著"
        print(f"  结论(α=0.05)    : {sig}")
        print(f"\n  {res['note']}")

    # cluster bootstrap 准确率差 CI
    groups = {}
    for i, o in enumerate(obs):
        groups.setdefault(o, []).append(i)
    keys = list(groups.keys())
    diffs = []
    for _ in range(2000):
        pick = RNG.integers(0, len(keys), size=len(keys))
        idx = np.concatenate([groups[keys[p]] for p in pick])
        diffs.append(B[idx].mean() - A[idx].mean())
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    print(f"\n  准确率差 (B−A) 的 95% CI（按观察聚类）: [{lo:+.4%}, {hi:+.4%}]")
    print(f"  {'CI 不含 0 → 差异显著' if (lo > 0 or hi < 0) else 'CI 含 0 → 差异不显著'}")

    out = Path(args.out) if args.out else (ROOT / "reports" / f"mcnemar_{args.model_a}_vs_{args.model_b}_{args.split}.json")
    out.write_text(json.dumps({
        "modelA": args.model_a, "modelB": args.model_b, "split": args.split,
        "n": len(ok), "accA": float(A.mean()), "accB": float(B.mean()),
        "accDiff": float(B.mean() - A.mean()),
        "accDiffCi95Cluster": [float(lo), float(hi)],
        "mcnemar": res,
        "note": "二分类口径（bleached vs 非白化）比较；CI 按观察聚类重采样",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果: {out}")


if __name__ == "__main__":
    main()
