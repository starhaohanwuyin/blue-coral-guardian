"""
从 Coralscapes 掩膜提取珊瑚个体框 → 组织 YOLO 检测数据集
============================================================
P3（YOLOv9 珊瑚个体计数）第 2–3 步。

思路：
  Coralscapes 的标注是**逐像素语义掩膜**（40 类，含"生长形态×健康状态×属"），
  本脚本把「珊瑚类」像素（alive / bleached / dead，经 functional_group 判定）
  做**连通域**分析，每个连通域 = 一个珊瑚个体 → 取外接矩形 → YOLO 标签。

  类别数固定为 1（`coral`），即只回答"这里有一个珊瑚个体"，
  不区分属/形态 —— 属与健康状态由现有 Model A/B 负责，不做重复。

数据划分（沿用官方 split，无泄漏）：
  train ← data/raw/coralscapes/data/train-*.parquet
  val   ← data/raw/coralscapes/data/validation-00000-of-00001.parquet

用法：
    python build_yolo_coral_dataset.py                      # 全量
    python build_yolo_coral_dataset.py --limit 8 --out data/yolo_coral_probe
    python build_yolo_coral_dataset.py --force              # 忽略已提取的文件

输出：
    data/yolo_coral/
    ├── images/{train,val}/*.jpg
    ├── labels/{train,val}/*.txt
    └── data.yaml
    reports/yolo_coral_dataset.json    （统计：实例数、面积分布等）
"""
import argparse
import io
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from segment_coral import functional_group  # noqa: E402
from dl_coralscapes import EXPECTED, parquet_ok  # noqa: E402

CS_DATA = ROOT / "data" / "raw" / "coralscapes" / "data"
ID2LABEL = ROOT / "weights" / "segformer_coralscapes" / "id2label.json"
CORAL_GROUPS = ("alive", "bleached", "dead")
CONN8 = np.ones((3, 3), dtype=np.uint8)   # 8 邻域：斜向相接的同种珊瑚算一个个体

# ⚠️ 已修的 bug：`dead clam`（死双壳类）经 functional_group 被判为 "dead"，
#    于是被当成"珊瑚个体"——**蛤蜊不是珊瑚**，这类框会污染真值、拉低 mAP。
#    这里按**类名**排除（而不是硬编码 id，避免索引错位）。
#    注：`millepora`(21) / `turbinaria`(27) 是珊瑚，却被 functional_group 归入 "other" 而被漏掉；
#    由于该函数同时服务分割覆盖率（改它会动摇已验收的覆盖率/星地结论），
#    这里**不动** functional_group，只在报告中如实声明这一口径差异。
EXCLUDE_NAME_PATTERNS = ("clam",)


def coral_class_ids():
    """从模型自带的 id2label.json 派生珊瑚类 id（不硬编码类名，避免索引错位）。

    返回 (珊瑚类 dict, 被排除的非珊瑚类列表)。
    """
    i2l = json.loads(ID2LABEL.read_text(encoding="utf-8"))
    out, excluded = {}, []
    for k, name in i2l.items():
        g = functional_group(str(name))
        if g not in CORAL_GROUPS:
            continue
        if any(p in str(name).lower() for p in EXCLUDE_NAME_PATTERNS):
            excluded.append((int(k), str(name)))
            continue
        out[int(k)] = (str(name), g)
    if excluded:
        print("已排除的非珊瑚类（functional_group 误判为珊瑚）：")
        for cid, name in excluded:
            print(f"  {cid:>2} {name}  ← 不是珊瑚（如双壳类）")
    if not out:
        raise SystemExit("未能从 id2label.json 派生出珊瑚类，请检查映射")
    return out, excluded


def to_pil(obj):
    from PIL import Image
    if isinstance(obj, dict):
        if obj.get("bytes"):
            return Image.open(io.BytesIO(obj["bytes"]))
        if obj.get("path"):
            return Image.open(obj["path"])
    if isinstance(obj, (bytes, bytearray)):
        return Image.open(io.BytesIO(obj))
    raise TypeError(f"无法解析: {type(obj)}")


