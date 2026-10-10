"""
气候上下文模块（NOAA Coral Reef Watch）
================================================================
把已缓存的 NOAA CRW v3.1 5km DHW 数据变成可查询的气候背景。

数据来源：
    data/noaa/_raw_CRW_DHW_{year}.csv
    网格：4.025–5.025°N × 118.025–119.525°E，0.05° 分辨率（21 × 31）
    覆盖仙本那（4.2–4.6°N, 118.6–119.0°E）及其周边

用法（命令行）：
    python climate_context.py --build                 # 构建索引（只跑一次）
    python climate_context.py --lat 4.4 --lon 118.8 --year 2024
    python climate_context.py --cells                 # 列出所有格点

用法（代码）：
    from climate_context import context_for
    ctx = context_for(lat=4.4, lon=118.8, year=2024)
"""
import argparse
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOAA_DIR = ROOT / "data" / "noaa"
INDEX = NOAA_DIR / "climate_index.json"

# NOAA 白化预警等级（BAA, Bleaching Alert Area）
BAA_LABEL = {
    0: "无压力",
    1: "白化观察",
    2: "白化警告",
    3: "白化警报一级",
    4: "白化警报二级",
}
BAA_RISK = {0: 0.0, 1: 0.25, 2: 0.5, 3: 0.75, 4: 1.0}

# NOAA 对 DHW 的风险解读（Degree Heating Weeks，单位 °C·周）
#   参考：NOAA CRW 公开标准 —— DHW ≥ 4 开始显著白化，≥ 8 常伴随大面积死亡
DHW_THRESHOLDS = [
    (8.0, "严重热应激：大面积白化并可能出现死亡"),
    (4.0, "中度热应激：已具备明显白化条件"),
    (1.0, "轻度热应激：需持续关注"),
    (0.0, "无明显热应激"),
]


def _year_files():
    return sorted(NOAA_DIR.glob("_raw_CRW_DHW_*.csv"))


def _series_files(var: str):
    """按变量取逐年文件，如 var='BAA' -> _raw_CRW_BAA_2023.csv"""
    return {f.stem.split("_")[-1]: f for f in sorted(NOAA_DIR.glob(f"_raw_CRW_{var}_*.csv"))}


def _read_cell_series(path, cell_filter=None):
    """读取一个 CSV，返回 {格点key: [(时间, 值), ...]}。NaN 跳过。"""
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        r = csv.reader(fh)
        next(r)
        next(r)
        for row in r:
            if len(row) < 4:
                continue
            try:
                v = float(row[3])
                la, lo = float(row[1]), float(row[2])
            except ValueError:
                continue
            if math.isnan(v):      # ⚠️ float("NaN") 不报错，必须显式过滤
                continue
            key = f"{la:.3f}_{lo:.3f}"
            if cell_filter is not None and key not in cell_filter:
                continue
            out.setdefault(key, []).append((row[0][:10], v))
    return out


