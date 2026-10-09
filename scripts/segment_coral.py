"""
珊瑚礁语义分割 —— 覆盖率 / 白化占比计算（模型 A）
================================================================
基于 EPFL 的 Coralscapes 数据集与预训练模型：
    EPFL-ECEO/segformer-b2-finetuned-coralscapes-1024-1024
    (Coralscapes: 2075 图 / 39 个底栖类 / Apache-2.0)

Coralscapes 的类别体系同时编码了「生长形态 × 健康状态 × 部分属」，
例如 branching alive / branching bleached / branching dead，
可直接聚合成项目需要的功能群占比。

输出：
    活珊瑚% / 白化珊瑚% / 死亡珊瑚% / 藻类覆盖% / 沙砾% / 其他%
    + 各类明细 + 可视化叠加图

用法：
    python segment_coral.py --image <图片路径>
    python segment_coral.py --image <图片路径> --save-overlay out.png
    python segment_coral.py --batch <目录>

注意：本模块需要 8GB 显存，默认输入 512px；可用 --size 调整。
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "weights" / "segformer_coralscapes"

# ---- 39 类 → 项目功能群 的映射 ----
# 依据 id2label.json 的实际类别名
def functional_group(name: str) -> str:
    n = name.lower()
    if "bleached" in n:
        return "bleached"          # 白化珊瑚
    if n.endswith("dead") or " dead" in n or n.startswith("dead"):
        return "dead"              # 死亡珊瑚
    if n.endswith("alive") or "alive" in n:
        return "alive"             # 活珊瑚
    if "algae" in n:
        return "algae"             # 藻类覆盖
    if n in ("sand", "rubble", "unknown hard substrate", "background", "dark"):
        return "substrate"         # 沙/碎石/硬底质
    if n in ("seagrass",):
        return "seagrass"          # 海草
    return "other"                 # 鱼类/无脊椎/人造物等


GROUP_CN = {
    "alive": "活珊瑚", "bleached": "白化珊瑚", "dead": "死亡珊瑚",
    "algae": "藻类覆盖", "substrate": "沙/碎石/底质", "seagrass": "海草", "other": "其他",
}
GROUP_COLOR = {
    "alive": (60, 200, 90), "bleached": (255, 210, 60), "dead": (150, 150, 150),
    "algae": (90, 120, 60), "substrate": (225, 205, 160), "seagrass": (40, 140, 80),
    "other": (120, 120, 200),
}


class CoralSegmenter:
    def __init__(self, model_dir=MODEL_DIR, device=None, size=512):
        from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor
        self.size = size
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.processor = SegformerImageProcessor.from_pretrained(str(model_dir))
        self.model = SegformerForSemanticSegmentation.from_pretrained(str(model_dir)).to(self.device).eval()
        i2l = json.loads((Path(model_dir) / "id2label.json").read_text(encoding="utf-8"))
        self.id2label = {int(k): v for k, v in i2l.items()}
        self.n_classes = max(self.id2label) + 1
        try:
            self.label2color = json.loads((Path(model_dir) / "label2color.json").read_text(encoding="utf-8"))
        except Exception:
            self.label2color = {}

    @torch.no_grad()
    def segment(self, img: Image.Image):
        """返回 (pred_mask[H,W] numpy, 各类像素占比 dict, 功能群占比 dict)"""
        img = img.convert("RGB")
        W0, H0 = img.size
        # 等比例缩放到 size（宽高均为 32 的倍数，SegFormer 要求）
        scale = self.size / max(W0, H0)
        nw, nh = max(32, int(W0 * scale) // 32 * 32), max(32, int(H0 * scale) // 32 * 32)
        small = img.resize((nw, nh), Image.BILINEAR)

        inputs = self.processor(images=small, return_tensors="pt").to(self.device)
        logits = self.model(**inputs).logits           # (1, C, h/4, w/4)
        up = torch.nn.functional.interpolate(logits, size=(nh, nw), mode="bilinear", align_corners=False)
        pred = up.argmax(1)[0].cpu().numpy().astype(np.uint8)

        total = pred.size
        cls_frac = {}
        for cid, cnt in zip(*np.unique(pred, return_counts=True)):
            cls_frac[self.id2label.get(int(cid), f"class_{cid}")] = float(cnt) / total

        grp = {}
        for name, frac in cls_frac.items():
            g = functional_group(name)
            grp[g] = grp.get(g, 0.0) + frac
        return pred, cls_frac, grp


def overlay(img: Image.Image, pred: np.ndarray, alpha=0.55) -> Image.Image:
    """把功能群着色叠加到原图（可视化）。"""
    rgb = np.array(img.convert("RGB").resize((pred.shape[1], pred.shape[0]), Image.BILINEAR)).astype(np.float32)
    color = np.zeros_like(rgb)
    for cid in np.unique(pred):
        name = f"class_{cid}"
        color[pred == cid] = (120, 120, 200)
    # 用功能群颜色重绘
    for cid in np.unique(pred):
        g = functional_group(str(cid))
        color[pred == cid] = GROUP_COLOR.get(g, (255, 0, 255))
    out = (rgb * (1 - alpha) + color * alpha).clip(0, 255).astype(np.uint8)
    return Image.fromarray(out)


def report(grp, cls_frac, topn=10):
    print("-" * 58)
    print(f"{'功能群':<14}{'占比':>10}")
    print("-" * 58)
    for g in ("alive", "bleached", "dead", "algae", "substrate", "seagrass", "other"):
        if g in grp:
            print(f"{GROUP_CN[g]:<14}{grp[g]:>10.2%}")
    coral_total = grp.get("alive", 0) + grp.get("bleached", 0) + grp.get("dead", 0)
    if coral_total > 0:
        print("-" * 58)
        print(f"{'珊瑚总覆盖':<14}{coral_total:>10.2%}")
        print(f"{'  其中白化比':<12}{grp.get('bleached',0)/coral_total:>10.2%}")
        print(f"{'  其中死亡比':<12}{grp.get('dead',0)/coral_total:>10.2%}")
    print("-" * 58)
    print(f"\n细分类别 Top{topn}:")
    for k, v in sorted(cls_frac.items(), key=lambda kv: -kv[1])[:topn]:
        print(f"  {k:<34}{v:>8.2%}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--save-overlay", default=None)
    ap.add_argument("--json", default=None, help="把结果写入 JSON")
    args = ap.parse_args()

    seg = CoralSegmenter(size=args.size)
    print(f"模型: Coralscapes SegFormer-B2  设备={seg.device}  输入={args.size}px  类别={seg.n_classes}")
    img = Image.open(args.image)
    print(f"图片: {args.image}  ({img.size[0]}x{img.size[1]})")
    pred, cls_frac, grp = seg.segment(img)
    report(grp, cls_frac)

    if args.save_overlay:
        overlay(img, pred).save(args.save_overlay)
        print(f"\n叠加图已保存: {args.save_overlay}")
    if args.json:
        Path(args.json).write_text(json.dumps(
            {"image": args.image, "groups": grp, "classes": cls_frac},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"结果 JSON: {args.json}")


if __name__ == "__main__":
    main()
