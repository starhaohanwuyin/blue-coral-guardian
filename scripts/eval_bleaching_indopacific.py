"""在**印太域**（泰国 Koh Tao，CoralConditionDataset）上评本项目的白化三分类模型。

为什么需要：项目最大的已知短板是「印太域白化不可用」（跨域 top1 = 多数类基线 85.23%，
bleached 召回仅 42.31%）。本脚本把这条短板变成**可度量、可迭代**的指标：
先测出基线，后续做域自适应/LoRA 微调时用它对比，而不是靠感觉说"改好了"。

⚠️ 口径差异（必须随结论声明）：
  · 本模型输出的是**整图**三分类（bleached / dead / healthy）；
  · CoralConditionDataset 是**瓦片级多标签**（9 类，一个瓦片可同时有"健康"和"死亡"）；
  · 因此映射是近似的：「Compromised coral」≈ 受损（含白化但不限于白化）。
  故本脚本按**一对其余（one-vs-rest）**分别评估三类，而不是硬套单标签混淆矩阵。

前提：图像已下载（`python dl_ccd_images.py`）；本网络常无法直连 Google Drive，
      缺图像时脚本会明确报出阻塞原因，而不是抛一句看不懂的异常。

用法：
    python eval_bleaching_indopacific.py                  # 评夏季测试集
    python eval_bleaching_indopacific.py --split winter   # 评冬季测试集
    python eval_bleaching_indopacific.py --split train --limit 500
"""
import argparse
import json
from collections import defaultdict
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

CCD = ROOT / "data" / "raw" / "CoralConditionDataset"
LABELS = CCD / "CoralConditionDataset-main" / "code" / "datasets"
WEIGHTS = ROOT / "weights" / "bleaching_all" / "best.pt"
OUT = ROOT / "reports" / "bleaching_indopacific.json"

# 两种标签来源：
#   ① 主仓库 JSON（train/test/winter，瓦片多标签 0/1 九列）
#   ② external 包（label_coral_image_external.csv，patchid + 逗号分隔的类别号；
#      海域为 **Arafura / Darwin**（印尼—澳北），是我们最弱的域）
EXT_CSV = CCD / "external" / "label_coral_image_external.csv"
EXT_IMGS = CCD / "external" / "coral_image_external"

# CCD 9 类 → 本项目三分类（0/1 多标签）
CCD_TO_3 = {1: "healthy", 2: "bleached", 3: "dead"}
CCD_NAMES = {0: "Background", 1: "Healthy coral", 2: "Compromised coral", 3: "Dead coral",
             4: "Rubble", 5: "Competition", 6: "Disease", 7: "Predation", 8: "Physical issues"}
SPLIT_FILE = {"test": "test_set.json", "winter": "winter_data_test_set.json",
              "train": "train_set_fully_supervision.json"}


def image_index(dirs):
    """tileid → 图像路径（可给多个目录；文件名以 tileid 开头或以 tileid 命名）。"""
    idx = {}
    for d in dirs:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
                idx.setdefault(p.stem, p)
    return idx


