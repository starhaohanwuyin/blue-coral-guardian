"""接入 GCBD（全球珊瑚白化数据库 1980–2020）并与本项目的 41 年 DHW 序列做一致性分析。

为什么做：② 要求"分析历史白化事件分布特征"，而项目当前只有 **RCM 报告里的 8 个事件年**
（事件级）。GCBD 是逐条白化观测（时间/地点/严重度），能把这件事从"8 个年份对上了 3 个"
升级为**统计级**：命中率、漏报年、以及"白化起始 DHW 阈值"在本区域的合理性。

出处：van Woesik & Kratochwill (2022) *A global coral-bleaching database, 1980–2020*,
Scientific Data, DOI 10.1038/s41597-022-01121-y；数据托管在 figshare（见下）。

⚠️ 本网络实测：figshare / Zenodo 均返回 **403**（站点侧拦截出口 IP），因此脚本支持两种输入：
  ① 直接 `--file 本地.csv`（推荐：让能上外网的队友下载后给你）
  ② 不给 `--file` 时尝试从候选 URL 下载（通就下，不通就打印手工指引）

用法：
    python ingest_gcbd.py --file data/raw/gcbd/gcbd.csv
    python ingest_gcbd.py --try-download
输出：reports/gcbd_consistency.json
"""
import argparse
import csv
import io
import json
import pathlib
import sys
import urllib.request
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROFILE = ROOT / "data" / "noaa" / "site_profiles.json"
OUT = ROOT / "reports" / "gcbd_consistency.json"
GRID = {"latMin": 4.025, "latMax": 5.025, "lonMin": 118.025, "lonMax": 119.525}

# 候选下载地址（figshare 文章 19121737 是 GCBD 的常见入口；不同版本 id 可能不同）
CANDIDATES = [
    "https://figshare.com/ndownloader/articles/19121737/versions/1",
    "https://ndownloader.figshare.com/articles/19121737/versions/1",
    "https://springernature.figshare.com/ndownloader/articles/19121737/versions/1",
]

# 列名模糊匹配（GCBD 各版本字段名不完全一致）
COLMAP = {
    "year": ["bleaching_year", "year", "date", "bleaching_date", "survey_year"],
    "lat": ["latitude", "lat", "lat_dd", "decimal_latitude"],
    "lon": ["longitude", "lon", "lng", "long", "decimal_longitude"],
    "severity": ["severity", "bleaching_severity", "severity_code", "bleaching_level"],
    "country": ["country", "country_name", "nation"],
    "site": ["site", "site_name", "reef", "location"],
}


def pick(cols, keys):
    low = {c.lower().strip(): c for c in cols}
    for k in keys:
        if k in low:
            return low[k]
    for c in cols:
        for k in keys:
            if k in c.lower():
                return c
    return None


