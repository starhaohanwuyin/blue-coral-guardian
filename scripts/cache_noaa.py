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
    "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/dhw_5km.csv",       # ✅ 2026-10-11 实测仍可用
    "https://coastwatch.pfeg.noaa.gov/erddap/griddap/NOAA_DHW.csv",          # ⚠️ 2026-10-11 本机 IP 被该站
    #                                                                          request blacklist（403，无 Retry-After）
    "https://coastwatch.noaa.gov/erddap/griddap/noaacrwdhw5km.csv",          # ❌ 2026-10-11 实测 404（数据集 ID 已失效）
    # ✅ 2026-10-11 实测可用：该站**没有 DHW 数据集**，但托管了 HotSpot 每日 5km
    #    （覆盖 1985-01-01 → 2026-10-03，逐日）。⚠️ 变量名是小写 `hotspot`，靠下面的别名表映射。
    "https://coastwatch.noaa.gov/erddap/griddap/noaacrwhotspotDaily.csv",
    # ✅ 2026-10-11 实测可用：官方 **BAA（白化预警区）7 天最大合成**，覆盖 1985-03-31 → 2026-10-09。
    #    ⚠️ 变量名是 `bleaching_alert_area`。已做对照试验：用它算的 **2024 年逐格点全年最大等级
    #    与现有逐日产品完全一致（544/544 格，0 处差异）** → 可安全用于补老年份。
    "https://coastwatch.noaa.gov/erddap/griddap/noaacrwbaa7dDaily.csv",
]
ERDDAP = ERDDAP_ENDPOINTS[0]

# 同一物理量在不同 ERDDAP 上的变量名可能不同（用别名表映射；响应列名会归一化回 VARS 里的名字，
# 否则下游 _raw_*.csv 的 schema 会不一致）
ENDPOINT_VAR_ALIAS = {
    "https://coastwatch.noaa.gov/erddap/griddap/noaacrwhotspotDaily.csv": {"CRW_HOTSPOT": "hotspot"},
    "https://coastwatch.noaa.gov/erddap/griddap/noaacrwbaa7dDaily.csv": {"CRW_BAA": "bleaching_alert_area"},
}

# 运行期可由 CLI 覆盖：只打单一镜像 / 请求间放慢（避免触发 ERDDAP 黑名单）
FETCH_ENDPOINTS = None
FETCH_THROTTLE = 0.0
VARS = ["CRW_DHW", "CRW_HOTSPOT", "CRW_SSTANOMALY", "CRW_BAA", "CRW_SST"]
UA = "CoralReefResearch/1.0 (academic; contact: coral-research@example.org)"
# NOAA 白化预警等级定义（实测确认）
BAA_LEVELS = {0: "No Stress", 1: "Watch", 2: "Warning", 3: "Alert Level 1", 4: "Alert Level 2"}


def build_url(bbox, start, end, var, endpoint=None, stride=1):
    """⚠️ 实测：多变量合并查询会失败（404），必须**逐变量**请求。"""
    s, w, n, e = [f"{x}" for x in bbox]
    return (f"{endpoint or ERDDAP}?{var}[({start}):{stride}:({end})]"
            f"[({n}):1:({s})][({w}):1:({e})]")


def fetch_year(var, a, b, bbox, stride=1, chunk_days=0, suffix=""):
    """抓取某变量某年的数据；chunk_days>0 时分段请求再拼接。

    ⚠️ 分块不是为了省流量而是为了**提速 + 可续传**：实测同一镜像上
    半年请求 9.7s、整年请求 120s（服务端对大请求明显更慢），且 NOAA 镜像
    **间歇性断连**（一次失败要等 5/10s 退避）。因此：
      1) 把一年拆成若干段，**每段单独落盘**（`.chunk_{var}{suffix}_{y}_{i}.csv`），
         中断后重跑可跳过已完成的段；
      2) 段大小按实测取 90 天（约 450 KB / 请求，~10 秒）。
    """
    if chunk_days <= 0:
        return fetch(build_url(bbox, a, b, var, stride=stride), var=var)
    from datetime import date, timedelta
    d0, d1 = date.fromisoformat(a), date.fromisoformat(b)
    spans, cur = [], d0
    while cur <= d1:
        nxt = min(cur + timedelta(days=chunk_days - 1), d1)
        spans.append((cur.isoformat(), nxt.isoformat()))
        cur = nxt + timedelta(days=1)
    head, rows, done = None, [], 0
    for i, (ca, cb) in enumerate(spans):
        # ⚠️ 分块文件名必须带 stride：否则同一日期区间的"每 5 天"缓存会被
        #    逐日请求复用，导致**静默拿到抽稀数据**（本轮真实踩到）
        cf = CACHE / f".chunk_{var}{suffix}_s{stride}_{ca}_{cb}.csv"
        if cf.exists() and cf.stat().st_size > 200:
            txt = cf.read_text(encoding="utf-8", errors="replace")
            done += 1
        else:
            txt = fetch(build_url(bbox, ca, cb, var, stride=stride), var=var)
            cf.write_text(txt, encoding="utf-8")
            time.sleep(0.5)
        lines = txt.splitlines()
        if head is None:
            head = lines[:2]                     # 仅首段保留表头两行
        rows.extend(lines[2:])
    print(f"        ({var} {done}/{len(spans)} 段来自缓存)")
    return "\n".join((head or []) + rows) + "\n"


