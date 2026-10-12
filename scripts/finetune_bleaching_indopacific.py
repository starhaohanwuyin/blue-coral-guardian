"""用印太域数据（泰国 Koh Tao）微调白化三分类模型 —— 针对"印太域不可用"这一最大短板。

背景：`eval_bleaching_indopacific.py` 实测我们的 `bleaching_all` 在 Arafura/Darwin（印太）
外部测试集上**宏平均 F1 仅 0.322**，且几乎从不判"死亡"（dead 召回 0.004）。
本脚本用同一个数据集的"训练侧"数据（Koh Tao 干季）做域自适应微调，
把 Arafura/Darwin **留作 held-out 测试**（这是数据集原始设计，不构成泄漏）。

做法：
  1. 标签映射：CCD 9 类多标签 → 本项目三类单标签，按**优先级 dead > bleached > healthy**
     （与线上模型的三分类 softmax 头一致，便于复用同一套推理代码）
  2. 初始化：`weights/bleaching_all/best.pt`（不覆盖它）→ 输出到 `weights/bleaching_all_koh_tao/`
  3. 类别不均衡：按类别频率做 WeightedRandomSampler
  4. 早停/选优：以 CCD 测试集（test_set.json）三类宏平均 F1 为准
  5. 训练后请用 eval_bleaching_indopacific.py --weights <新权重> 看跨域是否真的改善

用法：
    python finetune_bleaching_indopacific.py --epochs 6
    python finetune_bleaching_indopacific.py --epochs 6 --freeze-backbone   # 只训分类头（更快）
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

CCD = ROOT / "data" / "raw" / "CoralConditionDataset"
LABELS = CCD / "CoralConditionDataset-main" / "code" / "datasets"
DRY_IMGS = CCD / "dry"                       # 干季图像（coral_images_dry.zip 解压后）
INIT_W = ROOT / "weights" / "bleaching_all" / "best.pt"
OUT_DIR = ROOT / "weights" / "bleaching_all_koh_tao"
REPORT = ROOT / "reports" / "finetune_indopacific.json"

# CCD 类别号 → 本项目三类（优先级从高到低）
PRIORITY = [(3, "dead"), (2, "bleached"), (1, "healthy")]


class PatchDataset:
    """瓦片数据集。

    ⚠️ 必须在**模块级**定义：Windows 下 DataLoader 的 `num_workers>0` 需要能 pickle 数据集类，
    定义在函数内部的类无法 pickle（会报 can't pickle / AttributeError）。本脚本已踩过。
    """

    def __init__(self, items, tf, classes_index):
        self.items, self.tf, self.ci = items, tf, classes_index

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        from PIL import Image
        p, y = self.items[i]
        return self.tf(Image.open(p).convert("RGB")), self.ci[y]


def map_label(row):
    for k, name in PRIORITY:
        if int(row.get(str(k), 0)) == 1:
            return name
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--freeze-backbone", action="store_true", help="只训分类头（更快，适合小数据）")
    ap.add_argument("--limit", type=int, default=0, help="训练集只用前 N 张（冒烟/加速）")
    ap.add_argument("--val-limit", type=int, default=1500, help="验证集上限（每轮都要评，控制耗时）")
    ap.add_argument("--workers", type=int, default=8, help="DataLoader 进程数（解码是瓶颈，别用 0）")
    ap.add_argument("--out", default=str(OUT_DIR))
    a = ap.parse_args()

    if not INIT_W.exists():
        print(f"❌ 缺少初始化权重 {INIT_W}")
        return 2
    train_json, test_json = LABELS / "train_set_fully_supervision.json", LABELS / "test_set.json"
    if not (train_json.exists() and test_json.exists()):
        print(f"❌ 缺少标签文件（{train_json.name} / {test_json.name}）")
        return 2
    if not DRY_IMGS.exists():
        print(f"❌ 缺少干季图像目录 {DRY_IMGS}\n   先下载并解压 coral_images_dry.zip 到该路径")
        return 3

    idx = {}
    for p in DRY_IMGS.rglob("*"):
        if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
            idx.setdefault(p.stem, p)
    if not idx:
        print(f"❌ {DRY_IMGS} 下没有图像")
        return 3
    print(f"干季图像索引：{len(idx)} 张")

    def build(rows, name):
        items, skipped = [], 0
        for r in rows:
            y = map_label(r)
            p = idx.get(str(r.get("tileid", "")))
            if y is None or p is None:
                skipped += 1
                continue
            items.append((p, y))
        c = Counter(y for _, y in items)
        print(f"{name}: 可用 {len(items)} 张（跳过 {skipped}）  类别分布 {dict(c)}")
        return items

    train = build(json.loads(train_json.read_text(encoding="utf-8")), "训练集")
    val = build(json.loads(test_json.read_text(encoding="utf-8")), "验证集")
    if a.limit:
        train = train[: a.limit]
    if a.val_limit and len(val) > a.val_limit:
        random.Random(0).shuffle(val)          # 固定种子，保证跨次可比
        val = val[: a.val_limit]
    print(f"实际使用：训练 {len(train)} 张 / 验证 {len(val)} 张（workers={a.workers}）")
    if len(train) < 100 or len(val) < 50:
        print("❌ 可用样本太少（图像是否解压完整？）")
        return 3

    import torch
    import torch.nn as nn
    from PIL import Image
    from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
    from torchvision import transforms
    from train import build_model  # 与官方同一套构建路径

    classes = ["bleached", "dead", "healthy"]      # 与线上 bleaching_all 的顺序保持一致
    ci = {c: i for i, c in enumerate(classes)}

    ck = torch.load(INIT_W, map_location="cpu", weights_only=False)
    if [str(c).lower() for c in ck["classes"]] != classes:
        classes = [str(c).lower() for c in ck["classes"]]
        ci = {c: i for i, c in enumerate(classes)}
        print(f"⚠️ 按权重里的类别顺序调整：{classes}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model(ck["backbone"], len(classes)).to(device)
    model.load_state_dict(ck["model"])
    print(f"初始化自 {INIT_W.name}  骨干={ck['backbone']}  设备={device.type}")
    if a.freeze_backbone:
        for n, p in model.named_parameters():
            if not n.startswith("classifier") and not n.startswith("head"):
                p.requires_grad = False
        print("  （只训练分类头）")

    sz = ck.get("img_size", 224)
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

    counts = Counter(y for _, y in train)
    w = [1.0 / counts[y] for _, y in train]
    sampler = WeightedRandomSampler(w, num_samples=len(train), replacement=True)
    dl_tr = DataLoader(PatchDataset(train, tf_tr, ci), batch_size=a.batch, sampler=sampler,
                       num_workers=a.workers, pin_memory=True, persistent_workers=a.workers > 0)
    dl_va = DataLoader(PatchDataset(val, tf_va, ci), batch_size=a.batch, shuffle=False,
                       num_workers=a.workers, pin_memory=True, persistent_workers=a.workers > 0)

    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=1e-4)
    lossf = nn.CrossEntropyLoss()

    def evaluate():
        model.eval()
        tp = Counter(); fp = Counter(); fn = Counter()
        with torch.no_grad():
            for x, y in dl_va:
                x, y = x.to(device), y.to(device)
                pred = model(x).argmax(dim=1)
                for t, q in zip(y.tolist(), pred.tolist()):
                    if t == q:
                        tp[t] += 1
                    else:
                        fp[q] += 1
                        fn[t] += 1
        f1s = {}
        for c, i in ci.items():
            prec = tp[i] / (tp[i] + fp[i]) if tp[i] + fp[i] else 0.0
            rec = tp[i] / (tp[i] + fn[i]) if tp[i] + fn[i] else 0.0
            f1s[c] = (2 * prec * rec / (prec + rec)) if prec + rec else 0.0
        return f1s, sum(f1s.values()) / max(len(f1s), 1)

    out_dir = pathlib.Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    best_macro, history = -1.0, []
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
        f1s, macro = evaluate()
        history.append({"epoch": ep, "trainLoss": round(run / len(train), 4),
                        "valMacroF1": round(macro, 4),
                        "valF1": {k: round(v, 4) for k, v in f1s.items()}})
        print(f"  epoch {ep}/{a.epochs}  loss={run/len(train):.4f}  val宏F1={macro:.4f}  "
              f"{ {k: round(v,3) for k, v in f1s.items()} }  ({time.time()-t0:.0f}s)")
        if macro > best_macro:
            best_macro = macro
            torch.save({"model": model.state_dict(), "backbone": ck["backbone"],
                        "classes": classes, "img_size": sz,
                        "note": "在泰国 Koh Tao 干季数据上域自适应微调（Arafura/Darwin 未参与训练）"},
                       out_dir / "best.pt")
            print(f"    ↑ 保存新最优 → {out_dir / 'best.pt'}")

    def rel_or_abs(p):
        """仓库内给相对路径（便于写文档），仓库外给绝对路径（--out 可能指向临时目录）。"""
        try:
            return str(pathlib.Path(p).relative_to(ROOT))
        except ValueError:
            return str(p)

    report = {
        "task": "印太域（Koh Tao）域自适应微调 —— 针对跨域白化识别不可用",
        "init": rel_or_abs(INIT_W), "out": rel_or_abs(out_dir),
        "classes": classes, "args": vars(a),
        "data": {"train": len(train), "val": len(val),
                 "trainClassCounts": dict(counts), "dryImagesIndexed": len(idx)},
        "labelMapping": "CCD 9 类多标签 → 三类单标签，优先级 dead > bleached > healthy",
        "history": history, "bestValMacroF1": round(best_macro, 4),
        "next": ("python eval_bleaching_indopacific.py --source external --weights "
                 f"{rel_or_abs(out_dir)}/best.pt"),
        "caveats": [
            "训练数据只有 Koh Tao 一个海域（泰国湾），不等于整个印太域都能泛化",
            "标签映射是近似的：Compromised ≈ 白化（含非白化损伤）",
            "Arafura/Darwin（external 包）全程未参与训练，作为 held-out 跨域测试",
            "线上权重 weights/bleaching_all 未被覆盖；本产物是独立实验权重",
        ],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n最优验证宏F1 = {best_macro:.4f}；报告写入 {REPORT}")
    print(f"下一步：{report['next']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
