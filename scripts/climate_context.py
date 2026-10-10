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


def build_index(force: bool = False):
    """把逐年 CSV 压缩成「格点 × 年份」统计索引（一次性）。"""
    files = _year_files()
    if not files:
        raise SystemExit(f"未找到 NOAA 数据：{NOAA_DIR}/_raw_CRW_DHW_*.csv")
    if INDEX.exists() and not force:
        print(f"索引已存在（--force 可重建）：{INDEX}")
        return json.loads(INDEX.read_text(encoding="utf-8"))

    out = {"source": "NOAA CRW v3.1 5km via PacIOOS mirror",
           "region": "4.025-5.025N, 118.025-119.525E", "years": {}}

    for f in files:
        year = f.stem.split("_")[-1]
        # key = "lat_lon" → 该格点该年的统计
        cells = {}
        with open(f, newline="", encoding="utf-8") as fh:
            r = csv.reader(fh)
            next(r)
            next(r)  # 两行表头
            for row in r:
                if len(row) < 4:
                    continue
                try:
                    dhw = float(row[3])
                except ValueError:
                    continue  # NaN
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

        # 由 DHW 峰值推 BAA 等级
        #   简化规则（与 NOAA 的 5km 产品一致）：
        #     DHW < 1              → 0 无压力
        #     1 ≤ DHW < 4          → 1 白化观察
        #     4 ≤ DHW < 8          → 2 白化警告
        #     DHW ≥ 8 且 hotspot<1 → 3 白化警报一级
        #     DHW ≥ 8 且 hotspot≥1 → 4 白化警报二级（此处按 DHW≥12 近似）
        for c in cells.values():
            m = c["max"]
            if m < 1:
                baa = 0
            elif m < 4:
                baa = 1
            elif m < 8:
                baa = 2
            elif m < 12:
                baa = 3
            else:
                baa = 4
            c["baa"] = baa
            c["baaLabel"] = BAA_LABEL[baa]
        out["years"][year] = cells
        print(f"  {year}: {len(cells)} 个格点，峰值 DHW = {max(c['max'] for c in cells.values()):.2f}")

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

    c = idx["years"][str(year)][key]
    la, lo = (float(x) for x in key.split("_"))

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
        "typicalDhwMax": round(typical, 2) if typical is not None else None,
        "anomalyVsOtherYears": round(anomaly, 2) if anomaly is not None else None,
        "anomalyNote": (
            f"比其它年份平均高 {anomaly:+.2f}（{(anomaly/typical*100):+.0f}%）"
            if typical and anomaly is not None else "无对比年份"
        ),
        "source": idx["source"],
        "availableYears": years,
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


if __name__ == "__main__":
    main()
