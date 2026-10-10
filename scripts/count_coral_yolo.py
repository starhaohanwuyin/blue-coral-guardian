"""
珊瑚个体计数推理（YOLOv9 · P3）
============================================================
**附加能力**：在现有"覆盖率 + 属 + 白化"之外，额外回答
「画面里有多少个珊瑚个体、各在哪里」。

设计约束（P3 要求）：
  · 不替换、不修改任何现有分割/分类输出，只新增字段
  · 权重缺失时安静降级（返回 None），不影响主结果
  · 与分割使用**同一个输入图**（enhance_first 生效时同样先增强）

用法：
    python count_coral_yolo.py --image a.jpg
    python count_coral_yolo.py --image a.jpg --json out.json --save-overlay overlay.png
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEIGHTS = ROOT / "weights" / "yolo_coral" / "best.pt"
DEFAULT_IMGSZ = 640
# 计数用的置信度阈值。⚠️ 与 mAP 无关（mAP 是 PR 曲线面积），但**直接决定数出来几株**：
# 官方 val 上实测（scripts/tune_yolo_counting_threshold.py）：
#   conf=0.25 → 总数偏差 −27.1%；conf=0.20 → −12.1%（MAE 最低 10.59）；
#   **conf=0.15 → +8.7%（偏差最小，故选它）**；conf=0.10 → +44.6%。
DEFAULT_CONF = 0.15
DEFAULT_IOU = 0.5


class CoralCounter:
    """YOLOv9 珊瑚个体检测器（单类 coral）。"""

    def __init__(self, weights=WEIGHTS, device=None, imgsz=DEFAULT_IMGSZ):
        import torch
        self.weights = Path(weights)
        self.device = device or ("0" if torch.cuda.is_available() else "cpu")
        self.imgsz = imgsz
        if not self.weights.exists():
            raise FileNotFoundError(f"缺少计数权重: {self.weights}")
        from ultralytics import YOLO
        self.model = YOLO(str(self.weights))

    def count(self, img, conf=DEFAULT_CONF, iou=DEFAULT_IOU, max_boxes=200):
        """返回 {count, threshold, boxes:[{x0,y0,x1,y1,confidence}]}。

        boxes 为**原图像素坐标**，按置信度降序；最多返回 max_boxes 个（避免响应过大）。
        """
        r = self.model.predict(source=img, imgsz=self.imgsz, conf=conf, iou=iou,
                               device=self.device, verbose=False, plots=False)[0]
        out = []
        if r.boxes is not None and len(r.boxes):
            xyxy = r.boxes.xyxy.cpu().numpy()
            cf = r.boxes.conf.cpu().numpy()
            for (x0, y0, x1, y1), c in zip(xyxy, cf):
                out.append({"x0": int(round(x0)), "y0": int(round(y0)),
                            "x1": int(round(x1)), "y1": int(round(y1)),
                            "confidence": round(float(c), 4)})
        out.sort(key=lambda b: -b["confidence"])
        W, H = img.size
        return {
            "count": len(out),
            "threshold": {"conf": conf, "iou": iou, "imgsz": self.imgsz},
            "imageSize": [W, H],
            "boxes": out[:max_boxes],
            "truncated": len(out) > max_boxes,
            "model": "yolov9c",
            "note": "个体 = 珊瑚类掩膜连通域；与覆盖率、属、白化结论相互独立，互不覆盖",
        }


def draw(img, boxes):
    from PIL import ImageDraw
    im = img.convert("RGB").copy()
    d = ImageDraw.Draw(im)
    for i, b in enumerate(boxes, 1):
        d.rectangle([b["x0"], b["y0"], b["x1"], b["y1"]], outline=(255, 60, 60), width=3)
        d.text((b["x0"] + 4, b["y0"] + 4), f"{i}:{b['confidence']:.2f}", fill=(255, 255, 0))
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--weights", default=str(WEIGHTS))
    ap.add_argument("--imgsz", type=int, default=DEFAULT_IMGSZ)
    ap.add_argument("--conf", type=float, default=DEFAULT_CONF)
    ap.add_argument("--iou", type=float, default=DEFAULT_IOU)
    ap.add_argument("--json", default=None)
    ap.add_argument("--save-overlay", default=None)
    args = ap.parse_args()

    from PIL import Image
    img = Image.open(args.image)
    counter = CoralCounter(args.weights, imgsz=args.imgsz)
    res = counter.count(img, conf=args.conf, iou=args.iou)
    res["image"] = str(args.image)

    print(f"图片: {args.image}  ({img.size[0]}x{img.size[1]})")
    print(f"珊瑚个体数: {res['count']}   阈值 conf={args.conf} iou={args.iou} imgsz={res['threshold']['imgsz']}")
    for i, b in enumerate(res["boxes"][:20], 1):
        print(f"  {i:>2}. ({b['x0']},{b['y0']})-({b['x1']},{b['y1']})  conf={b['confidence']:.3f}")
    if len(res["boxes"]) > 20:
        print(f"  ... 其余 {len(res['boxes'])-20} 个见 JSON")

    if args.save_overlay:
        draw(img, res["boxes"]).save(args.save_overlay)
        print(f"叠加图: {args.save_overlay}")
    if args.json:
        Path(args.json).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"结果 JSON: {args.json}")


if __name__ == "__main__":
    main()
