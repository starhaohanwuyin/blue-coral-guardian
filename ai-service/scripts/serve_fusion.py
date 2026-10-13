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
import os          # P16：读取 DISABLE_BLEACH_CONSENSUS（缺失会导致 init() 抛 NameError）
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SEG_DIR = ROOT / "weights" / "segformer_coralscapes"
SEG_DIR_INV = ROOT / "weights" / "segformer_coralscapes_degradinv"
SPECIES_CKPT = ROOT / "weights" / "species_ip" / "best.pt"
# 珊瑚个体计数权重（P3 附加能力，YOLOv9c）。缺失时服务照常工作，只是少一个附加字段。
COUNT_CKPT = ROOT / "weights" / "yolo_coral" / "best.pt"
# 白化状态分类模型（全图级）。
# ⚠️ 实测：分割模型（Model A）的白化像素占比在第三方数据上 AUC 仅 0.46（无效），
#    因此「白化程度」必须由分类模型给出，不能用 cover.bleachedPct。
#    优先级：bleaching_all（旧域+新域合并，三域最优）> bleaching_ip > bleaching
BLEACH_DIRS = ["bleaching_all", "bleaching_ip", "bleaching"]

try:
    from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request
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
from climate_context import context_for as climate_context  # noqa: E402
from climate_site_profile import profile_for as climate_profile_for  # noqa: E402
from restoration_priority import assess as assess_restoration  # noqa: E402

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
BLEACH = None                   # 白化状态分类模型
# P16 附加：第二白化模型（纯域自适应版）—— 用于「共识弃权」：两模型一致才判定，
#     不一致则标记待人工复核。缺失时该功能安静降级（consensus=None）。
# P16 共识弃权的第二模型候选（按顺序找第一个可用的）。
# 为什么首选 multidomain2 而不是纯印太版：实测在**仙本那实拍**上，
#   纯印太版与线上 D4 分歧率高达 56.7%（它系统性偏向"死亡"），提示过密；
#   而 multidomain2（同为多域模型）分歧率仅 22.8%，且域内覆盖率 92–98%、
#   orig_test 宏 F1 0.9700（纯印太版为 0.9130）→ 把关更有意义。
# 可用环境变量覆盖：CONSENSUS_ALT=<权重目录名>（如 bleaching_all_koh_tao_bb 面向印太域）。
BLEACH_ALT_DIRS = ["bleaching_all_multidomain2", "bleaching_all_koh_tao_bb",
                   "bleaching_all_koh_tao"]
