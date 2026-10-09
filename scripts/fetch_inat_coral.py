"""
从 iNaturalist 抓取指定海域的珊瑚观察记录（含照片 URL、许可、坐标）
================================================================
用途：为「仙本那珊瑚识别」构建**目标域**数据集。

iNaturalist 的价值：
  - 地理位置精确（可框定仙本那/Sipadan/Mabul/Kapalai）
  - 物种鉴定为**专家/社区共识**（quality_grade=research 表示已达研究级）
  - 照片带许可证字段，可合规使用

用法：
    python fetch_inat_coral.py --name semporna --bbox 4.0,118.2,4.8,119.0
    python fetch_inat_coral.py --name sabah    --bbox 4.0,115.0,7.5,119.5
    python fetch_inat_coral.py --name sulu     --bbox 1.0,116.0,7.5,126.0

输出：data/inat/<name>.json  （观察记录清单）
     终端打印物种分布统计
"""
import argparse
import collections
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "inat"
API = "https://api.inaturalist.org/v1/observations"

# iNaturalist 会封禁泛化的 User-Agent，必须带可识别信息
UA = "CoralReefResearch/1.0 (academic coral reef study; contact: coral-research@example.org)"

# 石珊瑚目（硬珊瑚）
SCLERACTINIA = 47532

# 关注的高级类群（用于诊断覆盖度）
TAXA = {
    "Scleractinia(石珊瑚目)": 47532,
    "Acropora(鹿角珊瑚属)": 48745,
    "Porites(滨珊瑚属)": 47530,
    "Montipora(蔷薇珊瑚属)": 90035,
    "Pocillopora(杯形珊瑚属)": 60547,
}


def call(url, retries=6):
    """带指数退避的请求。403/429 视为限流，退避后重试。"""
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 429, 500, 502, 503, 504):
                wait = min(90, 5 * (2 ** i))
                print(f"    HTTP {e.code} 限流/错误 → 等待 {wait}s 后重试 ({i+1}/{retries})", flush=True)
                time.sleep(wait)
                continue
            raise
        except Exception as e:
            last = e
            wait = min(60, 3 * (i + 1))
            print(f"    {type(e).__name__}: {e} → 等待 {wait}s ({i+1}/{retries})", flush=True)
            time.sleep(wait)
    raise last


def fetch(taxon_id, bbox, max_pages=200, sleep=2.5, partial=None, tile=1):
    """逐页抓取，**每页落盘**（partial 文件），支持断点续传。

    ⚠️ iNaturalist API 有**分页硬上限**：单个查询最多返回 10,000 条
       （超出会返回 HTTP 403，而非限流）。
       因此当目标区域总量 > 10,000 时，必须用 tile=N 把区域切成 N×N 网格，
       分别查询后再合并去重。
    """
    swlat, swlng, nelat, nelng = [float(x) for x in bbox.split(",")]

    # 构造查询网格
    if tile <= 1:
        boxes = [(swlat, swlng, nelat, nelng)]
    else:
        boxes = []
        dlat = (nelat - swlat) / tile
        dlng = (nelng - swlng) / tile
        for i in range(tile):
            for j in range(tile):
                boxes.append((swlat + i * dlat, swlng + j * dlng,
                              swlat + (i + 1) * dlat, swlng + (j + 1) * dlng))

    out, seen = [], set()
    if partial and partial.exists():
        try:
            saved = json.loads(partial.read_text(encoding="utf-8"))
            out = saved.get("raw", [])
            seen = {o.get("id") for o in out}
            done_boxes = saved.get("done_boxes", [])
            print(f"    断点续传：已有 {len(out)} 条，已完成 {len(done_boxes)}/{len(boxes)} 个网格")
        except Exception as e:
            print(f"    续传文件损坏，重新开始: {e}")
            out, seen, done_boxes = [], set(), []
    else:
        done_boxes = []

    total_all = 0
    for bi, (a, w, b, e) in enumerate(boxes):
        if bi in done_boxes:
            continue
        page, sub_total = 1, None
        while page <= max_pages:
            q = urllib.parse.urlencode({
                "taxon_id": taxon_id,
                "swlat": a, "swlng": w, "nelat": b, "nelng": e,
                "per_page": 200, "page": page,
                "quality_grade": "research", "photos": "true",
            })
            try:
                j = call(f"{API}?{q}")
            except urllib.error.HTTPError as ex:
                if ex.code == 403:
                    print(f"    [网格 {bi+1}/{len(boxes)}] 第 {page} 页 403 —— "
                          f"已达 10,000 条分页上限，该网格停止（建议增大 --tile）", flush=True)
                    break
                raise
            res = j.get("results", [])
            if sub_total is None:
                sub_total = j.get("total_results", 0)
                total_all += sub_total
                print(f"    [网格 {bi+1}/{len(boxes)}] 子区域总数: {sub_total}", flush=True)
            added = 0
            for o in res:
                if o.get("id") not in seen:
                    seen.add(o.get("id"))
                    out.append(o)
                    added += 1
            print(f"      第 {page} 页: +{added}(新增)  累计 {len(out)}", flush=True)

            if partial:
                partial.write_text(json.dumps(
                    {"total": total_all, "next_page": page + 1,
                     "done_boxes": done_boxes, "raw": out}), encoding="utf-8")

            if not res or page * 200 >= (sub_total or 0):
                break
            page += 1
            time.sleep(sleep)
        done_boxes.append(bi)
        if partial:
            partial.write_text(json.dumps(
                {"total": total_all, "next_page": 1,
                 "done_boxes": done_boxes, "raw": out}), encoding="utf-8")
    return out, total_all


