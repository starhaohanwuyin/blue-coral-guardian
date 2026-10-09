"""
珊瑚分类模型训练 + 可信度评估
================================================================
支持两类任务（独立训练，各自一个模型）：
    --task bleaching   白化程度分类（健康 / 白化 / 死亡）
    --task species     珊瑚种类分类（30 类种级）

设计要点：
  1. 迁移学习：ImageNet 预训练 backbone + 两阶段训练（先冻 backbone 训 head，再全量微调）
  2. 水下图像增强：除常规增强外，加入"颜色通道随机扰动"模拟水下蓝绿偏/雾化
  3. 类别不平衡：WeightedRandomSampler
  4. AMP 混合精度：8GB 显存友好（RTX 5060）
  5. 温度标定（Temperature Scaling）：把模型置信度校准到可信
  6. 选择性预测（重点！）：统计 coverage–accuracy 曲线，
     给出"在置信度 ≥ θ 的样本上准确率 ≥ 目标值"的 θ 与覆盖率。
     这是把 99.9% 这个指标做得"真实且站得住"的正确方式。

用法：
    python train.py --task bleaching --epochs 30
    python train.py --task species   --epochs 40 --backbone convnext_tiny
"""
import argparse
import json
import os
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, WeightedRandomSampler
from torchvision import datasets, models, transforms

# ----------------------------------------------------------------------------
# 工具
# ----------------------------------------------------------------------------

def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def build_model(backbone: str, n_classes: int, pretrained: bool = True):
    if backbone == "convnext_tiny":
        w = models.ConvNeXt_Tiny_Weights.IMAGENET1K_V1 if pretrained else None
        m = models.convnext_tiny(weights=w)
        in_f = m.classifier[2].in_features
        m.classifier[2] = nn.Linear(in_f, n_classes)
    elif backbone == "efficientnet_b0":
        w = models.EfficientNet_B0_Weights.IMAGENET1K_V1 if pretrained else None
        m = models.efficientnet_b0(weights=w)
        in_f = m.classifier[1].in_features
        m.classifier[1] = nn.Linear(in_f, n_classes)
    elif backbone == "resnet50":
        w = models.ResNet50_Weights.IMAGENET1K_V2 if pretrained else None
        m = models.resnet50(weights=w)
        m.fc = nn.Linear(m.fc.in_features, n_classes)
    elif backbone == "resnet18":
        w = models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
        m = models.resnet18(weights=w)
        m.fc = nn.Linear(m.fc.in_features, n_classes)
    else:
        raise ValueError(f"未知 backbone: {backbone}")
    return m


class UnderwaterJitter:
    """模拟水下成像退化：蓝绿偏、雾化、光照不均（用通道增益/偏置近似）。"""

    def __init__(self, p=0.5):
        self.p = p

    def __call__(self, img):
        if random.random() > self.p:
            return img
        arr = np.asarray(img).astype(np.float32) / 255.0
        # 通道增益：水下红光衰减最强，故 R 增益偏低
        gains = np.array([random.uniform(0.75, 1.05),
                          random.uniform(0.9, 1.15),
                          random.uniform(0.9, 1.15)], dtype=np.float32)
        # 轻微雾化：整体抬升 + 对比度压缩
        haze = random.uniform(0.0, 0.12)
        contrast = random.uniform(0.85, 1.0)
        arr = arr * gains * contrast + haze
        arr = np.clip(arr, 0, 1) * 255.0
        from PIL import Image
        return Image.fromarray(arr.astype(np.uint8))