def extract_shard(pq_path: Path, split: str, coral_ids: dict,
                  min_area: int, min_side: int, limit: int, force: bool,
                  rebuild_labels: bool, img_dir: Path, lbl_dir: Path, jpeg_quality: int):
    """把一个分片处理成 {images,labels}。

    resume 语义（修过的坑）：
      · 图片已存在且标签已存在且**配置未变** → 跳过（什么也不解码）
      · **配置变了**（--min-area/--min-side/类集合 改动）→ 只**重建标签**，
        复用已有 jpg。否则旧标签会与新的过滤条件不一致，且不报错。
    """
    import pyarrow.parquet as pq
    from PIL import Image

    pf = pq.ParquetFile(str(pq_path))
    ids = list(coral_ids.keys())
    n_img = n_box = n_empty = n_relabel = n_newimg = 0
    used_names = set()

    for batch in pf.iter_batches(batch_size=8, columns=["image", "label"]):
        imgs = batch.column("image").to_pylist()
        labs = batch.column("label").to_pylist()
        for raw_img, raw_lab in zip(imgs, labs):
            if limit and n_img >= limit:
                return n_img, n_box, n_empty, used_names, n_relabel, n_newimg
            stem = Path(str(raw_lab.get("path") or f"{split}_{n_img:06d}")).stem
            if stem.endswith("_gtFine"):
                stem = stem[: -len("_gtFine")]
            name = stem
            k = 1
            while name in used_names:
                k += 1
                name = f"{stem}__{k}"
            used_names.add(name)

            jpg = img_dir / f"{name}.jpg"
            txt = lbl_dir / f"{name}.txt"
            need_img = force or not jpg.exists()
            need_lab = need_img or rebuild_labels or not txt.exists()
            if not need_img and not need_lab:
                n_img += 1
                n_box += sum(1 for line in txt.read_text(encoding="utf-8").splitlines() if line.strip())
                continue

            mask = np.array(to_pil(raw_lab).convert("L"))
            H, W = mask.shape
            if need_img:
                img = to_pil(raw_img)
                iw, ih = img.size
                if mask.shape != (ih, iw):      # 尺寸不一致则重采样，避免框错位
                    mask = np.array(Image.fromarray(mask).resize((iw, ih), Image.NEAREST))
                    H, W = ih, iw
                img.convert("RGB").save(jpg, quality=jpeg_quality, subsampling=0)
                n_newimg += 1
            else:
                n_relabel += 1

            boxes = []
            for cid in ids:
                m = (mask == cid)
                if not m.any():
                    continue
                lab, n = ndimage.label(m, structure=CONN8)
                if n == 0:
                    continue
                areas = np.bincount(lab.ravel(), minlength=n + 1)
                for k, sl in enumerate(ndimage.find_objects(lab), start=1):
                    if sl is None:
                        continue
                    ys, xs = sl
                    w, h = xs.stop - xs.start, ys.stop - ys.start
                    if w < min_side or h < min_side:
                        continue
                    if areas[k] < min_area:
                        continue
                    boxes.append((xs.start, ys.start, xs.stop, ys.stop, int(areas[k])))
                del lab, areas

            lines = []
            for (x0, y0, x1, y1, area) in boxes:
                cx = (x0 + x1) / 2.0 / W
                cy = (y0 + y1) / 2.0 / H
                bw = (x1 - x0) / W
                bh = (y1 - y0) / H
                lines.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
            txt.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
            del mask
            n_img += 1
            n_box += len(boxes)
            if not boxes:
                n_empty += 1
        print(f"  [{split}] {n_img} 张 / {n_box} 框"
              + (f"（重建标签 {n_relabel}）" if n_relabel else ""), flush=True)
    return n_img, n_box, n_empty, used_names, n_relabel, n_newimg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "yolo_coral"))
    ap.add_argument("--min-area", type=int, default=200, help="最小连通域面积（像素，原文 200）")
    ap.add_argument("--min-side", type=int, default=6, help="最小外接矩形边长（像素）")
    ap.add_argument("--limit", type=int, default=0, help="每分片最多处理多少张（调试用）")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--jpeg-quality", type=int, default=92)
    args = ap.parse_args()

    out = Path(args.out)
    img_train, img_val = out / "images" / "train", out / "images" / "val"
    lbl_train, lbl_val = out / "labels" / "train", out / "labels" / "val"
    for d in (img_train, img_val, lbl_train, lbl_val):
        d.mkdir(parents=True, exist_ok=True)

    coral_ids, excluded_ids = coral_class_ids()
    print("珊瑚类（由 id2label.json + functional_group 派生）：")
    for cid, (name, g) in sorted(coral_ids.items()):
        print(f"  {cid:>2} {name:<30} → {g}")
    print(f"共 {len(coral_ids)} 个珊瑚类，统一归为 YOLO 类别 0 = coral\n")

    def complete_shards(pattern: str) -> list:
        """只取**结构完整**的分片：判定用 parquet footer（见 dl_coralscapes.parquet_ok），
        文件大小只做快速早筛（原 EXPECTED 表比真实字节低 4.9%，不能单独当判据）。"""
        import pyarrow.parquet as pq
        out, skipped = [], []
        for p in sorted(CS_DATA.glob(pattern)):
            size = p.stat().st_size
            exp = EXPECTED.get(p.name)
            if exp and size < exp * 0.90:      # 明显没下完，连 footer 都不用试
                skipped.append(f"{p.name}（{size/1e6:.1f} MB，远小于预期 {exp/1e6:.1f} MB，仍在下载）")
                continue
            if not parquet_ok(p):
                skipped.append(f"{p.name}（parquet footer 不可读，疑似未下载完）")
                continue
            out.append((p, pq.ParquetFile(str(p)).metadata.num_rows))
        for s in skipped:
            print(f"  ⚠ 跳过 {s}")
        return out

    train_pairs = complete_shards("train-*.parquet")
    val_pairs = complete_shards("validation-*.parquet")
    for name, pairs in (("train", train_pairs), ("val", val_pairs)):
        tot = sum(r for _, r in pairs)
        print(f"  [{name}] 可用分片 {len(pairs)} 个，合计 {tot} 张: "
              + ", ".join(f"{p.name.replace('-of-00009','').replace('.parquet','')}={r}" for p, r in pairs))
    train_shards = [p for p, _ in train_pairs]
    val_shards = [p for p, _ in val_pairs]
    if not train_shards or not val_shards:
        raise SystemExit(f"缺少 parquet 分片，请先运行 dl_coralscapes.py\n  目录: {CS_DATA}")
    print(f"train 分片 {len(train_shards)} 个；val 分片 {len(val_shards)} 个")
    print(f"输出目录 {out}（min_area={args.min_area}px, min_side={args.min_side}px）\n")

    # ---- 配置指纹：过滤条件/类集合变了，就必须重建标签（否则会静默沿用旧口径）----
    cfg = {
        "minAreaPx": args.min_area, "minSidePx": args.min_side, "connectivity": 8,
        "coralClassIds": sorted(int(k) for k in coral_ids), "yoloClass": "coral",
        "excludeNamePatterns": list(EXCLUDE_NAME_PATTERNS),
    }
    cfg_file = out / "dataset_config.json"
    old_cfg = json.loads(cfg_file.read_text(encoding="utf-8")) if cfg_file.exists() else None
    # 没有指纹（老数据集/首次运行）或指纹不同 → 一律重建标签，绝不静默沿用旧口径
    rebuild_labels = (old_cfg != cfg)
    if rebuild_labels:
        print("⚠ 检测到数据集配置已变化（或无配置指纹）→ **重建全部标签**（图片复用，不重新编码）：")
        for k in cfg:
            if (old_cfg or {}).get(k) != cfg[k]:
                print(f"    {k}: {(old_cfg or {}).get(k)} → {cfg[k]}")
        print()
    cfg_file.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    stats = Counter()
    relabeled = newimgs = 0
    sizes = {"train": {}, "val": {}}
    for split, shards, idir, ldir in (("train", train_shards, img_train, lbl_train),
                                      ("val", val_shards, img_val, lbl_val)):
        ni = nb = ne = 0
        names = set()
        for sh in shards:
            print(f"[{split}] {sh.name}")
            a, b, c, nm, nrl, nni = extract_shard(sh, split, coral_ids, args.min_area,
                                                  args.min_side, args.limit, args.force,
                                                  rebuild_labels, idir, ldir, args.jpeg_quality)
            ni += a
            nb += b
            ne += c
            names |= nm
            relabeled += nrl
            newimgs += nni
        sizes[split] = {"images": ni, "boxes": nb, "emptyImages": ne, "classes": {str(k): v for k, v in coral_ids.items()}}
        print(f"[{split}] 合计 {ni} 张 / {nb} 框（其中 {ne} 张无珊瑚框）\n")
    print(f"本次：新编码图片 {newimgs} 张，仅重建标签 {relabeled} 张")

    # 以磁盘为准统计（续跑时不会漏统计已存在的文件）
    for split, idir, ldir in (("train", img_train, lbl_train), ("val", img_val, lbl_val)):
        jpgs = sorted(p.name for p in idir.glob("*.jpg"))
        missing = [n for n in jpgs if not (ldir / f"{Path(n).stem}.txt").exists()]
        boxes = 0
        for n in jpgs:
            f = ldir / f"{Path(n).stem}.txt"
            if not f.exists():
                continue
            for line in f.read_text(encoding="utf-8").splitlines():
                p = line.split()
                if len(p) != 5:
                    continue
                boxes += 1
                stats["box_w"] += float(p[3])
                stats["box_h"] += float(p[4])
        sizes[split]["boxesOnDisk"] = boxes
        sizes[split]["imagesOnDisk"] = len(jpgs)
        sizes[split]["labelsMissing"] = len(missing)
        stats["boxes"] += boxes

    yaml_txt = (
        "# 由 build_yolo_coral_dataset.py 自动生成\n"
        f"path: {out.as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n"
        "names:\n"
        "  0: coral\n"
    )
    (out / "data.yaml").write_text(yaml_txt, encoding="utf-8")

    nbox = max(stats["boxes"], 1)
    report = {
        "task": "YOLOv9 coral individual counting (P3)",
        "source": "Coralscapes official splits (masks → connected components → boxes)",
        "config": cfg,
        "coralClassIds": {str(k): v[0] for k, v in sorted(coral_ids.items())},
        "excludedNonCoral": {str(k): n for k, n in excluded_ids},
        "yoloClasses": ["coral"],
        "minAreaPx": args.min_area, "minSidePx": args.min_side,
        "connectivity": 8,
        "trainShards": [{"name": p.name, "rows": r} for p, r in train_pairs],
        "valShards": [{"name": p.name, "rows": r} for p, r in val_pairs],
        "splits": sizes,
        "totalBoxesOnDisk": int(stats["boxes"]),
        "meanBoxW": round(stats["box_w"] / nbox, 4),
        "meanBoxH": round(stats["box_h"] / nbox, 4),
        "meanBoxAreaFrac": round(stats["box_w"] * stats["box_h"] / nbox, 6),
        "note": "val = Coralscapes 官方 validation split；train = 官方 train split 已下载分片",
    }
    rep = ROOT / "reports" / "yolo_coral_dataset.json"
    rep.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 70)
    print(f"train: {sizes['train']['imagesOnDisk']} 张 / {sizes['train']['boxesOnDisk']} 框")
    print(f"val  : {sizes['val']['imagesOnDisk']} 张 / {sizes['val']['boxesOnDisk']} 框")
    print(f"平均框尺寸: {report['meanBoxW']:.3f} × {report['meanBoxH']:.3f}（归一化）")
    print(f"data.yaml: {out / 'data.yaml'}")
    print(f"统计: {rep}")


if __name__ == "__main__":
    main()
