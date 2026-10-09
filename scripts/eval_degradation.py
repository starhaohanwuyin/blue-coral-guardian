"""
降质鲁棒性评估：模型在「模拟真实拍摄条件」下的表现曲线
================================================================
对每个降质档位（L0 原始 → L4 恶劣）分别评测：

  Model A（分割）  ：活珊瑚/白化/死亡占比估计是否稳定
  Model B（属分类） ：Top-1 准确率衰减（需已训练权重 + 标签）

输出一条「性能 vs 拍摄条件」的曲线，用于回答：
  「在志愿者随手拍的真实条件下，系统还准不准？」

用法：
    python eval_degradation.py --model a
    python eval_degradation.py --model b --labels data/inat/semporna.json
"""
import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

LEVELS = ["L0_clean", "L1_near", "L2_typical", "L3_far", "L4_harsh"]
LEVEL_DESC = {
    "L0_clean": "原始(iNat 条件)", "L1_near": "近距(3m/沿岸)",
    "L2_typical": "典型潜水(8m/沿岸)", "L3_far": "远距浑浊(15m)",
    "L4_harsh": "恶劣(20m/浑浊/手抖)",
}
IMG_EXT = {".jpg", ".jpeg", ".png"}


def eval_model_a(limit=None, model_dir=None, out_tag="base", use_enhance=False):
    from segment_coral import CoralSegmenter
    seg = CoralSegmenter(model_dir=model_dir or (ROOT / "weights" / "segformer_coralscapes"), size=1024)
    print(f"Model A[{out_tag}]  设备={seg.device}  权重={Path(model_dir).name if model_dir else 'segformer_coralscapes'}")
    print(f"  测试前色彩还原: {use_enhance}\n")

    rows = []
    for lv in LEVELS:
        d = ROOT / "data" / "degraded" / lv
        if not d.exists():
            print(f"[跳过] {lv} 不存在"); continue
        files = sorted(f for f in d.rglob("*") if f.suffix.lower() in IMG_EXT)
        if limit:
            files = files[:limit]
        alive, bleach, dead, algae, subs = [], [], [], [], []
        for f in files:
            try:
                im = Image.open(f)
                if use_enhance:
                    from uw_enhance import enhance
                    im = enhance(im, clahe=True)
                _, _, grp = seg.segment(im)
            except Exception:
                continue
            alive.append(grp.get("alive", 0.0)); bleach.append(grp.get("bleached", 0.0))
            dead.append(grp.get("dead", 0.0)); algae.append(grp.get("algae", 0.0))
            subs.append(grp.get("substrate", 0.0))
        if not alive:
            continue
        rows.append({
            "level": lv, "desc": LEVEL_DESC[lv], "n": len(alive),
            "alive": statistics.mean(alive), "bleached": statistics.mean(bleach),
            "dead": statistics.mean(dead), "algae": statistics.mean(algae),
            "substrate": statistics.mean(subs),
            "coral_total": statistics.mean([a + b + c for a, b, c in zip(alive, bleach, dead)]),
        })
        print(f"  {lv:<12} n={len(alive):<4} 活珊瑚={rows[-1]['alive']:.2%} "
              f"白化={rows[-1]['bleached']:.2%} 死亡={rows[-1]['dead']:.2%} "
              f"藻类={rows[-1]['algae']:.2%} 底质={rows[-1]['substrate']:.2%}")

    print("\n" + "=" * 92)
    print(f"{'档位':<12}{'条件':<20}{'活珊瑚%':>9}{'白化%':>8}{'死亡%':>8}{'藻类%':>8}{'底质%':>8}{'珊瑚总%':>9}{'活珊瑚Δ':>10}")
    print("=" * 92)
    base = rows[0]["alive"] if rows else 0
    for r in rows:
        print(f"{r['level']:<12}{r['desc']:<20}{r['alive']:>9.2%}{r['bleached']:>8.2%}"
              f"{r['dead']:>8.2%}{r['algae']:>8.2%}{r['substrate']:>8.2%}{r['coral_total']:>9.2%}"
              f"{(r['alive']-base):>+10.2%}")
    print("=" * 92)
    if len(rows) > 1:
        worst = min(rows, key=lambda r: r["alive"])
        drop = base - worst["alive"]
        print(f"\n结论：活珊瑚估计从 {base:.2%}（原始）变化到 {worst['alive']:.2%}"
              f"（{worst['level']}，{worst['desc']}），变化 {drop:+.2%}")
        print(f"      相对变化 {abs(drop)/base*100 if base else 0:.1f}%  → "
              f"{'鲁棒' if base and abs(drop)/base < 0.25 else '存在明显衰减，需域适配'}")

    out = ROOT / "reports" / f"degradation_modelA_{out_tag}.json"
    out.write_text(json.dumps({"model": "coralscapes-segformer-b2", "tag": out_tag,
                               "use_enhance": use_enhance, "rows": rows},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果: {out}")


def eval_model_b(labels_path, limit=None):
    """Model B（属分类）在降质集上的准确率。需要已训练的 weights/species_ip。"""
    import torch
    from torchvision import transforms
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from train import build_model

    wp = ROOT / "weights" / "species_ip" / "best.pt"
    if not wp.exists():
        raise SystemExit(f"未找到 {wp}，请先训练 Model B（流水线会产出）")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(wp, map_location=device, weights_only=False)
    classes = ck["classes"]
    size = ck.get("img_size", 320)
    model = build_model(ck["backbone"], len(classes)).to(device)
    model.load_state_dict(ck["model"]); model.eval()
    tf = transforms.Compose([
        transforms.Resize(int(size * 1.14)), transforms.CenterCrop(size),
        transforms.ToTensor(), transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

    # 从 iNat 记录建立 图片文件名 → 属 的映射（文件名形如 "<obsid>_<hash>.jpg"）
    import re
    sem = json.loads(Path(labels_path).read_text(encoding="utf-8"))
    obs2genus = {}
    for r in sem["records"]:
        nm = r.get("taxon_name") or ""
        nm = re.sub(r"\([^)]*\)", " ", nm)
        parts = [p for p in nm.split() if p and p[0].isupper()]
        obs2genus[str(r["id"])] = parts[0] if parts else nm

    print(f"Model B: {len(classes)} 类  设备={device}\n")
    rows = []
    for lv in LEVELS:
        d = ROOT / "data" / "degraded" / lv
        if not d.exists():
            continue
        files = sorted(f for f in d.rglob("*") if f.suffix.lower() in IMG_EXT)
        if limit:
            files = files[:limit]
        correct = total = 0
        with torch.no_grad():
            for f in files:
                obsid = f.stem.split("_")[0]
                g = obs2genus.get(obsid)
                if g not in classes:
                    continue
                try:
                    x = tf(Image.open(f).convert("RGB")).unsqueeze(0).to(device)
                    p = model(x).argmax(1).item()
                except Exception:
                    continue
                total += 1
                correct += int(classes[p] == g)
        if total:
            rows.append({"level": lv, "desc": LEVEL_DESC[lv], "n": total,
                         "acc": correct / total})
            print(f"  {lv:<12} n={total:<4} Top-1 = {rows[-1]['acc']:.2%}")

    print("\n" + "=" * 64)
    print(f"{'档位':<12}{'条件':<22}{'样本':>6}{'Top-1':>10}{'相对原始':>10}")
    print("=" * 64)
    base = rows[0]["acc"] if rows else 0
    for r in rows:
        print(f"{r['level']:<12}{r['desc']:<22}{r['n']:>6}{r['acc']:>10.2%}"
              f"{(r['acc']-base):>+10.2%}")
    print("=" * 64)

    out = ROOT / "reports" / "degradation_modelB.json"
    out.write_text(json.dumps({"model": "species_ip", "rows": rows},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果: {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=["a", "b"])
    ap.add_argument("--labels", default=str(ROOT / "data" / "inat" / "semporna.json"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model-dir", default=None, help="分割模型权重目录")
    ap.add_argument("--tag", default="base", help="结果文件名后缀，用于区分不同权重")
    ap.add_argument("--enhance", action="store_true", help="分割前先做色彩还原")
    args = ap.parse_args()
    if args.model == "a":
        eval_model_a(args.limit or None, args.model_dir, args.tag, args.enhance)
    else:
        eval_model_b(args.labels, args.limit or None)


if __name__ == "__main__":
    main()
