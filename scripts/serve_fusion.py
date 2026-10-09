"""
融合推理服务（Model A 分割 + Model B 属识别）
================================================================
一次请求返回项目真正需要的两类结论：

  1. 覆盖率类（Model A · 语义分割）
     活珊瑚% / 白化珊瑚% / 死亡珊瑚% / 藻类覆盖% / 沙砾底质% / 海草%
     + 珊瑚总覆盖、白化占比、各类明细

  2. 是什么珊瑚（Model B · 属分类）
     从分割结果中取出「硬珊瑚」像素区域 → 裁剪主体 → 局属分类
     （Model B 未训练时自动跳过，不影响覆盖率输出）

  3. 可信度
     每个结论带置信度；低置信度标记 needReview；固定输出使用边界声明。

融合的价值：Model B 只在 Model A 判定为珊瑚的像素上运行，
输入更干净（背景已剔除），因此精度天然高于整图分类。

用法：
    python serve_fusion.py --port 8000
    curl -F "file=@a.jpg" http://127.0.0.1:8000/analyze
"""
import argparse
import base64
import io
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SEG_DIR = ROOT / "weights" / "segformer_coralscapes"
SEG_DIR_INV = ROOT / "weights" / "segformer_coralscapes_degradinv"
SPECIES_CKPT = ROOT / "weights" / "species_ip" / "best.pt"

try:
    from fastapi import FastAPI, File, UploadFile, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, FileResponse
    import uvicorn
except ImportError:
    raise SystemExit("缺少依赖：python -m pip install fastapi uvicorn python-multipart")

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from segment_coral import CoralSegmenter, functional_group, GROUP_CN  # noqa: E402
from uw_enhance import enhance  # noqa: E402
from check_capture_quality import metrics as quality_metrics, verdict as quality_verdict, \
    DEFAULT_THRESHOLDS  # noqa: E402

# 拍摄条件阈值（若已标定则读取标定结果）
QUALITY_TH = DEFAULT_THRESHOLDS
_qp = ROOT / "reports" / "capture_quality_thresholds.json"
if _qp.exists():
    try:
        QUALITY_TH = json.loads(_qp.read_text(encoding="utf-8"))["thresholds"]
    except Exception:
        pass

# 珊瑚功能群（用于取出珊瑚区域给 Model B）
CORAL_GROUPS = {"alive", "bleached", "dead"}

DISCLAIMER = ("本结果由AI模型给出，仅供保育决策参考，不作为唯一依据。"
              "模型在拍摄深度 ≤10m、能见度良好时表现最佳；"
              "15m 以上浑浊水域需人工复核。本项目仅用于学术研究与竞赛，非商业用途。")

