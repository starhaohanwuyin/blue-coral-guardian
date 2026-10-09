"""
拍摄条件自检：判断照片是否超出模型适用边界
================================================================
动机（已实测）：
    模型在 ≤8m 拍摄条件下覆盖率误差 ≤2.2%，15m 以上浑浊水域**完全失效**。
    但用户不会看文档，把 20m 拍的糊照片上传是常态。
    → 服务必须**自动判断照片质量**，超出边界时给出警告而不是编一个数字。

原理：
    水下成像模型 I = J·exp(-βz) + B(1-exp(-βz)) 中，红光衰减远快于蓝光。
    因此 **R/G 通道均值比** 是水深+浑浊度的良好代理：
        清水浅水  R/G ≈ 1.0
        8m 典型   R/G ≈ 0.6
        15m 浑浊  R/G ≈ 0.35
    再叠加「对比度（灰度标准差）」与「饱和度」，构成 3 维质量评分。

本脚本先用已标定的物理降质集**确定阈值**，供服务端使用。

用法：
    python check_capture_quality.py --calibrate    # 用降质集标定阈值
    python check_capture_quality.py --image x.jpg  # 评估单张
"""
import argparse
import json
import statistics
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
LEVELS = ["L0_clean", "L1_near", "L2_typical", "L3_far", "L4_harsh"]
LEVEL_CN = {"L0_clean": "原始/浅水", "L1_near": "近距3m", "L2_typical": "典型8m",
            "L3_far": "远距15m", "L4_harsh": "恶劣20m"}


def metrics(img: Image.Image) -> dict:
    """计算拍摄条件指标。"""
    a = np.asarray(img.convert("RGB")).astype(np.float32) / 255.0
    r, g, b = a[..., 0].mean(), a[..., 1].mean(), a[..., 2].mean()
    gray = a @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    contrast = float(gray.std())
    # 饱和度：最大通道 - 最小通道 的均值
    sat = float((a.max(axis=2) - a.min(axis=2)).mean())
    # 蓝绿优势：B 相对 R 的强度
    rg = float(r / max(g, 1e-6))
    return {
        "rgRatio": round(rg, 4),
        "contrast": round(contrast, 4),
        "saturation": round(sat, 4),
        "meanRGB": [round(float(r), 4), round(float(g), 4), round(float(b), 4)],
    }


# 阈值（由 --calibrate 标定后写入）
# ⚠️ 实测发现：**R/G 通道比不是单调的**——深度增加时后向散射的雾化光饱和，
#    R/G 反而回升（L2=0.318 → L3=0.355）。因此判别主指标必须用**对比度**：
#    L0=0.189, L1=0.098, L2=0.044  →  L3/L4=0.005（10 倍断崖）。
DEFAULT_THRESHOLDS = {
    "good": {"contrast": 0.030, "rgRatio": 0.15},
    "warn": {"contrast": 0.015, "rgRatio": 0.12},
}


def verdict(m: dict, th=None) -> dict:
    """根据指标给出可用性判定（**以对比度为主判据**）。"""
    th = th or DEFAULT_THRESHOLDS
    ct, rg = m["contrast"], m["rgRatio"]
    if ct >= th["good"]["contrast"] and rg >= th["good"]["rgRatio"]:
        return {"level": "good", "usable": True, "score": round(min(ct / th["good"]["contrast"], 1.0), 3),
                "message": "拍摄条件良好，评估结果可信"}
    if ct >= th["warn"]["contrast"] and rg >= th["warn"]["rgRatio"]:
        return {"level": "warn", "usable": True, "score": round(ct / th["good"]["contrast"], 3),
                "message": "拍摄条件一般（偏深或水体较浑），建议开补光灯或浅水重拍以提高可信度"}
    return {"level": "poor", "usable": False, "score": round(ct / th["good"]["contrast"], 3),
            "message": "拍摄条件超出模型适用边界（水太深/太浑/对比度过低），"
                       "本次覆盖率估计可能严重失真，建议在 10 米以内或加补光灯重拍"}


def calibrate(limit=60):
    """用物理降质集标定阈值：取 L0~L2 作为可用、L3/L4 作为不可用。"""
    print(f"{'档位':<14}{'条件':<12}{'R/G比':>9}{'对比度':>9}{'饱和度':>9}{'n':>5}")
    print("-" * 60)
    stats = {}
    for lv in LEVELS:
        d = ROOT / "data" / "degraded" / lv
        if not d.exists():
            continue
        ms = []
        for f in sorted(d.glob("*.jpg"))[:limit]:
            try:
                ms.append(metrics(Image.open(f)))
            except Exception:
                continue
        if not ms:
            continue
        agg = {k: statistics.mean(x[k] for x in ms) for k in ("rgRatio", "contrast", "saturation")}
        stats[lv] = agg
        print(f"{lv:<14}{LEVEL_CN[lv]:<12}{agg['rgRatio']:>9.3f}{agg['contrast']:>9.3f}"
              f"{agg['saturation']:>9.3f}{len(ms):>5}")

    # 阈值标定：**以对比度为主判据**（R/G 非单调，仅作极端情况兜底）
    usable = [stats[l] for l in ("L0_clean", "L1_near", "L2_typical") if l in stats]
    unusable = [stats[l] for l in ("L3_far", "L4_harsh") if l in stats]
    if usable and unusable:
        ct_good = min(x["contrast"] for x in usable)     # 0.044
        ct_bad = max(x["contrast"] for x in unusable)    # 0.005
        rg_min = min(x["rgRatio"] for x in usable)       # 0.318
        # good = 可用档下界再留 30% 余量；warn = 可用与不可用的中点
        th = {
            "good": {"contrast": round(ct_good * 0.70, 4),
                     "rgRatio": round(rg_min * 0.45, 4)},
            "warn": {"contrast": round((ct_good + ct_bad) / 2, 4),
                     "rgRatio": round(rg_min * 0.30, 4)},
        }
        print("\n标定阈值（主判据＝对比度）：")
        print(f"  可用(good): 对比度 ≥ {th['good']['contrast']}"
              f"   （实测可用档最低 {ct_good:.3f}，不可用档最高 {ct_bad:.3f}）")
        print(f"  警告(warn): 对比度 ≥ {th['warn']['contrast']}")
        print(f"  R/G 仅作兜底: good ≥{th['good']['rgRatio']}  warn ≥{th['warn']['rgRatio']}")
        out = ROOT / "reports" / "capture_quality_thresholds.json"
        out.write_text(json.dumps({
            "primaryMetric": "contrast",
            "reason": "R/G 通道比非单调（后向散射雾化光饱和），对比度才是判别指标",
            "thresholds": th, "levelStats": stats,
            "usableLevels": ["L0_clean", "L1_near", "L2_typical"],
            "unusableLevels": ["L3_far", "L4_harsh"],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  已写入: {out}")
        return th
    return DEFAULT_THRESHOLDS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--image")
    ap.add_argument("--limit", type=int, default=60)
    args = ap.parse_args()

    if args.calibrate:
        calibrate(args.limit)
        return
    if args.image:
        m = metrics(Image.open(args.image))
        v = verdict(m)
        print(json.dumps({"metrics": m, "verdict": v}, ensure_ascii=False, indent=2))
        return
    print("请指定 --calibrate 或 --image")


if __name__ == "__main__":
    main()
