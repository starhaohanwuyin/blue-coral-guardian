"""
站点级星地验证（把"聚合一致"升级为"站点级一致"）
================================================================
当前验证的弱点：
    只比了**区域平均**（模型 39.71% vs RCM 39.56%）。
    两个平均值接近，可能是巧合；**并未证明模型能区分不同站点**。

本脚本用 iNaturalist 的 `place_guess` 字段把仙本那照片按站点分组，
再与 Reef Check Malaysia 2024 的**分站点实测 LCC** 对比：

    Mabul     19 张  vs 实地 22.29%
    Mataking   9 张  vs 实地 26.88%
    Kapalai    6 张  vs 实地 20.50%
    Larapan    3 张  vs 实地 58.50%

产出：
  · 站点级模型估计 vs 实地 LCC
  · Pearson / Spearman 相关
  · MAE / RMSE / 偏差
  · 站点排序一致性（模型能否区分"最严重"的站点）

⚠️ 样本量小（3–19 张/站点），结论按"方向性"表述，不做强断言。

用法：
    python validate_site_level.py
    python validate_site_level.py --min-n 2
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from segment_coral import CoralSegmenter  # noqa: E402

# Reef Check Malaysia 2024 实地活珊瑚覆盖 LCC（%）
FIELD_LCC = {
    "Mabul": 22.29, "Mataking": 26.88, "Kapalai": 20.50, "Larapan": 58.50,
    "Mantanani": 33.00, "Lankayan": 49.53, "Pulau Penyu": 39.31,
    "Lahad Datu": 35.69, "Sipadan": None, "Pom Pom": None, "Timba Timba": None,
    "Pandanan": None, "Si Amil": None, "Mantabuan": None,
}

# place_guess 中的地点关键词 → 规范站点名
SITE_PATTERNS = [
    (r"mabul|seaventures", "Mabul"),
    (r"kapalai", "Kapalai"),
    (r"mataking", "Mataking"),
    (r"larapan", "Larapan"),
    (r"mantanani", "Mantanani"),
    (r"lankayan", "Lankayan"),
    (r"penyu", "Pulau Penyu"),
    (r"lahad\s*datu", "Lahad Datu"),
    (r"sipadan", "Sipadan"),
    (r"pom\s*pom", "Pom Pom"),
    (r"timba", "Timba Timba"),
    (r"pandanan", "Pandanan"),
    (r"si\s*amil", "Si Amil"),
    (r"mantabuan", "Mantabuan"),
]


def site_of(place: str):
    if not place:
        return None
    p = place.lower()
    for pat, name in SITE_PATTERNS:
        if re.search(pat, p):
            return name
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-n", type=int, default=2, help="站点最少照片数")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    # ---- 1. 按站点分组照片 ----
    data = json.loads((ROOT / "data" / "inat" / "semporna.json").read_text(encoding="utf-8"))
    photo_dir = ROOT / "data" / "semporna_photos"
    by_site = defaultdict(list)
    unmatched = 0
    for r in data["records"]:
        s = site_of(r.get("place_guess") or "")
        if s is None:
            unmatched += 1
            continue
        for ph in r.get("photos", [])[:1]:
            # 文件名规则与 download 脚本一致：{obsid}_{hash}.jpg
            cands = list(photo_dir.glob(f"{r['id']}_*.jpg"))
            if cands:
                by_site[s].extend(cands[:1])
    print(f"按站点分组：{len(by_site)} 个站点，未匹配地点 {unmatched} 条观察")
    for s in sorted(by_site):
        print(f"  {s:<14} {len(by_site[s]):>4} 张")

    # ---- 2. 跑分割模型 ----
    seg = CoralSegmenter(size=args.size)
    print(f"\n分割模型设备: {seg.device}\n")
    stats = {}
    for s, files in sorted(by_site.items()):
        if len(files) < args.min_n:
            continue
        alive, coral = [], []
        for f in files:
            try:
                _, _, grp = seg.segment(Image.open(f))
            except Exception:
                continue
            alive.append(grp.get("alive", 0.0))
            coral.append(grp.get("alive", 0.0) + grp.get("bleached", 0.0) + grp.get("dead", 0.0))
        if not alive:
            continue
        stats[s] = {"n": len(alive), "aliveMean": float(np.mean(alive)),
                    "aliveStd": float(np.std(alive)),
                    "coralTotalMean": float(np.mean(coral)),
                    "fieldLCC": FIELD_LCC.get(s)}

    # ---- 3. 对比 ----
    print("=" * 84)
    print("站点级对比：模型估计 vs Reef Check Malaysia 实地 LCC")
    print("=" * 84)
    print(f"{'站点':<14}{'照片数':>7}{'模型活珊瑚':>12}{'标准差':>10}{'实地LCC':>10}{'差值':>10}")
    print("-" * 84)
    pairs = []
    for s in sorted(stats, key=lambda x: -(stats[x]["fieldLCC"] or 0)):
        v = stats[s]
        f = v["fieldLCC"]
        diff = (v["aliveMean"] * 100 - f) if f is not None else None
        print(f"{s:<14}{v['n']:>7}{v['aliveMean']:>12.2%}{v['aliveStd']:>10.2%}"
              + (f"{f:>9.2f}%" if f is not None else f"{'—':>10}")
              + (f"{diff:>+9.2f}" if diff is not None else f"{'—':>10}"))
        if f is not None:
            pairs.append((s, v["aliveMean"] * 100, f, v["n"]))
    print("-" * 84)

    if len(pairs) >= 2:
        m = np.array([p[1] for p in pairs])
        f = np.array([p[2] for p in pairs])
        n = np.array([p[3] for p in pairs])
        print("\n" + "=" * 84)
        print("一致性统计")
        print("=" * 84)
        bias = m.mean() - f.mean()
        mae = np.abs(m - f).mean()
        rmse = np.sqrt(((m - f) ** 2).mean())
        print(f"  站点数            : {len(pairs)}")
        print(f"  照片数            : {int(n.sum())}")
        print(f"  模型均值          : {m.mean():.2f}%")
        print(f"  实地均值          : {f.mean():.2f}%")
        print(f"  平均偏差 (bias)   : {bias:+.2f} 个百分点")
        print(f"  MAE               : {mae:.2f} 个百分点")
        print(f"  RMSE              : {rmse:.2f} 个百分点")

        # 相关
        if len(pairs) >= 2 and m.std() > 0 and f.std() > 0:
            r = float(np.corrcoef(m, f)[0, 1])
            print(f"  Pearson r         : {r:+.3f}")
            from scipy.stats import spearmanr  # 可能未安装
        try:
            from scipy.stats import spearmanr
            rho, pval = spearmanr(m, f)
            print(f"  Spearman ρ        : {rho:+.3f}  (p={pval:.3f})")
        except Exception:
            # 手算 Spearman
            def rank(x):
                order = np.argsort(np.argsort(x))
                return order
            rs = float(np.corrcoef(rank(m), rank(f))[0, 1])
            print(f"  Spearman ρ        : {rs:+.3f}（scipy 未安装，手算秩相关）")

        # 排序一致性（模型能否识别"最严重"的站点）
        worst_model = pairs[int(np.argmax(m))][0]
        worst_field = pairs[int(np.argmax(f))][0]
        print(f"\n  最严重站点（模型判定）: {worst_model}")
        print(f"  最严重站点（实地）    : {worst_field}")
        print(f"  排序顶端一致: {'✅ 是' if worst_model == worst_field else '❌ 否'}")
        order_ok = sum(1 for i in range(len(pairs)) for j in range(i + 1, len(pairs))
                       if (m[i] - m[j]) * (f[i] - f[j]) > 0)
        total_pairs = len(pairs) * (len(pairs) - 1) // 2
        print(f"  排序一致对: {order_ok}/{total_pairs}")

        print(f"\n  ⚠️ 每站点仅 {int(n.min())}–{int(n.max())} 张照片，结论按**方向性**表述，不做强断言。")
        result = {"nSites": len(pairs), "nPhotos": int(n.sum()),
                  "modelMean": float(m.mean()), "fieldMean": float(f.mean()),
                  "bias": float(bias), "mae": float(mae), "rmse": float(rmse),
                  "pearson": float(np.corrcoef(m, f)[0, 1]) if m.std() > 0 and f.std() > 0 else None,
                  "orderConsistent": int(order_ok), "orderTotal": int(total_pairs),
                  "sites": [{"site": s, "n": int(nn), "model": float(mm), "field": float(ff)}
                            for (s, mm, ff, nn) in pairs]}
    else:
        result = {"error": "可比站点不足", "stats": stats}
        print("\n⚠️ 与实地数据可比的站点不足，仅输出模型侧统计")

    out = Path(args.out) if args.out else (ROOT / "reports" / "site_level_validation.json")
    out.write_text(json.dumps({
        "method": "按 iNaturalist place_guess 分组，与 RCM 2024 分站点 LCC 对比",
        "fieldSource": "Reef Check Malaysia 2024 (DOI 10.5281/zenodo.15290515)",
        "allSites": stats, "comparison": result,
        "caveat": "站点样本量小（3–19 张），仅作方向性验证",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果: {out}")


if __name__ == "__main__":
    main()