BLEACH_ALT = None               # 模块级初始化：/health 在 init 之前被调用也不能 NameError
# 共识弃权：主模型置信度低于此阈值且两模型分歧时，才提示「建议人工复核」；
# 否则只给「另一模型持不同意见」的弱提醒（避免一半以上上传都弹复核提示）
CONSENSUS_REVIEW_CONF = 0.90
# 第二模型置信度高于此值、且与主模型不一致 → 视为「强冲突」，同样提示人工复核
CONSENSUS_CONFLICT_CONF = 0.85
COUNTER = None                  # 珊瑚个体计数模型（P3，附加）
SEG_LOADED_DIR = None          # 实际加载的分割权重目录（供 /health 如实报告）
BLEACH_LOADED = None
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
    # 推理分辨率 1024（模型原生训练分辨率）。
    # 实测 Coralscapes 验证集 mIoU：512px=0.25 → 1024px=0.55（+120%），
    # 且星地验证在 1024px 下依然成立（38.05% vs 实地 39.56%）。耗时仅 378ms。
    SEG = CoralSegmenter(model_dir=d, size=1024)
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

    # ---- 白化状态分类模型 ----
    global BLEACH, BLEACH_LOADED, BLEACH_ALT

    def _load_bleach(name):
        """加载指定白化权重目录；失败返回 None（调用方决定是否降级）。"""
        w = ROOT / "weights" / name / "best.pt"
        if not w.exists():
            return None
        import torchvision.transforms as T
        from torchvision import models
        import torch.nn as nn
        ck = torch.load(w, map_location=DEVICE, weights_only=False)
        classes = ck["classes"]
        size = ck.get("img_size", 224)
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
        mp = ROOT / "reports" / name / "metrics.json"
        Tt = (float(json.loads(mp.read_text(encoding="utf-8")).get("temperature", 1.0))
              if mp.exists() else 1.0)
        return {"model": m, "classes": classes, "size": size, "temp": Tt, "name": name,
                "tf": T.Compose([T.Resize(int(size * 1.14)), T.CenterCrop(size),
                                 T.ToTensor(),
                                 T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])}

    for name in BLEACH_DIRS:
        try:
            got = _load_bleach(name)
            if got is None:
                continue
            BLEACH, BLEACH_LOADED = got, name
            print(f"[加载] 白化分类模型: {name}  类别={got['classes']}  T={got['temp']:.4f}")
            break
        except Exception as e:
            print(f"[跳过] 白化模型 {name} 加载失败: {e}")
    if BLEACH is None:
        print("[跳过] 白化分类模型未就绪（白化评估将不可用）")

    # ---- P16 附加：第二白化模型（共识弃权；缺失即安静降级）----
    # 可用环境变量关闭：DISABLE_BLEACH_CONSENSUS=1 → 不加载第二模型（App 不再出现复核提示）。
    # 实测真实照片上两模型分歧率约 57%（第二模型在仙本那照片上系统性偏向"死亡"），
    # 若觉得提示过密可用此开关或打包时不带第二模型。
    BLEACH_ALT = None
    alt_dirs = BLEACH_ALT_DIRS
    _env_alt = os.environ.get("CONSENSUS_ALT", "").strip()
    if _env_alt:                      # 允许指定第二模型（如面向印太域时用 koh_tao_bb）
        alt_dirs = [_env_alt] + [d for d in BLEACH_ALT_DIRS if d != _env_alt]
        print(f"[共识] 已按 CONSENSUS_ALT 指定第二模型优先：{_env_alt}")
    if os.environ.get("DISABLE_BLEACH_CONSENSUS", "").strip() in ("1", "true", "yes"):
        print("[关闭] 共识弃权已通过 DISABLE_BLEACH_CONSENSUS 关闭 → consensus=null")
    else:
        for name in alt_dirs:
            if name == BLEACH_LOADED:
                continue
            try:
                got = _load_bleach(name)
                if got is None:
                    continue
                # 只有类别集合与主模型一致时才能做共识比较
                if BLEACH is not None and (sorted(map(str, got["classes"]))
                                           != sorted(map(str, BLEACH["classes"]))):
                    print(f"[跳过] 第二白化模型 {name} 类别与主模型不一致，无法做共识")
                    continue
                BLEACH_ALT = got
                print(f"[加载] 第二白化模型（共识弃权）: {name}  类别={got['classes']}")
                break
            except Exception as e:
                print(f"[跳过] 第二白化模型 {name} 加载失败: {e}")
    if BLEACH_ALT is None:
        print("[提示] 第二白化模型未就绪 → 共识弃权功能降级（consensus=null）")

    # ---- 珊瑚个体计数模型（P3 附加能力）----
    # ⚠️ 只**新增**输出字段，不参与也不修改覆盖率 / 属 / 白化的任何计算。
    global COUNTER
    if COUNT_CKPT.exists():
        try:
            from count_coral_yolo import CoralCounter
            COUNTER = CoralCounter(COUNT_CKPT)
            print("[加载] 个体计数模型: YOLOv9c（附加能力，不影响现有输出）")
        except Exception as e:
            COUNTER = None
            print(f"[跳过] 个体计数模型加载失败: {e}")
    else:
        print(f"[跳过] 个体计数模型未就绪（{COUNT_CKPT} 不存在，仅少一个附加字段）")


def count_coral_individuals(img: Image.Image, conf=None, iou=None):
    """P3 附加能力：珊瑚个体数量 + 位置。

    任何异常都返回 None（或带 error 的字典），**绝不影响**主结果可用性 ——
    计数是锦上添花，覆盖率/属/白化才是主结论。
    """
    if COUNTER is None:
        return None
    try:
        t0 = time.time()
        kw = {}
        if conf is not None:
            kw["conf"] = conf
        if iou is not None:
            kw["iou"] = iou
        r = COUNTER.count(img, **kw)
        r["elapsedMs"] = round((time.time() - t0) * 1000, 1)
        return r
    except Exception as e:
        return {"count": None, "error": f"{type(e).__name__}: {e}"}


