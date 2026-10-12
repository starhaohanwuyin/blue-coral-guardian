"""多域联合训练：原始域 + 印太域（Koh Tao）混采，目标「域内不回退 + 跨域提升」。

## 为什么需要
前两轮发现：单纯用 Koh Tao 微调，印太域指标大涨（0.208→0.48），但**原域严重退化**
（Kaggle 白化测试集 bleached 召回 99% → 27%~93%）。根因是**只在新域上继续训练**，
把决策边界整体挪走了。正解是**混域训练**：每个 batch 里既有原始域也有印太域。

## 数据（本机实测可用）
| 域 | 来源 | 规模 | 类别 |
|---|---|---|---|
| 原始域-旧 | `data/processed/bleaching/train` | 1,920 | bleached/dead/healthy |
| 原始域-印太 | `data/processed/bleaching_ip/train` | 2,621 | bleached/dead/healthy |
| 原始域-Kaggle | `competition_data/.../Coral Reef Images/train` | 9,662 | Bleached/Healthy（无 dead）|
| **印太域** | Koh Tao 干季 `clipped` 瓦片 | 12,809 | 由 9 类多标签按优先级映射 |

## 选优（双指标）
`score = 0.5 × 域内验证宏F1（data/processed/bleaching/val） + 0.5 × 印太验证宏F1（Koh Tao test_set 抽样）`
—— 只有两个域都不掉，才算真正可用。两个指标与保存记录都写进报告，便于复核。

用法：
    python finetune_bleaching_multidomain.py --epochs 3 --workers 6
    python finetune_bleaching_multidomain.py --epochs 3 --orig-weight 0.6   # 更偏原始域（更保守）
"""
import argparse
import json
import pathlib
import random
import sys
import time
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

CLASSES = ["bleached", "dead", "healthy"]
CI = {c: i for i, c in enumerate(CLASSES)}
# 复用的 PatchDataset 期望「标签→索引」映射；本项目数据已存整数标签，故用恒等映射
IDX = {i: i for i in range(len(CLASSES))}
CCD = ROOT / "data" / "raw" / "CoralConditionDataset"
ORIG_DIRS = {                       # 原始域三分类目录
    "old": ROOT / "data" / "processed" / "bleaching" / "train",
    "ip": ROOT / "data" / "processed" / "bleaching_ip" / "train",
}
KAGGLE_TRAIN = (ROOT.parent / "competition_data" / "AI4Climate_data" / "Kaggle_coral_images"
                / "Coral Reef Images" / "train")
IN_DOMAIN_VAL = ROOT / "data" / "processed" / "bleaching" / "val"
INIT_W = ROOT / "weights" / "bleaching_all" / "best.pt"
OUT_DIR = ROOT / "weights" / "bleaching_all_multidomain"

# CCD 多标签 → 三分类（优先级 dead > bleached > healthy，与训练口径一致）
CCD_JSON = CCD / "CoralConditionDataset-main" / "code" / "datasets"


