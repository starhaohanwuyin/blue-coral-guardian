"""
构建「仙本那专属」珊瑚识别数据集
================================================================
核心设计（决定指标是否可信）：

  训练集 = 珊瑚大三角（iNaturalist 全域）**剔除仙本那区域**
  测试集 = 仙本那区域（4.0–4.8°N, 118.2–119.0°E）

  两者地理完全隔离 → **不存在任何图像/拍摄点泄漏**，
  因此在仙本那测得的精度就是真实的「跨地点泛化精度」。

类别策略：
  --level genus   按属聚合（样本更多、更可迁移，推荐）
  --level species 按种聚合（更细，但长尾严重）

   只保留「仙本那侧 ≥ --min-test 条」且「训练侧 ≥ --min-train 条」的类别，
   保证每一类都**既能训、又能测**。

用法：
    python build_inat_dataset.py --level genus --min-test 8 --min-train 40
    python build_inat_dataset.py --level species --min-test 10 --min-train 40
"""
import argparse
import collections
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INAT = ROOT / "data" / "inat"

# 仙本那目标域 bbox（与 fetch 时一致）
SEMPORNA_BBOX = (4.0, 118.2, 4.8, 119.0)


def in_bbox(lat, lon, bbox):
    if lat is None or lon is None:
        return False
    s, w, n, e = bbox
    return s <= lat <= n and w <= lon <= e


def genus_of(rec):
    """取属名：学名首词。需先剥离 "(Isopora)" 这类亚属括号与 'cf.'/'sp.' 等修饰。"""
    name = (rec.get("taxon_name") or "").strip()
    name = re.sub(r"\([^)]*\)", " ", name)
    name = re.sub(r"\b(cf|aff|sp|spp|nr)\.?\b", " ", name, flags=re.I)
    parts = [p for p in name.split() if p and p[0].isupper()]
    return parts[0] if parts else name


def label_of(rec, level):
    return genus_of(rec) if level == "genus" else (rec.get("taxon_name") or "")


