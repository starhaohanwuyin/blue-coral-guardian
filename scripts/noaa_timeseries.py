"""
NOAA 热压力时间序列分析
================================================================
把 2024 白化事件放进多年背景，回答：
  「2024 是不是异常年份？异常到什么程度？」

统计每年：
  · 最大 DHW / 最大 HotSpot
  · DHW≥4（白化预警）、DHW≥8（严重白化）的天数
  · 最高 BAA 预警等级、各等级持续天数

用法：
    python noaa_timeseries.py
    python noaa_timeseries.py --years 2023 2024 2025
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "noaa"
BAA_CN = {0: "无压力", 1: "白化观察", 2: "白化警告", 3: "白化警报一级", 4: "白化警报二级"}


def load(p):
    rows = []
    with p.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                rows.append((row["time"][:10], float(row.get("CRW_DHW") or 0),
                             float(row.get("CRW_HOTSPOT") or 0),
                             int(float(row.get("CRW_BAA") or 0))))
            except (ValueError, TypeError):
                continue
    return rows


def year_stats(rows):
    """按格点-日期聚合后取区域最大。"""
    by_day = defaultdict(lambda: {"dhw": 0.0, "hs": 0.0, "baa": 0})
    for t, dhw, hs, baa in rows:
        d = by_day[t]
        d["dhw"] = max(d["dhw"], dhw)
        d["hs"] = max(d["hs"], hs)
        d["baa"] = max(d["baa"], baa)
    days = sorted(by_day)
    dhw_max = max(by_day[t]["dhw"] for t in days) if days else 0
    hs_max = max(by_day[t]["hs"] for t in days) if days else 0
    baa_max = max(by_day[t]["baa"] for t in days) if days else 0
    return {
        "days": len(days),
        "dhwMax": round(dhw_max, 2),
        "hotspotMax": round(hs_max, 2),
        "baaMax": baa_max,
        "baaMaxLabel": BAA_CN.get(baa_max, "?"),
        "daysDhwGe4": sum(1 for t in days if by_day[t]["dhw"] >= 4),
        "daysDhwGe8": sum(1 for t in days if by_day[t]["dhw"] >= 8),
        "daysByBaa": {BAA_CN[i]: sum(1 for t in days if by_day[t]["baa"] == i) for i in range(5)},
        "peakDate": max(days, key=lambda t: by_day[t]["dhw"]) if days else None,
        "monthlyDhwMax": {m: round(max((by_day[t]["dhw"] for t in days
                                        if t[5:7] == f"{m:02d}"), default=0), 2)
                          for m in range(1, 13)},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="*", type=int, default=None)
    args = ap.parse_args()

    if args.years:
        years = args.years
    else:
        years = sorted(int(p.stem.split("_")[-1]) for p in CACHE.glob("CRW_semporna_*.csv"))

    if not years:
        raise SystemExit("没有缓存数据，请先运行 cache_noaa.py")

    stats = {}
    print("=" * 84)
    print("NOAA CRW 热压力年度对比（仙本那海域 4.0–5.0°N, 118.0–119.5°E）")
    print("=" * 84)
    print(f"{'年份':<8}{'最大DHW':>10}{'最大HS':>9}{'最高预警':>18}"
          f"{'DHW≥4天':>10}{'DHW≥8天':>10}{'峰值日':>14}")
    print("-" * 84)
    for y in years:
        p = CACHE / f"CRW_semporna_{y}.csv"
        if not p.exists():
            print(f"{y:<8}{'（未缓存）':>10}")
            continue
        s = year_stats(load(p))
        stats[y] = s
        print(f"{y:<8}{s['dhwMax']:>10.2f}{s['hotspotMax']:>9.2f}"
              f"{s['baaMaxLabel']:>18}{s['daysDhwGe4']:>10}{s['daysDhwGe8']:>10}"
              f"{str(s['peakDate']):>14}")
    print("=" * 84)

    if stats:
        best = max(stats.items(), key=lambda kv: kv[1]["dhwMax"])
        print(f"\n【结论】热压力最高的年份：{best[0]}（最大 DHW {best[1]['dhwMax']}，"
              f"预警等级 {best[1]['baaMaxLabel']}）")
        if len(stats) > 1:
            others = [v["dhwMax"] for k, v in stats.items() if k != best[0]]
            avg = sum(others) / len(others)
            print(f"        其余年份平均最大 DHW {avg:.2f} → {best[0]} 高出 "
                  f"{(best[1]['dhwMax']/avg-1)*100 if avg else 0:.0f}%")
        print("\n  月度最大 DHW 分布：")
        print(f"    {'年':<6}" + "".join(f"{m:>7}月" for m in range(1, 13)))
        for y, s in stats.items():
            print(f"    {y:<6}" + "".join(f"{s['monthlyDhwMax'][m]:>8.1f}" for m in range(1, 13)))

    out = ROOT / "reports" / "noaa_timeseries.json"
    out.write_text(json.dumps({
        "region": "Semporna 4.0-5.0N, 118.0-119.5E",
        "source": "NOAA CRW v3.1 5km via PacIOOS mirror",
        "years": stats,
        "baaLevels": BAA_CN,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果: {out}")


if __name__ == "__main__":
    main()