def build_loaders(data_dir: Path, img_size: int, batch_size: int, workers: int):
    mean = [0.485, 0.456, 0.406]
    std = [0.229, 0.224, 0.225]

    train_tf = transforms.Compose([
        transforms.RandomResizedCrop(img_size, scale=(0.6, 1.0), ratio=(0.8, 1.25)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(p=0.2),
        UnderwaterJitter(p=0.5),
        transforms.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.25, hue=0.05),
        transforms.RandomRotation(15),
        transforms.ToTensor(),
        transforms.Normalize(mean, std),
        transforms.RandomErasing(p=0.15),
    ])
    eval_tf = transforms.Compose([
        transforms.Resize(int(img_size * 1.14)),
        transforms.CenterCrop(img_size),
        transforms.ToTensor(),
        transforms.Normalize(mean, std),
    ])

    ds = {s: datasets.ImageFolder(data_dir / s, transform=train_tf if s == "train" else eval_tf)
          for s in ("train", "val", "test")}

    # 类别不平衡 → 加权采样
    targets = [y for _, y in ds["train"].samples]
    counts = np.bincount(targets, minlength=len(ds["train"].classes))
    w = 1.0 / np.maximum(counts, 1)
    sample_w = [float(w[t]) for t in targets]
    sampler = WeightedRandomSampler(sample_w, num_samples=len(sample_w), replacement=True)

    loaders = {
        "train": DataLoader(ds["train"], batch_size=batch_size, sampler=sampler,
                            num_workers=workers, pin_memory=True, drop_last=False),
        "val": DataLoader(ds["val"], batch_size=batch_size, shuffle=False,
                          num_workers=workers, pin_memory=True),
        "test": DataLoader(ds["test"], batch_size=batch_size, shuffle=False,
                           num_workers=workers, pin_memory=True),
    }
    return ds, loaders, counts


@torch.no_grad()
def infer_logits(model, loader, device):
    model.eval()
    logits, ys = [], []
    for x, y in loader:
        x = x.to(device, non_blocking=True)
        with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
            out = model(x)
        logits.append(out.float().cpu())
        ys.append(y)
    return torch.cat(logits), torch.cat(ys)


def macro_f1(conf: np.ndarray) -> float:
    n = conf.shape[0]
    f1s = []
    for c in range(n):
        tp = conf[c, c]
        fp = conf[:, c].sum() - tp
        fn = conf[c, :].sum() - tp
        if tp + fp + fn == 0:
            continue
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(0.0 if p + r == 0 else 2 * p * r / (p + r))
    return float(np.mean(f1s)) if f1s else 0.0


def calibrate_temperature(logits: torch.Tensor, y: torch.Tensor) -> float:
    """在验证集上做温度标定，使 NLL 最小。"""
    logT = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([logT], lr=0.1, max_iter=100)
    nll = nn.CrossEntropyLoss()

    def closure():
        opt.zero_grad()
        loss = nll(logits / torch.exp(logT), y)
        loss.backward()
        return loss

    opt.step(closure)
    return float(torch.exp(logT).item())