def build_index(force: bool = False):
    """
    把逐年 CSV 压缩成「格点 × 年份」统计索引（一次性）。

    ⚠️ 重要：BAA 等级**直接取 NOAA 官方 CRW_BAA 产品的最大值**，
       不用 DHW 阈值推算 —— 二者实测会差一级
       （仙本那核心区 2024：官方 BAA=3，按 DHW 推算仅得 2）。
    同时接入 HotSpot（热异常）与 SSTANOMALY（海温距平）作为补充指标。
    """
    files = _year_files()
    if not files:
        raise SystemExit(f"未找到 NOAA 数据：{NOAA_DIR}/_raw_CRW_DHW_*.csv")
    if INDEX.exists() and not force:
        print(f"索引已存在（--force 可重建）：{INDEX}")
        return json.loads(INDEX.read_text(encoding="utf-8"))

    baa_files = _series_files("BAA")
    hs_files = _series_files("HOTSPOT")
    sa_files = _series_files("SSTANOMALY")
    sst_files = _series_files("SST")

    out = {"source": "NOAA CRW v3.1 5km via PacIOOS mirror",
           "variables": ["CRW_DHW", "CRW_BAA", "CRW_HOTSPOT", "CRW_SSTANOMALY", "CRW_SST"],
           "baaSource": "NOAA 官方 CRW_BAA 产品（非阈值推算）",
           "region": "4.025-5.025N, 118.025-119.525E", "years": {}}

    for f in files:
        year = f.stem.split("_")[-1]
        cells = {}
        with open(f, newline="", encoding="utf-8") as fh:
            r = csv.reader(fh)
            next(r)
            next(r)
            for row in r:
                if len(row) < 4:
                    continue
                try:
                    dhw = float(row[3])
                except ValueError:
                    continue
                if math.isnan(dhw):    # ⚠️ 必须显式判断，float("NaN") 不会抛异常
                    continue
                key = f"{float(row[1]):.3f}_{float(row[2]):.3f}"
                c = cells.get(key)
                if c is None:
                    c = cells[key] = {"max": 0.0, "ge4": 0, "ge8": 0, "day": 0, "peak": ""}
                if dhw > c["max"]:
                    c["max"] = dhw
                    c["peak"] = row[0][:10]
                if dhw >= 4.0:
                    c["ge4"] += 1
                if dhw >= 8.0:
                    c["ge8"] += 1
                c["day"] += 1

        keys = set(cells)
        # --- 官方 BAA：取该格点该年的最大等级 ---
        if year in baa_files:
            for k, series in _read_cell_series(baa_files[year], keys).items():
                vals = [v for _, v in series]
                if vals:
                    cells[k]["baaOfficial"] = int(round(max(vals)))
                    # 各等级天数
                    from collections import Counter
                    cells[k]["baaDays"] = dict(sorted(Counter(int(round(v)) for v in vals).items()))
        # --- HotSpot / SST 距平：取峰值 ---
        for src, field, agg in ((hs_files, "hotspotMax", max),
                                (sa_files, "sstAnomalyMax", max),
                                (sst_files, "sstMax", max),
                                (sst_files, "sstMean", None)):
            if year in src:
                for k, series in _read_cell_series(src[year], keys).items():
                    vals = [v for _, v in series]
                    if not vals:
                        continue
                    cells[k][field] = round(max(vals), 3) if agg else round(sum(vals) / len(vals), 3)

        for c in cells.values():
            m = c["max"]
            if "baaOfficial" in c:
                baa = c["baaOfficial"]          # ✅ 优先用官方值
            else:
                # 兜底：无官方值时才用 DHW 阈值推算。
                # ⚠️ 阈值已按 NOAA 5km BAA 产品实测校准（此前假设错了整整一档）：
                #      BAA 2 白化警告   : DHW > 0（且 HotSpot ≥ 1）
                #      BAA 3 警报一级   : DHW ≥ 4
                #      BAA 4 警报二级   : DHW ≥ 8
                if m <= 0:
                    baa = 0
                elif m < 4:
                    baa = 2
                elif m < 8:
                    baa = 3
                else:
                    baa = 4
                c["baaEstimated"] = True
            c["baa"] = baa
            c["baaLabel"] = BAA_LABEL.get(baa, f"等级{baa}")
        out["years"][year] = cells
        n_off = sum(1 for c in cells.values() if "baaOfficial" in c)
        print(f"  {year}: {len(cells)} 个格点，峰值 DHW = "
              f"{max(c['max'] for c in cells.values()):.2f}，"
              f"官方 BAA 覆盖 {n_off} 个格点")

    INDEX.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"索引已写入：{INDEX}  ({INDEX.stat().st_size/1024:.0f} KB)")
    return out


def _load():
    if not INDEX.exists():
        return build_index()
    return json.loads(INDEX.read_text(encoding="utf-8"))