def load(name):
    p = INAT / f"{name}.json"
    if not p.exists():
        raise SystemExit(f"缺少 {p}，请先运行 fetch_inat_coral.py --name {name} --bbox ...")
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", choices=["genus", "species"], default="genus")
    ap.add_argument("--min-test", type=int, default=8, help="仙本那侧每类最少观察数")
    ap.add_argument("--min-train", type=int, default=40, help="训练侧每类最少观察数")
    ap.add_argument("--max-per-class", type=int, default=400, help="训练侧每类最多保留观察数（防失衡）")
    args = ap.parse_args()

    tri = load("coraltriangle")
    sem = load("semporna")

    # ---- 训练侧剔除仙本那（地理隔离，防泄漏）----
    train_all = tri["records"]
    leaked = [r for r in train_all if in_bbox(r.get("lat"), r.get("lon"), SEMPORNA_BBOX)]
    train_pool = [r for r in train_all if not in_bbox(r.get("lat"), r.get("lon"), SEMPORNA_BBOX)]
    print(f"训练池: {len(train_all)} 条 → 剔除仙本那 {len(leaked)} 条 → 剩 {len(train_pool)} 条")
    print(f"测试集: {len(sem['records'])} 条（仙本那）")

    # ---- 统计 ----
    tr_cnt = collections.Counter(label_of(r, args.level) for r in train_pool)
    te_cnt = collections.Counter(label_of(r, args.level) for r in sem["records"])

    # ---- 选类：两侧都要够 ----
    classes = sorted(
        c for c in te_cnt
        if te_cnt[c] >= args.min_test and tr_cnt.get(c, 0) >= args.min_train
    )
    print(f"\n层级={args.level}  仙本那≥{args.min_test} 且 训练侧≥{args.min_train} → 入选 {len(classes)} 类")
    if not classes:
        print("⚠ 没有类别同时满足条件，放宽 --min-test / --min-train")
        return

    # ---- 组装 ----
    def photos_of(rs):
        out = []
        for r in rs:
            for ph in r["photos"]:
                out.append({
                    "label": label_of(r, args.level),
                    "obs_id": r["id"],
                    "url": ph["url"],
                    "license": ph.get("license") or "none",
                    "attribution": ph.get("attribution"),
                    "lat": r.get("lat"), "lon": r.get("lon"),
                    "observed_on": r.get("observed_on"),
                    "taxon_name": r.get("taxon_name"),
                })
        return out

    train_pool = [r for r in train_pool if label_of(r, args.level) in classes]
    test_pool = [r for r in sem["records"] if label_of(r, args.level) in classes]

    # 每类截断（防止某个大类碾压）
    by_cls = collections.defaultdict(list)
    for r in train_pool:
        by_cls[label_of(r, args.level)].append(r)
    train_sel = []
    for c, rs in by_cls.items():
        rs = sorted(rs, key=lambda r: r["id"])
        train_sel.extend(rs[: args.max_per_class])

    # ---- 训练池内按「观察 ID」切出验证集（同观察多图绝不跨 split）----
    rng = random.Random(42)
    tr_obs, va_obs = [], []
    by_cls2 = collections.defaultdict(list)
    for r in train_sel:
        by_cls2[label_of(r, args.level)].append(r)
    for c, rs in by_cls2.items():
        rs = sorted(rs, key=lambda r: r["id"])
        rng.shuffle(rs)
        k = max(1, int(round(len(rs) * 0.15)))
        va_obs.extend(rs[:k])
        tr_obs.extend(rs[k:])

    tr_photos = photos_of(tr_obs)
    va_photos = photos_of(va_obs)
    te_photos = photos_of(test_pool)

    # ---- 报告 ----
    print(f"\n{'类别':<26}{'训练obs':>8}{'训练图':>7}{'验证图':>7}{'测试obs':>8}{'测试图':>7}")
    print("-" * 70)
    tot_tr = tot_va = tot_te = 0
    for c in classes:
        a = sum(1 for x in tr_photos if x["label"] == c)
        v = sum(1 for x in va_photos if x["label"] == c)
        b = sum(1 for x in te_photos if x["label"] == c)
        tot_tr += a; tot_va += v; tot_te += b
        print(f"{c:<26}{tr_cnt[c]:>8}{a:>7}{v:>7}{te_cnt[c]:>8}{b:>7}")
    print("-" * 70)
    print(f"{'合计':<26}{'':>8}{tot_tr:>7}{tot_va:>7}{'':>8}{tot_te:>7}")

    outdir = ROOT / "data" / "inat_dataset"
    outdir.mkdir(parents=True, exist_ok=True)
    meta = {
        "level": args.level, "classes": classes,
        "min_test": args.min_test, "min_train": args.min_train,
        "semporna_bbox": SEMPORNA_BBOX,
        "leaked_removed": len(leaked),
        "train_obs": len(tr_obs), "val_obs": len(va_obs), "test_obs": len(test_pool),
        "train_photos": len(tr_photos), "val_photos": len(va_photos), "test_photos": len(te_photos),
        "eval_protocol": "训练/验证来自珊瑚大三角；测试来自仙本那（地理隔离，无泄漏）",
    }
    for split, data in (("train", tr_photos), ("val", va_photos), ("test", te_photos)):
        (outdir / f"{args.level}_{split}.json").write_text(
            json.dumps({"meta": meta, "photos": data}, ensure_ascii=False, indent=1), encoding="utf-8")
    (outdir / f"{args.level}_classes.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    lic = collections.Counter(x["license"] for x in tr_photos + va_photos + te_photos)
    print(f"\n许可证分布: {dict(lic)}")
    print(f"已写入: {outdir}\\{args.level}_{{train,val,test}}.json")


if __name__ == "__main__":
    main()