CN_BC = {"bleached": "白化", "healthy": "健康", "dead": "死亡",
         "Bleached": "白化", "Healthy": "健康", "Dead": "死亡"}


def classify_bleaching(img: Image.Image, min_conf=0.55):
    """全图白化状态分类。

    ⚠️ 为什么不用分割模型的 bleachedPct：实测该指标在第三方白化数据集上
       AUC 仅 0.46（低于随机），跨域无效。白化状态必须由分类模型给出。

    P16 新增（**只增字段，不改既有键**）：若第二模型 `BLEACH_ALT` 可用，则额外给出
    `altLabel` / `consensus`。依据：实测「两模型一致才算判定、不一致交人工复核」在
    4 个测试集上都优于任一单模型（宏 F1 +0.02~0.07），代价是约 1/3~1/2 图片进入待复核
    （见 docs/项目交接与续接指引.md §9.16.13）。
    """
    if BLEACH is None:
        return None
    try:
        with torch.no_grad():
            x = BLEACH["tf"](img.convert("RGB")).unsqueeze(0).to(DEVICE)
            p = torch.softmax(BLEACH["model"](x).float() / BLEACH["temp"], 1)[0].cpu().numpy()
    except Exception:
        return None
    order = np.argsort(-p)
    top = [{"label": BLEACH["classes"][i], "labelCn": CN_BC.get(BLEACH["classes"][i], BLEACH["classes"][i]),
            "confidence": round(float(p[i]), 6)} for i in order]
    out = {
        "model": BLEACH["name"],
        "label": top[0]["label"], "labelCn": top[0]["labelCn"],
        "confidence": top[0]["confidence"],
        "reliable": top[0]["confidence"] >= min_conf,
        "probabilities": {BLEACH["classes"][i]: round(float(p[i]), 6) for i in range(len(BLEACH["classes"]))},
        "top": top[:3],
    }
    # ---- P16 附加：第二模型 + 共识（缺失时安静降级，不影响既有字段）----
    if BLEACH_ALT is not None:
        try:
            with torch.no_grad():
                xa = BLEACH_ALT["tf"](img.convert("RGB")).unsqueeze(0).to(DEVICE)
                pa = torch.softmax(BLEACH_ALT["model"](xa).float() / BLEACH_ALT["temp"], 1)[0].cpu().numpy()
            ia = int(pa.argmax())
            alt_label = BLEACH_ALT["classes"][ia]
            alt_cn = CN_BC.get(alt_label, alt_label)
            agree = (alt_label == top[0]["label"])
            # 三档提示：一致 / 强复核（主模型也不自信）/ 弱提醒（主模型高置信但有异议）。
            # 为什么需要分档：实测真实照片上两模型分歧率高达 56.7%，若分歧一律提示"建议人工复核"，
            # 会让一半以上的上传都出现复核提示（体验上像功能坏了）。分档后
            # 强复核只占 ~24%，其余降级为"另一模型持不同意见"的弱提醒，主结论仍然给出。
            if agree:
                severity = "agree"
            elif (top[0]["confidence"] < CONSENSUS_REVIEW_CONF
                  or float(pa[ia]) >= CONSENSUS_CONFLICT_CONF):
                # 强复核的两种情形：① 主模型自己不自信；② **两个模型都很自信却冲突**
                # （后者最危险：一定有一个模型大错，必须人工看）
                severity = "review"
            else:
                severity = "note"
            out["altModel"] = BLEACH_ALT["name"]
            out["altLabel"] = alt_label
            out["altLabelCn"] = alt_cn
            out["altConfidence"] = round(float(pa[ia]), 6)
            out["consensus"] = {
                "agree": bool(agree),
                "label": top[0]["label"] if agree else None,
                "labelCn": top[0]["labelCn"] if agree else None,
                "severity": severity,          # agree | review | note
                # review=True 表示应提示人工复核（两模型分歧 **且** 主模型置信度不足）
                "review": severity == "review",
                "reason": ("两模型判定一致，可直接采信" if agree
                           else (f"主模型判「{top[0]['labelCn']}」但置信度仅 "
                                 f"{top[0]['confidence']:.0%}，第二模型判「{alt_cn}」，建议人工复核"
                                 if severity == "review" else
                                 f"主模型判「{top[0]['labelCn']}」（置信度 {top[0]['confidence']:.0%}），"
                                 f"第二模型持不同意见（「{alt_cn}」），仅供参考")),
            }
        except Exception:
            out["consensus"] = None
    else:
        out["consensus"] = None
    return out


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
            "categories": SEG.n_classes if SEG else 0,
            # P3 新增：个体计数模型状态（原有字段语义与取值均未改动）
            "coralCounter": "loaded" if COUNTER else "not_trained",
            # P16 新增：第二白化模型（共识弃权用）；既有字段不受影响
            "bleachAlt": (BLEACH_ALT["name"] if BLEACH_ALT else "not_loaded")}


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
async def analyze(request: Request, file: UploadFile = File(...),
                  enhance_first: bool = False,
                  lat: float = Form(None), lon: float = Form(None),
                  year: int = Form(None), count: bool = True):
    # 兼容两种传参方式：
    #   · 表单字段（小程序 wx.uploadFile 的 formData 走这条）
    #   · 查询参数（curl / Skill 拼接 URL 走这条）
    if lat is None or lon is None:
        qp = request.query_params
        lat = lat if lat is not None else (float(qp["lat"]) if "lat" in qp else None)
        lon = lon if lon is not None else (float(qp["lon"]) if "lon" in qp else None)
        if year is None and "year" in qp:
            year = int(qp["year"])
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

    # ② 白化状态：由**分类模型**给出（分割模型的白化像素占比经实测跨域无效）
    bleach = classify_bleaching(img)

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
        "bleaching": bleach,
        # P3 新增字段（附加能力）：珊瑚个体数量 + 位置。count=False 时为 None。
        # 注意：只新增键，上面所有既有键的名称、类型与取值口径均未改动。
        "coralCount": count_coral_individuals(src) if count else None,
        "captureQuality": {
            "level": qv["level"],            # good / warn / poor
            "usable": qv["usable"],
            "contrast": qm["contrast"],
            "rgRatio": qm["rgRatio"],
            "message": qv["message"],
            # 阈值由服务端下发，避免前端硬编码过期
            "thresholds": {
                "goodContrast": QUALITY_TH["good"]["contrast"],
                "warnContrast": QUALITY_TH["warn"]["contrast"],
            },
        },
        "enhanced": bool(enhance_first),
        "disclaimer": DISCLAIMER,
        "inferenceMs": round((time.time() - t0) * 1000, 1),
    }

    # ③ 综合研判（可选）：给出坐标时，融合图像 + NOAA 环境数据，输出修复优先级
    if lat is not None and lon is not None:
        try:
            result["climate"] = climate_context(lat, lon, year)
            # 新增（P5 之外的独立能力）：往年白化预警记录 → 投放时间窗建议
            result["deployment"] = climate_profile_for(lat, lon)
            result["restoration"] = assess_restoration(
                cover={
                    "alivePct": live,
                    "bleachedPct": grp.get("bleached", 0.0),
                    "deadPct": grp.get("dead", 0.0),
                    "algaePct": grp.get("algae", 0.0),
                    "substratePct": grp.get("substrate", 0.0),
                    "coralTotalPct": coral_total,
                },
                climate=result["climate"],
                coral_region=result["coralRegion"],
                capture_quality=result["captureQuality"],
                cell=result["climate"],
                # 把已算好的档案传进去（并把坐标也带上），否则研判拿不到历史热压力，
                # 投放建议会退化成"未提供经纬度"（本会话实测踩过）
                profile=result["deployment"],
                lat=lat, lon=lon, year=year,
            )
        except Exception as e:      # 研判失败不影响主结果
            # 保证响应形状一致：任一环节失败也要有这几个键（否则前端可能 KeyError）
            result.setdefault("climate", None)
            result.setdefault("deployment", None)
            result["restoration"] = None
            result["climateError"] = f"{type(e).__name__}: {e}"
    else:
        result["climate"] = None
        result["deployment"] = None
        result["restoration"] = None
        result["restorationHint"] = "传入 lat/lon 即可获得气候背景与修复优先级研判"

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