def selective_report(probs: np.ndarray, y: np.ndarray, target=0.999):
    """coverage–accuracy 曲线；找出达到 target 准确率所需的最小置信度阈值。"""
    conf = probs.max(axis=1)
    pred = probs.argmax(axis=1)
    correct = (pred == y)
    order = np.argsort(-conf)
    correct_sorted = correct[order]
    conf_sorted = conf[order]
    n = len(y)

    curve = []
    for frac in [0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]:
        k = max(1, int(round(n * frac)))
        curve.append({
            "coverage": round(k / n, 4),
            "threshold": round(float(conf_sorted[k - 1]), 4),
            "accuracy": round(float(correct_sorted[:k].mean()), 6),
        })

    # 找满足 target 的最大覆盖
    best = None
    cum = np.cumsum(correct_sorted) / np.arange(1, n + 1)
    ok = np.where(cum >= target)[0]
    if len(ok):
        i = int(ok.max())          # 覆盖最大且仍达标
        best = {"coverage": round((i + 1) / n, 4),
                "threshold": round(float(conf_sorted[i]), 4),
                "accuracy": round(float(cum[i]), 6)}
    return {"curve": curve, "target_accuracy": target, "best_meeting_target": best,
            "overall_accuracy": round(float(correct.mean()), 6)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True,
                    choices=["bleaching", "bleaching_ip", "bleaching_new", "bleaching_all", "species", "species_ip"])
    ap.add_argument("--backbone", default="convnext_tiny",
                    choices=["convnext_tiny", "efficientnet_b0", "resnet50", "resnet18"])
    ap.add_argument("--img-size", type=int, default=224)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--freeze-epochs", type=int, default=3, help="前 N 轮冻结 backbone")
    ap.add_argument("--lr-head", type=float, default=3e-4)
    ap.add_argument("--lr-backbone", type=float, default=1e-5)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--patience", type=int, default=8)
    ap.add_argument("--target-acc", type=float, default=0.999)
    ap.add_argument("--resume", action="store_true",
                    help="从 weights/<task>/last.pt 续训（进程被中断后用这个接着跑）")
    ap.add_argument("--data-dir", default=None,
                    help="自定义数据目录（ImageFolder 结构，含 train/val/test 子目录）；"
                         "默认 data/processed/<task>")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    data_dir = Path(args.data_dir) if args.data_dir else (root / "data" / "processed" / args.task)
    if not data_dir.is_absolute():
        data_dir = (root / data_dir).resolve()
    wdir = root / "weights" / args.task
    rdir = root / "reports" / args.task
    wdir.mkdir(parents=True, exist_ok=True)
    rdir.mkdir(parents=True, exist_ok=True)
    if not data_dir.exists():
        raise SystemExit(f"找不到数据目录 {data_dir}，请先运行 split_data.py")

    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"设备: {device}" + (f" ({torch.cuda.get_device_name(0)})" if device.type == "cuda" else ""))
    print(f"任务: {args.task} | backbone: {args.backbone} | 输入: {args.img_size}")

    ds, loaders, counts = build_loaders(data_dir, args.img_size, args.batch_size, args.workers)
    classes = ds["train"].classes
    print(f"类别数: {len(classes)}")
    print(f"train/val/test = {len(ds['train'])}/{len(ds['val'])}/{len(ds['test'])}")
    print("各类训练样本数:", dict(zip(classes, counts.tolist())))

    model = build_model(args.backbone, len(classes)).to(device)
    crit = nn.CrossEntropyLoss(label_smoothing=0.05)

    best_acc, best_epoch, history = 0.0, -1, []
    ckpt = wdir / "best.pt"
    last = wdir / "last.pt"
    start_epoch = 1

    # ---- 断点续训 ----
    if args.resume and last.exists():
        prev = torch.load(last, map_location=device, weights_only=False)
        if prev.get("classes") == classes and prev.get("backbone") == args.backbone:
            model.load_state_dict(prev["model"])
            best_acc = float(prev.get("best_acc", 0.0))
            best_epoch = int(prev.get("epoch", -1))
            start_epoch = int(prev.get("epoch", 0)) + 1
            history = list(prev.get("history", []))
            print(f"[续训] 从第 {start_epoch} 轮继续，历史最佳 val_acc={best_acc:.4f} (第 {best_epoch} 轮)")
        else:
            print("[续训] 忽略 last.pt（类别或 backbone 不匹配）")

    for epoch in range(start_epoch, args.epochs + 1):
        frozen = epoch <= args.freeze_epochs
        for p in model.parameters():
            p.requires_grad = True
        if frozen:
            for name, p in model.named_parameters():
                if "classifier" not in name and "fc" not in name:
                    p.requires_grad = False
        params = [{"params": [p for p in model.parameters() if p.requires_grad],
                   "lr": args.lr_head if frozen else args.lr_head}]
        if not frozen:
            head_ids = set()
            for name, p in model.named_parameters():
                if "classifier" in name or "fc" in name:
                    head_ids.add(id(p))
            params = [
                {"params": [p for p in model.parameters() if id(p) in head_ids], "lr": args.lr_head},
                {"params": [p for p in model.parameters() if id(p) not in head_ids], "lr": args.lr_backbone},
            ]
        opt = torch.optim.AdamW(params, weight_decay=0.05)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs - args.freeze_epochs)
        scaler = torch.amp.GradScaler("cuda", enabled=(device.type == "cuda"))

        model.train()
        t0 = time.time()
        tr_loss, tr_n, tr_c = 0.0, 0, 0
        for x, y in loaders["train"]:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            opt.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                out = model(x)
                loss = crit(out, y)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            tr_loss += loss.item() * y.size(0)
            tr_n += y.size(0)
            tr_c += (out.argmax(1) == y).sum().item()
        if not frozen:
            sched.step()

        # 验证
        vlogits, vy = infer_logits(model, loaders["val"], device)
        vacc = (vlogits.argmax(1) == vy).float().mean().item()
        history.append({"epoch": epoch, "frozen": frozen,
                        "train_loss": round(tr_loss / max(tr_n, 1), 4),
                        "train_acc": round(tr_c / max(tr_n, 1), 4),
                        "val_acc": round(vacc, 4)})
        flag = ""
        if vacc > best_acc:
            best_acc, best_epoch = vacc, epoch
            torch.save({"model": model.state_dict(), "classes": classes,
                        "backbone": args.backbone, "img_size": args.img_size,
                        "val_acc": vacc, "epoch": epoch}, ckpt)
            flag = "  <- 保存"
        # 每轮都存一份 last.pt，供 --resume 续训
        torch.save({"model": model.state_dict(), "classes": classes,
                    "backbone": args.backbone, "img_size": args.img_size,
                    "val_acc": vacc, "epoch": epoch,
                    "best_acc": best_acc, "history": history}, last)
        print(f"[{epoch:>3}/{args.epochs}] {'冻结' if frozen else '微调'} "
              f"loss={tr_loss/max(tr_n,1):.4f} train={tr_c/max(tr_n,1):.4f} "
              f"val={vacc:.4f} {time.time()-t0:.0f}s{flag}", flush=True)

        if epoch - best_epoch >= args.patience:
            print(f"验证集 {args.patience} 轮无提升，提前停止")
            break

    # ---------------- 测试集最终评估 ----------------
    print("\n" + "=" * 62)
    print("加载最优权重，进行测试集评估 ...")
    ck = torch.load(ckpt, map_location=device, weights_only=False)
    model.load_state_dict(ck["model"])
    model.eval()

    vlogits, vy = infer_logits(model, loaders["val"], device)
    T = calibrate_temperature(vlogits, vy)
    print(f"温度标定 T = {T:.4f}")

    tlogits, ty = infer_logits(model, loaders["test"], device)
    probs = torch.softmax(tlogits / T, dim=1).numpy()
    y = ty.numpy()
    pred = probs.argmax(1)

    top1 = float((pred == y).mean())
    n_cls = len(classes)
    conf = np.zeros((n_cls, n_cls), dtype=np.int64)
    for t, p in zip(y, pred):
        conf[t, p] += 1
    mf1 = macro_f1(conf)
    per_class = {}
    for i, c in enumerate(classes):
        tot = conf[i].sum()
        per_class[c] = {
            "n": int(tot),
            "acc": round(float(conf[i, i] / tot), 4) if tot else None,
            "f1": round(float(2 * conf[i, i] / max(conf[i].sum() + conf[:, i].sum(), 1)), 4),
        }

    sel = selective_report(probs, y, args.target_acc)

    # ---- 额外测试集（如 test_ip 印太域）----
    # ⚠️ 关键：额外测试集的类别子集会让 ImageFolder **重新分配索引**
    #    （例如 test_ip 只有 bleached/healthy → 索引 0/1，
    #      而模型类别是 bleached/dead/healthy → 0/1/2），
    #    必须把标签与预测都映射回模型类别空间，否则结果完全错误。
    extra_tests = {}
    for extra in ("test_ip",):
        d = data_dir / extra
        if d.exists() and any(p.is_dir() for p in d.iterdir()):
            ed = datasets.ImageFolder(d, transform=ds["test"].transform)
            missing = [c for c in ed.classes if c not in classes]
            if missing:
                print(f"\n⚠ {extra} 含模型未知类别 {missing}，已跳过")
                continue
            remap = np.array([classes.index(c) for c in ed.classes])
            print(f"\n[{extra}] 类别索引映射: {dict(zip(ed.classes, remap.tolist()))}")

            ldr = DataLoader(ed, batch_size=args.batch_size, shuffle=False,
                             num_workers=args.workers, pin_memory=True)
            elogits, ey = infer_logits(model, ldr, device)
            eprobs = torch.softmax(elogits / T, dim=1).numpy()
            eyy = remap[ey.numpy()]                    # ← 标签映射到模型空间
            epred = eprobs.argmax(1)
            econf = np.zeros((n_cls, n_cls), dtype=np.int64)
            for t, p in zip(eyy, epred):
                econf[t, p] += 1
            extra_tests[extra] = {
                "n": int(len(eyy)),
                "top1": round(float((epred == eyy).mean()), 6),
                "macro_f1": round(macro_f1(econf), 6),
                "selective": selective_report(eprobs, eyy, args.target_acc),
                "confusion_matrix": econf.tolist(),
                "class_remap": {c: int(i) for c, i in zip(ed.classes, remap)},
            }
            print(f"【{extra}】样本 {len(eyy)}  Top-1 = "
                  f"{extra_tests[extra]['top1']:.4%}  宏F1 = {extra_tests[extra]['macro_f1']:.4f}")

    print("-" * 62)
    print(f"测试集 Top-1 准确率 : {top1:.4%}")
    print(f"宏平均 F1           : {mf1:.4f}")
    print(f"整体准确率(校准后)   : {sel['overall_accuracy']:.4%}")
    print(f"\n=== 选择性预测（置信度拒识）===")
    print(f"{'覆盖率':>8}{'阈值':>10}{'准确率':>12}")
    for pt in sel["curve"]:
        print(f"{pt['coverage']:>8.0%}{pt['threshold']:>10.4f}{pt['accuracy']:>12.4%}")
    b = sel["best_meeting_target"]
    if b:
        print(f"\n★ 达到 {args.target_acc:.1%} 准确率所需: 置信度阈值 ≥ {b['threshold']}"
              f"，此时覆盖率 {b['coverage']:.1%}，准确率 {b['accuracy']:.4%}")
    else:
        print(f"\n⚠ 测试集上无法达到 {args.target_acc:.1%}（即便全部拒识也不够）；"
              f"最高可用: 覆盖率 {sel['curve'][-1]['coverage']:.0%} 时准确率 {sel['curve'][-1]['accuracy']:.4%}")

    # 最易混淆的类对
    off = conf.copy()
    np.fill_diagonal(off, 0)
    pairs = []
    for i in range(n_cls):
        for j in range(n_cls):
            if off[i, j] > 0:
                pairs.append((int(off[i, j]), classes[i], classes[j]))
    pairs.sort(reverse=True)
    print("\n=== 最易混淆的类对（真实→预测）===")
    for n_, a, b_ in pairs[:10]:
        print(f"  {a:<26} -> {b_:<26} {n_} 次")

    report = {
        "task": args.task, "backbone": args.backbone, "img_size": args.img_size,
        "classes": classes, "temperature": T,
        "test_top1": round(top1, 6), "test_macro_f1": round(mf1, 6),
        "extra_tests": extra_tests,
        "per_class": per_class,
        "selective_prediction": sel,
        "confusion_matrix": conf.tolist(),
        "train_history": history,
        "best_val_acc": round(best_acc, 6), "best_epoch": best_epoch,
    }
    with open(rdir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 混淆矩阵 CSV
    with open(rdir / "confusion_matrix.csv", "w", encoding="utf-8") as f:
        f.write("true\\pred," + ",".join(classes) + "\n")
        for i, c in enumerate(classes):
            f.write(c + "," + ",".join(str(v) for v in conf[i]) + "\n")

    print(f"\n权重: {ckpt}")
    print(f"报告: {rdir/'metrics.json'}")
    print(f"混淆矩阵: {rdir/'confusion_matrix.csv'}")


if __name__ == "__main__":
    main()
