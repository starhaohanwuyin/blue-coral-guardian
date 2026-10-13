"""
投放窗口与热压力档案（格点级 · 多年）
============================================================
回答的问题：**"这片海往年哪个时间段白化预警严重？哪些格点多年比较稳？"**
→ 给出「建议避开哪几个月 / 哪些格点在热压力维度上更友好」的**规则化建议**。

数据来源：本地已缓存的 NOAA CRW 日数据（`data/noaa/_raw_CRW_{DHW,BAA,HOTSPOT}_*.csv`），
**不联网、不用 GPU**，纯聚合。

⚠️ 三条必须随结论一起讲清的口径（脚本也会写进输出）：
  1. **样本年数有限**：当前缓存为 2023–2025（3 年）；长序列（1985 起）需先跑
   `cache_noaa.py --vars CRW_DHW,CRW_HOTSPOT --stride 5 --suffix _lt --chunk-days 90`，
   **下载慢（镜像限速，约 7.5 分钟/年）且可断点续传**。样本短时"多年稳定"很大程度等于
   "只遇上一次事件"，因此档案里会显式写出覆盖年份与年数，不要笼统说"多年"。
     气候态一般需要 ≥10 年。
  2. **5km 格点 ≠ 礁点**：能说"哪片海"，不能说"哪个礁"。
  3. **只覆盖热压力这一个维度**：底质、水深、水流、藻类、草食动物、人力管护都不在模型里；
     本档案**不是投放效果评估**（项目没有投放后的存活率数据）。

用法：
    python climate_site_profile.py --build                     # 预计算（3 年数据约 2–3 分钟）
    python climate_site_profile.py --build --years 2023,2024,2025   # 固定年份，产物可复现
    python climate_site_profile.py --lat 4.4 --lon 118.8       # 查一个点位
    python climate_site_profile.py --list-risky                # 列出风险格点
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOAA_DIR = ROOT / "data" / "noaa"
PROFILES = NOAA_DIR / "site_profiles.json"
REPORT = ROOT / "reports" / "deployment_windows.json"

# 复用气候插件的读取与覆盖闸门，保证格点 key、覆盖范围口径完全一致
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from climate_context import (  # noqa: E402
    _read_cell_series, _series_files, grid_bbox, GRID_MARGIN_DEG,
)

DHW_ALERT = 4.0      # DHW ≥ 4：NOAA 白化警戒起点
DHW_SEVERE = 8.0     # DHW ≥ 8：常伴大面积死亡
HOTSPOT_TRIGGER = 1.0  # HotSpot ≥ 1：热异常开始（用于定位"热事件月份"，比 DHW 更及时）

ADVICE_NOTE = ("口径：仅热压力维度（DHW/BAA/HotSpot），未含底质/水深/水流/藻类/人力等；"
               "空间为 5km 格点，非礁点；本档案不是投放效果评估。")


# ------------------------------------------------------------------ 构建档案
def build(years_pin=None) -> dict:
    """构建档案。years_pin 可**固定年份集合**（如 ['2023','2024','2025']），
    用于在长序列下载未完成时也能得到**可复现**的产物；缺省用缓存里全部年份。"""
    all_years = sorted(_series_files("DHW", include_lt=True).keys())
    years = [y for y in all_years if years_pin is None or y in years_pin]
    if not years:
        raise SystemExit(f"未找到 NOAA 数据：{NOAA_DIR}/_raw_CRW_DHW_*.csv"
                         + (f"（年份筛选 {years_pin} 无匹配）" if years_pin else ""))
    if years_pin:
        miss = sorted(set(years_pin) - set(years))
        if miss:
            print(f"  ⚠️ 以下年份无缓存、已忽略：{miss}")
    lt_years = [y for y in years if "_lt_" in _series_files("DHW", include_lt=True)[y].name]

    # ⚠️ 不能只看文件名判断"抽稀"：`--force --stride 1` 补全后，文件名仍带 `_lt_` 但数据已是逐日。
    #    改为按**实际采样密度**判定（逐日约 360 个时间点/年，每 5 天约 73 个）。
    #    DHW 与 HotSpot 分开统计：两者可分别补齐，档案必须**如实标注各自的覆盖状态**，
    #    否则会出现"DHW 已逐日但 HotSpot 仍抽稀"却被记成全逐日的失真。
    def _n_times(path):
        try:
            with path.open(encoding="utf-8", errors="replace") as fh:
                return len({ln.split(",", 1)[0] for i, ln in enumerate(fh) if i >= 2 and ln.strip()})
        except OSError:
            return 0

    sampled_years = []            # DHW 仍抽稀的年份（决定"峰值是下界"这一限制）
    sampled_hotspot = []          # HotSpot 仍抽稀的年份（只影响"热事件月份"的采样密度）
    for y in years:
        n_dhw = _n_times(_series_files("DHW", include_lt=True)[y])
        if 0 < n_dhw < 200:
            sampled_years.append(y)
        hs = _series_files("HOTSPOT", include_lt=True).get(y)
        n_hs = _n_times(hs) if hs else 0
        if 0 < n_hs < 200:
            sampled_hotspot.append(y)
    if sampled_years:
        print(f"  注：{len(sampled_years)} 个年份 DHW 为**抽稀采样**（每 5 天一个点），"
              f"逐日年份 {len([y for y in years if y not in sampled_years])} 个")
    else:
        print(f"  注：DHW 全部 {len(years)} 年已为**逐日**（峰值不再受抽稀下界影响）")
    if sampled_hotspot:
        print(f"  注：{len(sampled_hotspot)} 个年份 HotSpot 仍为抽稀（仅影响热事件月份的采样密度）")
    lt_years = sampled_years      # 沿用旧变量名，供后续 caveats 使用

    dhw_files, baa_files, hs_files = (_series_files("DHW", include_lt=True),
                                      _series_files("BAA", include_lt=True),
                                      _series_files("HOTSPOT", include_lt=True))
    cells = defaultdict(lambda: {"years": {}})

    for y in years:
        print(f"  [{y}] 读取 DHW / BAA / HotSpot …", flush=True)
        dhw = _read_cell_series(dhw_files[y])
        baa = _read_cell_series(baa_files[y]) if y in baa_files else {}
        hs = _read_cell_series(hs_files[y]) if y in hs_files else {}
        for key, series in dhw.items():
            vals = [v for _, v in series]
            if not vals:
                continue
            peak = max(vals)
            peak_date = max(series, key=lambda t: t[1])[0]
            hot_months = sorted({int(d[5:7]) for d, v in series if v >= DHW_ALERT})
            # HotSpot≥1 的月份 → 更接近"热事件发生的时间窗"（DHW 是 12 周累积量，会滞后）
            heat_months = sorted({int(d[5:7]) for d, v in hs.get(key, []) if v >= HOTSPOT_TRIGGER})
            cells[key]["years"][y] = {
                "dhwPeak": round(peak, 2),
                "peakDate": peak_date,
                "peakMonth": int(peak_date[5:7]),
                "daysDhwGe4": sum(1 for v in vals if v >= DHW_ALERT),
                "daysDhwGe8": sum(1 for v in vals if v >= DHW_SEVERE),
                "baaMax": max((v for _, v in baa.get(key, [])), default=None),
                "alertMonths": hot_months,
                "heatMonths": heat_months or hot_months,
            }

    out_cells = {}
    n_years_all = len(years)
    for key, rec in cells.items():
        ys = rec["years"]
        n = len(ys) or 1
        peaks = {y: ys[y]["dhwPeak"] for y in ys}
        alert_years = sorted(y for y, p in peaks.items() if p >= DHW_ALERT)
        severe_years = sorted(y for y, p in peaks.items() if p >= DHW_SEVERE)
        alert_freq = len(alert_years) / n
        severe_freq = len(severe_years) / n

        # ---- 月份按"出现频率"统计（年份多寡都能用；3 年与 41 年同一套口径）----
        #   对每个月统计：有多少年的该月出现过 DHW≥4 / HotSpot≥1
        alert_month_count = {m: sum(1 for y in ys if m in ys[y]["alertMonths"]) for m in range(1, 13)}
        heat_month_count = {m: sum(1 for y in ys if m in ys[y]["heatMonths"]) for m in range(1, 13)}
        alert_month_freq = {m: alert_month_count[m] / n for m in range(1, 13)}
        heat_month_freq = {m: heat_month_count[m] / n for m in range(1, 13)}

        # ---- 风险月：按"相对本格点峰值"取季节窗口（长序列必须这样做）----
        # 41 年样本里"某月曾出现过 DHW≥4"几乎覆盖全年（实测高危格点会得到 10 个月），结论不可用。
        # 改为：取**出现次数** ≥ ceil(峰值月次数 / 2) 的月份 → 紧凑季节窗口
        # ⚠️ 用**整数计数**而不是浮点频率比较：频率存成小数会四舍五入，
        #    导致"恰好等于峰值一半"的月份在外部重算时翻转（实测 544 格中 84 格受影响）。
        def _season_months(counts):
            mx = max(counts.values()) if counts else 0
            if mx <= 0:
                return []
            thr = -(-mx // 2)          # ceil(mx/2)，纯整数运算
            return sorted(m for m, c in counts.items() if c >= thr)

        risky = _season_months(alert_month_count)
        heat = _season_months(heat_month_count)
        # 建议避开 = DHW 已达警戒的月份 ∪ 出现过热异常（HotSpot≥1）的月份
        # （DHW 是 12 周累积量、会滞后，用 HotSpot 把"提前预警窗口"也覆盖进来，取并集更保守）
        avoid = sorted(set(risky) | set(heat))

        # 风险分级（按"达警戒年份占比" + "严重档事件次数"，与样本年数无关）
        # ⚠️ 41 年实测：没有任何格点警戒频率 >20%，若仍用"≥50%"则 high 恒为空；
        #    真正能区分风险的是**严重白化事件（DHW≥8）次数**（150 格出现过 1–3 次）。
        if len(severe_years) >= 3 or alert_freq >= 0.15:
            level = "high"
        elif alert_years or severe_years:
            level = "medium"
        else:
            level = "low"
        label = (f"{len(years)} 年中 {len(alert_years)} 年达白化警戒"
                 f"（{alert_freq:.0%}）"
                 + (f"，其中 {len(severe_years)} 年达严重档（DHW≥8）" if severe_years else "")
                 ) if alert_years else f"{len(years)} 年均未达白化警戒"
        pv = list(peaks.values())
        mean_p = sum(pv) / len(pv)
        std_p = (sum((x - mean_p) ** 2 for x in pv) / len(pv)) ** 0.5
        out_cells[key] = {
            "years": ys,
            "nYears": len(ys),
            "peakByYear": peaks,
            "alertYears": alert_years,
            "severeYears": severe_years,
            "alertYearFreq": round(alert_freq, 3),
            "severeYearFreq": round(severe_freq, 3),
            "peakMean": round(mean_p, 2),
            "peakStd": round(std_p, 2),
            "peakRange": round(max(pv) - min(pv), 2),
            "alertMonthFreq": {str(m): round(v, 4) for m, v in alert_month_freq.items() if v},
            "heatMonthFreq": {str(m): round(v, 4) for m, v in heat_month_freq.items() if v},
            # 整数计数（权威口径）：风险月由它算出，避免浮点四舍五入造成外部重算不一致
            "alertMonthCount": {str(m): c for m, c in alert_month_count.items() if c},
            "heatMonthCount": {str(m): c for m, c in heat_month_count.items() if c},
            "riskyMonths": risky,          # DHW≥4 出现频率达标的月份
            "heatMonths": heat,            # HotSpot≥1 半数以上年份出现的月份（更及时）
            "avoidMonths": avoid,          # 建议避开（两者并集）
            "safeMonths": [m for m in range(1, 13) if m not in set(avoid)],  # 无任何风险信号
            "riskLevel": level,
            "label": label,
        }

    lats = [float(k.split("_")[0]) for k in out_cells]
    lons = [float(k.split("_")[1]) for k in out_cells]

    # ---- 空间自检：若某一侧远高于中部，很可能是"近岸浅水/陆缘像元"效应而非礁级差异 ----
    def _mean_max_peak(pred) -> float:
        v = [max(c["peakByYear"].values()) for k, c in out_cells.items()
             if pred(float(k.split("_")[1]))]
        return sum(v) / len(v) if v else 0.0

    west = _mean_max_peak(lambda lo: lo <= 118.2)
    mid = _mean_max_peak(lambda lo: 118.6 <= lo <= 118.9)
    east = _mean_max_peak(lambda lo: lo >= 119.2)
    spatial_warn = None
    if mid and west / mid >= 2:
        spatial_warn = (
            f"⚠️ **空间自检告警**：西缘格点（≤118.2°E）3 年最高 DHW 均值 **{west:.2f}**，"
            f"是中部（118.6–118.9°E，{mid:.2f}）的 **{west/mid:.1f} 倍**，呈平滑东西梯度"
            f"（东侧 119.2°E 以东均值 {east:.2f}）。这更像**近岸浅水/陆缘像元效应**，"
            f"而不是礁块之间的真实差异 —— 引用时**必须实地核实**，"
            f"不要仅凭格点数值就排除一个真实礁点。")

    n_yr = len(years)
    span = f"{years[0]}–{years[-1]}（{n_yr} 年）" if years else "无"
    caveats = [
        (f"样本为 {span}" + ("；样本较短，'多年稳定'不等于'以后不会遇上'"
                             if n_yr < 10 else "；已可做频率统计，但历史记录不等于未来情景")),
        f"格点为 5km 网格；原始网格 651 格中约 107 格长期无数据（陆地/掩膜外），"
        f"本档案只保留有数据的 {len(out_cells)} 格",
        "5km 格点 ≠ 礁点：只能给'哪片海'，不能给'哪个礁'",
        "仅热压力维度；不是投放效果评估（项目无投放后存活率数据）",
        "DHW 为 12 周累积量，月份会滞后；heatMonths 用 HotSpot≥1 定位热事件窗口",
        "风险月由**出现次数**（整数）算出：取 ≥ ceil(峰值月次数/2) 的月份；"
        "字段 alertMonthCount/heatMonthCount 为权威值",
        "官方源本身有零星空缺日（如 2024 年缺 5 天，已现场核对确认非下载问题）",
    ]
    if lt_years:
        caveats.append(f"其中 {len(lt_years)} 个年份 DHW 为**每 5 天抽稀**采样（峰值是下界，"
                       f"可能略低于逐日真值；警戒月份判定不受影响）")
    else:
        caveats.append(f"DHW 全部 {n_yr} 年均为**逐日**（已消除「峰值是下界」的限制）")
    if sampled_hotspot:
        caveats.append(f"其中 {len(sampled_hotspot)} 个年份 HotSpot 仍为每 5 天抽稀"
                       f"（仅影响热事件月份的采样密度，每月仍有约 6 个采样点）")

    data = {
        "source": "NOAA CRW v3.1 5km via PacIOOS/CoastWatch mirror（本地缓存聚合）",
        "years": years,
        "yearSpan": span,
        "nYears": n_yr,
        "sampledYears": sorted(lt_years),
        "sampledHotspotYears": sorted(sampled_hotspot),
        "gridCells": len(out_cells),
        "coverageBBox": {"latMin": min(lats), "latMax": max(lats),
                         "lonMin": min(lons), "lonMax": max(lons)},
        "thresholds": {"dhwAlert": DHW_ALERT, "dhwSevere": DHW_SEVERE,
                       "hotspotTrigger": HOTSPOT_TRIGGER},
        "spatialMeans": {"west_le118.2": round(west, 2), "mid_118.6_118.9": round(mid, 2),
                         "east_ge119.2": round(east, 2)},
        "spatialWarning": spatial_warn,
        "caveats": caveats,
        "adviceNote": (f"口径：仅热压力维度（DHW/BAA/HotSpot），未含底质/水深/水流/藻类/人力等；"
                       f"样本 {span}；空间为 5km 格点，非礁点；本档案不是投放效果评估。"),
        "cells": out_cells,
    }
    return data


def _months_en(months) -> str:
    """把月份数字转成英文缩写，如 [4,5,6] -> 'Apr, May, Jun'。"""
    names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return ", ".join(names[m] for m in months if 1 <= m <= 12) or "none"


def advice_for(cell: dict) -> dict:
    """把档案转成一句可执行的规则化建议（只说热压力，不涉及投放效果）。中英双版。"""
    risky = cell.get("riskyMonths") or []
    heat = cell.get("heatMonths") or []
    avoid = cell.get("avoidMonths") or sorted(set(risky) | set(heat))
    safe = cell.get("safeMonths") or []
    avoid_txt = "、".join(f"{m} 月" for m in avoid) if avoid else "无"
    heat_txt = "、".join(f"{m} 月" for m in heat) if heat else "无"
    safe_txt = ("全年未见风险信号" if len(safe) == 12
                else ("、".join(f"{m} 月" for m in safe) if safe else "无"))
    alert_years = cell.get("alertYears") or []
    lv = cell.get("riskLevel")
    n_years = len(cell.get("peakByYear") or {}) or 1
    # 兼容旧档案（无 alertYearFreq 字段时按 alertYears/年数 现算）
    freq = cell.get("alertYearFreq")
    if freq is None:
        freq = len(cell.get("alertYears") or []) / n_years
    freq_pct = f"{freq:.0%}"
    avoid_en, heat_en, safe_en = _months_en(avoid), _months_en(heat), _months_en(safe)

    if lv == "high":
        sev = len(cell.get("severeYears") or [])
        sev_txt = f"，其中 **{sev} 年**达严重档（DHW≥8）" if sev else ""
        text = (f"⚠️ 近 {n_years} 年中有 **{len(alert_years)} 年**达到白化警戒"
                f"（{freq_pct}）{sev_txt}：**不建议**在此期间投放；"
                f"如必须投放，应避开 {avoid_txt}。")
        label_en = f"Alert level (DHW>=4) in {len(alert_years)}/{n_years} years" + \
                   (f", {sev} severe (DHW>=8)" if sev else "")
        text_en = (f"Alert-level heat stress reached in {len(alert_years)} of {n_years} years "
                   f"({freq_pct})" + (f", {sev} of them severe (DHW>=8)" if sev else "")
                   + f": deployment is NOT recommended; if unavoidable, avoid {avoid_en}.")
    elif lv == "medium":
        text = (f"近 {n_years} 年中有 {len(alert_years)} 年达到白化警戒（DHW≥4 出现于 "
                f"{'、'.join(f'{m} 月' for m in risky) if risky else '无'}）："
                f"建议避开 {avoid_txt} 投放（含热异常月份 {heat_txt}，取并集更保守）。")
        label_en = f"Alert level reached in {len(alert_years)}/{n_years} years"
        text_en = (f"Alert level reached in {len(alert_years)} of {n_years} years: avoid "
                   f"{avoid_en} for deployment (union of DHW>=4 and HotSpot>=1 months, conservative).")
    elif heat:
        text = (f"近 {n_years} 年**均未**达到白化警戒（DHW≥4），热压力维度总体友好；"
                f"但 {heat_txt} 出现过热异常（HotSpot≥1），建议避开这些月份投放，"
                f"其余月份（{safe_txt}）无风险信号。")
        label_en = f"No alert level in any of the {n_years} years"
        text_en = (f"No alert-level DHW in the {n_years} years available; heat-stress dimension is "
                   f"broadly favourable, but heat anomalies (HotSpot>=1) occurred in {heat_en} — "
                   f"avoid those months. No risk signal in {safe_en}.")
    else:
        text = (f"近 {n_years} 年**均未**达到白化警戒、也未出现热异常："
                "**热压力维度上属于较友好区域**。（底质/水流/管护等仍需现场判断）")
        label_en = f"No alert level or heat anomaly in any of the {n_years} years"
        text_en = (f"No alert-level DHW and no heat anomaly in the {n_years} years available: "
                   f"broadly favourable in the heat-stress dimension only "
                   f"(substrate/currents/management still require field checking).")

    return {"level": lv, "label": cell.get("label"), "labelEn": label_en,
            "riskyMonths": risky, "heatMonths": heat, "avoidMonths": avoid,
            "safeMonths": safe, "text": text, "textEn": text_en}


# ------------------------------------------------------------------ 查询接口
def _load_profiles():
    if not PROFILES.exists():
        return None
    return json.loads(PROFILES.read_text(encoding="utf-8"))


def profile_for(lat: float, lon: float):
    """按坐标取最近格点的档案。覆盖闸门与气候插件一致：网格外返回 ok=False。"""
    pf = _load_profiles()
    if not pf:
        return {"ok": False, "error": "热压力档案尚未生成，请运行 climate_site_profile.py --build"}
    key, dist = _nearest_cell_key(pf, lat, lon)
    y0, x0, y1, x1 = grid_bbox(pf["cells"])
    la, lo = (float(v) for v in key.split("_"))
    if not (y0 - GRID_MARGIN_DEG <= lat <= y1 + GRID_MARGIN_DEG and
            x0 - GRID_MARGIN_DEG <= lon <= x1 + GRID_MARGIN_DEG):
        return {"ok": False,
                "error": f"坐标 ({lat}, {lon}) 不在热压力档案覆盖范围内（网格 {y0:.3f}~{y1:.3f}N, "
                         f"{x0:.3f}~{x1:.3f}E）",
                "coverageBBox": {"latMin": y0, "latMax": y1, "lonMin": x0, "lonMax": x1},
                "nearestCell": {"lat": la, "lon": lo, "distanceDeg": round(dist, 3)}}
    cell = pf["cells"][key]
    return {
        "ok": True,
        "gridCell": {"lat": la, "lon": lo, "distanceDeg": round(dist, 3)},
        "years": pf["years"],
        "nYears": cell.get("nYears"),
        "peakByYear": cell["peakByYear"],
        "peakMean": cell.get("peakMean"),
        "peakStd": cell.get("peakStd"),
        "alertYears": cell["alertYears"],
        "alertYearFreq": cell.get("alertYearFreq"),
        "severeYears": cell["severeYears"],
        "severeYearFreq": cell.get("severeYearFreq"),
        "peakRange": cell["peakRange"],
        "alertMonthFreq": cell.get("alertMonthFreq"),
        "heatMonthFreq": cell.get("heatMonthFreq"),
        "riskyMonths": cell["riskyMonths"],
        "heatMonths": cell["heatMonths"],
        "avoidMonths": cell["avoidMonths"],
        "safeMonths": cell["safeMonths"],
        "riskLevel": cell["riskLevel"],
        "label": cell["label"],
        "advice": advice_for(cell),
        "adviceNote": pf["adviceNote"],
        "caveats": pf["caveats"],
    }


def _nearest_cell_key(pf, lat, lon):
    best, bestd = None, 1e9
    for k in pf["cells"]:
        la, lo = (float(x) for x in k.split("_"))
        d = (la - lat) ** 2 + (lo - lon) ** 2
        if d < bestd:
            best, bestd = k, d
    la, lo = (float(x) for x in best.split("_"))
    return best, math.sqrt(bestd)


# ------------------------------------------------------------------ CLI
def input_fingerprint() -> str:
    """输入指纹：所有参与聚合的原始 CSV 的 (变量, 文件名, 大小) 摘要。

    用途：长序列抽稀年份正被逐日数据逐步替换时，**防止误重建**把已验收的
    峰值/警戒年份悄悄改掉。指纹不一致时 --build 会拒绝执行（除非显式 --allow-input-change）。
    """
    import hashlib
    h = hashlib.sha1()
    for var in ("DHW", "BAA", "HOTSPOT", "SSTANOMALY", "SST"):
        try:
            files = _series_files(var, include_lt=True)
        except Exception:
            continue
        for y, p in sorted(files.items()):
            try:
                h.update(f"{var}|{p.name}|{p.stat().st_size}|".encode())
            except OSError:
                pass
    return h.hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="预计算档案（写入 data/noaa/site_profiles.json）")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--list-risky", action="store_true", help="列出年年达警戒的格点")
    ap.add_argument("--allow-input-change", action="store_true",
                    help="原始缓存已变（如逐日补全进行中）时仍允许重建档案")
    ap.add_argument("--check-inputs", action="store_true",
                    help="只比对输入指纹与已构建档案是否一致（不改动任何文件）")
    ap.add_argument("--years", default="",
                    help="固定年份集合（逗号分隔，如 2023,2024,2025）；缺省用缓存里全部年份。"
                         "长序列下载未完成时用它保证产物可复现")
    args = ap.parse_args()

    years_pin = [y.strip() for y in args.years.split(",") if y.strip()] or None

    if args.check_inputs:
        cur = input_fingerprint()
        old = None
        if PROFILES.exists():
            try:
                old = json.loads(PROFILES.read_text(encoding="utf-8")).get("inputFingerprint")
            except (OSError, ValueError):
                old = None
        print(f"当前输入指纹: {cur}")
        print(f"档案里记录  : {old or '（该档案构建于本守卫加入之前）'}")
        if not old:
            print("→ 无法比对（旧档案没有指纹）。下次 --build 会写入指纹。")
        elif old == cur:
            print("→ ✅ 一致：重建不会改变已验收的数字。")
        else:
            print("→ ⚠️ 不一致：原始缓存已变（很可能是逐日补全进行中）；此时重建会改变已验收数字。")
        return 0

    if args.build:
        print("聚合 NOAA 数据（DHW/BAA/HotSpot）…")
        # ⚠️ 输入指纹守卫：原始缓存一旦变动（例如长序列抽稀年份正被逐日数据替换），
        #    重建出的峰值/警戒年份就会与**已验收的数字**不同。先比对再动手，避免误改。
        fp = input_fingerprint()
        old_fp = None
        if PROFILES.exists():
            try:
                old_fp = json.loads(PROFILES.read_text(encoding="utf-8")).get("inputFingerprint")
            except (OSError, ValueError):
                old_fp = None
        if old_fp and old_fp != fp:
            print("  ⚠️ 原始缓存自上次构建后已变化（指纹不一致）：")
            print(f"     已验收产物指纹 {old_fp} → 当前输入 {fp}")
            print("     重建后的峰值/警戒年份可能与文档中已验收的数字不同；")
            print("     若长序列（1985–2022）的逐日补全尚未完成，建议**暂不重建**。")
            if not args.allow_input_change:
                print("     如确实要重建：加 `--allow-input-change`。")
                return 2
        data = build(years_pin=years_pin)
        data["inputFingerprint"] = fp
        PROFILES.parent.mkdir(parents=True, exist_ok=True)
        PROFILES.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print(f"档案：{PROFILES}（{(PROFILES.stat().st_size/1024):.0f} KB，{data['gridCells']} 个格点）")

        cells = data["cells"]
        lv = defaultdict(int)
        for c in cells.values():
            lv[c["riskLevel"]] += 1
        risky = sorted([k for k, c in cells.items() if c["riskLevel"] == "high"],
                       key=lambda k: -max(cells[k]["peakByYear"].values()))[:10]
        summary = {
            "source": data["source"], "years": data["years"],
            "gridCells": data["gridCells"], "coverageBBox": data["coverageBBox"],
            "levelCounts": dict(lv),
            "severeCellsAnyYear": sum(1 for c in cells.values() if c["severeYears"]),
            "medianPeakRange": sorted(c["peakRange"] for c in cells.values())[len(cells)//2],
            "spatialMeans": data.get("spatialMeans"),
            "spatialWarning": data.get("spatialWarning"),
            "topRiskyCells": [{"cell": k, "maxPeak": max(cells[k]["peakByYear"].values()),
                               "label": cells[k]["label"], "riskyMonths": cells[k]["riskyMonths"]}
                              for k in risky],
            "caveats": data["caveats"], "adviceNote": data["adviceNote"],
            "cells": {k: {kk: v[kk] for kk in ("peakByYear", "alertYears", "severeYears",
                                               "riskyMonths", "heatMonths", "avoidMonths",
                                               "safeMonths", "riskLevel", "label", "peakRange")}
                      for k, v in cells.items()},
        }
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"汇总：{REPORT}")
        print(f"  风险等级分布：{dict(lv)}")
        print(f"  三年内出现过 DHW≥8 的格点：{summary['severeCellsAnyYear']}")
        print("  最需要避开的格点（按 3 年最高 DHW）：")
        for r in summary["topRiskyCells"][:5]:
            print(f"    {r['cell']:<18} 峰值 {r['maxPeak']:>5}  {r['label']:<14} 风险月 {r['riskyMonths']}")
        return

    if args.list_risky:
        pf = _load_profiles()
        if not pf:
            raise SystemExit("档案不存在，先 --build")
        rows = [(k, c) for k, c in pf["cells"].items() if c["riskLevel"] == "high"]
        rows.sort(key=lambda kv: -max(kv[1]["peakByYear"].values()))
        print(f"年年达白化警戒的格点：{len(rows)} 个（共 {pf['gridCells']}）")
        for k, c in rows[:20]:
            print(f"  {k:<18} {c['label']:<14} 峰值 {max(c['peakByYear'].values()):>5}  "
                  f"风险月 {c['riskyMonths']}  热事件月 {c['heatMonths']}")
        return

    if args.lat is None or args.lon is None:
        ap.error("请给出 --lat/--lon，或使用 --build / --list-risky")
    r = profile_for(args.lat, args.lon)
    if not r.get("ok"):
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    print(f"格点 {r['gridCell']['lat']}°N {r['gridCell']['lon']}°E"
          f"（距查询点 {r['gridCell']['distanceDeg']}°）")
    print(f"  逐年 DHW 峰值：{r['peakByYear']}")
    print(f"  判定：{r['label']}（达到警戒的年份：{r['alertYears'] or '无'}；"
          f"严重档年份：{r['severeYears'] or '无'}）")
    print(f"  风险月份（DHW≥4）：{r['riskyMonths']}    热异常月份（HotSpot≥1）：{r['heatMonths']}")
    print(f"  建议避开：{r['avoidMonths']}    无风险信号月份："
          f"{'全年' if len(r['safeMonths']) == 12 else r['safeMonths']}")
    print(f"\n  **建议**：{r['advice']['text']}")
    print(f"\n  ⚠️ {r['adviceNote']}")


if __name__ == "__main__":
    # ⚠️ 必须把 main() 的返回码传出去：否则守卫"拒绝重建"时退出码仍是 0，
    #    CI / resume_all 会把它当成成功（本轮实测踩到）
    sys.exit(main())
