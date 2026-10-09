"""
完整评估协议（E9）
================================================================
产出可直接写进报告的统计指标，而不只是一个裸准确率：

  1. Top-1 准确率 + **Bootstrap 95% 置信区间**（默认 2000 次重采样）
  2. 宏平均 F1 + 置信区间
  3. 每类指标（精确率/召回率/F1/样本量）及其置信区间
  4. **ECE 校准误差**（Expected Calibration Error）+ 可靠性曲线数据
  5. **覆盖率–准确率曲线**（选择性预测），并给出固定覆盖率下的准确率
  6. 混淆矩阵 + Top 混淆类对
  7. 稳定的「高置信区间准确率」报告口径

统一口径说明（避免误读）：
  · 报告主指标 = 全部样本 Top-1（附 CI）
  · 报告工程指标 = 覆盖率 90% 时的准确率（附覆盖率）
  · 不再单吹「99.9%」——那通常对应极低覆盖率，工程上不可用

用法：
    python evaluate_protocol.py --task species_ip
    python evaluate_protocol.py --task bleaching_ip --data-dir data/processed/bleaching_ip
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
from train import build_model, macro_f1  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
N_BOOT = 2000
RNG = np.random.default_rng(2026)


# ---------------------------------------------------------------- 指标
def bootstrap_ci(correct: np.ndarray, n_boot=N_BOOT, alpha=0.05, clusters=None):
    """对 0/1 正确性向量做 bootstrap，返回 (mean, lo, hi)。

    ⚠️ 若提供 clusters（如 observation id），改用 **cluster bootstrap**：
       按「簇」重采样而非按「样本」重采样。
       原因：同一观察的多张照片高度相关（同潜点、同时刻），
       按样本重采样会**低估方差 → 置信区间过窄 → 虚高精度**。
    """
    n = len(correct)
    if n == 0:
        return 0.0, 0.0, 0.0
    mean = float(correct.mean())
    if clusters is None:
        idx = RNG.integers(0, n, size=(n_boot, n))
        accs = correct[idx].mean(axis=1)
        return (mean, float(np.percentile(accs, 100 * alpha / 2)),
                float(np.percentile(accs, 100 * (1 - alpha / 2))))

    # --- cluster bootstrap ---
    groups = {}
    for i, c in enumerate(np.asarray(clusters)):
        groups.setdefault(c, []).append(i)
    keys = list(groups.keys())
    vals = [correct[groups[k]] for k in keys]
    n_cl = len(keys)
    if n_cl < 2:
        return mean, mean, mean
    accs = np.empty(n_boot)
    for b in range(n_boot):
        pick = RNG.integers(0, n_cl, size=n_cl)
        cat = np.concatenate([vals[p] for p in pick])
        accs[b] = cat.mean()
    return (mean, float(np.percentile(accs, 100 * alpha / 2)),
            float(np.percentile(accs, 100 * (1 - alpha / 2))))


def macro_f1_ci(y_true, y_pred, n_cls, n_boot=500, alpha=0.05):
    def mf1(yt, yp):
        conf = np.zeros((n_cls, n_cls), dtype=np.int64)
        for t, p in zip(yt, yp):
            conf[t, p] += 1
        return macro_f1(conf)

    base = mf1(y_true, y_pred)
    n = len(y_true)
    vals = []
    for _ in range(n_boot):
        idx = RNG.integers(0, n, size=n)
        vals.append(mf1(y_true[idx], y_pred[idx]))
    return base, float(np.percentile(vals, 100 * alpha / 2)), float(np.percentile(vals, 100 * (1 - alpha / 2)))


def expected_calibration_error(probs, y_true, n_bins=15):
    """ECE：按置信度分箱，比较平均置信度与真实准确率。"""
    conf = probs.max(axis=1)
    pred = probs.argmax(axis=1)
    correct = (pred == y_true).astype(np.float64)
    bins = np.linspace(0, 1, n_bins + 1)
    ece, details = 0.0, []
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        m = (conf > lo) & (conf <= hi) if i > 0 else (conf >= lo) & (conf <= hi)
        if m.sum() == 0:
            continue
        avg_conf = float(conf[m].mean())
        acc = float(correct[m].mean())
        w = float(m.mean())
        ece += w * abs(avg_conf - acc)
        details.append({"bin": f"{lo:.2f}-{hi:.2f}", "n": int(m.sum()),
                        "avgConf": round(avg_conf, 4), "acc": round(acc, 4),
                        "gap": round(avg_conf - acc, 4)})
    return float(ece), details


def coverage_curve(probs, y_true, targets=(0.99, 0.995, 0.999), coverages=(0.5, 0.7, 0.8, 0.9, 0.95, 1.0)):
    conf = probs.max(axis=1)
    pred = probs.argmax(axis=1)
    correct = (pred == y_true)
    order = np.argsort(-conf)
    cs, cs_correct = conf[order], correct[order]
    n = len(y_true)

    by_cov = []
    for cov in coverages:
        k = max(1, int(round(n * cov)))
        by_cov.append({"coverage": round(k / n, 4),
                       "threshold": round(float(cs[k - 1]), 4),
                       "accuracy": round(float(cs_correct[:k].mean()), 6),
                       "ci": [round(v, 6) for v in bootstrap_ci(cs_correct[:k].astype(np.float64))]})

    by_target = []
    cum = np.cumsum(cs_correct) / np.arange(1, n + 1)
    for t in targets:
        ok = np.where(cum >= t)[0]
        if len(ok):
            i = int(ok.max())
            by_target.append({"target": t, "coverage": round((i + 1) / n, 4),
                              "threshold": round(float(cs[i]), 4),
                              "accuracy": round(float(cum[i]), 6)})
        else:
            by_target.append({"target": t, "coverage": 0.0, "threshold": 1.0,
                              "accuracy": None, "note": "全置信度区间均未达标"})
    return {"byCoverage": by_cov, "byTarget": by_target}


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--split", default="test", help="test / test_ip / val")
    ap.add_argument("--weights", default=None)
    ap.add_argument("--out-tag", default=None)
    ap.add_argument("--exclude-phash", action="store_true",
                    help="剔除与训练集近似重复（pHash）的样本后评估——防止数据泄漏虚高指标")
    ap.add_argument("--phash-file", default=None,
                    help="pHash 审计结果文件（默认 reports/phash_audit.json）")
    args = ap.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else (ROOT / "data" / "processed" / args.task)
    if not data_dir.is_absolute():
        data_dir = (ROOT / data_dir).resolve()
    wpath = Path(args.weights) if args.weights else (ROOT / "weights" / args.task / "best.pt")
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
    T = 1.0
    if mp.exists():
        T = float(json.loads(mp.read_text(encoding="utf-8")).get("temperature", 1.0))

    tf = transforms.Compose([
        transforms.Resize(int(size * 1.14)), transforms.CenterCrop(size),
        transforms.ToTensor(), transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
    split_dir = data_dir / args.split
    if not split_dir.exists():
        raise SystemExit(f"找不到 {split_dir}")
    ds = datasets.ImageFolder(split_dir, transform=tf)
    all_classes = list(ds.classes)          # Subset 不带 classes，需先保存

    # ---- 可选：剔除与其它 split 近似重复的样本（防数据泄漏）----
    excluded = []
    if args.exclude_phash:
        ap_ = Path(args.phash_file) if args.phash_file else (ROOT / "reports" / "phash_audit.json")
        if not ap_.is_absolute():
            ap_ = ROOT / ap_
        if not ap_.exists():
            raise SystemExit(f"缺少 {ap_}，请先运行 phash_audit.py")
        pairs = json.loads(ap_.read_text(encoding="utf-8")).get("pairs", [])
        bad = set()
        # 该 split 的目录名（用于匹配审计结果里的 "train/xxx.jpg" 前缀）
        split_key = split_dir.name
        for pr in pairs:
            a, b = pr["a"], pr["b"]
            if a.startswith(split_key + "/"):
                bad.add(a.split("/", 1)[1])
            if b.startswith(split_key + "/"):
                bad.add(b.split("/", 1)[1])
        # 只在「与该 split 之外的其它 split 重复」时才剔除
        if bad:
            keep = [i for i, (p, _) in enumerate(ds.samples) if Path(p).name not in bad]
            excluded = [Path(p).name for p, _ in ds.samples if Path(p).name in bad]
            ds = torch.utils.data.Subset(ds, keep)
            print(f"⚠ 已剔除 {len(excluded)} 张与其它 split 近似重复的图片（pHash 泄漏）")
        else:
            print("pHash 检查：本 split 无跨集重复")

    missing = [c for c in all_classes if c not in classes]
    if missing:
        raise SystemExit(f"{args.split} 含模型未知类别: {missing}")
    remap = np.array([classes.index(c) for c in all_classes])
    print(f"[{args.task}/{args.split}] 样本 {len(ds)}  类别 {len(all_classes)}  温度 T={T:.4f}")
    print(f"  类别映射: {dict(zip(all_classes, remap.tolist()))}")

    loader = DataLoader(ds, batch_size=32, shuffle=False, num_workers=4, pin_memory=True)
    probs_all, y_all = [], []
    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                logits = model(x).float()
            probs_all.append(F.softmax(logits / T, dim=1).cpu().numpy())
            y_all.append(remap[y.numpy()])
    probs = np.concatenate(probs_all)
    y_true = np.concatenate(y_all)

    # ---- 观察 ID（用于 cluster bootstrap）----
    # 文件名格式 <obsId>_<hash>.<ext>；无该格式则退回「按文件聚类」
    files_all = [Path(p).name for p, _ in (ds.dataset.samples if isinstance(ds, torch.utils.data.Subset)
                                            else ds.samples)]
    if isinstance(ds, torch.utils.data.Subset):
        files_all = [files_all[i] for i in ds.indices]
    obs_ids = []
    for fname in files_all:
        stem = Path(fname).stem
        obs_ids.append(stem.split("_")[0] if "_" in stem else stem)
    obs_ids = np.array(obs_ids)
    n_clusters = len(set(obs_ids.tolist()))
    pred = probs.argmax(1)

    # ---- 1/2 Top-1 与宏F1（含 CI）----
    # 同时给出「按样本」与「按观察聚类」两种 CI，后者更保守也更诚实
    correct_vec = (pred == y_true).astype(np.float64)
    acc, lo, hi = bootstrap_ci(correct_vec)
    _, clo, chi = bootstrap_ci(correct_vec, clusters=obs_ids)
    mf1, mlo, mhi = macro_f1_ci(y_true, pred, len(classes))

    # ---- 3 每类 ----
    n_cls = len(classes)
    conf = np.zeros((n_cls, n_cls), dtype=np.int64)
    for t, p in zip(y_true, pred):
        conf[t, p] += 1
    per_class = {}
    for i, c in enumerate(classes):
        tp = conf[i, i]; fp = conf[:, i].sum() - tp; fn = conf[i].sum() - tp
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        m = (y_true == i)
        a, alo, ahi = bootstrap_ci((pred[m] == i).astype(np.float64)) if m.sum() else (0, 0, 0)
        per_class[c] = {"n": int(conf[i].sum()), "precision": round(p, 4), "recall": round(r, 4),
                        "f1": round(f1, 4), "acc": round(a, 4),
                        "accCi": [round(alo, 4), round(ahi, 4)]}

    # ---- 4 ECE ----
    ece, bins = expected_calibration_error(probs, y_true)

    # ---- 5 覆盖率曲线 ----
    cov = coverage_curve(probs, y_true)

    # ---- 6 混淆 ----
    off = conf.copy(); np.fill_diagonal(off, 0)
    pairs = sorted(((int(off[i, j]), classes[i], classes[j])
                    for i in range(n_cls) for j in range(n_cls) if off[i, j] > 0), reverse=True)

    # ---- 输出 ----
    print("=" * 66)
    print(f"Top-1 准确率 : {acc:.4%}")
    print(f"  · 按样本 bootstrap : [95% CI {lo:.4%} – {hi:.4%}]  (宽 {(hi-lo)*100:.2f}pt)")
    print(f"  · 按观察 cluster   : [95% CI {clo:.4%} – {chi:.4%}]  (宽 {(chi-clo)*100:.2f}pt)"
          f"   ← 更保守，建议以此为准")
    print(f"    观察簇数: {n_clusters} 个（平均 {len(y_true)/max(n_clusters,1):.2f} 张/观察）")
    if (chi - clo) > (hi - lo) * 1.15:
        print(f"    ⚠️ 聚类 CI 比朴素 CI 宽 {(chi-clo)/max(hi-lo,1e-9):.2f}×，"
              f"说明同观察的多张照片确实相关 → 朴素 CI 偏乐观")
    print(f"宏平均 F1    : {mf1:.4f}   [95% CI {mlo:.4f} – {mhi:.4f}]")
    print(f"ECE 校准误差 : {ece:.4f}   (越小越好，<0.05 为良好)")
    print("-" * 66)
    print("覆盖率–准确率（选择性预测）:")
    for r in cov["byCoverage"]:
        print(f"  覆盖率 {r['coverage']:>6.1%}  阈值 {r['threshold']:.4f}  "
              f"准确率 {r['accuracy']:.4%}  CI[{r['ci'][1]:.2%},{r['ci'][2]:.2%}]")
    print("-" * 66)
    print("达到目标准确率所需条件:")
    for r in cov["byTarget"]:
        if r.get("accuracy") is not None:
            print(f"  准确率 ≥{r['target']:.1%} → 置信度 ≥{r['threshold']}，覆盖率 {r['coverage']:.1%}")
        else:
            print(f"  准确率 ≥{r['target']:.1%} → 不可达")
    print("-" * 66)
    print("最易混淆类对 Top8（真实→预测）:")
    for n_, a, b in pairs[:8]:
        print(f"  {a:<26} → {b:<26} {n_}")
    worst = sorted(per_class.items(), key=lambda kv: kv[1]["recall"])[:6]
    print("-" * 66)
    print("召回率最低的类 Top6:")
    for c, v in worst:
        print(f"  {c:<26} n={v['n']:<4} recall={v['recall']:.3f}  f1={v['f1']:.3f}")

    out = ROOT / "reports" / (args.out_tag or f"protocol_{args.task}_{args.split}.json")
    out.write_text(json.dumps({
        "task": args.task, "split": args.split, "weights": str(wpath), "temperature": T,
        "n_samples": int(len(y_true)), "n_classes": n_cls,
        "nObservationClusters": int(n_clusters),
        "top1": round(acc, 6),
        "top1Ci95": [round(lo, 6), round(hi, 6)],
        "top1Ci95Cluster": [round(clo, 6), round(chi, 6)],
        "macroF1": round(mf1, 6), "macroF1Ci95": [round(mlo, 6), round(mhi, 6)],
        "ece": round(ece, 6), "reliabilityBins": bins,
        "coverageCurve": cov, "perClass": per_class,
        "confusionTop": [{"count": n_, "true": a, "pred": b} for n_, a, b in pairs[:20]],
        "confusionMatrix": conf.tolist(),
        "classOrder": classes,
        "clusterBootstrapNote": "top1Ci95 按样本重采样；top1Ci95Cluster 按观察 id 聚类重采样，更保守",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完整报告: {out}")


if __name__ == "__main__":
    main()
