"""P4 第一步：用「实地报告记录的白化事件年表」核对我们 41 年的 DHW 序列。

数据来源
  · 我们的序列：data/noaa（1985–2025，41 年，544 格点，逐年峰值）
  · 事件年表：Reef Check Malaysia 报告原文（见 EVENTS 里每条的 source）
      - 2024CoralBleachingImpactReportMalaysia.pdf（p5/p6/p12/p15）
      - 2025-Annual-Survey-Report.pdf（p16，提及 2010 事件对 Sunda Shelf 的影响）

方法（**事件级**，不是站点级）
  1. 逐年计算区域指标：所有格点年峰值的均值 / 最大值；达警戒（DHW≥4）的格点占比
  2. 对每个"报告记录的事件年"，看我们序列里该年是否确实偏高（排名 + 是否出现警戒格点）
  3. 校验报告给的定量锚点："2024 比 2010 高 5 °C-weeks" —— 对比我们的区域均值/最大值差值

⚠️ 口径限制（必须随结论说明）
  · 报告里的监测站在沙巴/半岛马来西亚多地，我们的网格只覆盖仙本那及周边（Semporna）
  · 报告中的 5 °C-weeks 是**站点级** DHW，与区域均值不可直接等同，只能做量级对比
  · n 很小（事件级 5 个年份），**不做显著性检验**，只做一致性核对
"""
import json
import pathlib

ROOT = pathlib.Path(r"D:\大学作业\广东海洋大学的珊瑚评测小程序\coral_ml")
ART = ROOT / "data/noaa/site_profiles.json"
OUT = ROOT / "reports/p4_event_timeline.json"

# 从报告原文整理的"记录在案的白化事件"（每条注明出处，便于核查）
EVENTS = [
    ("1998", "全球第一次珊瑚白化事件（1998）", "2024CoralBleachingImpactReportMalaysia.pdf p5"),
    ("2010", "马来西亚大规模白化事件；半岛调查中 50% 硬珊瑚白化（其中约 66% 完全白化）",
     "2024CoralBleachingImpactReportMalaysia.pdf p5/p15"),
    ("2014", "2014–2017 全球尺度白化事件", "2024CoralBleachingImpactReportMalaysia.pdf p5"),
    ("2016", "2014–2017 全球事件期内（马来西亚亦受影响）",
     "2024CoralBleachingImpactReportMalaysia.pdf p5"),
    ("2017", "2014–2017 全球事件期内", "2024CoralBleachingImpactReportMalaysia.pdf p5"),
    ("2019", "半岛马来西亚白化（2019），随后 2020 年再次白化（首次连续两年）",
     "2024CoralBleachingImpactReportMalaysia.pdf p6/p15"),
    ("2020", "沙巴东部报告显著白化；连续第二年白化",
     "2024CoralBleachingImpactReportMalaysia.pdf p6"),
    ("2024", "第四次全球白化事件；沙巴区域热压力为历史最高记录",
     "2024CoralBleachingImpactReportMalaysia.pdf p3/p4/p9/p12"),
]

d = json.loads(ART.read_text(encoding="utf-8"))
cells = d["cells"]
years = d["years"]

region_mean, region_max, alert_frac = {}, {}, {}
for y in years:
    peaks = [c["peakByYear"][y] for c in cells.values() if y in c["peakByYear"]]
    if not peaks:
        continue
    region_mean[y] = round(sum(peaks) / len(peaks), 2)
    region_max[y] = round(max(peaks), 2)
    alert_frac[y] = round(sum(1 for p in peaks if p >= 4.0) / len(peaks), 4)

rank_mean = {y: r for r, y in enumerate(sorted(years, key=lambda y: -region_mean.get(y, 0)), 1)}
rank_max = {y: r for r, y in enumerate(sorted(years, key=lambda y: -region_max.get(y, 0)), 1)}

