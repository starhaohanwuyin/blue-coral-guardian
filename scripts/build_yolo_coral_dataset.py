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
from dl_coralscapes import EXPECTED  # noqa: E402

CS_DATA = ROOT / "data" / "raw" / "coralscapes" / "data"
ID2LABEL = ROOT / "weights" / "segformer_coralscapes" / "id2label.json"
CORAL_GROUPS = ("alive", "bleached", "dead")
CONN8 = np.ones((3, 3), dtype=np.uint8)   # 8 邻域：斜向相接的同种珊瑚算一个个体


def coral_class_ids() -> dict:
    """从模型自带的 id2label.json 派生珊瑚类 id（不硬编码类名，避免索引错位）。"""
    i2l = json.loads(ID2LABEL.read_text(encoding="utf-8"))
    out = {}
    for k, name in i2l.items():
        g = functional_group(str(name))
        if g in CORAL_GROUPS:
            out[int(k)] = (str(name), g)
    if not out:
        raise SystemExit("未能从 id2label.json 派生出珊瑚类，请检查映射")
    return out


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
                  img_dir: Path, lbl_dir: Path, jpeg_quality: int):
    import pyarrow.parquet as pq
    from PIL import Image

    pf = pq.ParquetFile(str(pq_path))
    ids = list(coral_ids.keys())
    n_img = n_box = n_empty = 0
    used_names = set()

    for batch in pf.iter_batches(batch_size=8, columns=["image", "label"]):
        imgs = batch.column("image").to_pylist()
        labs = batch.column("label").to_pylist()
        for raw_img, raw_lab in zip(imgs, labs):
            if limit and n_img >= limit:
                return n_img, n_box, n_empty, used_names
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
            if not force and jpg.exists() and txt.exists():
                n_img += 1
                n_box += sum(1 for line in txt.read_text(encoding="utf-8").splitlines() if line.strip())
                continue

            img = to_pil(raw_img)
            W, H = img.size
            mask = np.array(to_pil(raw_lab).convert("L"))

            # 掩膜与图像尺寸一致性校验（不一致则重采样，避免框错位）
            if mask.shape != (H, W):
                mask = np.array(Image.fromarray(mask).resize((W, H), Image.NEAREST))

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

            img.convert("RGB").save(jpg, quality=jpeg_quality, subsampling=0)
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
        print(f"  [{split}] {n_img} 张 / {n_box} 框", flush=True)
    return n_img, n_box, n_empty, used_names


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

    coral_ids = coral_class_ids()
    print("珊瑚类（由 id2label.json + functional_group 派生）：")
    for cid, (name, g) in sorted(coral_ids.items()):
        print(f"  {cid:>2} {name:<30} → {g}")
    print(f"共 {len(coral_ids)} 个珊瑚类，统一归为 YOLO 类别 0 = coral\n")

    def complete_shards(pattern: str) -> list:
        """只取**结构完整**的分片。

        ⚠️ 不能只看文件大小：EXPECTED 表里的数值比真实字节数低约 4.9%
        （疑似把「显示用 MiB」当字节记了），按 0.995 判完整会放过下载到
        ~95% 的残片。这里改为打开 parquet footer 校验 —— 文件被截断时
        尾部 magic 必然缺失，pyarrow 会直接报错，是最可靠的完整性判据。
        """
        import pyarrow.parquet as pq
        out, skipped = [], []
        for p in sorted(CS_DATA.glob(pattern)):
            exp = EXPECTED.get(p.name)
            if exp and p.stat().st_size < exp * 0.995:
                skipped.append(f"{p.name}（{p.stat().st_size/1e6:.1f} MB < 预期 {exp/1e6:.1f} MB，仍在下载）")
                continue
            try:
                md = pq.ParquetFile(str(p)).metadata
            except Exception as e:
                skipped.append(f"{p.name}（parquet 不可读: {type(e).__name__}，疑似未下载完）")
                continue
            out.append((p, md.num_rows))
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

    stats = Counter()
    sizes = {"train": {}, "val": {}}
    for split, shards, idir, ldir in (("train", train_shards, img_train, lbl_train),
                                      ("val", val_shards, img_val, lbl_val)):
        ni = nb = ne = 0
        names = set()
        for sh in shards:
            print(f"[{split}] {sh.name}")
            a, b, c, nm = extract_shard(sh, split, coral_ids, args.min_area,
                                        args.min_side, args.limit, args.force,
                                        idir, ldir, args.jpeg_quality)
            ni += a
            nb += b
            ne += c
            names |= nm
        sizes[split] = {"images": ni, "boxes": nb, "emptyImages": ne, "classes": {str(k): v for k, v in coral_ids.items()}}
        print(f"[{split}] 合计 {ni} 张 / {nb} 框（其中 {ne} 张无珊瑚框）\n")

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
        "coralClassIds": {str(k): v[0] for k, v in sorted(coral_ids.items())},
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
