"""更强的路由仲裁：温度校准置信度 + 分歧弃权（在 domain_router.py 的基线上做改进尝试）。

## 为什么
`domain_router.py` 的两种策略都没跑赢"单一多域模型 D2"：
- 外观判域：留出 0.79，Kaggle 上只有 68.5%
- 直接比 softmax 最大值：两模型分别在不同域微调过，**置信度尺度不可比**

## 本脚本的两个改进
1. **温度校准**：先在各模型自己的验证集上拟合温度 T（最小化 NLL），再比校准后的置信度；
2. **分歧弃权**：两模型判不同的样本标为「待复核」而不硬选 —— 牺牲覆盖率换准确率，
   并如实报告覆盖率（这是产品上更诚实的做法）。

用法：
    python router_arbitration.py            # 校准 + 在 4 个测试集上评 2 种策略
    python router_arbitration.py --source external
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

CLASSES = ["bleached", "dead", "healthy"]
CI = {c: i for i, c in enumerate(CLASSES)}
CCD = ROOT / "data" / "raw" / "CoralConditionDataset"
CCD_JSON = CCD / "CoralConditionDataset-main" / "code" / "datasets"
KAGGLE = (ROOT.parent / "competition_data" / "AI4Climate_data" / "Kaggle_coral_images"
          / "Coral Reef Images")
CCD_TO_3 = {1: "healthy", 2: "bleached", 3: "dead"}
MODELS = {
    "orig": ROOT / "weights" / "bleaching_all" / "best.pt",              # D2（线上）
    "indo": ROOT / "weights" / "bleaching_all_koh_tao_bb" / "best.pt",   # C（纯域自适应）
}


def build_one(wp, device):
    """单独加载一个权重（用于按 --alt 替换共识第二模型）。"""
    import torch
    from torchvision import transforms
    from train import build_model
    ck = torch.load(wp, map_location=device, weights_only=False)
    m = build_model(ck["backbone"], len(ck["classes"])).to(device)
    m.load_state_dict(ck["model"]); m.eval()
    sz = ck.get("img_size", 224)
    tf = transforms.Compose([transforms.Resize(int(sz * 1.14)), transforms.CenterCrop(sz),
                             transforms.ToTensor(),
                             transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
    return (m, [str(c).lower() for c in ck["classes"]], tf)


def build():
    import torch
    from torchvision import transforms
    from train import build_model
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out = {}
    for k, wp in MODELS.items():
        ck = torch.load(wp, map_location=device, weights_only=False)
        m = build_model(ck["backbone"], len(ck["classes"])).to(device)
        m.load_state_dict(ck["model"])
        m.eval()
        sz = ck.get("img_size", 224)
        tf = transforms.Compose([
            transforms.Resize(int(sz * 1.14)), transforms.CenterCrop(sz),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
        out[k] = (m, [str(c).lower() for c in ck["classes"]], tf)
    return out, device


def calibration_sets():
    """两个模型各自的验证集：Koh Tao test_set（印太）+ 原始域 val。"""
    import random
    idx = {}
    for p in (CCD / "dry").rglob("*.jpg"):
        idx.setdefault(p.stem, p)
    rows = json.loads((CCD_JSON / "test_set.json").read_text(encoding="utf-8"))
    random.Random(0).shuffle(rows)
    ccd = []
    for r in rows:
        p = idx.get(str(r.get("tileid", "")))
        if p is None:
            continue
        c = "dead" if int(r.get("3", 0)) == 1 else ("bleached" if int(r.get("2", 0)) == 1
                                                    else ("healthy" if int(r.get("1", 0)) == 1 else None))
        if c:
            ccd.append((p, c))
        if len(ccd) >= 800:
            break
    orig = []
    for c in CLASSES:
        for p in (ROOT / "data" / "processed" / "bleaching" / "val" / c).glob("*"):
            if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
                orig.append((p, c))
    return ccd, orig


def fit_T(model, tf, pairs, device, iters=80):
    import torch
    import torch.nn.functional as F
    from PIL import Image
    L, y = [], []
    with torch.no_grad():
        for p, c in pairs:
            try:
                x = tf(Image.open(p).convert("RGB")).unsqueeze(0).to(device)
            except Exception:
                continue
            L.append(model(x).squeeze(0).cpu())
            y.append(CI[c])
    if len(L) < 20:
        return 1.0, 0
    L, y = torch.stack(L), torch.tensor(y)
    logT = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([logT], lr=0.1, max_iter=iters)

    def closure():
        opt.zero_grad()
        loss = F.cross_entropy(L / logT.exp(), y)
        loss.backward()
        return loss
    opt.step(closure)
    return float(logT.exp().item()), len(L)


def test_items(source):
    if source == "external":
        import csv as _csv
        rows = list(_csv.DictReader((CCD / "external" / "label_coral_image_external.csv")
                                    .open(newline="", encoding="utf-8-sig")))
        imgs = CCD / "external" / "coral_image_external"
        out = []
        for r in rows:
            labs = [int(x) for x in (r["label"] or "").replace(" ", "").split(",") if x.isdigit()]
            t = {CCD_TO_3[k] for k in labs if k in CCD_TO_3}
            if t:
                out.append((imgs / f"{r['patchid']}.jpg", t))
        return out, "indo"
    if source == "winter":
        idx = {}
        for p in (CCD / "wet").rglob("*.jpg"):
            idx.setdefault(p.stem, p)
        rows = json.loads((CCD_JSON / "winter_data_test_set.json").read_text(encoding="utf-8"))
        out = []
        for r in rows:
            p = idx.get(str(r.get("tileid", "")))
            t = {CCD_TO_3[k] for k in CCD_TO_3 if int(r.get(str(k), 0)) == 1}
            if p is not None and t:
                out.append((p, t))
        return out, "indo"
    if source == "kaggle":
        out = []
        for cdir, c in (("Bleached", "bleached"), ("Healthy", "healthy")):
            for p in (KAGGLE / "test" / cdir).glob("*"):
                if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
                    out.append((p, {c}))
        return out, "orig"
    if source == "orig_test":
        out = []
        for c in CLASSES:
            for p in (ROOT / "data" / "processed" / "bleaching" / "test" / c).glob("*"):
                if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
                    out.append((p, {c}))
        return out, "orig"
    raise SystemExit(f"未知 source {source}")


def macro(C):
    f1s = {}
    for t in CLASSES:
        tp, fn = C[t][t], sum(C[t][o] for o in CLASSES if o != t)
        fp = sum(C[o][t] for o in CLASSES if o != t)
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        f1s[t] = round(2 * pr * rc / (pr + rc), 4) if pr + rc else 0.0
    return sum(f1s.values()) / 3, f1s


def main():
    import torch
    from PIL import Image
    srcs = ["external", "winter", "kaggle", "orig_test"]
    if "--source" in sys.argv:
        srcs = [sys.argv[sys.argv.index("--source") + 1]]

    models, device = build()
    alt = ""
    if "--alt" in sys.argv:
        alt = sys.argv[sys.argv.index("--alt") + 1]
        models["indo"] = build_one(pathlib.Path(alt), device)
        print(f"  第二模型改为 {alt}")
    ccd, orig = calibration_sets()
    Ts = {}
    for k in MODELS:
        T1, n1 = fit_T(models[k][0], models[k][2], ccd, device)
        T2, n2 = fit_T(models[k][0], models[k][2], orig, device)
        Ts[k] = (T1, T2)
        print(f"  温度 {k}: Koh Tao 域 T={T1:.3f}(n={n1})   原始域 T={T2:.3f}(n={n2})")

    results = {}
    for src in srcs:
        items, true_dom = test_items(src)
        C_cal = {t: {c: 0 for c in CLASSES} for t in CLASSES}
        C_abs = {t: {c: 0 for c in CLASSES} for t in CLASSES}
        n_dec = n_abs = n_agree = 0
        with torch.no_grad():
            for p, truth in items:
                if not pathlib.Path(p).exists():
                    continue
                try:
                    img = Image.open(p).convert("RGB")
                except Exception:
                    continue
                probs = {}
                for k, (m, cls, tf) in models.items():
                    lg = m(tf(img).unsqueeze(0).to(device))[0]
                    T = Ts[k][0] if true_dom == "indo" else Ts[k][1]
                    probs[k] = (torch.softmax(lg / T, dim=0), cls)
                po, cl_o = probs["orig"]
                pi, cl_i = probs["indo"]
                io, ii = int(po.argmax()), int(pi.argmax())
                same = io == ii
                n_agree += int(same)
                ts = next((c for c in ("dead", "bleached", "healthy") if c in truth), None)
                if ts is None:
                    continue
                # 策略A：校准后置信度
                pick = "orig" if float(po.max()) >= float(pi.max()) else "indo"
                pred = (cl_o[io] if pick == "orig" else cl_i[ii])
                C_cal[ts][pred] += 1
                n_dec += 1
                # 策略B：分歧弃权（一致才算判定）
                if same:
                    C_abs[ts][cl_o[io]] += 1
                    n_abs += 1
        m_cal, f_cal = macro(C_cal)
        m_abs, f_abs = macro(C_abs)
        results[src] = {"trueDomain": true_dom, "samples": n_dec,
                        "agreement": round(n_agree / max(n_dec, 1), 4),
                        "tempCalibratedConfidence": {"macroF1": round(m_cal, 4), "perClass": f_cal},
                        "abstainOnDisagreement": {"macroF1": round(m_abs, 4), "perClass": f_abs,
                                                  "decided": n_abs, "coverage": round(n_abs / max(n_dec, 1), 4)}}
        print(f"\n{src}（真实域 {true_dom}，{n_dec} 张，两模型一致率 {n_agree/max(n_dec,1):.1%}）")
        print(f"  校准置信度仲裁: 宏F1={m_cal:.4f}")
        print(f"  分歧弃权:       宏F1={m_abs:.4f}（覆盖 {n_abs/max(n_dec,1):.1%}，"
              f"另有 {n_dec-n_abs} 张标记待复核）")

    (ROOT / "reports" / "router_arbitration.json").write_text(json.dumps({
        "task": "路由仲裁改进：温度校准置信度 + 分歧弃权",
        "temperatures": {k: {"kohTao": round(v[0], 4), "orig": round(v[1], 4)} for k, v in Ts.items()},
        "results": results,
        "baseline": {"domain策略": {"external": 0.4531, "winter": 0.5326, "kaggle": 0.5918, "orig_test": 0.8487},
                     "confidence策略": {"external": 0.4682, "winter": 0.5576, "kaggle": 0.6523, "orig_test": 0.7644},
                     "纯D2": {"external": 0.4476, "winter": 0.5397, "kaggle": 0.6485, "orig_test": 0.8910},
                     "纯C": {"external": 0.4826, "winter": 0.5445, "kaggle": 0.4183, "orig_test": 0.4253}},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n写入 reports/router_arbitration.json")


if __name__ == "__main__":
    main()