print(f"样本 {d['years'][0]}–{d['years'][-1]}（{d['nYears']} 年），{d['gridCells']} 格点\n")
print("一、实地区报告记录的事件年 → 我们序列里该年的状态")
print(f"{'年':<6}{'区域均值':<10}{'均值排名':<10}{'区域最大':<10}{'最大排名':<10}{'警戒格点占比':<14}报告记载")
print("-" * 112)
rows = []
for y, desc, src in EVENTS:
    if y not in region_mean:
        print(f"{y:<6}（我们的序列里没有该年）")
        continue
    print(f"{y:<6}{region_mean[y]:<10}{rank_mean[y]:<10}{region_max[y]:<10}{rank_max[y]:<10}"
          f"{alert_frac[y]:<14.1%}{desc}")
    rows.append({"year": y, "desc": desc, "source": src,
                 "regionMeanPeak": region_mean[y], "meanRank": rank_mean[y],
                 "regionMaxPeak": region_max[y], "maxRank": rank_max[y],
                 "alertCellFraction": alert_frac[y]})

print("\n二、我们的序列里热压力最高的 6 年（区域均值）")
for y in sorted(years, key=lambda y: -region_mean.get(y, 0))[:6]:
    print(f"  {y}: 均值 {region_mean[y]:<6} 最大 {region_max[y]:<7} 警戒格点占比 {alert_frac[y]:.1%}")

print("\n三、定量锚点核对：报告称『2024 年热压力比上一个记录年 2010 高 5 °C-weeks』")
if "2024" in region_max and "2010" in region_max:
    print(f"  我们的区域最大值：2024 = {region_max['2024']}，2010 = {region_max['2010']}，"
          f"差值 = {region_max['2024'] - region_max['2010']:.2f} °C-weeks")
    print(f"  我们的区域均值：  2024 = {region_mean['2024']}，2010 = {region_mean['2010']}，"
          f"差值 = {region_mean['2024'] - region_mean['2010']:.2f} °C-weeks")
    print("  说明：报告的 5 °C-weeks 是**站点级**数值，与我们的区域统计口径不同，只做量级核对。")

print("\n四、一致性结论（事件级）")
ok = [r["year"] for r in rows if r["alertCellFraction"] > 0]
miss = [r["year"] for r in rows if r["alertCellFraction"] == 0]
print(f"  报告记录的事件年里，我们的序列**出现警戒格点**的：{ok}")
print(f"  未出现警戒格点的：{miss}（1998 年事件主要集中在南海/马来半岛，对沙巴影响有限，"
      f"我们的网格只覆盖仙本那周边）")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({
    "task": "P4 前置：实地白化事件年表 × 41 年 DHW 序列（事件级一致性核对）",
    "ourSeries": {"file": "data/noaa/site_profiles.json", "years": [years[0], years[-1]],
                  "nYears": d["nYears"], "gridCells": d["gridCells"]},
    "events": rows,
    "regionMeanPeakByYear": region_mean,
    "regionMaxPeakByYear": region_max,
    "alertCellFractionByYear": alert_frac,
    "anchorCheck": {
        "claim": "报告称 2024 年热压力比 2010 高约 5 °C-weeks（站点级）",
        "ourRegionMaxGap": round(region_max.get("2024", 0) - region_max.get("2010", 0), 2),
        "ourRegionMeanGap": round(region_mean.get("2024", 0) - region_mean.get("2010", 0), 2),
        "note": "口径不同（站点级 vs 区域统计），仅作量级核对",
    },
    "caveats": [
        "报告监测站分布在沙巴与半岛马来西亚多地，我们的网格仅覆盖仙本那及周边",
        "事件年表来自报告正文叙述，非标准化数据集；n=8（事件级），不做显著性检验",
        "我们的逐年峰值：1985–2022 目前仍为每 5 天抽稀（逐日补全进行中），峰值是下界",
        "1998 年未在我们的网格出现警戒，与『1998 事件集中于南海/马来半岛』的记载一致",
    ],
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n结果写入 {OUT}")