# ---------------------------------------------------------------- 个体计数（P3）
@app.post("/count")
async def count_only(file: UploadFile = File(...),
                     conf: float = Form(0.20), iou: float = Form(0.5),
                     enhance_first: bool = False):
    """P3 附加端点：只做珊瑚个体计数（YOLOv9c），不跑分割/分类。

    返回：个体总数 + 每个个体的像素框与置信度。
    `/analyze` 的响应里也新增了同样口径的 `coralCount` 字段（附加，不覆盖既有结论）。
    """
    if COUNTER is None:
        raise HTTPException(503, "个体计数模型未加载（缺少 weights/yolo_coral/best.pt）")
    data = await file.read()
    if not data:
        raise HTTPException(400, "空文件")
    try:
        img = Image.open(io.BytesIO(data))
    except Exception:
        raise HTTPException(400, "无法解析图片")
    src = enhance(img, clahe=True) if enhance_first else img
    r = count_coral_individuals(src, conf=conf, iou=iou) or {}
    r["enhanced"] = bool(enhance_first)
    r["disclaimer"] = DISCLAIMER
    return JSONResponse(r)


# ---------------------------------------------------------------- 环境数据
@app.get("/climate")
def climate(lat: float, lon: float, year: int = None):
    """环境数据插件：查询某坐标的海表热压力（NOAA CRW DHW / 白化预警等级）。"""
    return JSONResponse(climate_context(lat, lon, year))


