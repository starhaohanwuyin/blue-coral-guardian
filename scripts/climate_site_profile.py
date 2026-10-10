"""
投放窗口与热压力档案（格点级 · 多年）
============================================================
回答的问题：**"这片海往年哪个时间段白化预警严重？哪些格点多年比较稳？"**
→ 给出「建议避开哪几个月 / 哪些格点在热压力维度上更友好」的**规则化建议**。

数据来源：本地已缓存的 NOAA CRW 日数据（`data/noaa/_raw_CRW_{DHW,BAA,HOTSPOT}_*.csv`），
**不联网、不用 GPU**，纯聚合。

⚠️ 三条必须随结论一起讲清的口径（脚本也会写进输出）：
  1. **只有 3 年（2023–2025）**：2024 是极端年，"多年稳定"很大程度等于"只遇上一次事件"，
     不等于以后不会遇上；气候态一般需要 ≥10 年。
  2. **5km 格点 ≠ 礁点**：能说"哪片海"，不能说"哪个礁"。
  3. **只覆盖热压力这一个维度**：底质、水深、水流、藻类、草食动物、人力管护都不在模型里；
     本档案**不是投放效果评估**（项目没有投放后的存活率数据）。

用法：
    python climate_site_profile.py --build                     # 预计算（约 2–3 分钟）
    python climate_site_profile.py --lat 4.4 --lon 118.8       # 查一个点位
    python climate_site_profile.py --list-risky                # 列出年年达警戒的格点
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
               "样本仅 2023–2025 三年；空间为 5km 格点，非礁点；本档案不是投放效果评估。")


# ------------------------------------------------------------------ 构建档案
def build() -> dict:
    years = sorted(_series_files("DHW").keys())
    if not years:
        raise SystemExit(f"未找到 NOAA 数据：{NOAA_DIR}/_raw_CRW_DHW_*.csv")

    dhw_files, baa_files, hs_files = _series_files("DHW"), _series_files("BAA"), _series_files("HOTSPOT")
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
    for key, rec in cells.items():
        ys = rec["years"]
        peaks = {y: ys[y]["dhwPeak"] for y in ys}
        alert_years = sorted(y for y, p in peaks.items() if p >= DHW_ALERT)
        severe_years = sorted(y for y, p in peaks.items() if p >= DHW_SEVERE)
        risky = sorted({m for y in ys for m in ys[y]["alertMonths"]})
        heat = sorted({m for y in ys for m in ys[y]["heatMonths"]})
        pv = list(peaks.values())
        if len(alert_years) == len(ys) and alert_years:
            label, level = "年年达白化警戒", "high"
        elif alert_years:
            label, level = f"{len(alert_years)}/{len(ys)} 年达白化警戒", "medium"
        else:
            label, level = "近 3 年均未达白化警戒", "low"
        safe = [m for m in range(1, 13) if m not in set(risky)]
        # 建议避开 = DHW 已达警戒的月份 ∪ 出现过热异常（HotSpot≥1）的月份
        # （DHW 是 12 周累积量、会滞后，用 HotSpot 把"提前预警窗口"也覆盖进来，取并集更保守）
        avoid = sorted(set(risky) | set(heat))
        out_cells[key] = {
            "years": ys,
            "peakByYear": peaks,
            "alertYears": alert_years,
            "severeYears": severe_years,
            "peakRange": round(max(pv) - min(pv), 2),
            "riskyMonths": risky,          # DHW≥4 出现过的月份
            "heatMonths": heat,            # HotSpot≥1 出现过的月份（更及时）
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

    caveats = [
        "仅 2023–2025 三年：2024 为极端年，'多年稳定'不等于'以后不会遇上'",
        "5km 格点 ≠ 礁点：只能给'哪片海'，不能给'哪个礁'",
        "仅热压力维度；不是投放效果评估（项目无投放后存活率数据）",
        "DHW 为 12 周累积量，月份会滞后；heatMonths 用 HotSpot≥1 定位热事件窗口",
    ]
    if spatial_warn:
        caveats.append(spatial_warn)

    data = {
        "source": "NOAA CRW v3.1 5km via PacIOOS mirror（本地缓存日数据聚合）",
        "years": years,
        "gridCells": len(out_cells),
        "coverageBBox": {"latMin": min(lats), "latMax": max(lats),
                         "lonMin": min(lons), "lonMax": max(lons)},
        "thresholds": {"dhwAlert": DHW_ALERT, "dhwSevere": DHW_SEVERE,
                       "hotspotTrigger": HOTSPOT_TRIGGER},
        "spatialMeans": {"west_le118.2": round(west, 2), "mid_118.6_118.9": round(mid, 2),
                         "east_ge119.2": round(east, 2)},
        "spatialWarning": spatial_warn,
        "caveats": caveats,
        "adviceNote": ADVICE_NOTE,
        "cells": out_cells,
    }
    return data


def advice_for(cell: dict) -> dict:
    """把档案转成一句可执行的规则化建议（只说热压力，不涉及投放效果）。"""
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
    if lv == "high":
        text = (f"⚠️ 近 3 年**年年**达到白化警戒（DHW≥4）：**不建议**在此期间投放；"
                f"如必须投放，应避开 {avoid_txt}。")
    elif lv == "medium":
        text = (f"近 3 年有 {len(alert_years)} 年达到白化警戒（DHW≥4 出现于 "
                f"{'、'.join(f'{m} 月' for m in risky) if risky else '无'}）："
                f"建议避开 {avoid_txt} 投放（含热异常月份 {heat_txt}，取并集更保守）。")
    elif heat:
        text = (f"近 3 年**均未**达到白化警戒（DHW≥4），热压力维度总体友好；"
                f"但 {heat_txt} 出现过热异常（HotSpot≥1），建议避开这些月份投放，"
                f"其余月份（{safe_txt}）无风险信号。")
    else:
        text = ("近 3 年**均未**达到白化警戒、也未出现热异常："
                "**热压力维度上属于较友好区域**。（底质/水流/管护等仍需现场判断）")
    return {"level": lv, "label": cell.get("label"), "riskyMonths": risky,
            "heatMonths": heat, "avoidMonths": avoid, "safeMonths": safe, "text": text}


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
        "peakByYear": cell["peakByYear"],
        "alertYears": cell["alertYears"],
        "severeYears": cell["severeYears"],
        "peakRange": cell["peakRange"],
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
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="预计算档案（写入 data/noaa/site_profiles.json）")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--list-risky", action="store_true", help="列出年年达警戒的格点")
    args = ap.parse_args()

    if args.build:
        print("聚合 NOAA 日数据（DHW/BAA/HotSpot × 3 年）…")
        data = build()
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
    main()