def load_external():
    """读 external CSV → [(patchid, {三类真值})]，标签形如 "3,4"。"""
    import csv as _csv
    out = []
    if not EXT_CSV.exists():
        return out
    with EXT_CSV.open(newline="", encoding="utf-8-sig") as fh:
        for row in _csv.DictReader(fh):
            pid = (row.get("patchid") or "").strip()
            raw = (row.get("label") or "").strip().strip('"')
            if not pid:
                continue
            labs = [int(x) for x in raw.replace(" ", "").split(",") if x.isdigit()]
            truth = {CCD_TO_3[k] for k in labs if k in CCD_TO_3}
            out.append((pid, truth))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="external", choices=["external"] + list(SPLIT_FILE),
                    help="external = Arafura/Darwin 外部测试集（推荐，包小）；"
                         "test/winter/train = 泰国 Koh Tao 主仓库标签集")
    ap.add_argument("--limit", type=int, default=0, help="只评前 N 张（快速冒烟）")
    ap.add_argument("--weights", default="", help="换用其它权重（如微调后的 bleaching_all_koh_tao/best.pt）；"
                                                  "相对 coral_ml 或绝对路径均可")
    ap.add_argument("--offsets", default="", help="类别偏置 JSON（由 calibrate_bleaching_offsets.py 生成）；"
                                                  "在验证集上调、在此施加，用于修正「某类几乎不判」")
    ap.add_argument("--metric", default="single", choices=["single", "ovr"],
                    help="single=单标签（优先级 dead>bleached>healthy，与训练/项目其它评测一致，默认）；"
                         "ovr=多标签一对其余（额外视角，数值不可与单标签混用）")
    ap.add_argument("--out", default="",
                    help="报告输出路径（默认按权重目录名生成；多模型×多测试集对比时请显式指定，"
                         "否则同一权重在不同测试集上的报告会互相覆盖 —— 本脚本已踩过）")
    a = ap.parse_args()
    split = a.source

    global WEIGHTS, OUT
    if a.weights:
        w = pathlib.Path(a.weights)
        WEIGHTS = w if w.is_absolute() else (ROOT / w)
        OUT = ROOT / "reports" / f"bleaching_indopacific_{WEIGHTS.parent.name}.json"
        print(f"（使用指定权重：{WEIGHTS.relative_to(ROOT) if WEIGHTS.is_relative_to(ROOT) else WEIGHTS}）")
    if a.out:                      # 显式指定报告路径（多组合对比时必须，避免互相覆盖）
        OUT = pathlib.Path(a.out)
        if not OUT.is_absolute():
            OUT = ROOT / OUT

    if not WEIGHTS.exists():
        print(f"❌ 找不到权重 {WEIGHTS}\n   交付包里有：weights/bleaching_all/best.pt")
        return 2

    if split == "external":
        pairs = load_external()
        if not pairs or not EXT_IMGS.exists():
            print("❌ 缺少 external 包（Arafura/Darwin 印太外部测试集）。获取方式：\n")
            print("   该文件在 Google Drive（80 MB）：coral_image_external.zip")
            print("   ① python scripts/dl_ccd_images.py --external   （能上外网时直接下）")
            print(f"   ② 或手工解压到：{EXT_IMGS}")
            return 3
        idx = image_index([EXT_IMGS])
        rows = [{"tileid": pid, "_truth": truth} for pid, truth in pairs]
    else:
        lp = LABELS / SPLIT_FILE[split]
        if not lp.exists():
            print(f"❌ 找不到标签文件 {lp}")
            return 2
        idx = image_index([CCD / "images", CCD / "dry", CCD / "wet"])
        if not idx:
            print("❌ 主仓库图像未下载（Google Drive 的 coral_images_dry/wet）。")
            print("   先用 external 集：python eval_bleaching_indopacific.py --source external")
            return 3
        rows = json.loads(lp.read_text(encoding="utf-8"))

    if a.limit:
        rows = rows[: a.limit]
    print(f"印太域评测：source={split}（{len(rows)} 个样本，匹配到图像 {len(idx)} 张）")

    import torch
    from PIL import Image
    from torchvision import transforms
    from train import build_model  # 与项目官方评测同一套加载路径

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(WEIGHTS, map_location=device, weights_only=False)
    classes = [str(c).lower() for c in ck["classes"]]
    size = ck.get("img_size", 224)
    model = build_model(ck["backbone"], len(ck["classes"])).to(device)
    model.load_state_dict(ck["model"])
    model.eval()
    tf = transforms.Compose([
        transforms.Resize(int(size * 1.14)), transforms.CenterCrop(size),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
    print(f"模型: bleaching_all  骨干={ck['backbone']}  类别={classes}  输入={size}px  设备={device.type}")

    offs = None
    if a.offsets:
        op = pathlib.Path(a.offsets)
        if not op.is_absolute():
            op = ROOT / op
        od = json.loads(op.read_text(encoding="utf-8"))
        offs = torch.tensor([float(od["offsets"].get(c, 0.0)) for c in classes], device=device)
        print(f"类别偏置（调自验证集）: {od['offsets']}  ← {op.name}")

    # 统计容器：单标签口径（conf[pred][true]）+ 多标签一对其余（ovr）
    CONF = {"healthy": {}, "bleached": {}, "dead": {}}      # 只用于 single
    for t in CONF:
        CONF[t] = {c: 0 for c in ("healthy", "bleached", "dead")}
    stat = {c: {"tp": 0, "fp": 0, "fn": 0} for c in ("healthy", "bleached", "dead")}
    by_region = defaultdict(lambda: {c: {"tp": 0, "fp": 0, "fn": 0} for c in stat})
    truth_pos = {c: 0 for c in stat}
    n_done, n_missing, n_no_truth = 0, 0, 0
    unmatched = []

    def priority(truth: set):
        """多标签真值 → 单标签（优先级 dead > bleached > healthy），与训练口径一致。"""
        for c in ("dead", "bleached", "healthy"):
            if c in truth:
                return c
        return None

    with torch.no_grad():
        for r in rows:
            tid = str(r.get("tileid", ""))
            p = idx.get(tid)
            if p is None:
                n_missing += 1
                if len(unmatched) < 5:
                    unmatched.append(tid)
                continue
            try:
                img = Image.open(p).convert("RGB")
            except Exception:
                n_missing += 1
                continue
            x = tf(img).unsqueeze(0).to(device)
            logits = model(x)
            if offs is not None:
                logits = logits + offs
            pred = classes[int(logits.argmax(dim=1).item())]
            if "_truth" in r:
                truth = r["_truth"]
            else:
                truth = {CCD_TO_3[k] for k in CCD_TO_3 if int(r.get(str(k), 0)) == 1}
            t_single = priority(truth)
            if t_single is None:
                n_no_truth += 1
            else:
                CONF[t_single][pred] += 1
            region = "Arafura/Darwin" if split == "external" else split
            for c in stat:
                if pred == c and c in truth:
                    stat[c]["tp"] += 1
                    by_region[region][c]["tp"] += 1
                elif pred == c and c not in truth:
                    stat[c]["fp"] += 1
                    by_region[region][c]["fp"] += 1
                elif pred != c and c in truth:
                    stat[c]["fn"] += 1
                    by_region[region][c]["fn"] += 1
                if c in truth:
                    truth_pos[c] += 1
            n_done += 1

    if not n_done:
        print(f"❌ 一个瓦片都没匹配上图像（缺 {n_missing} 个）。示例 tileid: {unmatched}")
        print("   说明图像文件名与 tileid 不一致；请检查解压后的目录结构。")
        return 4

    print(f"\n已评 {n_done} 个样本（{n_missing} 个缺图像；{n_no_truth} 个无三类真值 · 已从单标签口径剔除）")

    # ① 单标签口径（与训练/项目其它评测一致）
    #    ⚠️ CONF 的索引是 CONF[真值][预测]：fn 必须取「真值为 t、预测为其它」= CONF[t][o]，
    #    fp 取「真值为其它、预测为 t」= CONF[o][t]。写反会把精确率与召回率互换（本脚本踩过）。
    cls3 = ("bleached", "dead", "healthy")
    single = {}
    for t in cls3:
        tp = CONF[t][t]
        fn = sum(CONF[t][o] for o in cls3 if o != t)
        fp = sum(CONF[o][t] for o in cls3 if o != t)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        single[t] = {"precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
                     "support": tp + fn}
    n_single = sum(v["support"] for v in single.values())
    acc = sum(CONF[t][t] for t in cls3) / n_single if n_single else 0.0
    macro_single = sum(v["f1"] for v in single.values()) / 3

    print("\n【单标签口径（主口径，与训练/项目其它评测一致）】")
    print(f"{'类别':<10}{'精确率':>9}{'召回':>9}{'F1':>9}{'真值数':>8}")
    for c in cls3:
        v = single[c]
        print(f"{c:<10}{v['precision']:>9.3f}{v['recall']:>9.3f}{v['f1']:>9.3f}{v['support']:>8}")
    print(f"宏平均 F1 = {macro_single:.4f}   准确率 = {acc:.4f}（{n_single} 个有单标签真值的样本）")

    # ② 多标签一对其余（附带视角，数值不可与单标签混用）
    print("\n【多标签一对其余（附带视角：瓦片可同时含健康与死亡）】")
    print(f"{'类别':<10}{'精确率':>9}{'召回':>9}{'F1':>9}{'真值数':>8}")
    out_stat = {}
    for c, s in stat.items():
        tp, fp, fn = s["tp"], s["fp"], s["fn"]
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        base = truth_pos[c] / n_done if n_done else 0.0
        out_stat[c] = {"precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
                       "tp": tp, "fp": fp, "fn": fn, "truthPositives": truth_pos[c],
                       "prevalence": round(base, 4)}
        print(f"{c:<10}{prec:>9.3f}{rec:>9.3f}{f1:>9.3f}{truth_pos[c]:>8}")
    macro = sum(v["f1"] for v in out_stat.values()) / 3
    print(f"宏平均 F1 = {macro:.4f}")

    if a.metric == "ovr":
        print("\n⚠️ 本次以 ovr 为准（--metric ovr）；与单标签数值**不可混用**。")
    print("\n判读：若某类**召回 ≈ 1、精确率 ≈ 该类的真值占比**，说明模型退化成「永远猜这一类」；"
          "白化类召回若明显低于其占比，说明该域白化基本识别不出来。")

    payload = {
        "task": "印太域白化三分类评测 —— 量化项目最大短板（印太域不可用）",
        "source": ("Arafura/Darwin 外部测试集（印尼—澳北，external 包）" if split == "external"
                   else ("泰国 Koh Tao **湿季**瓦片（winter_data_test_set，与训练用的干季不同季）"
                         if split == "winter" else
                         f"泰国 Koh Tao 主仓库标签集 split={split}")),
        "split": split, "samplesEvaluated": n_done, "missingImage": n_missing,
        "samplesWithoutThreeClass": n_no_truth,
        "model": {"weights": str(WEIGHTS), "backbone": ck["backbone"],
                  "classes": classes, "imgSize": size,
                  "offsets": ({c: float(offs[i]) for i, c in enumerate(classes)} if offs is not None else None)},
        "metric": a.metric,
        "singleLabel": {"perClass": single, "macroF1": round(macro_single, 4),
                        "accuracy": round(acc, 4), "samples": n_single,
                        "confusion": {t: dict(CONF[t]) for t in cls3},
                        "rule": "多标签真值按优先级 dead > bleached > healthy 取单标签（与训练一致）"},
        "oneVsRest": out_stat, "macroF1": round(macro, 4),
        "byRegion": {k: v for k, v in by_region.items()},
        "labelMapping": {"1": "healthy", "2": "bleached(≈Compromised coral)", "3": "dead"},
        "caveats": [
            "口径差异：本模型输出整图三分类；该数据集是瓦片级多标签（一个瓦片可同时含健康与死亡）",
            "「Compromised coral」≈ 受损（含白化但不限于白化），映射到 bleached 只是近似",
            "因此采用一对其余（one-vs-rest）评估，不与单标签混淆矩阵混用",
            "该域（Arafura/Darwin、Koh Tao）都不在项目 NOAA 网格内，未做热压力关联",
            "抽样偏差：external 集由数据集作者挑选，不代表该海域的随机抽样",
        ],
        "reference": {
            "inDomainTest": "同域 test top1 0.9150",
            "crossDomainTestIp": "跨域 test_ip top1 0.8523 = 多数类基线，bleached 召回 0.4231",
            "note": "本结果可与上面两条对比，看「换成印太实拍后」域偏移有多严重",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
