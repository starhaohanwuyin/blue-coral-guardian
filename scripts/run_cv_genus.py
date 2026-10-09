"""
属级模型交叉验证（固定地理隔离测试集）
================================================================
设计要点：
    我们的测试集是**地理隔离**的仙本那留出集，**不能轮换**（否则训练会看到仙本那，
    破坏"跨域泛化"这一核心验证）。因此采用：

        固定测试集（仙本那 1116 张）
        + 轮换**训练子集**（珊瑚大三角的分层 70% 抽样，不同 seed）

    这测量的是「训练集组成对结果的影响」——正是单次划分最容易被质疑的点。

产出：
    · 各折的仙本那 Top-1
    · 均值 ± 标准差
    · 与「全量训练」结果的对比
    · 逐类召回在不同折间的稳定性

用法：
    python run_cv_genus.py                      # 默认 3 折 × 70%
    python run_cv_genus.py --folds 3 --frac 0.7 --epochs 14
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
IMG_ROOT = ROOT / "data" / "inat_dataset" / "images"
LOG = R / "cv_genus.log"


def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd, logfile):
    with open(logfile, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*70}\n[{time.strftime('%H:%M:%S')}] {' '.join(str(c) for c in cmd)}\n{'='*70}\n")
        return subprocess.run(cmd, cwd=str(SCRIPTS), stdout=f, stderr=subprocess.STDOUT).returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument("--frac", type=float, default=0.7)
    ap.add_argument("--epochs", type=int, default=14)
    ap.add_argument("--img-size", type=int, default=320)
    ap.add_argument("--batch", type=int, default=20)
    args = ap.parse_args()

    LOG.write_text("", encoding="utf-8")
    log("=== 属级模型交叉验证（固定仙本那测试集，轮换训练子集）===")
    log(f"折数={args.folds}  训练抽样比例={args.frac:.0%}  每折轮数={args.epochs}")

    results = []
    for k in range(1, args.folds + 1):
        tag = f"_cv{k}"
        log(f"\n--- 第 {k}/{args.folds} 折（seed={k}，训练集 {args.frac:.0%}）---")
        rc = run([PY, "-u", "train.py", "--task", "species_ip", "--data-dir", str(IMG_ROOT),
                  "--img-size", str(args.img_size), "--batch-size", str(args.batch),
                  "--epochs", str(args.epochs), "--freeze-epochs", "2", "--patience", "6",
                  "--workers", "4", "--subset-frac", str(args.frac), "--subset-seed", str(k),
                  "--out-suffix", tag], R / "cv_genus.log")
        if rc != 0:
            log(f"  第 {k} 折训练失败（退出码 {rc}），跳过")
            continue
        wdir = ROOT / "weights" / ("species_ip" + tag)
        mp = R / ("species_ip" + tag) / "metrics.json"
        if not mp.exists():
            log(f"  第 {k} 折未产出 metrics.json，跳过")
            continue
        j = json.loads(mp.read_text(encoding="utf-8"))
        results.append({"fold": k, "seed": k, "frac": args.frac,
                        "top1": j["test_top1"], "macroF1": j["test_macro_f1"],
                        "nTrain": j.get("n_train"), "weights": str(wdir)})
        log(f"  第 {k} 折：仙本那 Top-1 = {j['test_top1']:.4%}  宏F1 = {j['test_macro_f1']:.4f}")

    if not results:
        log("没有成功的折，终止")
        return 1

    vals = [r["top1"] for r in results]
    f1s = [r["macroF1"] for r in results]
    import statistics as st
    mean, sd = st.mean(vals), (st.pstdev(vals) if len(vals) > 1 else 0.0)
    mean_f1, sd_f1 = st.mean(f1s), (st.pstdev(f1s) if len(f1s) > 1 else 0.0)

    full = R / "protocol_species_ip_test_clean.json"
    full_top1 = None
    if full.exists():
        full_top1 = json.loads(full.read_text(encoding="utf-8"))["top1"]

    log("\n" + "=" * 70)
    log("交叉验证结果汇总")
    log("=" * 70)
    log(f"{'折':<6}{'训练样本':>10}{'仙本那 Top-1':>14}{'宏F1':>10}")
    for r in results:
        log(f"{r['fold']:<6}{r.get('nTrain') or '?':>10}{r['top1']:>14.4%}{r['macroF1']:>10.4f}")
    log("-" * 70)
    log(f"{'均值':<6}{'':>10}{mean:>14.4%}{mean_f1:>10.4f}")
    if len(vals) > 1:
        log(f"{'标准差':<6}{'':>10}{sd:>14.4%}{sd_f1:>10.4f}")
        log(f"{'范围':<6}{'':>10}{f'[{min(vals):.4%}, {max(vals):.4%}]':>14}")
    if full_top1 is not None:
        log(f"\n参考：全量训练（100%）的仙本那 Top-1 = {full_top1:.4%}")
        if len(vals) > 1:
            log(f"      交叉验证均值与全量之差 = {mean - full_top1:+.4%}")
    log("=" * 70)

    out = R / "cv_genus_results.json"
    out.write_text(json.dumps({
        "design": "固定地理隔离测试集（仙本那 1116 张）+ 轮换训练子集（珊瑚大三角分层抽样）",
        "folds": results, "mean": mean, "std": sd, "macroF1Mean": mean_f1,
        "fullTrainTop1": full_top1,
        "note": "测试集不轮换，因为它是地理隔离留出集；本 CV 衡量训练集组成的影响",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"结果: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
