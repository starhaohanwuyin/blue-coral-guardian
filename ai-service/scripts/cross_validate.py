"""
星地交叉验证：NOAA 卫星热压力 vs Reef Check Malaysia 实地白化观测
================================================================
数据：
  · 卫星：data/noaa/CRW_semporna_YYYY.csv（NOAA CRW v3.1，5km，日尺度）
    变量：CRW_DHW（热压力累积）、CRW_HOTSPOT、CRW_SSTANOMALY、CRW_BAA（白化预警等级）
  · 实地：Reef Check Malaysia 2024 年度报告（DOI 10.5281/zenodo.15290515）
    仙本那海域 4 个站位的白化率、死亡率与 DHW

验证目标：
  1. 卫星 DHW 的**区域峰值**是否达到白化阈值（DHW≥4 为白化预警，≥8 为严重白化）
  2. **站点排序一致性**：卫星在 Mabul 与 Larapan 的 DHW 高低，是否与实地一致
  3. BAA 预警等级出现的时间与空间范围

用法：
    python cross_validate.py --year 2024
"""
import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "noaa"

# Reef Check Malaysia 2024 报告：仙本那海域实地数据
# (站点名, 纬度, 经度, 实地DHW, 白化率%, 死亡率%)
FIELD_SITES = [
    ("Larapan Point 3", 4.550, 118.760, 9.4, 69.2, 15.4),
    ("Larapan SMEE 2", 4.548, 118.755, 9.4, 8.7, 4.4),
    ("Mabul Eel Garden", 4.235, 118.630, 6.5, 4.6, 27.3),
    ("Mabul Panglima", 4.243, 118.660, 6.5, 15.4, 26.9),
]

BAA_CN = {0: "无压力", 1: "白化观察", 2: "白化警告", 3: "白化警报一级", 4: "白化警报二级"}


def load_year(year):
    p = CACHE / f"CRW_semporna_{year}.csv"
    if not p.exists():
        raise SystemExit(f"缺少 {p}，请先运行 cache_noaa.py")
    rows = []
    with p.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                rows.append({
                    "time": row["time"][:10],
                    "lat": float(row["latitude"]),
                    "lon": float(row["longitude"]),
                    "dhw": float(row.get("CRW_DHW") or 0),
                    "hs": float(row.get("CRW_HOTSPOT") or 0),
                    "ssta": float(row.get("CRW_SSTANOMALY") or 0),
                    "baa": int(float(row.get("CRW_BAA") or 0)),
                })
            except (ValueError, TypeError):
                continue
    return rows


