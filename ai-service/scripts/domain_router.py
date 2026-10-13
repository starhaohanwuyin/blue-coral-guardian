"""按域路由：先判断照片属于「原始域」还是「印太域」，再选对应模型。

## 为什么
前几轮的矛盾是：**纯域自适应模型（B/C）在印太域强、在原始域崩**；**多域联合模型（D）两边都不崩但跨域上限低**。
路由可以同时拿到两边的最优：原始域照片用 A/D，印太域照片用 B/C。

## 做法
1. 用轻量图像统计特征（颜色/饱和度/亮度/边缘/色彩丰富度）训练一个**逻辑回归**做域判别；
   系数存进 `reports/domain_router.json`（小、可入库、可复现），不引入新依赖。
2. `--eval` 在给定测试集上：先判域 → 再调用对应模型的 logits → 输出**单标签宏 F1**，
   并与「纯 A/D」「纯 B/C」对比，看路由是否真的取到两者之长。

用法：
    python domain_router.py --train                      # 训练并保存系数
    python domain_router.py --train --samples 2000
    python domain_router.py --eval --source external     # 印太外部集（应该路由到印太模型）
    python domain_router.py --eval --source kaggle       # 域内集（应该路由到原始域模型）
    python domain_router.py --eval --source winter
    python domain_router.py --eval --source orig_test    # data/processed/bleaching/test
"""
import argparse
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

CCD = ROOT / "data" / "raw" / "CoralConditionDataset"
CCD_JSON = CCD / "CoralConditionDataset-main" / "code" / "datasets"
ORIG_TRAIN = [ROOT / "data" / "processed" / "bleaching" / "train",
              ROOT / "data" / "processed" / "bleaching_ip" / "train"]
KAGGLE = (ROOT.parent / "competition_data" / "AI4Climate_data" / "Kaggle_coral_images"
          / "Coral Reef Images")
ROUTER = ROOT / "reports" / "domain_router.json"
CLASSES = ["bleached", "dead", "healthy"]
CI = {c: i for i, c in enumerate(CLASSES)}
IDX = {i: i for i in range(3)}
CCD_TO_3 = {1: "healthy", 2: "bleached", 3: "dead"}


def features(p):
    """轻量特征：颜色/亮度/饱和度/边缘/色彩丰富度（不依赖 cv2）。"""
    import numpy as np
    from PIL import Image, ImageFilter
    im = Image.open(p).convert("RGB").resize((128, 128))
    a = np.asarray(im, dtype=np.float32) / 255.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(2), a.min(2)
    v = mx
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    hsv_h = np.zeros_like(v)
    d = np.maximum(mx - mn, 1e-6)
    hsv_h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6.0
    gray = a.mean(2)
    edge = np.asarray(im.convert("L").filter(ImageFilter.FIND_EDGES), dtype=np.float32).mean() / 255.0
    # Hasler-Süsstrunk 色彩丰富度
    rg, yb = r - g, 0.5 * (r + g) - b
    colorfulness = float((np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2)))
    hh, _ = np.histogram(hsv_h.ravel(), bins=12, range=(0, 1))   # 必须 ravel
    hh = hh / max(hh.sum(), 1e-6)
    ss, _ = np.histogram(s, bins=6, range=(0, 1))
    ss = ss / max(ss.sum(), 1)
    vv, _ = np.histogram(v, bins=6, range=(0, 1))
    vv = vv / max(vv.sum(), 1)
    base = [r.mean(), g.mean(), b.mean(), r.std(), g.std(), b.std(),
            s.mean(), s.std(), v.mean(), v.std(), gray.mean(), gray.std(), edge, colorfulness]
    return np.concatenate([np.array(base, dtype=np.float32), hh.astype(np.float32),
                           ss.astype(np.float32), vv.astype(np.float32)])