def _nearest_cell(idx, year, lat, lon):
    cells = idx["years"].get(str(year))
    if not cells:
        return None, None
    best, bestd = None, 1e9
    for k in cells:
        la, lo = (float(x) for x in k.split("_"))
        d = (la - lat) ** 2 + (lo - lon) ** 2
        if d < bestd:
            best, bestd = k, d
    la, lo = (float(x) for x in best.split("_"))
    return best, math.sqrt(bestd)


# 空间覆盖闸门（修过的 bug）：
# 本项目 NOAA 网格只覆盖仙本那核心区，但 context_for() 原先对**任何**坐标都
# 「取最近格点」并照常返回 ok=True —— 实测查深圳（约 2000 km 外）会得到
# DHW 9.65 / BAA 4 /「严重热应激：大面积白化并可能出现死亡」，属于**错误结论**。
# 现在：超出网格 bbox 一个格点容差之外 → 直接 ok=False，宁可报缺数据也不猜。
GRID_MARGIN_DEG = 0.05


def grid_bbox(cells) -> tuple:
    """由索引里的实际格点推出覆盖范围 (latMin, lonMin, latMax, lonMax)。"""
    lats = [float(k.split("_")[0]) for k in cells]
    lons = [float(k.split("_")[1]) for k in cells]
    return min(lats), min(lons), max(lats), max(lons)


def dhw_verdict(dhw_max: float) -> str:
    for th, desc in DHW_THRESHOLDS:
        if dhw_max >= th:
            return desc
    return DHW_THRESHOLDS[-1][1]


def context_for(lat: float, lon: float, year: int | None = None):
    """查询某坐标某年的气候背景。year 缺省取数据中最新年份。"""
    idx = _load()
    years = sorted(idx["years"].keys())
    if not year:
        year = int(years[-1])
    year = int(year)
    key, dist = _nearest_cell(idx, year, lat, lon)
    if key is None:
        return {"ok": False, "error": f"无 {year} 年数据",
                "availableYears": years}

    cells_year = idx["years"][str(year)]
    y0, x0, y1, x1 = grid_bbox(cells_year)
    la, lo = (float(x) for x in key.split("_"))

    # ---- 覆盖闸门：网格外不返回结论（见 GRID_MARGIN_DEG 处说明）----
    if not (y0 - GRID_MARGIN_DEG <= lat <= y1 + GRID_MARGIN_DEG and
            x0 - GRID_MARGIN_DEG <= lon <= x1 + GRID_MARGIN_DEG):
        return {
            "ok": False,
            "year": year,
            "error": (f"坐标 ({lat}, {lon}) 不在气候数据覆盖范围内"
                      f"（网格 {y0:.3f}~{y1:.3f}N, {x0:.3f}~{x1:.3f}E），"
                      f"拒绝给出热压力结论"),
            "reason": ("网格外取「最近格点」的距离可达数十至数千公里，"
                       "据此报出的 DHW / 白化预警会是错误结论，故此处报缺数据而非猜测值。"),
            "coverageBBox": {"latMin": y0, "latMax": y1, "lonMin": x0, "lonMax": x1},
            # gridCell 与成功响应同形（供报告/前端复用）；nearestCell 额外给出距离
            "gridCell": {"lat": la, "lon": lo, "distanceDeg": round(dist, 3)},
            "nearestCell": {"lat": la, "lon": lo, "distanceDeg": round(dist, 3)},
            "availableYears": years,
            "hint": "如需覆盖该区域：用 cache_noaa.py 扩充网格后重建 data/noaa/climate_index.json",
        }

    c = cells_year[key]

    # 与其它年份对比，判断该年是否异常
    others = [idx["years"][y][key]["max"] for y in years
              if y != str(year) and key in idx["years"][y]]
    typical = sum(others) / len(others) if others else None
    anomaly = (c["max"] - typical) if typical is not None else None

    return {
        "ok": True,
        "year": year,
        "gridCell": {"lat": round(la, 3), "lon": round(lo, 3),
                     "distanceDeg": round(dist, 3)},
        "dhwMax": round(c["max"], 2),
        "baa": c["baa"],
        "baaLabel": c["baaLabel"],
        "riskScore": BAA_RISK[c["baa"]],
        "daysDhwGe4": c["ge4"],
        "daysDhwGe8": c["ge8"],
        "peakDate": c["peak"],
        "verdict": dhw_verdict(c["max"]),
        "hotspotMax": c.get("hotspotMax"),
        "sstMax": c.get("sstMax"),
        "sstMean": c.get("sstMean"),
        "sstAnomalyMax": c.get("sstAnomalyMax"),
        "baaDays": c.get("baaDays"),
        "baaSource": "官方 CRW_BAA 产品" if "baaOfficial" in c else "DHW 阈值推算（已校准）",
        "typicalDhwMax": round(typical, 2) if typical is not None else None,
        "anomalyVsOtherYears": round(anomaly, 2) if anomaly is not None else None,
        "anomalyNote": (
            f"比其它年份平均高 {anomaly:+.2f}（{(anomaly/typical*100):+.0f}%）"
            if typical and anomaly is not None else "无对比年份"
        ),
        "source": idx["source"],
        "availableYears": years,
        # P3 后新增（附加字段，原键值与口径未动）：让调用方自行判断是否在覆盖区内
        "withinGrid": True,
        "coverageBBox": {"latMin": y0, "latMax": y1, "lonMin": x0, "lonMax": x1},
    }