def simplify(obs):
    """只保留训练/评估需要的字段。"""
    t = obs.get("taxon") or {}
    photos = []
    for p in obs.get("photos", []) or []:
        url = p.get("url") or ""
        # 取原图尺寸
        orig = p.get("original_dimensions") or {}
        photos.append({
            "url": url.replace("/square.", "/large.").replace("/thumb.", "/large."),
            "url_original": url,
            "width": orig.get("width"), "height": orig.get("height"),
            "license": p.get("license_code") or obs.get("license_code"),
            "attribution": p.get("attribution"),
        })
    g = obs.get("geojson") or {}
    c = g.get("coordinates") or [None, None]
    return {
        "id": obs.get("id"),
        "observed_on": obs.get("observed_on"),
        "taxon_id": t.get("id"),
        "taxon_name": t.get("name"),
        "common_name": (t.get("preferred_common_name") or ""),
        "rank": t.get("rank"),
        "ancestry": t.get("ancestry"),
        "lon": c[0], "lat": c[1],
        "place_guess": obs.get("place_guess"),
        "license": obs.get("license_code"),
        "photos": photos,
        "uri": obs.get("uri"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--bbox", required=True, help="swlat,swlng,nelat,nelng")
    ap.add_argument("--taxon", type=int, default=SCLERACTINIA)
    ap.add_argument("--sleep", type=float, default=2.5,
                    help="每页间隔秒数（iNat 限制约 60 请求/分钟，2.5s 对应 24/分钟，安全）")
    ap.add_argument("--no-diagnose", action="store_true", help="跳过类群覆盖度诊断（省请求）")
    ap.add_argument("--tile", type=int, default=1,
                    help="把区域切成 N×N 网格分别查询。iNat 单查询上限 10,000 条，"
                         "大区域必须分块（如 --tile 3）")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    print(f"区域: {args.name}   bbox: {args.bbox}   taxon_id: {args.taxon}")

    if args.taxon == SCLERACTINIA and not args.no_diagnose:
        print("  诊断各高级类群覆盖度：")
        for label, tid in TAXA.items():
            swlat, swlng, nelat, nelng = [float(x) for x in args.bbox.split(",")]
            q = urllib.parse.urlencode({"taxon_id": tid, "swlat": swlat, "swlng": swlng,
                                        "nelat": nelat, "nelng": nelng,
                                        "per_page": 1, "quality_grade": "research"})
            try:
                j = call(f"{API}?{q}")
                print(f"    {label:<26} {j.get('total_results')}")
            except Exception as e:
                print(f"    {label:<26} ERR {e}")
            time.sleep(0.6)

    print("  抓取中...", flush=True)
    partial = OUT / f"{args.name}.partial.json"
    # 旧格式（未分块）迁移：保留已抓数据，让分块查询靠 obs id 去重续抓，不重复
    if partial.exists() and args.tile > 1:
        try:
            old = json.loads(partial.read_text(encoding="utf-8"))
            if not old.get("done_boxes") and old.get("raw"):
                keep = len(old["raw"])
                partial.write_text(json.dumps(
                    {"total": old.get("total", 0), "next_page": 1,
                     "done_boxes": [], "raw": old["raw"]}), encoding="utf-8")
                print(f"    已迁移旧续传文件：保留 {keep} 条已抓记录，"
                      f"按网格补齐剩余（自动按 obs id 去重）")
        except Exception as e:
            print(f"    续传文件迁移失败（将重新抓取）: {e}")
    raw, total = fetch(args.taxon, args.bbox, sleep=args.sleep, partial=partial, tile=args.tile)
    recs = [simplify(o) for o in raw]
    print(f"  抓取完成: {len(recs)}/{total}", flush=True)

    # 统计
    sp = collections.Counter(r["taxon_name"] for r in recs)
    ranks = collections.Counter(r["rank"] for r in recs)
    lic = collections.Counter(r["license"] or "none" for r in recs)
    n_photos = sum(len(r["photos"]) for r in recs)
    spp_ge10 = [k for k, v in sp.items() if v >= 10]
    spp_ge20 = [k for k, v in sp.items() if v >= 20]

    print(f"\n  观察记录: {len(recs)}   照片总数: {n_photos}")
    print(f"  鉴定等级: {dict(ranks)}")
    print(f"  许可证  : {dict(lic)}")
    print(f"  物种数  : {len(sp)}   (≥10 条: {len(spp_ge10)}   ≥20 条: {len(spp_ge20)})")
    print(f"\n  物种分布 Top 30:")
    for k, v in sp.most_common(30):
        print(f"    {k:<34} {v}")

    out = OUT / f"{args.name}.json"
    out.write_text(json.dumps({
        "name": args.name, "bbox": args.bbox, "taxon_id": args.taxon,
        "n_observations": len(recs), "n_photos": n_photos,
        "species_count": len(sp), "species_ge10": len(spp_ge10),
        "species_distribution": dict(sp.most_common()),
        "records": recs,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  已写入: {out}")

    # 成功后清理续传文件（节省磁盘）
    if partial.exists() and len(recs) >= (total or 0):
        partial.unlink()
        print(f"  已清理续传文件: {partial.name}")


if __name__ == "__main__":
    main()
