"""
属级模型训练链（E7 + E9 + E10）
================================================================
按依赖顺序串行执行，避免 GPU 争用：

  1. 等自蒸馏训练结束（用日志活跃度判活，不依赖 wmic）
  2. 用退化不变性权重重跑降质曲线 → 修复前后对比表
  3. 训练印太属级模型（34 属，训练集来自珊瑚大三角）
  4. 在**仙本那留出集**（1,116 张，地理隔离）上跑完整评估协议
  5. 近重复审计（pHash）

用法：
    python run_species_chain.py --epochs 26 --img-size 320 --batch 20
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
R = ROOT / "reports"
PY = sys.executable

DISTILL_LOG = R / "distill_train3.log"
SPECIES_LOG = R / "species_ip_train.log"
CHAIN_LOG = R / "species_chain.log"


def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    with open(CHAIN_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_active(path: Path, idle_sec=240):
    """日志在 idle_sec 内更新过 = 进程仍在跑。"""
    return path.exists() and (time.time() - path.stat().st_mtime) < idle_sec


def run(cmd, logfile):
    log("执行: " + " ".join(str(c) for c in cmd))
    with open(logfile, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*70}\n[{time.strftime('%H:%M:%S')}] {' '.join(str(c) for c in cmd)}\n{'='*70}\n")
        p = subprocess.run(cmd, cwd=str(SCRIPTS), stdout=f, stderr=subprocess.STDOUT)
    log(f"  退出码 {p.returncode}")
    return p.returncode


def wait_idle(path, desc, timeout_min=180):
    log(f"等待 {desc} 结束...")
    t0 = time.time()
    while log_active(path) and time.time() - t0 < timeout_min * 60:
        time.sleep(30)
    log(f"  {desc} 已结束（或超时）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=26)
    ap.add_argument("--img-size", type=int, default=320)
    ap.add_argument("--batch", type=int, default=20)
    ap.add_argument("--skip-distill-eval", action="store_true")
    args = ap.parse_args()

    CHAIN_LOG.write_text("", encoding="utf-8")
    log("=== 属级模型训练链启动 ===")

    # ---- 1&2. 等自蒸馏结束 → 降质对比 ----
    if not args.skip_distill_eval:
        wait_idle(DISTILL_LOG, "自蒸馏训练")
        inv = ROOT / "weights" / "segformer_coralscapes_degradinv"
        if (inv / "config.json").exists():
            for extra in ("preprocessor_config.json", "id2label.json"):
                src = ROOT / "weights" / "segformer_coralscapes" / extra
                if src.exists() and not (inv / extra).exists():
                    (inv / extra).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            run([PY, "-u", "eval_degradation.py", "--model", "a", "--model-dir", str(inv),
                 "--tag", "degradinv_anchor", "--limit", "120"], R / "degradinv_chain.log")
            run([PY, "-u", "eval_degradation.py", "--model", "a", "--model-dir", str(inv),
                 "--tag", "degradinv_anchor_enh", "--enhance", "--limit", "120"],
                R / "degradinv_chain.log")

    # ---- 3. 训练属级模型 ----
    img_root = ROOT / "data" / "inat_dataset" / "images"
    n_train = sum(1 for _ in (img_root / "train").rglob("*") if _.is_file())
    log(f"训练样本: {n_train} 张（34 属，来自珊瑚大三角）")
    rc = run([PY, "-u", "train.py", "--task", "species_ip",
              "--data-dir", str(img_root),
              "--img-size", str(args.img_size), "--batch-size", str(args.batch),
              "--epochs", str(args.epochs), "--freeze-epochs", "2",
              "--patience", "8", "--workers", "4"], SPECIES_LOG)
    if rc != 0:
        log("训练失败，链路终止")
        return 1

    # ---- 4. 仙本那留出集完整评估 ----
    run([PY, "-u", "evaluate_protocol.py", "--task", "species_ip", "--split", "test",
         "--data-dir", str(img_root)], R / "species_chain.log")

    # ---- 5. 近重复审计 ----
    run([PY, "-u", "phash_audit.py", "--root", str(img_root)], R / "species_chain.log")

    # ---- 汇总 ----
    p = R / "protocol_species_ip_test.json"
    if p.exists():
        j = json.loads(p.read_text(encoding="utf-8"))
        log("=" * 58)
        log("【最终结果】印太属级模型 · 仙本那留出集")
        log(f"  类别数      : {j['n_classes']}")
        log(f"  样本数      : {j['n_samples']}")
        log(f"  Top-1       : {j['top1']:.2%}  [95% CI {j['top1Ci95'][0]:.2%} – {j['top1Ci95'][1]:.2%}]")
        log(f"  宏平均 F1   : {j['macroF1']:.4f}")
        log(f"  ECE         : {j['ece']:.4f}")
        for r in j["coverageCurve"]["byCoverage"]:
            if abs(r["coverage"] - 0.9) < 0.02:
                log(f"  覆盖率 90%  : 准确率 {r['accuracy']:.2%}")
        log("=" * 58)
    log("链路完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