def cell_table():
    idx = _load()
    rows = []
    for y in sorted(idx["years"]):
        for k, c in idx["years"][y].items():
            la, lo = (float(x) for x in k.split("_"))
            rows.append((y, la, lo, c["max"], c["baaLabel"], c["ge8"]))
    return rows


def main():
    ap = argparse.ArgumentParser(description="NOAA 气候上下文查询")
    ap.add_argument("--build", action="store_true", help="构建/重建索引")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--year", type=int)
    ap.add_argument("--cells", action="store_true", help="列出所有格点")
    args = ap.parse_args()

    if args.build:
        build_index(force=args.force)
        return
    if args.cells:
        for y, la, lo, m, b, g8 in cell_table():
            print(f"  {y}  {la:.3f}N {lo:.3f}E  DHW={m:6.2f}  {b:<12} 天数≥8={g8}")
        return
    if args.lat is None or args.lon is None:
        ap.error("需要 --lat 与 --lon（或用 --build / --cells）")

    ctx = context_for(args.lat, args.lon, args.year)
    if not ctx["ok"]:
        print(json.dumps(ctx, ensure_ascii=False, indent=2))
        return
    print(f"坐标 {args.lat}N {args.lon}E  最近格点 {ctx['gridCell']['lat']}N "
          f"{ctx['gridCell']['lon']}E（相距 {ctx['gridCell']['distanceDeg']}°）")
    print(f"  年份          : {ctx['year']}")
    print(f"  DHW 峰值      : {ctx['dhwMax']}")
    print(f"  白化预警等级  : {ctx['baaLabel']}（{ctx['baa']}/4）")
    print(f"  风险分        : {ctx['riskScore']}")
    print(f"  DHW≥4 天数    : {ctx['daysDhwGe4']}")
    print(f"  DHW≥8 天数    : {ctx['daysDhwGe8']}")
    print(f"  峰值日期      : {ctx['peakDate']}")
    print(f"  与其它年份    : {ctx['anomalyNote']}")
    print(f"  解读          : {ctx['verdict']}")
    if ctx.get("sstMax") is not None:
        print(f"  海表温度      : 最高 {ctx['sstMax']}°C，平均 {ctx['sstMean']}°C")
    if ctx.get("sstAnomalyMax") is not None:
        print(f"  海温距平峰值  : {ctx['sstAnomalyMax']}°C")
    if ctx.get("hotspotMax") is not None:
        print(f"  热异常峰值    : {ctx['hotspotMax']}°C")
    print(f"  BAA 数据来源  : {ctx.get('baaSource')}")


if __name__ == "__main__":
    main()
