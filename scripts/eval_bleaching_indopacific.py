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
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

CCD = ROOT / "data" / "raw" / "CoralConditionDataset"
IMAGES = CCD / "images"
LABELS = CCD / "CoralConditionDataset-main" / "code" / "datasets"
WEIGHTS = ROOT / "weights" / "bleaching_all" / "best.pt"
OUT = ROOT / "reports" / "bleaching_indopacific.json"

# CCD 9 类 → 本项目三分类（0/1 多标签）
CCD_TO_3 = {1: "healthy", 2: "bleached", 3: "dead"}
CCD_NAMES = {0: "Background", 1: "Healthy coral", 2: "Compromised coral", 3: "Dead coral",
             4: "Rubble", 5: "Competition", 6: "Disease", 7: "Predation", 8: "Physical issues"}
SPLIT_FILE = {"test": "test_set.json", "winter": "winter_data_test_set.json",
              "train": "train_set_fully_supervision.json"}


def image_index():
    """tileid → 图像路径（文件名通常以 tileid 开头；也兼容放在子目录里）。"""
    idx = {}
    if not IMAGES.exists():
        return idx
    for p in IMAGES.rglob("*"):
        if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
            idx.setdefault(p.stem, p)
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test", choices=list(SPLIT_FILE))
    ap.add_argument("--limit", type=int, default=0, help="只评前 N 张（快速冒烟）")
    a = ap.parse_args()

    lp = LABELS / SPLIT_FILE[a.split]
    if not lp.exists():
        print(f"❌ 找不到标签文件 {lp}\n   请先跑：python analyze_ccd_indopacific.py（它会检查数据是否就位）")
        return 2
    if not WEIGHTS.exists():
        print(f"❌ 找不到权重 {WEIGHTS}\n   交付包里有：weights/bleaching_all/best.pt")
        return 2

    idx = image_index()
    if not idx:
        print("❌ 没找到 CoralConditionDataset 的图像，因此**无法评测**。阻塞原因与解决办法：\n")
        print("   该数据集图像放在 Google Drive（coral_images.zip），本机网络通常直连不了。")
        print("   ① 跑 `python dl_ccd_images.py` 看连通性；能通就直接下")
        print(f"   ② 或在能上外网的机器上下载后解压到：{IMAGES}")
        print("   ③ 或让队友把他下载好的 zip 发你，解压到同一路径")
        print("\n   注意：**标签与元数据已经可用**（analyze_ccd_indopacific.py 已出报告），"
              "只有模型评测与域适配需要图像。")
        return 3

    rows = json.loads(lp.read_text(encoding="utf-8"))
    if a.limit:
        rows = rows[: a.limit]
    print(f"印太域评测：{a.split}（{len(rows)} 个瓦片）  图像目录 {IMAGES}")

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

    # 一对其余统计
    stat = {c: {"tp": 0, "fp": 0, "fn": 0} for c in ("healthy", "bleached", "dead")}
    n_done, n_missing = 0, 0
    unmatched = []
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
            pred = classes[int(model(x).argmax(dim=1).item())]
            truth = {CCD_TO_3[k] for k in CCD_TO_3 if int(r.get(str(k), 0)) == 1}
            for c in stat:
                if pred == c and c in truth:
                    stat[c]["tp"] += 1
                elif pred == c and c not in truth:
                    stat[c]["fp"] += 1
                elif pred != c and c in truth:
                    stat[c]["fn"] += 1
            n_done += 1

    if not n_done:
        print(f"❌ 一个瓦片都没匹配上图像（缺 {n_missing} 个）。示例 tileid: {unmatched}")
        print("   说明图像文件名与 tileid 不一致；请检查解压后的目录结构。")
        return 4

    print(f"\n已评 {n_done} 个瓦片（{n_missing} 个缺图像）")
    print(f"{'类别':<10}{'精确率':>9}{'召回':>9}{'F1':>9}{'TP/FP/FN':>16}")
    out_stat = {}
    for c, s in stat.items():
        tp, fp, fn = s["tp"], s["fp"], s["fn"]
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        out_stat[c] = {"precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
                       "tp": tp, "fp": fp, "fn": fn}
        print(f"{c:<10}{prec:>9.3f}{rec:>9.3f}{f1:>9.3f}{f'{tp}/{fp}/{fn}':>16}")
    macro = sum(v["f1"] for v in out_stat.values()) / 3
    print(f"宏平均 F1 = {macro:.4f}")

    payload = {
        "task": "印太域（泰国 Koh Tao）白化三分类评测 —— 量化项目最大短板",
        "split": a.split, "tilesEvaluated": n_done, "tilesMissingImage": n_missing,
        "model": {"weights": "weights/bleaching_all/best.pt", "backbone": ck["backbone"],
                  "classes": classes, "imgSize": size},
        "oneVsRest": out_stat, "macroF1": round(macro, 4),
        "labelMapping": {"1": "healthy", "2": "bleached(≈Compromised coral)", "3": "dead"},
        "caveats": [
            "口径差异：本模型输出整图三分类；本数据集是瓦片级多标签（一个瓦片可同时含健康与死亡）",
            "「Compromised coral」≈ 受损（含白化但不限于白化），映射到 bleached 只是近似",
            "因此采用一对其余（one-vs-rest）评估，不与单标签混淆矩阵混用",
            "该站点（10.06N, 99.83E）不在项目 NOAA 网格内，未做热压力关联",
        ],
        "reference": {
            "inDomainBleachingIpTest": "同域 test top1 0.9150",
            "crossDomainBleachingIpTestIp": "跨域 top1 0.8523 = 多数类基线，bleached 召回 0.4231",
            "note": "本脚本给的是**印太实拍瓦片**上的指标，可与上面两条对比看域偏移",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