@app.get("/climate/profile")
def climate_profile(lat: float, lon: float):
    """投放窗口与热压力档案：把**往年白化预警记录**（DHW/BAA/HotSpot，2023–2025）变成
    「建议避开哪几个月投放 / 哪些格点在热压力维度上更友好」的规则化建议。

    ⚠️ 三条口径（响应里也带）：仅热压力维度、样本仅 3 年、5km 格点非礁点；
    且**不是投放效果评估**（项目没有投放后的存活率数据）。
    与 `/climate` 相同的**空间覆盖闸门**：网格外返回 `ok=false`。
    """
    return JSONResponse(climate_profile_for(lat, lon))


@app.get("/climate/cells")
def climate_cells(limit: int = 200):
    """列出可用格点（供前端做点位选择）。"""
    import climate_context as cc
    rows = cc.cell_table()[:max(1, min(limit, 2000))]
    return JSONResponse({
        "count": len(rows),
        "cells": [{"year": y, "lat": la, "lon": lo, "dhwMax": m,
                   "baaLabel": b, "daysDhwGe8": g} for y, la, lo, m, b, g in rows],
    })


# ---------------------------------------------------------------- 综合研判
@app.post("/priority")
def priority(payload: dict):
    """
    综合研判插件：融合图像结果 + 环境数据，输出修复优先级与保育报告。

    body:
      {
        "cover": {alivePct, bleachedPct, deadPct, algaePct, coralTotalPct},
        "lat": 4.4, "lon": 118.8, "year": 2024,          # 可选，给了就查气候
        "coralRegion": {...}, "captureQuality": {...}     # 可选
      }
    """
    cover = payload.get("cover") or {}
    lat, lon, year = payload.get("lat"), payload.get("lon"), payload.get("year")
    climate = None
    if lat is not None and lon is not None:
        climate = climate_context(lat, lon, year)
    r = assess_restoration(
        cover=cover, climate=climate,
        coral_region=payload.get("coralRegion") or {},
        capture_quality=payload.get("captureQuality") or {},
        cell=climate,
        # ⚠️ 必须把坐标传下去：否则研判拿不到「往年热压力档案」，
        #    投放建议会退化成"未提供经纬度"（/analyze 与 /priority 都踩过）
        lat=lat, lon=lon, year=year,
    )
    return JSONResponse(r)


# ---------------------------------------------------------------- 网页版（H5）
# 把 web/ 目录挂到根路径：同一个进程、同一个端口，手机与电脑浏览器打开
#   http://<本机IP>:8000/  即可用完整服务（识别 + 环境 + 研判 + 中英报告）。
# ⚠️ 必须放在**所有 API 路由之后**：Starlette 按注册顺序匹配，前面的 /analyze 等
#    接口会优先命中，只有其它路径才落到静态文件。
WEB_DIR = ROOT / "web"
if WEB_DIR.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
    print(f"[网页版] 已挂载 {WEB_DIR}")
    print("         本机访问: http://127.0.0.1:8000/")
    print("         手机访问: http://<电脑局域网IP>:8000/  （需同一 Wi-Fi；摄像头需 HTTPS）")
else:
    print(f"[网页版] 未找到 {WEB_DIR}（只有 API，无网页界面）")


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