def fetch(url, timeout=300, retries=3, verbose=True, endpoints=None, throttle=0.0, var=None):
    """依次尝试各个 ERDDAP 端点，全部失败才抛错。

    ⚠️ 2026-10-11 教训：`coastwatch.pfeg.noaa.gov` 因请求过多把本机 IP 加入
    **request blacklist**（403，无 Retry-After），而 `coastwatch.noaa.gov` 的
    兜底数据集 ID（`noaacrwdhw5km`）已失效（404）。PacIOOS 仍可用（200）。
    因此支持 `endpoints` 只打一个镜像 + `throttle` 放慢节奏，避免再次被封。

    `var`：本请求的物理量。若该端点在其变量名不同（见 ENDPOINT_VAR_ALIAS，例如
    HotSpot 在 coastwatch.noaa 上叫 `hotspot`），这里会做**双向映射**：
    请求时把变量名换成别名、响应时把列名换回标准名（保证 `_raw_*.csv` schema 一致）。
    """
    eps = endpoints or FETCH_ENDPOINTS or ERDDAP_ENDPOINTS
    last = None
    for i in range(retries):
        for ep in eps:
            alias = (ENDPOINT_VAR_ALIAS.get(ep) or {}).get(var) if var else None
            u = url.replace(ERDDAP, ep, 1)
            if alias:
                u = u.replace(var, alias, 1)
            try:
                req = Request(u, headers={"User-Agent": UA})
                with urlopen(req, timeout=timeout) as r:
                    txt = r.read().decode("utf-8", errors="replace")
                    if txt.startswith("time") and len(txt) > 100:
                        if alias:
                            txt = txt.replace(alias, var)      # 列名归一化
                        if throttle or FETCH_THROTTLE:
                            time.sleep(throttle or FETCH_THROTTLE)
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
    ap.add_argument("--vars", default=",".join(VARS),
                    help="逗号分隔的变量子集；长时序只需 DHW 与 HOTSPOT（体积减 60%）")
    ap.add_argument("--stride", type=int, default=1,
                    help="时间抽稀步长（天）：1=逐日；5=每 5 天（长时序用，体积减 80%）")
    ap.add_argument("--suffix", default="",
                    help="文件名后缀，用于与既有缓存区分（如 _lt），避免覆盖逐日缓存")
    ap.add_argument("--chunk-days", type=int, default=0,
                    help=">0 时把每年的请求拆成 N 天一段（小块请求实测更快）")
    ap.add_argument("--endpoint", default="",
                    help="优先使用的镜像 URL（默认 PacIOOS；实测 CoastWatch-PFEG 快约 5 倍）")
    ap.add_argument("--force", action="store_true",
                    help="忽略已有缓存重新抓取（用于改变抽稀步长后补全，如把每 5 天升为逐日）")
    ap.add_argument("--skip-daily", action="store_true",
                    help="跳过**已是逐日**的年份（用于长时间补全中断后续跑，避免重抓已完成年份）")
    ap.add_argument("--retries", type=int, default=3,
                    help="单个年份失败后的重试次数（镜像时段性不可用，默认 3）")
    ap.add_argument("--retry-sleep", type=float, default=20.0,
                    help="重试前的等待秒数（默认 20）")
    ap.add_argument("--single-endpoint", action="store_true",
                    help="只用 --endpoint 指定的镜像（被 ERDDAP 拉黑时用：不再浪费重试在 403 的服务器上）")
    ap.add_argument("--throttle", type=float, default=0.0,
                    help="每次成功请求后额外等待秒数（放慢节奏，避免被 ERDDAP 加入黑名单）")
    args = ap.parse_args()

    global ERDDAP, ERDDAP_ENDPOINTS, FETCH_ENDPOINTS, FETCH_THROTTLE
    if args.endpoint:
        ERDDAP = args.endpoint
        ERDDAP_ENDPOINTS = [args.endpoint] + [e for e in ERDDAP_ENDPOINTS if e != args.endpoint]
    if args.single_endpoint:
        # 只打一个镜像：被拉黑时不再把重试浪费在 403/404 的服务器上
        FETCH_ENDPOINTS = [ERDDAP]
        print(f"（--single-endpoint：只用 {ERDDAP.split('/')[2]}）")
    FETCH_THROTTLE = args.throttle
    if args.throttle:
        print(f"（--throttle {args.throttle}s：每次成功请求后等待，避免触发 ERDDAP 黑名单）")

    sel_vars = [v.strip() for v in args.vars.split(",") if v.strip() in VARS]
    if not sel_vars:
        print(f"错误：--vars 必须从 {VARS} 中选择")
        return 2

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
    print(f"变量: {sel_vars}   抽稀步长: {args.stride} 天   分块: {args.chunk_days or '不拆'}   后缀: {args.suffix or '(无)'}")
    print(f"ERDDAP: {ERDDAP}\n")

    ok_years, failed = [], []
    manifest = []

    def is_daily(p: Path) -> bool:
        """该变量文件是否已是**逐日**（≈360 个时间点/年），用于 --skip-daily 跳过已完成年份。"""
        if not p.exists() or p.stat().st_size < 3_000_000:
            return False
        try:
            with p.open(encoding="utf-8", errors="replace") as fh:
                return len({ln.split(",", 1)[0] for i, ln in enumerate(fh)
                            if i >= 2 and ln.strip()}) >= 200
        except OSError:
            return False

    for y, a, b in years(args.start, args.end):
        out = CACHE / f"CRW_semporna{args.suffix}_{y}.csv"
        raws = [CACHE / f"_raw_{v}{args.suffix}_{y}.csv" for v in sel_vars]
        if args.skip_daily and all(is_daily(p) for p in raws):
            print(f"  [跳过] {y}  已是逐日（{args.stride} 天步长请求下无需重抓）")
            ok_years.append(y)
            manifest.append({"year": y, "file": out.name, "status": "already-daily"})
            continue
        if out.exists() and out.stat().st_size > 200 and not args.force:
            n = sum(1 for _ in out.open(encoding="utf-8", errors="replace")) - 1
            print(f"  [跳过] {y}  已缓存 {n} 行")
            ok_years.append(y)
            manifest.append({"year": y, "file": out.name, "rows": n, "status": "cached"})
            continue

        # ⚠️ 逐变量抓取：多变量合并查询实测会 404
        print(f"  [拉取] {y}  ({a} → {b})  逐变量"
              + ("（--force：忽略已有缓存，按 stride=%d 重新抓取）" % args.stride
                 if args.force else ""), flush=True)
        yfiles, err = [], None
        attempt = 0
        while attempt < max(1, args.retries):
            attempt += 1
            if attempt > 1:
                print(f"      ↻ 第 {attempt} 次尝试（等待 {args.retry_sleep}s）", flush=True)
                time.sleep(args.retry_sleep)
            yfiles, err = [], None
            for var in sel_vars:
                vp = CACHE / f"_raw_{var}{args.suffix}_{y}.csv"
                if is_daily(vp) if args.skip_daily else (vp.exists() and vp.stat().st_size > 200):
                    if not args.force or is_daily(vp):
                        yfiles.append((var, vp))
                        print(f"      {var:<18} 已是逐日/已缓存", flush=True)
                        continue
                try:
                    txt = fetch_year(var, a, b, bbox, stride=args.stride,
                                     chunk_days=args.chunk_days, suffix=args.suffix)
                    vp.write_text(txt, encoding="utf-8")
                    n = txt.count("\n") - 2
                    yfiles.append((var, vp))
                    print(f"      {var:<18} OK  {n} 行  {vp.stat().st_size/1024:.0f} KB", flush=True)
                except Exception as e:
                    print(f"      {var:<18} 失败: {type(e).__name__}", flush=True)
                    err = e
                time.sleep(0.8)
            if len(yfiles) >= len(sel_vars):
                break
            print(f"      （本次 {len(yfiles)}/{len(sel_vars)} 个变量成功）", flush=True)

        # ⚠️ 门槛必须按**本次选中的变量数**判，不能写死 3（否则子集下载永远失败）
        if len(yfiles) >= len(sel_vars):
            merged = merge_year(yfiles)
            if merged:
                out.write_text(merged, encoding="utf-8")
                n = merged.count("\n") - 1
                print(f"      合并 → {out.name}  {n} 行  {out.stat().st_size/1024:.0f} KB")
                ok_years.append(y)
                manifest.append({"year": y, "file": out.name, "rows": n,
                                 "vars": [v for v, _ in yfiles], "status": "ok"})
                continue
        print(f"      失败：可用变量不足（{len(yfiles)}/{len(sel_vars)}）")
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
