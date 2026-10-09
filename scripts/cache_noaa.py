"""
NOAA CRW 离线缓存（E14）
================================================================
背景：NOAA Coral Reef Watch 的 ERDDAP 在国内访问**时段性中断**
      （实测：14:30 可下载 → 次日 08:00 返回 403/超时）。
      因此环境数据必须**离线缓存**，不能运行时实时拉取。

本脚本：
  · 拉取仙本那海域（可配置 bbox）的 CRW v3.1 5km 日序列
  · 变量：DHW（热压力累积）、HotSpot（白化热点）、SST SSTA、BAA（白化预警等级）
  · **分年请求**（单次请求过大易被中断），逐年落盘 + 断点续传
  · 每轮失败自动重试，可反复运行直到成功

数据集规格（实测确认）：
  datasetID  : NOAA_DHW（另有 NOAA_DHW_monthly）
  时间覆盖   : 1985-04-01 → 近实时（每日更新）
  分辨率     : 0.05°（5km），lat 为**降序**
  许可       : 美国联邦政府作品（公有领域）

用法：
    python cache_noaa.py --bbox 4.0,118.0,5.0,119.5 --start 2023-01-01
    python cache_noaa.py --bbox 4.0,118.0,5.0,119.5 --start 1985-04-01 --end 2025-12-31
    python cache_noaa.py --status            # 只查看已缓存情况
"""
import argparse
import json
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "noaa"

# ⚠️ 实测（2026-10）：
#   coastwatch.pfeg.noaa.gov 会 302 重定向到 PacIOOS，
#   而**只有 PacIOOS 镜像真正可达**（直连 coastwatch 拿不到数据）。
#   因此把 PacIOOS 作为主端点，其余作为兜底。
ERDDAP_ENDPOINTS = [
    "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/dhw_5km.csv",       # ✅ 实测可用
    "https://coastwatch.pfeg.noaa.gov/erddap/griddap/NOAA_DHW.csv",          # 302 → PacIOOS
    "https://coastwatch.noaa.gov/erddap/griddap/noaacrwdhw5km.csv",          # 兜底
]
ERDDAP = ERDDAP_ENDPOINTS[0]
VARS = ["CRW_DHW", "CRW_HOTSPOT", "CRW_SSTANOMALY", "CRW_BAA", "CRW_SST"]
UA = "CoralReefResearch/1.0 (academic; contact: coral-research@example.org)"
# NOAA 白化预警等级定义（实测确认）
BAA_LEVELS = {0: "No Stress", 1: "Watch", 2: "Warning", 3: "Alert Level 1", 4: "Alert Level 2"}


def build_url(bbox, start, end, var, endpoint=None):
    """⚠️ 实测：多变量合并查询会失败（404），必须**逐变量**请求。"""
    s, w, n, e = [f"{x}" for x in bbox]
    return (f"{endpoint or ERDDAP}?{var}[({start}):1:({end})]"
            f"[({n}):1:({s})][({w}):1:({e})]")


def fetch(url, timeout=300, retries=3, verbose=True):
    """依次尝试各个 ERDDAP 端点，全部失败才抛错。"""
    last = None
    for i in range(retries):
        for ep in ERDDAP_ENDPOINTS:
            u = url.replace(ERDDAP, ep, 1)
            try:
                req = Request(u, headers={"User-Agent": UA})
                with urlopen(req, timeout=timeout) as r:
                    txt = r.read().decode("utf-8", errors="replace")
                    if txt.startswith("time") and len(txt) > 100:
                        return txt
                    last = RuntimeError(f"{ep.split('/')[2]} 返回非 CSV")
            except Exception as e:
                last = e
                if verbose:
                    print(f"      [{ep.split('/')[2]}] {type(e).__name__}", flush=True)
        if i < retries - 1:
            time.sleep(5 * (i + 1))
    raise last


def merge_year(year_files):
    """把逐变量 CSV 按键 (time, lat, lon) 合并成一张宽表。"""
    table = {}          # key -> {var: value}
    header = None
    var_names = []
    for var, path in year_files:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) < 3:
            continue
        var_names.append(var)
        if header is None:
            # 跳过前两行（列名 + 单位）
            header = lines[0]
        for ln in lines[2:]:
            parts = ln.split(",")
            if len(parts) < 4:
                continue
            key = (parts[0], parts[1], parts[2])
            table.setdefault(key, {})[var] = parts[3]
    if not table:
        return None
    cols = ["time", "latitude", "longitude"] + var_names
    out = [",".join(cols)]
    for key in sorted(table.keys()):
        row = list(key) + [table[key].get(v, "") for v in var_names]
        out.append(",".join(row))
    return "\n".join(out) + "\n"


