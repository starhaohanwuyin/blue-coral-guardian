"""
Model A 星地验证：分割模型 vs Reef Check Malaysia 实地 LCC
================================================================
目的：检验 Coralscapes 预训练分割模型在**印太（仙本那）**影像上的
      活珊瑚覆盖率估计是否与**实地调查**数量级一致。

对照基准（Reef Check Malaysia 2024 年度调查报告，Table: LCC by location）：
    North Borneo 区域平均活珊瑚覆盖 LCC = 39.56%
      Sabah Kapalai   20.50%    Sabah Mabul      22.29%
      Sabah Mataking  26.88%    Sabah Mantanani  33.00%
      Sabah Lahad Datu 35.69%   Sabah Pulau Penyu 39.31%
      Sabah Lankayan  49.53%    Sabah Larapan    58.50%

⚠️ 说明：iNat 照片是潜水员对着珊瑚近距离拍的，**天然偏向珊瑚主体**，
   因此模型估计的覆盖率预期**高于**实地样线 LCC（样线是等距抽样，包含大量沙/砾）。
   本实验主要验证「数量级一致」，而非精确相等。

用法：
    python validate_segment.py --dir data/semporna_photos --limit 180
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from segment_coral import CoralSegmenter, GROUP_CN  # noqa: E402

from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# 实地对照值（Reef Check Malaysia 2024）
FIELD_LCC = {
    "North Borneo 区域平均": 39.56,
    "Sabah Larapan": 58.50, "Sabah Lankayan": 49.53, "Sabah Pulau Penyu": 39.31,
    "Sabah Lahad Datu": 35.69, "Sabah Mantanani": 33.00, "Sabah Mataking": 26.88,
    "Sabah Mabul": 22.29, "Sabah Kapalai": 20.50,
}
IMG_EXT = {".jpg", ".jpeg", ".png"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    d = Path(args.dir)
    if not d.is_absolute():
        d = ROOT / d
    files = sorted(f for f in d.rglob("*") if f.suffix.lower() in IMG_EXT)[: args.limit]
    print(f"待评估图片: {len(files)} 张（{d}）")

    seg = CoralSegmenter(size=args.size)
    print(f"模型: Coralscapes SegFormer-B2  设备={seg.device}")

    alive, bleached, dead, algae, substrate = [], [], [], [], []
    per_img = []
    for i, f in enumerate(files, 1):
        try:
            img = Image.open(f)
            _, cls_frac, grp = seg.segment(img)
        except Exception as e:
            print(f"  [跳过] {f.name}: {type(e).__name__}")
            continue
        a = grp.get("alive", 0.0); b = grp.get("bleached", 0.0); dd = grp.get("dead", 0.0)
        alive.append(a); bleached.append(b); dead.append(dd)
        algae.append(grp.get("algae", 0.0)); substrate.append(grp.get("substrate", 0.0))
        per_img.append({"file": f.name, "alive": a, "bleached": b, "dead": dd,
                        "algae": grp.get("algae", 0.0), "substrate": grp.get("substrate", 0.0)})
        if i % 25 == 0:
            print(f"  {i}/{len(files)}  当前均值 活珊瑚={statistics.mean(alive):.1%}")

    n = len(alive)
    if n == 0:
        raise SystemExit("没有可用图片")

    def stat(x):
        x = sorted(x)
        return {"mean": statistics.mean(x), "median": statistics.median(x),
                "p25": x[len(x)//4], "p75": x[3*len(x)//4]}

    A, B, D, AL, S = stat(alive), stat(bleached), stat(dead), stat(algae), stat(substrate)
    coral_total = statistics.mean([a+b+d for a, b, d in zip(alive, bleached, dead)])

    print("\n" + "=" * 68)
    print(f"Model A 在仙本那照片上的估计（n={n}）")
    print("=" * 68)
    print(f"{'指标':<16}{'均值':>9}{'中位数':>10}{'P25':>9}{'P75':>9}")
    print("-" * 68)
    for name, s in (("活珊瑚%", A), ("白化珊瑚%", B), ("死亡珊瑚%", D),
                    ("藻类覆盖%", AL), ("沙/底质%", S)):
        print(f"{name:<16}{s['mean']:>9.2%}{s['median']:>10.2%}{s['p25']:>9.2%}{s['p75']:>9.2%}")
    print("-" * 68)
    print(f"{'珊瑚总覆盖%':<16}{coral_total:>9.2%}")
    if coral_total > 0:
        print(f"{'  其中白化占比':<14}{statistics.mean(bleached)/coral_total:>9.2%}")

    print("\n" + "=" * 68)
    print("对照：Reef Check Malaysia 2024 实地活珊瑚覆盖 (LCC)")
    print("=" * 68)
    for k, v in FIELD_LCC.items():
        print(f"  {k:<22}{v/100:>8.2%}")

    print("\n" + "=" * 68)
    print("结论")
    print("=" * 68)
    region = FIELD_LCC["North Borneo 区域平均"] / 100
    ratio = A["mean"] / region if region else float("nan")
    print(f"  模型估计活珊瑚均值 : {A['mean']:.2%}")
    print(f"  实地区域平均 LCC   : {region:.2%}")
    print(f"  比值               : {ratio:.2f}x")
    print(f"  实地各站点范围     : {min(FIELD_LCC.values())/100:.2%} – {max(FIELD_LCC.values())/100:.2%}")
    print(f"  模型估计落在实地区间内? {'是' if min(FIELD_LCC.values())/100 <= A['mean'] <= max(FIELD_LCC.values())/100 else '否'}")

    out = Path(args.out) if args.out else (ROOT / "reports" / "segment_validation.json")
    out.write_text(json.dumps({
        "n_images": n, "dir": str(d), "model": "EPFL-ECEO/segformer-b2-finetuned-coralscapes-1024-1024",
        "estimates": {"alive": A, "bleached": B, "dead": D, "algae": AL, "substrate": S,
                      "coral_total_mean": coral_total},
        "field_lcc": FIELD_LCC,
        "note": "iNat 照片偏向珊瑚主体，预期覆盖率高于实地样线 LCC，本实验验证数量级一致性",
        "per_image": per_img,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已写入: {out}")


if __name__ == "__main__":
    main()