def nearest(rows, lat, lon):
    """返回距目标坐标最近格点的全部序列。"""
    ks = {(r["lat"], r["lon"]) for r in rows}
    k = min(ks, key=lambda x: (x[0] - lat) ** 2 + (x[1] - lon) ** 2)
    return [r for r in rows if (r["lat"], r["lon"]) == k], k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    args = ap.parse_args()

    rows = load_year(args.year)
    print(f"载入 {args.year} 年 NOAA CRW 数据: {len(rows)} 条")
    days = sorted({r["time"] for r in rows})
    cells = {(r["lat"], r["lon"]) for r in rows}
    print(f"  时间跨度: {days[0]} → {days[-1]}（{len(days)} 天）")
    print(f"  空间格点: {len(cells)} 个")

    # ---- 区域整体峰值 ----
    peak_dhw = max(r["dhw"] for r in rows)
    peak_day = [r for r in rows if r["dhw"] == peak_dhw][0]
    print("\n" + "=" * 74)
    print("【区域热压力峰值】")
    print("=" * 74)
    print(f"  最大 DHW : {peak_dhw:.2f}   出现在 {peak_day['time']} "
          f"({peak_day['lat']:.3f}°N, {peak_day['lon']:.3f}°E)")
    print(f"  最大 HotSpot : {max(r['hs'] for r in rows):.2f} °C")
    print(f"  最大 SSTA    : {max(r['ssta'] for r in rows):.2f} °C")
    baa_max = max(r["baa"] for r in rows)
    print(f"  最高预警等级 : {baa_max} = {BAA_CN.get(baa_max, '?')}")

    # 各预警等级首次出现日期
    print("\n  各预警等级首次出现:")
    for lvl in range(1, 5):
        ds = sorted({r["time"] for r in rows if r["baa"] >= lvl})
        if ds:
            print(f"    BAA≥{lvl} ({BAA_CN[lvl]:<10}): {ds[0]} 起（共 {len(ds)} 天）")
        else:
            print(f"    BAA≥{lvl} ({BAA_CN[lvl]:<10}): 未出现")

    # ---- 站点级对比 ----
    print("\n" + "=" * 74)
    print("【站点级对比：卫星 vs 实地】")
    print("=" * 74)
    print(f"{'站点':<20}{'实地DHW':>9}{'卫星DHW峰':>11}{'卫星HS峰':>10}{'BAA峰':>7}"
          f"{'实地白化%':>10}{'实地死亡%':>10}")
    print("-" * 74)
    site_rows = []
    for name, lat, lon, fdhw, bleach, mort in FIELD_SITES:
        seq, k = nearest(rows, lat, lon)
        sdhw = max(r["dhw"] for r in seq)
        shs = max(r["hs"] for r in seq)
        sbaa = max(r["baa"] for r in seq)
        site_rows.append({"site": name, "lat": k[0], "lon": k[1], "fieldDhw": fdhw,
                          "satDhwPeak": round(sdhw, 2), "satHotspotPeak": round(shs, 2),
                          "satBaaPeak": sbaa, "fieldBleachPct": bleach, "fieldMortalityPct": mort})
        print(f"{name:<20}{fdhw:>9.1f}{sdhw:>11.2f}{shs:>10.2f}{sbaa:>7}"
              f"{bleach:>10.1f}{mort:>10.1f}")
    print("-" * 74)

    # ---- 一致性检验 ----
    print("\n" + "=" * 74)
    print("【一致性检验】")
    print("=" * 74)
    fmax = max(s["fieldDhw"] for s in site_rows)
    smax = max(s["satDhwPeak"] for s in site_rows)
    print(f"  ① 量级一致：实地最大 DHW {fmax:.1f}  vs  卫星最大 DHW {smax:.2f}  "
          f"→ 比值 {smax/fmax:.2f}×")

    # 排序一致性：Larapan(高) vs Mabul(低)
    lar = [s for s in site_rows if s["site"].startswith("Larapan")]
    mab = [s for s in site_rows if s["site"].startswith("Mabul")]
    if lar and mab:
        f_lar = statistics.mean(s["fieldDhw"] for s in lar)
        f_mab = statistics.mean(s["fieldDhw"] for s in mab)
        s_lar = statistics.mean(s["satDhwPeak"] for s in lar)
        s_mab = statistics.mean(s["satDhwPeak"] for s in mab)
        ok = (f_lar > f_mab) == (s_lar > s_mab)
        print(f"  ② 站点排序：实地 Larapan {f_lar:.1f} > Mabul {f_mab:.1f}；"
              f"卫星 Larapan {s_lar:.2f} vs Mabul {s_mab:.2f}")
        print(f"     → 排序一致: {'✅ 是' if ok else '❌ 否'}")

    # 白化率与卫星热压力的相关性（站点级，n=4）
    bl = [s["fieldBleachPct"] for s in site_rows]
    sd = [s["satDhwPeak"] for s in site_rows]
    if len(bl) >= 3:
        mb, ms = statistics.mean(bl), statistics.mean(sd)
        num = sum((a - mb) * (b - ms) for a, b in zip(bl, sd))
        den = (sum((a - mb) ** 2 for a in bl) * sum((b - ms) ** 2 for b in sd)) ** 0.5
        corr = num / den if den else 0
        print(f"  ③ 实地白化率 vs 卫星 DHW 的 Pearson 相关: r = {corr:.3f}  (n={len(bl)})")
        print(f"     ⚠️ n=4 样本极小，相关系数仅供方向性参考，不具统计显著性")

    print("\n  ④ 阈值判定：白化预警阈值为 DHW≥4，严重白化为 DHW≥8")
    for s in site_rows:
        lvl = ("严重白化" if s["satDhwPeak"] >= 8 else
               "白化预警" if s["satDhwPeak"] >= 4 else "未达阈值")
        print(f"     {s['site']:<20} 卫星DHW {s['satDhwPeak']:>5.2f} → {lvl}"
              f"   （实地白化 {s['fieldBleachPct']}%）")

    out = ROOT / "reports" / f"cross_validation_{args.year}.json"
    out.write_text(json.dumps({
        "year": args.year, "source": "NOAA CRW v3.1 5km (PacIOOS mirror)",
        "fieldSource": "Reef Check Malaysia 2024 (DOI 10.5281/zenodo.15290515)",
        "regionPeak": {"dhw": round(peak_dhw, 2), "date": peak_day["time"],
                       "lat": peak_day["lat"], "lon": peak_day["lon"],
                       "hotspotMax": round(max(r["hs"] for r in rows), 2),
                       "sstaMax": round(max(r["ssta"] for r in rows), 2),
                       "baaMax": baa_max, "baaMaxLabel": BAA_CN.get(baa_max)},
        "sites": site_rows,
        "note": "卫星格点 5km，与站位存在空间尺度差异；n=4 时相关性仅供方向参考",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果: {out}")


if __name__ == "__main__":
    main()