def try_download(dest: pathlib.Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    for u in CANDIDATES:
        try:
            print(f"  尝试 {u[:80]} …")
            with urllib.request.urlopen(urllib.request.Request(
                    u, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
                body = r.read()
            if len(body) < 1000:
                print(f"    返回过小（{len(body)} 字节），可能是错误页")
                continue
            dest.write_bytes(body)
            print(f"  ✅ 已下载 {len(body)/1024:.0f} KB → {dest}")
            return dest
        except Exception as e:
            print(f"    ❌ {type(e).__name__}: {str(e)[:70]}")
    print("\n❌ 候选地址均不可用。本机网络实测 figshare 返回 403（站点侧拦截）。手工获取方式：")
    print("   ① 让能上外网的队友打开论文的 Data availability（DOI 10.1038/s41597-022-01121-y）")
    print("      下载 GCBD 的 CSV，放到 data/raw/gcbd/ 下")
    print("   ② 然后运行：python ingest_gcbd.py --file data/raw/gcbd/<文件名>.csv")
    print("   ③ 或换网络/代理后重跑：python ingest_gcbd.py --try-download")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="", help="本地 GCBD CSV 路径")
    ap.add_argument("--try-download", action="store_true", help="尝试从候选地址下载")
    a = ap.parse_args()

    path = pathlib.Path(a.file) if a.file else None
    if path is None and a.try_download:
        path = try_download(ROOT / "data" / "raw" / "gcbd" / "gcbd.csv")
    if path is None or not path.exists():
        # 也许用户已经手工放到默认目录
        guess = sorted((ROOT / "data" / "raw" / "gcbd").glob("*.csv")) if (ROOT / "data" / "raw" / "gcbd").exists() else []
        if guess:
            path = guess[0]
            print(f"发现本地文件：{path}")
        else:
            print("❌ 没有可用输入。用 --file 指定 CSV，或 --try-download 尝试下载（本网络大概率不通）。")
            return 2

    text = path.read_text(encoding="utf-8", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        print(f"❌ {path} 里没有数据行")
        return 2
    cols = list(rows[0].keys())
    print(f"读取 {path.name}：{len(rows)} 条记录，{len(cols)} 列")
    print(f"  列名: {cols[:14]}{' …' if len(cols) > 14 else ''}")

    cy, cla, clo = pick(cols, COLMAP["year"]), pick(cols, COLMAP["lat"]), pick(cols, COLMAP["lon"])
    csev = pick(cols, COLMAP["severity"])
    print(f"  自动识别：年份={cy}  纬度={cla}  经度={clo}  严重度={csev}")
    if not (cy and cla and clo):
        print("❌ 无法识别 年份/经纬度 列；请把实际列名发我，我补进 COLMAP。")
        return 3

    def fnum(v):
        try:
            return float(str(v).replace("°", " ").split()[0])
        except Exception:
            return None

    in_grid, years_in_grid, years_all = [], Counter(), Counter()
    for r in rows:
        y = str(r.get(cy, ""))[:4]
        if not y.isdigit():
            continue
        years_all[y] += 1
        la, lo = fnum(r.get(cla)), fnum(r.get(clo))
        if la is None or lo is None:
            continue
        if GRID["latMin"] <= la <= GRID["latMax"] and GRID["lonMin"] <= lo <= GRID["lonMax"]:
            in_grid.append(r)
            years_in_grid[y] += 1

    print(f"\n落在本项目网格（仙本那 4.03–5.03N / 118.03–119.53E）的记录：{len(in_grid)} 条")
    if years_in_grid:
        print(f"  涉及年份: {sorted(years_in_grid.items())}")

    # 与项目 41 年 DHW 对比
    result = {
        "task": "GCBD 全球白化数据库 × 项目 41 年 DHW 序列（命中率与阈值一致性）",
        "source": {"dataset": "GCBD (van Woesik & Kratochwill 2022)",
                   "doi": "10.1038/s41597-022-01121-y", "file": path.name,
                   "records": len(rows), "columns": cols,
                   "detected": {"year": cy, "lat": cla, "lon": clo, "severity": csev}},
        "grid": GRID, "recordsInGrid": len(in_grid),
        "yearsInGrid": dict(sorted(years_in_grid.items())),
    }

    if PROFILE.exists():
        prof = json.loads(PROFILE.read_text(encoding="utf-8"))
        region_max = prof.get("regionMaxPeakByYear") or {}
        region_mean = prof.get("regionMeanPeakByYear") or {}
        alert_frac = prof.get("alertCellFractionByYear") or {}
        if not region_max:      # 档案里是逐格点结构时，现算区域统计
            peaks = defaultdict(list)
            for c in prof["cells"].values():
                for y, v in (c.get("peakByYear") or {}).items():
                    peaks[y].append(v)
            region_max = {y: max(v) for y, v in peaks.items()}
            region_mean = {y: sum(v) / len(v) for y, v in peaks.items()}
            alert_frac = {y: sum(1 for x in v if x >= 4) / len(v) for y, v in peaks.items()}
        all_years = sorted(int(y) for y in region_max)      # ⚠️ 档案里的键是字符串，统一转 int 再比较
        report_years = sorted(int(y) for y in years_in_grid)
        rmax = {int(y): v for y, v in region_max.items()}
        # 命中率：网格内有白化记录的年份中，我们 DHW 是否也达警戒（≥4）
        hit = [y for y in report_years if y in rmax and rmax[y] >= 4]
        miss = [y for y in report_years if y in rmax and rmax[y] < 4]
        # 反向：我们达警戒但 GCBD 没记录（GCBD 只到 2020，故只看 1980–2020）
        only_ours = [y for y in all_years if y <= 2020 and rmax[y] >= 4 and y not in report_years]
        thr_table = []
        for thr in (2, 3, 4, 5, 6, 8):
            tp = sum(1 for y in report_years if y in rmax and rmax[y] >= thr)
            fn = sum(1 for y in report_years if y in rmax and rmax[y] < thr)
            fp = sum(1 for y in all_years if y <= 2020 and rmax[y] >= thr and y not in report_years)
            tn = sum(1 for y in all_years if y <= 2020 and rmax[y] < thr and y not in report_years)
            prec = tp / (tp + fp) if tp + fp else 0.0
            rec = tp / (tp + fn) if tp + fn else 0.0
            thr_table.append({"threshold": thr, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                              "precision": round(prec, 3), "recall": round(rec, 3)})
        result["consistency"] = {
            "gridReportYears": report_years,
            "yearsOurDhwAlsoAlert": hit, "yearsOurDhwBelow4": miss,
            "alertYearsWithoutGcbdRecord": only_ours,
            "thresholdSweep": thr_table,
            "regionMaxPeakByYear": {str(y): rmax[y] for y in report_years if y in rmax},
        }
        print(f"\n命中率分析（GCBD 记录年 vs 我们 DHW≥4）：命中 {hit} / 未达 4 的 {miss}")
        print("阈值扫描：")
        print(f"  {'阈值':>5}{'TP':>5}{'FP':>5}{'FN':>5}{'TN':>5}{'精确率':>9}{'召回':>8}")
        for t in thr_table:
            print(f"  {t['threshold']:>5}{t['tp']:>5}{t['fp']:>5}{t['fn']:>5}{t['tn']:>5}"
                  f"{t['precision']:>9.3f}{t['recall']:>8.3f}")
    else:
        print(f"⚠️ 找不到 {PROFILE}（先用 climate_site_profile.py --build 生成），本次只做记录统计")
        result["consistency"] = None

    result["caveats"] = [
        "GCBD 是**报告式**数据库：存在报告偏差（有人调查才有记录），不能当「未记录=未发生」来解读",
        "GCBD 覆盖 1980–2020，本项目 DHW 到 2025，故 2021–2025 无法做双向核对",
        "GCBD 的空间精度是站点级（经纬度来自文献），与 5km 格点不是同一尺度",
        "网格内记录数可能很少（仙本那/沙巴的报告密度远低于加勒比），命中率n 小，只作方向性核对",
        "本网络无法直连 figshare，数据需由可访问的机器下载后提供（脚本支持 --file）",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