def collect():
    """返回 [(路径, 类别索引, 域)]。"""
    items = []
    for dname, d in ORIG_DIRS.items():
        if not d.exists():
            print(f"  ⚠️ 缺少原始域目录 {d}")
            continue
        n = 0
        for c in CLASSES:
            for p in (d / c).glob("*"):
                if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
                    items.append((p, CI[c], "orig"))
                    n += 1
        print(f"  原始域[{dname}] {n} 张")
    if KAGGLE_TRAIN.exists():
        n = 0
        for cdir, cname in (("Bleached", "bleached"), ("Healthy", "healthy")):
            for p in (KAGGLE_TRAIN / cdir).glob("*"):
                if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
                    items.append((p, CI[cname], "orig"))
                    n += 1
        print(f"  原始域[kaggle] {n} 张（无 dead 类）")
    # 印太域：Koh Tao 干季 clipped
    idx = {}
    for p in (CCD / "dry").rglob("*.jpg"):
        idx.setdefault(p.stem, p)
    rows = json.loads((CCD_JSON / "test_set.json").read_text(encoding="utf-8"))
    tr = json.loads((CCD_JSON / "train_set_fully_supervision.json").read_text(encoding="utf-8"))
    n = 0
    for r in tr:
        p = idx.get(str(r.get("tileid", "")))
        if p is None:
            continue
        if int(r.get("3", 0)) == 1:
            c = "dead"
        elif int(r.get("2", 0)) == 1:
            c = "bleached"
        elif int(r.get("1", 0)) == 1:
            c = "healthy"
        else:
            continue
        items.append((p, CI[c], "indo"))
        n += 1
    print(f"  印太域[Koh Tao 干季] {n} 张")
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=8e-5)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--orig-weight", type=float, default=0.5,
                    help="原始域在采样中的占比（0.5 = 两域各半；调大更保守、更不容易回退）")
    ap.add_argument("--max-per-domain", type=int, default=4000,
                    help="每个域每个 epoch 的采样上限（控制耗时）")
    ap.add_argument("--val-limit", type=int, default=1200, help="印太验证集上限")
    ap.add_argument("--init", default="")
    ap.add_argument("--out", default=str(OUT_DIR))
    a = ap.parse_args()

    print("收集数据：")
    items = collect()
    if not items:
        print("❌ 没有可用数据")
        return 2
    by_dom = Counter(d for _, _, d in items)
    print(f"  合计 {len(items)} 张，分布 {dict(by_dom)}")

    import torch
    import torch.nn as nn
    from PIL import Image
    from torch.utils.data import DataLoader, WeightedRandomSampler
    from torchvision import transforms
    from train import build_model

    init_w = pathlib.Path(a.init) if a.init else INIT_W
    if not init_w.is_absolute():
        init_w = ROOT / init_w
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(init_w, map_location="cpu", weights_only=False)
    classes = [str(c).lower() for c in ck["classes"]]
    assert classes == CLASSES, f"权重类别顺序为 {classes}，本脚本假定 {CLASSES}"
    sz = ck.get("img_size", 224)
    model = build_model(ck["backbone"], len(classes)).to(device)
    model.load_state_dict(ck["model"])
    print(f"初始化自 {init_w.name}  骨干={ck['backbone']}  设备={device.type}  输入={sz}px")

    tf_tr = transforms.Compose([
        transforms.Resize(int(sz * 1.2)), transforms.RandomCrop(sz),
        transforms.RandomHorizontalFlip(), transforms.RandomVerticalFlip(),
        transforms.ColorJitter(0.2, 0.2, 0.2, 0.05),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
    tf_va = transforms.Compose([
        transforms.Resize(int(sz * 1.14)), transforms.CenterCrop(sz),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

    # 采样权重 = 域配额 ÷ (该域出现的类别数 × 该类别数量)
    #   → 每个域的权重之和恰为该域配额；域内各类别均衡。
    weights = [0.0] * len(items)
    for dom, quota in (("orig", a.orig_weight), ("indo", 1.0 - a.orig_weight)):
        sub = [(i, it) for i, it in enumerate(items) if it[2] == dom]
        if not sub:
            continue
        cnt = Counter(it[1] for _, it in sub)
        for i, it in sub:
            weights[i] = quota / (len(cnt) * cnt[it[1]])
    n_per_epoch = min(2 * a.max_per_domain, 8000)
    sampler = WeightedRandomSampler(weights, num_samples=n_per_epoch, replacement=True)
    print(f"采样：每 epoch {n_per_epoch} 张（原始域配额 {a.orig_weight:.0%}，域内类别均衡）")

    from finetune_bleaching_indopacific import PatchDataset  # 复用模块级数据集类（可 pickle）

    # ⚠️ 复用的 PatchDataset 要求 items 是 2 元组 (路径, 标签)；
    #    域信息只用于上面的采样权重，不能塞进 items（塞了会 ValueError: too many values to unpack）
    train_pairs = [(p, c) for p, c, _ in items]
    dl_tr = DataLoader(PatchDataset(train_pairs, tf_tr, IDX), batch_size=a.batch, sampler=sampler,
                       num_workers=a.workers, pin_memory=True, persistent_workers=a.workers > 0)

    # 验证集①：原始域 val（三分类）
    val_orig = []
    for c in CLASSES:
        for p in (IN_DOMAIN_VAL / c).glob("*"):
            if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
                val_orig.append((p, CI[c]))
    # 验证集②：印太域 CCD test_set（抽样）
    idx = {}
    for p in (CCD / "dry").rglob("*.jpg"):
        idx.setdefault(p.stem, p)
    rows = json.loads((CCD_JSON / "test_set.json").read_text(encoding="utf-8"))
    val_ccd = []
    for r in rows:
        p = idx.get(str(r.get("tileid", "")))
        if p is None:
            continue
        if int(r.get("3", 0)) == 1:
            c = "dead"
        elif int(r.get("2", 0)) == 1:
            c = "bleached"
        elif int(r.get("1", 0)) == 1:
            c = "healthy"
        else:
            continue
        val_ccd.append((p, CI[c]))
    random.Random(0).shuffle(val_ccd)
    val_ccd = val_ccd[: a.val_limit]
    print(f"验证：原始域 {len(val_orig)} 张 / 印太域 {len(val_ccd)} 张")
    dl_vo = DataLoader(PatchDataset(val_orig, tf_va, IDX), batch_size=a.batch, shuffle=False,
                       num_workers=a.workers, pin_memory=True)
    dl_vc = DataLoader(PatchDataset(val_ccd, tf_va, IDX), batch_size=a.batch, shuffle=False,
                       num_workers=a.workers, pin_memory=True)

    def macro_f1(dl):
        model.eval()
        tp, fp, fn = Counter(), Counter(), Counter()
        with torch.no_grad():
            for x, y in dl:
                x, y = x.to(device), y.to(device)
                pred = model(x).argmax(dim=1)
                for t, q in zip(y.tolist(), pred.tolist()):
                    if t == q:
                        tp[t] += 1
                    else:
                        fp[q] += 1
                        fn[t] += 1
        f1s = {}
        for c, i in CI.items():
            prec = tp[i] / (tp[i] + fp[i]) if tp[i] + fp[i] else 0.0
            rec = tp[i] / (tp[i] + fn[i]) if tp[i] + fn[i] else 0.0
            f1s[c] = (2 * prec * rec / (prec + rec)) if prec + rec else 0.0
        return sum(f1s.values()) / 3, f1s

    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
    lossf = nn.CrossEntropyLoss()
    out_dir = pathlib.Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_p = ROOT / "reports" / f"finetune_{out_dir.name}.json"

    # 初始状态（作为"未训练"基线）
    m0_o, f0_o = macro_f1(dl_vo)
    m0_c, f0_c = macro_f1(dl_vc)
    print(f"起始：域内宏F1={m0_o:.4f} {f0_o}  印太宏F1={m0_c:.4f} {f0_c}  综合={0.5*(m0_o+m0_c):.4f}")
    history = [{"epoch": 0, "inDomainMacroF1": round(m0_o, 4), "indoMacroF1": round(m0_c, 4),
                "combined": round(0.5 * (m0_o + m0_c), 4),
                "inDomainF1": {k: round(v, 4) for k, v in f0_o.items()},
                "indoF1": {k: round(v, 4) for k, v in f0_c.items()}}]
    best = 0.5 * (m0_o + m0_c)
    torch.save({"model": model.state_dict(), "backbone": ck["backbone"], "classes": classes,
                "img_size": sz, "note": "多域联合训练（原始域+印太域）初始状态=部署权重"},
               out_dir / "best.pt")

    for ep in range(1, a.epochs + 1):
        model.train()
        t0, run = time.time(), 0.0
        for x, y in dl_tr:
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            loss = lossf(model(x), y)
            loss.backward()
            opt.step()
            run += loss.item() * x.size(0)
        mo, fo = macro_f1(dl_vo)
        mc, fc = macro_f1(dl_vc)
        comb = 0.5 * (mo + mc)
        history.append({"epoch": ep, "trainLoss": round(run / max(n_per_epoch, 1), 4),
                        "inDomainMacroF1": round(mo, 4), "indoMacroF1": round(mc, 4),
                        "combined": round(comb, 4),
                        "inDomainF1": {k: round(v, 4) for k, v in fo.items()},
                        "indoF1": {k: round(v, 4) for k, v in fc.items()}})
        print(f"  epoch {ep}/{a.epochs}  loss={run/max(n_per_epoch,1):.4f}  "
              f"域内={mo:.4f}{{bleached {fo['bleached']:.3f}}}  印太={mc:.4f}{{bleached {fc['bleached']:.3f}}}  "
              f"综合={comb:.4f}  ({time.time()-t0:.0f}s)")
        if comb > best:
            best = comb
            torch.save({"model": model.state_dict(), "backbone": ck["backbone"], "classes": classes,
                        "img_size": sz,
                        "note": "多域联合训练（原始域+印太域混采）；以综合指标选优"},
                       out_dir / "best.pt")
            print(f"    ↑ 保存新最优（综合 {comb:.4f}）→ {out_dir / 'best.pt'}")

    def rel_or_abs(p):
        """仓库内给相对路径，仓库外（如 --out 指向临时目录）给绝对路径。"""
        try:
            return str(pathlib.Path(p).relative_to(ROOT))
        except ValueError:
            return str(p)

    report_p.write_text(json.dumps({
        "task": "多域联合训练（原始域 + 印太域）—— 目标是域内不回退且跨域提升",
        "init": str(init_w), "out": str(out_dir), "classes": classes,
        "args": vars(a), "dataCounts": {k: len([1 for _, _, d in items if d == k])
                                        for k in ("orig", "indo")},
        "selection": "score = 0.5 × 域内验证宏F1 + 0.5 × 印太验证宏F1",
        "history": history, "bestCombined": round(best, 4),
        "next": [f"python scripts/eval_bleaching_indopacific.py --source external "
                 f"--weights {rel_or_abs(out_dir)}/best.pt --out reports/matrix_external_multidomain.json",
                 f"python scripts/eval_bleaching_indopacific.py --source winter "
                 f"--weights {rel_or_abs(out_dir)}/best.pt --out reports/matrix_winter_multidomain.json",
                 "python scripts/eval_new_bleaching.py --task bleaching_all --split test "
                 f"--weights {rel_or_abs(out_dir)}/best.pt   # 域内不回退检查"],
        "caveats": [
            "原始域与印太域混采，不能保证两域都最优；以综合指标选优",
            "印太域只有泰国 Koh Tao 一个海域",
            "原始域含历史项目的三分类数据与 Kaggle 二分类数据（无 dead）",
        ],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n最优综合={best:.4f}；报告 {report_p}")
    for line in report_p and json.loads(report_p.read_text(encoding="utf-8"))["next"]:
        print(f"  下一步: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