SEG = None
SPECIES = None
SEG_LOADED_DIR = None          # 实际加载的分割权重目录（供 /health 如实报告）
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
app = FastAPI(title="蓝珊 · 珊瑚礁智能评估服务", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def load_models(prefer_degradinv=False):
    """加载模型。

    ⚠️ 默认使用**校准良好的原始 Coralscapes 权重**。
    退化不变性微调权重（segformer_coralscapes_degradinv）虽然把 15m 浑浊下的
    鲁棒性从 0% 恢复到 38%，但 L0 基准从 39.66% 漂移到 53.07%（+13.4 个百分点），
    **会破坏星地验证，不能用于绝对值输出**，仅在显式指定时加载。
    """
    global SEG, SPECIES, SEG_LOADED_DIR
    d = SEG_DIR_INV if (prefer_degradinv and (SEG_DIR_INV / "config.json").exists()) else SEG_DIR
    SEG_LOADED_DIR = d
    print(f"[加载] 分割模型: {d.name}" + ("  ⚠️ 实验性权重（未校准）" if d == SEG_DIR_INV else "  （已校准）"))
    SEG = CoralSegmenter(model_dir=d, size=512)
    if SPECIES_CKPT.exists():
        try:
            import torchvision.transforms as T
            from torchvision import models
            import torch.nn as nn
            ck = torch.load(SPECIES_CKPT, map_location=DEVICE, weights_only=False)
            classes = ck["classes"]
            size = ck.get("img_size", 320)
            bb = ck["backbone"]
            if bb == "convnext_tiny":
                m = models.convnext_tiny(weights=None)
                m.classifier[2] = nn.Linear(m.classifier[2].in_features, len(classes))
            elif bb == "efficientnet_b0":
                m = models.efficientnet_b0(weights=None)
                m.classifier[1] = nn.Linear(m.classifier[1].in_features, len(classes))
            else:
                m = models.resnet50(weights=None)
                m.fc = nn.Linear(m.fc.in_features, len(classes))
            m.load_state_dict(ck["model"]); m.to(DEVICE).eval()
            SPECIES = {"model": m, "classes": classes, "size": size,
                       "tf": T.Compose([T.Resize(int(size * 1.14)), T.CenterCrop(size),
                                        T.ToTensor(),
                                        T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])}
            print(f"[加载] 属分类模型: {len(classes)} 类")
        except Exception as e:
            print(f"[跳过] 属分类模型加载失败: {e}")
    else:
        print("[跳过] 属分类模型未训练（仅输出覆盖率）")


def classify_coral_region(img: Image.Image, pred: np.ndarray, topk=3, min_conf=0.40):
    """从分割掩膜取出珊瑚像素 → 裁剪外接框 → 属分类。

    返回 None 的情况：
      · 属分类模型未加载
      · 珊瑚像素占比过低（<2%）
      · **最高置信度低于 min_conf**（如模型尚在训练中）——此时不给结论，
        避免把欠训练的预测当成识别结果输出
    """
    if SPECIES is None:
        return None
    h, w = pred.shape
    # 把 pred 映射回原图尺寸
    names = np.array([SEG.id2label.get(int(c), f"class_{c}") for c in range(SEG.n_classes)])
    grp = np.array([functional_group(n) for n in names])
    coral_mask = np.isin(grp[pred], list(CORAL_GROUPS))
    if coral_mask.sum() < (h * w) * 0.02:
        return None
    ys, xs = np.where(coral_mask)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    Ih, Iw = img.size[1], img.size[0]
    sy, sx = Ih / h, Iw / w
    box = (int(x0 * sx), int(y0 * sy), int(x1 * sx) + 1, int(y1 * sy) + 1)
    crop = img.convert("RGB").crop(box)
    if crop.size[0] < 16 or crop.size[1] < 16:
        return None
    with torch.no_grad():
        x = SPECIES["tf"](crop).unsqueeze(0).to(DEVICE)
        p = torch.softmax(SPECIES["model"](x).float(), 1)[0]
        conf, idx = p.topk(min(topk, len(SPECIES["classes"])))
    top1_conf = float(conf[0])
    if top1_conf < min_conf:
        return {"regionBox": box, "coralPixelRatio": round(float(coral_mask.mean()), 4),
                "top": [], "reliable": False,
                "note": f"最高置信度 {top1_conf:.1%} 低于门槛 {min_conf:.0%}，本次不给出属级结论"}
    return {
        "regionBox": box,
        "coralPixelRatio": round(float(coral_mask.mean()), 4),
        "reliable": True,
        "top": [{"genus": SPECIES["classes"][i], "confidence": round(float(c), 6)}
                for c, i in zip(conf, idx)],
    }


@app.get("/health")
def health():
    return {"status": "ok", "device": str(DEVICE),
            "segmentation": "loaded" if SEG else "missing",
            "species": "loaded" if SPECIES else "not_trained",
            "segModel": SEG_LOADED_DIR.name if SEG_LOADED_DIR else "none",
            "segCalibrated": SEG_LOADED_DIR == SEG_DIR,
            "categories": SEG.n_classes if SEG else 0}


@app.get("/sample")
def sample(index: int = 0, set: str = "semporna"):
    """返回一张样例礁区照片，供小程序端到端演示/自测使用。

    小程序的 wx.chooseMedia 需要人工选择文件，无法自动化；
    此接口让开发者用 wx.downloadFile 取到真实图片路径，从而跑通完整链路。

    set: semporna（仙本那健康礁区）| bleached（印太白化样本，验证白化检测）
    """
    dirs = {
        "semporna": ROOT / "data" / "semporna_photos",
        "bleached": ROOT / "data" / "processed" / "bleaching_ip" / "test_ip" / "bleached",
        "healthy": ROOT / "data" / "processed" / "bleaching_ip" / "test_ip" / "healthy",
    }
    d = dirs.get(set)
    if d is None:
        raise HTTPException(400, f"未知 set={set}，可选 {list(dirs)}")
    if not d.exists():
        raise HTTPException(404, f"样例图目录不存在: {set}")
    files = sorted(f for f in d.rglob("*.jpg") if f.stat().st_size > 20000)
    if not files:
        raise HTTPException(404, "无可用样例图")
    f = files[index % len(files)]
    return FileResponse(str(f), media_type="image/jpeg",
                        headers={"X-Sample-Name": f.name, "X-Sample-Count": str(len(files)),
                                 "X-Sample-Set": set})


@app.get("/sample/list")
def sample_list(limit: int = 20):
    d = ROOT / "data" / "semporna_photos"
    files = sorted(f.name for f in d.glob("*.jpg")) if d.exists() else []
    return {"count": len(files), "first": files[:limit]}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...), enhance_first: bool = False):
    if SEG is None:
        raise HTTPException(503, "分割模型未加载")
    data = await file.read()
    if not data:
        raise HTTPException(400, "空文件")
    try:
        img = Image.open(io.BytesIO(data))
    except Exception:
        raise HTTPException(400, "无法解析图片")

    t0 = time.time()
    # ① 先做拍摄条件自检：超出适用边界时明确告知，而不是编一个覆盖率数字
    qm = quality_metrics(img)
    qv = quality_verdict(qm, QUALITY_TH)

    src = enhance(img, clahe=True) if enhance_first else img
    pred, cls_frac, grp = SEG.segment(src)

    cover = {GROUP_CN.get(g, g): round(v, 6) for g, v in sorted(grp.items(), key=lambda kv: -kv[1])}
    coral_total = grp.get("alive", 0) + grp.get("bleached", 0) + grp.get("dead", 0)
    live = grp.get("alive", 0.0)
    bleach_ratio = (grp.get("bleached", 0.0) / coral_total) if coral_total > 0 else 0.0

    result = {
        "success": True,
        "cover": {
            "alivePct": round(live, 6),
            "bleachedPct": round(grp.get("bleached", 0.0), 6),
            "deadPct": round(grp.get("dead", 0.0), 6),
            "algaePct": round(grp.get("algae", 0.0), 6),
            "substratePct": round(grp.get("substrate", 0.0), 6),
            "seagrassPct": round(grp.get("seagrass", 0.0), 6),
            "coralTotalPct": round(coral_total, 6),
            "bleachingShareOfCoral": round(bleach_ratio, 6),
        },
        "groups": cover,
        "topClasses": [{"name": k, "pct": round(v, 6)}
                       for k, v in sorted(cls_frac.items(), key=lambda kv: -kv[1])[:8]],
        "coralRegion": classify_coral_region(img, pred),
        "captureQuality": {
            "level": qv["level"],            # good / warn / poor
            "usable": qv["usable"],
            "contrast": qm["contrast"],
            "rgRatio": qm["rgRatio"],
            "message": qv["message"],
        },
        "enhanced": bool(enhance_first),
        "disclaimer": DISCLAIMER,
        "inferenceMs": round((time.time() - t0) * 1000, 1),
    }
    return JSONResponse(result)


@app.post("/analyze_base64")
async def analyze_base64(payload: dict):
    b64 = payload.get("image_base64") or ""
    if "," in b64[:100]:
        b64 = b64.split(",", 1)[1]
    try:
        img = Image.open(io.BytesIO(base64.b64decode(b64)))
    except Exception:
        raise HTTPException(400, "base64 解码失败")
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    buf.seek(0)

    class _F:
        async def read(self):
            return buf.getvalue()
    return await analyze(_F(), payload.get("enhance_first", False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--use-degradinv", action="store_true",
                    help="使用退化不变性微调权重（实验性，未校准，会高估覆盖率约 13 个百分点）")
    args = ap.parse_args()
    print(f"设备: {DEVICE}")
    load_models(prefer_degradinv=args.use_degradinv)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
