"""
自动链路：等待自蒸馏训练结束 → 用新权重重跑降质评估 → 输出修复前后对比
================================================================
无需人工介入，可在后台运行。

用法：
    python run_degradinv_chain.py
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
PY = sys.executable
INV_DIR = ROOT / "weights" / "segformer_coralscapes_degradinv"
BASE_DIR = ROOT / "weights" / "segformer_coralscapes"


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


TRAIN_LOG = ROOT / "reports" / "distill_train2.log"


def training_running(idle_sec=180):
    """用日志活跃度判断训练是否在跑（wmic 已被新版 Windows 移除，不可用）。"""
    if not TRAIN_LOG.exists():
        return False
    age = time.time() - TRAIN_LOG.stat().st_mtime
    return age < idle_sec


def run(cmd, logfile):
    log("执行: " + " ".join(str(c) for c in cmd))
    with open(logfile, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*70}\n[{time.strftime('%H:%M:%S')}] {' '.join(str(c) for c in cmd)}\n{'='*70}\n")
        p = subprocess.run(cmd, cwd=str(SCRIPTS), stdout=f, stderr=subprocess.STDOUT)
    return p.returncode


def main():
    log("等待自蒸馏训练结束...")
    t0 = time.time()
    while training_running() and time.time() - t0 < 3600:
        time.sleep(20)
    log("训练结束（或超时）")

    if not (INV_DIR / "config.json").exists():
        log("⚠ 未找到退化不变性权重，链路终止")
        return 1
    log(f"权重就绪: {INV_DIR}")

    lf = ROOT / "reports" / "degradinv_chain.log"
    log("评估 1/2：退化不变性权重（无色彩还原）")
    run([PY, "-u", "eval_degradation.py", "--model", "a",
         "--model-dir", str(INV_DIR), "--tag", "degradinv", "--limit", "120"], lf)

    log("评估 2/2：退化不变性权重 + 色彩还原前端")
    run([PY, "-u", "eval_degradation.py", "--model", "a",
         "--model-dir", str(INV_DIR), "--tag", "degradinv_enh", "--enhance", "--limit", "120"], lf)

    # 汇总对比
    files = {
        "修复前(base)": ROOT / "reports" / "degradation_modelA_base.json",
        "修复后(degradinv)": ROOT / "reports" / "degradation_modelA_degradinv.json",
        "修复后+色彩还原": ROOT / "reports" / "degradation_modelA_degradinv_enh.json",
    }
    data = {}
    for k, p in files.items():
        if p.exists():
            data[k] = {r["level"]: r for r in json.loads(p.read_text(encoding="utf-8"))["rows"]}

    levels = ["L0_clean", "L1_near", "L2_typical", "L3_far", "L4_harsh"]
    desc = {"L0_clean": "原始", "L1_near": "3m", "L2_typical": "8m典型",
            "L3_far": "15m浑浊", "L4_harsh": "20m恶劣"}

    print("\n" + "=" * 88)
    print("活珊瑚覆盖率估计对比（%）")
    print("=" * 88)
    print(f"{'档位':<12}{'条件':<10}" + "".join(f"{k:>20}" for k in data))
    print("-" * 88)
    for lv in levels:
        row = f"{lv:<12}{desc[lv]:<10}"
        for k in data:
            v = data[k].get(lv)
            row += f"{v['alive']:>19.2%} " if v else f"{'—':>19} "
        print(row)
    print("=" * 88)

    out = ROOT / "reports" / "degradinv_comparison.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n汇总: {out}")
    log("链路完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
