"""
一键状态检查与续跑（DoD #5：可复现）
================================================================
用途：
  · 不传 --run  → 只做**状态体检**，列出每个阶段的完成情况与下一步该干什么
  · 传 --run    → 自动按依赖顺序续跑所有**未完成**的阶段

设计原则（针对本项目的实际痛点）：
  本会话中后台任务至少被中断 3 次，因此每个阶段都必须：
    ① 有明确的「完成标志文件」
    ② 可幂等重跑（已完成的跳过，未完成的续跑）
    ③ 判活不依赖 wmic（新版 Windows 已移除）

用法：
    python resume_all.py                 # 状态体检
    python resume_all.py --run           # 续跑
    python resume_all.py --run --only species_ip
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


# ---------------------------------------------------------------- 阶段定义
# (id, 描述, 完成标志, 依赖, 命令)
STAGES = [
    ("inat_semporna", "仙本那珊瑚观察元数据",
     "data/inat/semporna.json", [],
     [PY, "-u", "fetch_inat_coral.py", "--name", "semporna",
      "--bbox=4.0,118.2,4.8,119.0", "--no-diagnose"]),

    ("inat_triangle", "珊瑚大三角元数据（网格化，>10k 需 --tile）",
     "data/inat/coraltriangle.json", [],
     [PY, "-u", "fetch_inat_coral.py", "--name", "coraltriangle",
      "--bbox=-11.0,92.0,22.0,141.0", "--sleep", "1.5", "--no-diagnose", "--tile", "3"]),

    ("reefcheck", "Reef Check Malaysia 报告（实地验证数据）",
     "data/raw/reefcheck_my/2024CoralBleachingImpactReportMalaysia.pdf", [],
     None),

    ("genus_dataset", "属级数据集划分（训练=大三角 / 测试=仙本那）",
     "data/inat_dataset/genus_classes.json", ["inat_semporna", "inat_triangle"],
     [PY, "-u", "build_inat_dataset.py", "--level", "genus",
      "--min-test", "6", "--min-train", "60", "--max-per-class", "250"]),

    ("genus_images", "属级图片下载（约 1.2 万张）",
     "data/inat_dataset/ATTRIBUTION.csv", ["genus_dataset"],
     [PY, "-u", "download_inat_images.py", "--level", "genus", "--split", "all", "--workers", "14"]),

    ("bleaching_ip", "印太白化模型",
     "reports/bleaching_ip/metrics.json", [],
     [PY, "-u", "train.py", "--task", "bleaching_ip", "--img-size", "224",
      "--batch-size", "32", "--epochs", "30", "--freeze-epochs", "2",
      "--patience", "8", "--workers", "4"]),

    ("seg_base", "分割基线（Coralscapes 预训练，已就绪）",
     "weights/segformer_coralscapes/config.json", [], None),

    ("seg_degradinv", "退化不变性自蒸馏",
     "weights/segformer_coralscapes_degradinv/config.json", ["seg_base"],
     [PY, "-u", "finetune_degradinv_distill.py", "--epochs", "3", "--crop", "384",
      "--batch", "6", "--limit", "1200", "--workers", "2", "--anchor-w", "1.5",
      "--init", str(ROOT / "weights" / "segformer_coralscapes")]),

    ("species_ip", "印太属级模型（34 属）",
     "reports/species_ip/metrics.json", ["genus_images"],
     [PY, "-u", "train.py", "--task", "species_ip",
      "--data-dir", str(ROOT / "data" / "inat_dataset" / "images"),
      "--img-size", "320", "--batch-size", "20", "--epochs", "26",
      "--freeze-epochs", "2", "--patience", "8", "--workers", "4"]),

    ("protocol_species", "属级模型仙本那留出集评估协议",
     "reports/protocol_species_ip_test.json", ["species_ip"],
     [PY, "-u", "evaluate_protocol.py", "--task", "species_ip", "--split", "test",
      "--data-dir", str(ROOT / "data" / "inat_dataset" / "images")]),

    ("phash", "近重复审计",
     "reports/phash_audit.json", ["genus_images"],
     [PY, "-u", "phash_audit.py", "--root", str(ROOT / "data" / "inat_dataset" / "images")]),

    # ---- 以下为后续补充的阶段（早期版本遗漏，导致状态体检不完整）----
    ("coralscapes", "Coralscapes 分割数据集（官方验证集，用于 mIoU）",
     "data/raw/coralscapes/data/validation-00000-of-00001.parquet", [],
     [PY, "-u", "dl_coralscapes.py", "--shards", "validation-00000-of-00001.parquet"]),

    ("seg_miou", "分割质量 mIoU 评估",
     "reports/segmentation_miou_1024.json", ["coralscapes", "seg_base"],
     [PY, "-u", "eval_segmentation_miou.py", "--size", "1024"]),

    ("bleaching_new", "Roboflow 白化模型（第三方数据集）",
     "reports/bleaching_new/metrics.json", [],
     [PY, "-u", "train.py", "--task", "bleaching_new",
      "--data-dir", str(ROOT / "data" / "processed" / "bleaching_new"),
      "--img-size", "224", "--batch-size", "32", "--epochs", "18",
      "--freeze-epochs", "2", "--patience", "6", "--workers", "4"]),

    ("bleaching_all_dataset", "合并白化数据集（旧集 + RoBoflow 集）",
     "reports/combined_dataset.json", ["bleaching_new"],
     [PY, "-u", "build_combined_bleaching.py"]),

    ("bleaching_all", "合并白化模型（三域最优）",
     "reports/bleaching_all/metrics.json", ["bleaching_new", "bleaching_all_dataset"],
     [PY, "-u", "train.py", "--task", "bleaching_all",
      "--data-dir", str(ROOT / "data" / "processed" / "bleaching_all"),
      "--img-size", "224", "--batch-size", "32", "--epochs", "18",
      "--freeze-epochs", "2", "--patience", "6", "--workers", "4"]),

    ("cv_genus", "属级模型交叉验证（固定地理隔离测试集）",
     "reports/cv_genus_results.json", ["species_ip"],
     [PY, "-u", "run_cv_genus.py", "--folds", "3", "--frac", "0.7", "--epochs", "14"]),
]

CRITICAL = {"inat_semporna", "inat_triangle", "genus_dataset", "genus_images", "species_ip"}


def status(stage):
    sid, desc, marker, deps, cmd = stage
    return (ROOT / marker).exists()


def log_active(path: Path, idle_sec=240):
    return path.exists() and (time.time() - path.stat().st_mtime) < idle_sec


def run(cmd, logfile):
    with open(logfile, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*70}\n[{time.strftime('%H:%M:%S')}] {' '.join(str(c) for c in cmd)}\n{'='*70}\n")
        return subprocess.run(cmd, cwd=str(SCRIPTS), stdout=f, stderr=subprocess.STDOUT).returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="执行续跑（默认只体检）")
    ap.add_argument("--only", default=None, help="只跑指定阶段 id")
    args = ap.parse_args()

    # ---- 体检 ----
    print("=" * 78)
    print(f"{'阶段':<18}{'状态':<10}{'说明':<44}")
    print("=" * 78)
    done, todo = [], []
    for st in STAGES:
        ok = status(st)
        mark = "✅ 完成" if ok else "⬜ 待办"
        print(f"{st[0]:<18}{mark:<10}{st[1]:<44}")
        (done if ok else todo).append(st[0])
    print("=" * 78)
    print(f"完成 {len(done)}/{len(STAGES)}   关键路径缺: "
          f"{[s for s in CRITICAL if s not in done] or '无'}")

    # ---- 运行中的进程提示 ----
    running = []
    for name, lp, idle in (("自蒸馏", R / "distill_train3.log", 300),
                           ("属级模型", R / "species_ip_train.log", 300),
                           ("白化模型", R / "bleaching_ip_train.log", 300)):
        if log_active(lp, idle):
            running.append(name)
    if running:
        print(f"⚠ 检测到仍在运行: {', '.join(running)}（建议等其结束再续跑，避免 GPU 争用）")

    if not args.run:
        print("\n加 --run 执行续跑；加 --only <阶段id> 只跑单个阶段。")
        return 0

    # ---- 续跑 ----
    print("\n开始续跑...")
    for st in STAGES:
        sid, desc, marker, deps, cmd = st
        if args.only and sid != args.only:
            continue
        if status(st):
            print(f"[跳过] {sid} 已完成")
            continue
        if cmd is None:
            print(f"[跳过] {sid} 无自动命令（需人工准备）")
            continue
        missing = [d for d in deps if d not in done]
        if missing:
            print(f"[阻塞] {sid} 依赖未完成: {missing}")
            continue
        print(f"[执行] {sid} — {desc}")
        rc = run(cmd, R / "resume.log")
        print(f"        退出码 {rc}")
        if rc == 0:
            done.append(sid)
        else:
            print(f"        失败，停止后续依赖它的阶段")
    print("\n续跑结束。重新运行本脚本可查看最新状态。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
