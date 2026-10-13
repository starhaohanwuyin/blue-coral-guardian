"""为白化三分类模型标定「类别偏置」——修"某一类几乎不判"的退化。

动机：微调后的模型在印太域 dead 类修好了（F1 0.008→0.640），但 **bleached 召回掉到 0.222**
（原模型是"过度判白化"换来的 0.779，属另一极端）。两头都不是我们想要的。

做法：在**验证集**上网格搜索每类的 logit 偏置（等价于调整类先验），
使得项目一贯使用的**一对其余宏平均 F1**最大；把偏置存成 JSON，
评测时用 `eval_bleaching_indopacific.py --offsets <json>` 施加。

⚠️ 纪律：偏置**只在验证集（CCD test_set）上调**，绝不看 Arafura/Darwin 测试集
（否则就是用测试集调参，结果不可信）。

用法：
    python calibrate_bleaching_offsets.py                                   # 线上权重 + CCD 验证集
    python calibrate_bleaching_offsets.py --weights weights/bleaching_all_koh_tao/best.pt
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

CCD = ROOT / "data" / "raw" / "CoralConditionDataset"
LABELS = CCD / "CoralConditionDataset-main" / "code" / "datasets"
CCD_TO_3 = {1: "healthy", 2: "bleached", 3: "dead"}


def collect_logits(weights, limit):
    """跑一遍验证集，返回 (logits[N,3], truth_mask[N,3]) 与类别顺序。"""
    import numpy as np
    import torch
    from PIL import Image
    from torchvision import transforms
    from train import build_model

    idx = {}
    for p in (CCD / "dry").rglob("*.jpg"):
        idx.setdefault(p.stem, p)
    if not idx:
        print(f"❌ 找不到干季图像（{CCD / 'dry'}）")
        return None

    rows = json.loads((LABELS / "test_set.json").read_text(encoding="utf-8"))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(weights, map_location=device, weights_only=False)
    classes = [str(c).lower() for c in ck["classes"]]
    size = ck.get("img_size", 224)
    model = build_model(ck["backbone"], len(ck["classes"])).to(device)
    model.load_state_dict(ck["model"])
    model.eval()
    tf = transforms.Compose([
        transforms.Resize(int(size * 1.14)), transforms.CenterCrop(size),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

    L, T_single, T_multi = [], [], []
    # ⚠️ 真值索引必须跟随**权重里的类别顺序**（classes 可能是 bleached/dead/healthy），
    #    不能想当然按 1/2/3 原序排 —— 本脚本曾因此把真值整体错位（宏F1 假跌到 0.16）。
    ci = {c: i for i, c in enumerate(classes)}
    with torch.no_grad():
        for r in rows:
            p = idx.get(str(r.get("tileid", "")))
            if p is None:
                continue
            x = tf(Image.open(p).convert("RGB")).unsqueeze(0).to(device)
            L.append(model(x).squeeze(0).float().cpu().numpy())
            multi = [1 if int(r.get(str(k), 0)) == 1 else 0 for k in (1, 2, 3)]
            T_multi.append(multi)
            has_healthy, has_bleached, has_dead = multi[0], multi[1], multi[2]
            if has_dead:
                single = ci["dead"]
            elif has_bleached:
                single = ci["bleached"]
            elif has_healthy:
                single = ci["healthy"]
            else:
                single = -1
            T_single.append(single)
            if limit and len(L) >= limit:
                break
    keep = np.array(T_single) >= 0
    return (np.array(L)[keep], np.array(T_single)[keep],
            np.array(T_multi)[keep].astype(int), classes)


def macro_f1_single(pred, truth, nc=3):
    """单标签宏平均 F1（与评测主口径、训练口径一致）。"""
    f1s = []
    for c in range(nc):
        tp = int(((pred == c) & (truth == c)).sum())
        fp = int(((pred == c) & (truth != c)).sum())
        fn = int(((pred != c) & (truth == c)).sum())
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append((2 * prec * rec / (prec + rec)) if prec + rec else 0.0)
    return sum(f1s) / nc, f1s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default=str(ROOT / "weights" / "bleaching_all" / "best.pt"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    w = pathlib.Path(a.weights)
    if not w.exists():
        print(f"❌ 找不到权重 {w}")
        return 2
    got = collect_logits(w, a.limit)
    if not got:
        return 3
    import numpy as np
    L, T, T_multi, classes = got
    print(f"验证样本 {len(L)} 张；类别顺序 {classes}")

    base_macro, base_f1 = macro_f1_single(L.argmax(1), T)
    print(f"偏置全零：单标签宏F1={base_macro:.4f}  " + "  ".join(
        f"{classes[i]} F1={base_f1[i]:.3f}" for i in range(len(classes))))

    grid = np.arange(-2.0, 2.01, 0.25)
    best = (base_macro, np.zeros(len(classes)), base_f1)
    for o0 in grid:
        for o1 in grid:
            for o2 in grid:
                off = np.array([o0, o1, o2])[: len(classes)]
                macro, f1s = macro_f1_single((L + off).argmax(1), T)
                if macro > best[0] + 1e-9:
                    best = (macro, off.copy(), f1s)
    macro, off, f1s = best
    print(f"\n最优偏置 {dict(zip(classes, np.round(off, 2)))}")
    print(f"  宏F1 {base_macro:.4f} → {macro:.4f}   各类 " +
          "  ".join(f"{classes[i]} {base_f1[i]:.3f}→{f1s[i]:.3f}" for i in range(len(classes))))

    outp = pathlib.Path(a.out) if a.out else (
        ROOT / "reports" / f"bleaching_offsets_{w.parent.name}.json")
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps({
        "weights": str(w), "classes": classes,
        "offsets": {c: float(np.round(off[i], 3)) for i, c in enumerate(classes)},
        "tunedOn": "CCD test_set（验证集）——**未使用** Arafura/Darwin 测试集",
        "metric": "单标签宏平均 F1（优先级 dead>bleached>healthy，与训练/评测主口径一致）",
        "valSamples": int(len(L)),
        "macroF1Before": round(float(base_macro), 4),
        "macroF1After": round(float(macro), 4),
        "perClassBefore": {classes[i]: round(float(base_f1[i]), 4) for i in range(len(classes))},
        "perClassAfter": {classes[i]: round(float(f1s[i]), 4) for i in range(len(classes))},
        "caveat": "偏置等价于改类先验，可修正「某类几乎不判」，但不能凭空造出判别能力；"
                  "在别的域是否同样有效需实测",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"写入 {outp}")
    print(f"施加方式：python eval_bleaching_indopacific.py --source external "
          f"--weights {w} --offsets {outp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