def years(start, end):
    y0, y1 = int(start[:4]), int(end[:4])
    for y in range(y0, y1 + 1):
        a = f"{y}-01-01" if y > y0 else start
        b = f"{y}-12-31" if y < y1 else end
        yield y, a, b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", default="4.0,118.0,5.0,119.5",
                    help="south,west,north,east（默认仙本那外海）")
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--end", default="2026-10-01")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)

    if args.status:
        files = sorted(CACHE.glob("*.csv"))
        tot = 0
        print(f"缓存目录: {CACHE}")
        for f in files:
            n = sum(1 for _ in f.open(encoding="utf-8", errors="replace")) - 1
            tot += max(n, 0)
            print(f"  {f.name:<34} {n:>8} 行  {f.stat().st_size/1024:>8.0f} KB")
        print(f"合计约 {tot} 条记录")
        meta = CACHE / "cache_meta.json"
        if meta.exists():
            print("\n元信息:", json.dumps(json.loads(meta.read_text(encoding="utf-8")), ensure_ascii=False))
        return 0

    bbox = [float(x) for x in args.bbox.split(",")]
    print(f"区域 bbox(S,W,N,E) = {bbox}")
    print(f"时间范围: {args.start} → {args.end}")
    print(f"变量: {VARS}")
    print(f"ERDDAP: {ERDDAP}\n")

    ok_years, failed = [], []
    manifest = []
    for y, a, b in years(args.start, args.end):
        out = CACHE / f"CRW_semporna_{y}.csv"
        if out.exists() and out.stat().st_size > 200:
            n = sum(1 for _ in out.open(encoding="utf-8", errors="replace")) - 1
            print(f"  [跳过] {y}  已缓存 {n} 行")
            ok_years.append(y)
            manifest.append({"year": y, "file": out.name, "rows": n, "status": "cached"})
            continue

        # ⚠️ 逐变量抓取：多变量合并查询实测会 404
        print(f"  [拉取] {y}  ({a} → {b})  逐变量", flush=True)
        yfiles, err = [], None
        for var in VARS:
            vp = CACHE / f"_raw_{var}_{y}.csv"
            if vp.exists() and vp.stat().st_size > 200:
                yfiles.append((var, vp))
                print(f"      {var:<18} 已缓存", flush=True)
                continue
            try:
                txt = fetch(build_url(bbox, a, b, var))
                vp.write_text(txt, encoding="utf-8")
                n = txt.count("\n") - 2
                yfiles.append((var, vp))
                print(f"      {var:<18} OK  {n} 行  {vp.stat().st_size/1024:.0f} KB", flush=True)
            except Exception as e:
                print(f"      {var:<18} 失败: {type(e).__name__}", flush=True)
                err = e
            time.sleep(0.8)

        if len(yfiles) >= 3:
            merged = merge_year(yfiles)
            if merged:
                out.write_text(merged, encoding="utf-8")
                n = merged.count("\n") - 1
                print(f"      合并 → {out.name}  {n} 行  {out.stat().st_size/1024:.0f} KB")
                ok_years.append(y)
                manifest.append({"year": y, "file": out.name, "rows": n,
                                 "vars": [v for v, _ in yfiles], "status": "ok"})
                continue
        print(f"      失败：可用变量不足（{len(yfiles)}/{len(VARS)}）")
        failed.append(y)
        manifest.append({"year": y, "file": None, "rows": 0,
                         "vars": [v for v, _ in yfiles], "status": f"failed: {err}"})
        time.sleep(1.5)

    (CACHE / "cache_meta.json").write_text(json.dumps({
        "bbox": bbox, "vars": VARS, "dataset": "NOAA_DHW (CRW v3.1 5km)",
        "baaLevels": BAA_LEVELS, "license": "US Government work (public domain)",
        "okYears": ok_years, "failedYears": failed, "manifest": manifest,
        "note": "NOAA 在国内访问时段性中断；本脚本可反复运行直到全部年份拉取成功",
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n成功 {len(ok_years)} 年，失败 {len(failed)} 年 {failed if failed else ''}")
    if failed:
        print("提示：NOAA 时段性不可达，稍后重跑本脚本即可续传（已缓存的年份会自动跳过）")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
