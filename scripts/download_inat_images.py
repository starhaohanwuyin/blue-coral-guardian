"""
下载 iNaturalist 图片并组织成 ImageFolder 结构
================================================================
输出：
    data/inat_dataset/images/train/<class>/<photoId>.jpg
    data/inat_dataset/images/test/<class>/<photoId>.jpg
    data/inat_dataset/ATTRIBUTION.csv      ← 许可证与作者归属（合规必需）

特性：
  - 断点续传（已存在的文件跳过）
  - 并发下载（默认 8 线程，对 iNat 友善）
  - 损坏图片自动跳过并记录
  - 兼容 jpg/png，统一保存原扩展名

用法：
    python download_inat_images.py --level genus --split train
    python download_inat_images.py --level genus --split test
    python download_inat_images.py --level genus --split all
"""
import argparse
import csv
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
DS = ROOT / "data" / "inat_dataset"
IMG = DS / "images"

HEADERS = {"User-Agent": "coral-research/1.0 (academic use)"}


def safe_name(s):
    return re.sub(r"[^0-9A-Za-z_.\-]", "_", str(s))


def download_one(item, out_dir):
    label = safe_name(item["label"])
    url = item["url"]
    ext = os.path.splitext(url.split("?")[0])[1].lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    dst = out_dir / label / f"{safe_name(item['obs_id'])}_{abs(hash(url)) % 100000}{ext}"
    if dst.exists() and dst.stat().st_size > 1024:
        return ("skip", dst, item)
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=60) as r:
            data = r.read()
        if len(data) < 1024:
            return ("small", dst, item)
        # 基本健康检查：JPEG/PNG 魔数
        if not (data[:2] == b"\xff\xd8" or data[:8].startswith(b"\x89PNG") or data[:4] == b"RIFF"):
            return ("bad", dst, item)
        dst.write_bytes(data)
        return ("ok", dst, item)
    except Exception as e:
        return (f"err:{type(e).__name__}", dst, item)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default="genus")
    ap.add_argument("--split", choices=["train", "val", "test", "all"], default="all")
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()

    splits = ["train", "val", "test"] if args.split == "all" else [args.split]
    attribution = []

    for split in splits:
        src = DS / f"{args.level}_{split}.json"
        if not src.exists():
            print(f"[跳过] 缺少 {src}，请先运行 build_inat_dataset.py")
            continue
        payload = json.loads(src.read_text(encoding="utf-8"))
        photos = payload["photos"]
        out_dir = IMG / split
        print(f"\n=== {split}: {len(photos)} 张 → {out_dir} ===")

        stats = {}
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(download_one, it, out_dir) for it in photos]
            done = 0
            for f in as_completed(futs):
                status, dst, item = f.result()
                key = status if not status.startswith("err") else "err"
                stats[key] = stats.get(key, 0) + 1
                if status == "ok":
                    attribution.append({
                        "split": split, "label": item["label"],
                        "file": str(dst.relative_to(DS)),
                        "taxon": item.get("taxon_name"),
                        "obs_id": item["obs_id"],
                        "license": item.get("license"),
                        "attribution": (item.get("attribution") or "").replace("\n", " "),
                        "lat": item.get("lat"), "lon": item.get("lon"),
                        "observed_on": item.get("observed_on"),
                        "source_url": item["url"],
                    })
                done += 1
                if done % 500 == 0:
                    print(f"    {done}/{len(photos)}  {stats}")

        print(f"  完成: {stats}")
        n_cls = len([d for d in out_dir.iterdir() if d.is_dir()]) if out_dir.exists() else 0
        print(f"  类别目录: {n_cls}")

    if attribution:
        ap_csv = DS / "ATTRIBUTION.csv"
        new = not ap_csv.exists()
        with open(ap_csv, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(attribution[0].keys()))
            if new:
                w.writeheader()
            w.writerows(attribution)
        print(f"\n归属记录追加 {len(attribution)} 行 → {ap_csv}")


if __name__ == "__main__":
    main()