def collect_domains(samples):
    """返回 (特征, 域标签 0=原始域 1=印太域) 与留出集。"""
    rng = random.Random(0)
    orig, indo = [], []
    for d in ORIG_TRAIN:
        for c in CLASSES:
            fs = [p for p in (d / c).glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
            rng.shuffle(fs)
            orig += fs[: samples // 4]
    fs = [p for p in (KAGGLE / "train" / "Bleached").glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    rng.shuffle(fs)
    orig += fs[: samples // 2]
    # 印太域：Koh Tao 干季
    idx = {}
    for p in (CCD / "dry").rglob("*.jpg"):
        idx.setdefault(p.stem, p)
    rows = json.loads((CCD_JSON / "train_set_fully_supervision.json").read_text(encoding="utf-8"))
    rng.shuffle(rows)
    for r in rows:
        p = idx.get(str(r.get("tileid", "")))
        if p is not None:
            indo.append(p)
        if len(indo) >= samples:
            break
    orig = orig[:samples]
    print(f"训练特征：原始域 {len(orig)} 张 / 印太域 {len(indo)} 张")
    X = [features(p) for p in orig + indo]
    y = [0] * len(orig) + [1] * len(indo)
    # 留出集
    ho_orig, ho_indo = [], []
    fs = [p for p in (KAGGLE / "valid" / "Bleached").glob("*")] + \
         [p for p in (KAGGLE / "valid" / "Healthy").glob("*")]
    rng.shuffle(fs)
    ho_orig = [p for p in fs if p.suffix.lower() in (".jpg", ".jpeg", ".png")][:200]
    idx2 = {}
    for p in (CCD / "dry").rglob("*.jpg"):
        idx2.setdefault(p.stem, p)
    rows2 = json.loads((CCD_JSON / "test_set.json").read_text(encoding="utf-8"))
    rng.shuffle(rows2)
    for r in rows2:
        p = idx2.get(str(r.get("tileid", "")))
        if p is not None:
            ho_indo.append(p)
        if len(ho_indo) >= 200:
            break
    return X, y, ho_orig, ho_indo


def train(samples, out):
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    X, y, ho_orig, ho_indo = collect_domains(samples)
    sc = StandardScaler().fit(X)
    clf = LogisticRegression(max_iter=2000, C=0.5).fit(sc.transform(X), y)
    acc_tr = clf.score(sc.transform(X), y)
    hx = [features(p) for p in ho_orig + ho_indo]
    hy = [0] * len(ho_orig) + [1] * len(ho_indo)
    pred = clf.predict(sc.transform(hx))
    acc_ho = float((pred == np.array(hy)).mean())
    print(f"训练准确率 {acc_tr:.3f}  留出准确率 {acc_ho:.3f}"
          f"（原始域 {float((pred[:len(ho_orig)] == 0).mean()):.3f} / 印太域 {float((pred[len(ho_orig):] == 1).mean()):.3f}）")
    out.write_text(json.dumps({
        "task": "域路由（原始域 vs 印太域）：逻辑回归 + 轻量图像统计特征",
        "features": "RGB/HSV 统计 + 直方图(12+6+6) + 边缘密度 + 色彩丰富度 = 38 维",
        "coef": clf.coef_[0].tolist(),
        "intercept": float(clf.intercept_[0]),
        "scalerMean": sc.mean_.tolist(), "scalerScale": sc.scale_.tolist(),
        "trainAcc": round(float(acc_tr), 4), "holdoutAcc": round(acc_ho, 4),
        "holdoutDetail": {"origAcc": round(float((pred[:len(ho_orig)] == 0).mean()), 4),
                          "indoAcc": round(float((pred[len(ho_orig):] == 1).mean()), 4),
                          "nOrig": len(ho_orig), "nIndo": len(ho_indo)},
        "caveats": ["域判别基于外观统计，不是语义理解；光照/相机差异大时可能误判",
                    "留出集来自 Kaggle valid 与 Koh Tao test，与训练同源不同样本"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"系数写入 {out}")


def load_model():
    d = json.loads(ROUTER.read_text(encoding="utf-8"))
    import numpy as np
    return (np.array(d["coef"], dtype=np.float64), float(d["intercept"]),
            np.array(d["scalerMean"]), np.array(d["scalerScale"]))


def evaluate(source, w_orig, w_indo, out, strategy="domain"):
    import numpy as np
    import torch
    from PIL import Image
    from torchvision import transforms
    from train import build_model

    # 测试集
    if source == "external":
        import csv as _csv
        p = CCD / "external" / "label_coral_image_external.csv"
        rows = list(_csv.DictReader(p.open(newline="", encoding="utf-8-sig")))
        items, imgs = [], CCD / "external" / "coral_image_external"
        for r in rows:
            labs = [int(x) for x in (r["label"] or "").replace(" ", "").split(",") if x.isdigit()]
            truth = {CCD_TO_3[k] for k in labs if k in CCD_TO_3}
            if truth:
                items.append((r["patchid"], truth))
        kind = "indo"
    elif source == "winter":
        rows = json.loads((CCD_JSON / "winter_data_test_set.json").read_text(encoding="utf-8"))
        items, imgs = [], None
        for r in rows:
            truth = {CCD_TO_3[k] for k in CCD_TO_3 if int(r.get(str(k), 0)) == 1}
            if truth:
                items.append((r["tileid"], truth))
        kind = "indo"
    elif source == "kaggle":
        base = KAGGLE / "test"
        items = []
        for cdir, cname in (("Bleached", "bleached"), ("Healthy", "healthy")):
            for p in (base / cdir).glob("*"):
                if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
                    items.append((p, {cname}))
        imgs = None
        kind = "orig"
    elif source == "orig_test":
        base = ROOT / "data" / "processed" / "bleaching" / "test"
        items = []
        for c in CLASSES:
            for p in (base / c).glob("*"):
                if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
                    items.append((p, {c}))
        imgs = None
        kind = "orig"
    else:
        raise SystemExit(f"未知 source {source}")

    def resolve(key):
        if isinstance(key, pathlib.Path):
            return key
        if imgs is not None:
            return imgs / f"{key}.jpg"
        idx = resolve.idx
        return idx.get(str(key))

    idx = {}
    for p in list((CCD / "dry").rglob("*.jpg")) + list((CCD / "wet").rglob("*.jpg")):
        idx.setdefault(p.stem, p)
    resolve.idx = idx

    coef, b, mu, sd = load_model()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def load_w(wp):
        ck = torch.load(wp, map_location=device, weights_only=False)
        m = build_model(ck["backbone"], len(ck["classes"])).to(device)
        m.load_state_dict(ck["model"])
        m.eval()
        cls = [str(c).lower() for c in ck["classes"]]
        tf = transforms.Compose([
            transforms.Resize(int(ck.get("img_size", 224) * 1.14)),
            transforms.CenterCrop(ck.get("img_size", 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
        return m, cls, tf

    mO, clsO, tfO = load_w(w_orig)
    mI, clsI, tfI = load_w(w_indo)
    print(f"原始域模型 {pathlib.Path(w_orig).parent.name} / 印太域模型 {pathlib.Path(w_indo).parent.name}")

    CONF = {t: {c: 0 for c in CLASSES} for t in CLASSES}
    n_route_indo = n_route_orig = 0
    n_done = 0
    with torch.no_grad():
        for key, truth in items:
            p = resolve(key)
            if p is None or not pathlib.Path(p).exists():
                continue
            x = features(p)
            img = Image.open(p).convert("RGB")
            if strategy == "pure_orig":
                is_indo = False
            elif strategy == "pure_indo":
                is_indo = True
            elif strategy == "confidence":
                # 不判域：两个模型都跑，取 softmax 最大值更高者（"谁更自信用谁"）
                with torch.no_grad():
                    lo = torch.softmax(mO(tfO(img).unsqueeze(0).to(device)), dim=1)[0]
                    li = torch.softmax(mI(tfI(img).unsqueeze(0).to(device)), dim=1)[0]
                is_indo = float(li.max()) > float(lo.max())
            else:
                z = float(((x - mu) / sd) @ coef + b)
                is_indo = z > 0
            n_route_indo += int(is_indo)
            n_route_orig += int(not is_indo)
            tf = tfI if is_indo else tfO
            model, cls = (mI, clsI) if is_indo else (mO, clsO)
            img = Image.open(p).convert("RGB")
            pred = cls[int(model(tf(img).unsqueeze(0).to(device)).argmax(dim=1).item())]
            ts = next((c for c in ("dead", "bleached", "healthy") if c in truth), None)
            if ts:
                CONF[ts][pred] += 1
            n_done += 1

    def macro(C):
        f1s = {}
        for t in CLASSES:
            tp = C[t][t]
            fn = sum(C[t][o] for o in CLASSES if o != t)
            fp = sum(C[o][t] for o in CLASSES if o != t)
            pr = tp / (tp + fp) if tp + fp else 0.0
            rc = tp / (tp + fn) if tp + fn else 0.0
            f1s[t] = round(2 * pr * rc / (pr + rc), 4) if pr + rc else 0.0
        return sum(f1s.values()) / 3, f1s

    macro_r, f1_r = macro(CONF)
    print(f"\n已评 {n_done} 张；路由到印太模型 {n_route_indo} / 原始域模型 {n_route_orig}"
          f"（该测试集真实属「{'印太' if kind == 'indo' else '原始'}域」）")
    print(f"路由后单标签宏F1 = {macro_r:.4f}   各类 " + "  ".join(f"{c}:{v:.3f}" for c, v in f1_r.items()))
    p = pathlib.Path(out)
    if not p.is_absolute():
        p = ROOT / p
    p.write_text(json.dumps({
        "strategy": strategy, "source": source, "trueDomain": kind, "samples": n_done,
        "routedToIndo": n_route_indo, "routedToOrig": n_route_orig,
        "macroF1": round(float(macro_r), 4), "perClass": f1_r,
        "routingHitRate": round((n_route_indo if kind == "indo" else n_route_orig) / max(n_done, 1), 4),
        "models": {"orig": str(w_orig), "indo": str(w_indo)},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告写入 {p}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--samples", type=int, default=1500)
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--source", default="external")
    ap.add_argument("--w-orig", default="weights/bleaching_all/best.pt")
    ap.add_argument("--w-indo", default="weights/bleaching_all_koh_tao_bb/best.pt")
    ap.add_argument("--out", default="")
    ap.add_argument("--strategy", default="domain", choices=["domain", "confidence", "pure_orig", "pure_indo"],
                    help="domain=先用外观统计判域；confidence=两个模型都跑、取更自信者")
    a = ap.parse_args()
    if a.train:
        train(a.samples, ROUTER)
        return 0
    if a.eval:
        wo = pathlib.Path(a.w_orig)
        wi = pathlib.Path(a.w_indo)
        out = a.out or f"reports/router_{a.strategy}_{a.source}.json"
        evaluate(a.source, wo if wo.is_absolute() else ROOT / wo,
                 wi if wi.is_absolute() else ROOT / wi, out, a.strategy)
        return 0
    print("请指定 --train 或 --eval")
    return 2


if __name__ == "__main__":
    sys.exit(main())
