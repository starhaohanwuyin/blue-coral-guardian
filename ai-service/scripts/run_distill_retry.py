"""
自蒸馏修正版重跑（等待属级链结束后自动执行）
================================================================
第一次自蒸馏失败的原因（已定位）：
    训练用**随机裁剪 384×384**，对整景照片只是一个小局部；若该局部珊瑚密集，
    教师输出很高的珊瑚占比，学生学到「珊瑚偏多」先验
    → L0 基准 39.66% 漂到 53.07%（锚定后）/+75.73%（无锚定）。

本次修正：
    · --resize-mode：**整图缩放**，训练视图与推理时的整景输入分布一致
    · --anchor-w 1.5：继续保留锚定损失
    · --out-suffix _v2：保留旧权重作对照

用法：
    python run_distill_retry.py
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
R = ROOT / "reports"
PY = sys.executable

CHAIN_LOG = R / "species_chain.log"
TRAIN_LOG = R / "species_ip_train.log"
OUT = R / "distill_retry.log"


def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_active(p: Path, idle=300):
    return p.exists() and (time.time() - p.stat().st_mtime) < idle


def run(cmd, logfile):
    log("执行: " + " ".join(str(c) for c in cmd))
    with open(logfile, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*70}\n[{time.strftime('%H:%M:%S')}] {' '.join(str(c) for c in cmd)}\n{'='*70}\n")
        rc = subprocess.run(cmd, cwd=str(SCRIPTS), stdout=f, stderr=subprocess.STDOUT).returncode
    log(f"  退出码 {rc}")
    return rc


def main():
    OUT.write_text("", encoding="utf-8")
    log("等待属级链结束（含评估与 pHash 审计）...")
    t0 = time.time()
    while time.time() - t0 < 3 * 3600:
        txt = CHAIN_LOG.read_text(encoding="utf-8", errors="replace") if CHAIN_LOG.exists() else ""
        if "链路完成" in txt:
            log("属级链已完成")
            break
        if not log_active(TRAIN_LOG, 400) and not log_active(CHAIN_LOG, 400):
            log("训练日志已静止，认为训练已结束")
            break
        time.sleep(30)

    new_dir = ROOT / "weights" / "segformer_coralscapes_degradinv_v2"

    # 1. 重跑自蒸馏（整图缩放 + 锚定）
    log("=== 步骤 1/2：修正版自蒸馏（整图缩放）===")
    run([PY, "-u", "finetune_degradinv_distill.py",
         "--epochs", "3", "--crop", "384", "--batch", "8",
         "--limit", "1200", "--workers", "2",
         "--anchor-w", "1.5", "--resize-mode", "--out-suffix", "_v2",
         "--init", str(ROOT / "weights" / "segformer_coralscapes")], R / "distill_retry.log")

    if not (new_dir / "config.json").exists():
        log("⚠ 未生成 v2 权重，链路终止")
        return 1

    # 补齐配置文件
    for extra in ("preprocessor_config.json", "id2label.json"):
        src = ROOT / "weights" / "segformer_coralscapes" / extra
        if src.exists() and not (new_dir / extra).exists():
            (new_dir / extra).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    # 2. 评估
    log("=== 步骤 2/2：降质曲线评估（修正版）===")
    run([PY, "-u", "eval_degradation.py", "--model", "a", "--model-dir", str(new_dir),
         "--tag", "degradinv_v2_resize", "--limit", "120"], R / "distill_retry.log")

    # 3. 汇总对比
    def load(n):
        p = R / n
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    base = load("degradation_modelA_base.json")
    v1 = load("degradation_modelA_degradinv_anchor.json")
    v2 = load("degradation_modelA_degradinv_v2_resize.json")
    lv = ["L0_clean", "L1_near", "L2_typical", "L3_far", "L4_harsh"]

    log("=" * 78)
    log("活珊瑚覆盖率对比（%）")
    log("=" * 78)
    log(f"{'档位':<12}{'原始':>12}{'v1裁剪+锚定':>16}{'v2整图缩放+锚定':>18}")
    b0 = next((x for x in base["rows"] if x["level"] == "L0_clean"), {}).get("alive", 0) if base else 0
    for l in lv:
        def g(d):
            if not d:
                return None
            return next((x["alive"] for x in d["rows"] if x["level"] == l), None)
        a, b, c = g(base), g(v1), g(v2)
        log(f"{l:<12}{(f'{a:.2%}' if a is not None else '—'):>12}"
            f"{(f'{b:.2%}' if b is not None else '—'):>16}"
            f"{(f'{c:.2%}' if c is not None else '—'):>18}")
    log("=" * 78)
    if v2:
        c0 = next((x["alive"] for x in v2["rows"] if x["level"] == "L0_clean"), 0)
        c3 = next((x["alive"] for x in v2["rows"] if x["level"] == "L3_far"), 0)
        log(f"L0 漂移: {(c0-b0):+.2%}   L3 恢复: {c3:.2%}")
        if abs(c0 - b0) < 0.05 and c3 > 0.05:
            log("✅ 修复成功：L0 稳定且 L3 恢复")
        elif abs(c0 - b0) < 0.05:
            log("⚠️ L0 稳定，但 L3 未恢复")
        else:
            log("❌ 仍有漂移，整图缩放未能完全解决问题")
    log("完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
