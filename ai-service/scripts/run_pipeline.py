"""
仙本那识别流水线（全自动串联）
================================================================
按依赖顺序执行，每步完成才进入下一步：

  1. 等 iNaturalist 珊瑚大三角元数据抓取完成
  2. 构建属级数据集（训练=珊瑚大三角 / 测试=仙本那，地理隔离）
  3. 下载图片（train/val/test，含许可证归属记录）
  4. 等 GPU 空闲（印太白化模型训练结束）
  5. 训练印太属级识别模型（在仙本那测试集上评估）
  6. 输出汇总

用法：
    python run_pipeline.py --level genus --min-test 8 --min-train 40
    python run_pipeline.py --skip-download        # 图片已下载过
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
LOGS = ROOT / "reports"
PY = sys.executable


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run(cmd, logfile, timeout=None):
    """运行子进程并把输出写入日志。"""
    log(f"执行: {' '.join(str(c) for c in cmd)}")
    with open(logfile, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*70}\n[{time.strftime('%H:%M:%S')}] {' '.join(str(c) for c in cmd)}\n{'='*70}\n")
        p = subprocess.run(cmd, cwd=str(SCRIPTS), stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
    return p.returncode


def wait_file(path, desc, timeout_min=90):
    log(f"等待 {desc}: {path.name}")
    t0 = time.time()
    while time.time() - t0 < timeout_min * 60:
        if Path(path).exists():
            log(f"  ✓ {desc} 就绪（{int(time.time()-t0)}s）")
            return True
        time.sleep(20)
    log(f"  ✗ 超时未就绪: {path}")
    return False


def gpu_busy():
    """检测是否还有 python 在跑训练（粗略但够用）。"""
    try:
        out = subprocess.run(["wmic", "process", "where", "name='python.exe'", "get", "commandline"],
                             capture_output=True, text=True, timeout=30).stdout
        return "train.py" in out
    except Exception:
        return False


def wait_gpu(timeout_min=120):
    log("等待 GPU 空闲（其它训练结束）")
    t0 = time.time()
    while time.time() - t0 < timeout_min * 60:
        if not gpu_busy():
            log("  ✓ GPU 空闲")
            return True
        time.sleep(30)
    log("  ⚠ 等待超时，继续执行")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default="genus", choices=["genus", "species"])
    ap.add_argument("--min-test", type=int, default=8)
    ap.add_argument("--min-train", type=int, default=40)
    ap.add_argument("--max-per-class", type=int, default=300)
    ap.add_argument("--img-size", type=int, default=320)
    ap.add_argument("--epochs", type=int, default=28)
    ap.add_argument("--skip-download", action="store_true")
    args = ap.parse_args()

    LOGS.mkdir(parents=True, exist_ok=True)

    # ---- 1. 等元数据 ----
    tri = ROOT / "data" / "inat" / "coraltriangle.json"
    if not wait_file(tri, "珊瑚大三角元数据", 120):
        log("无法继续：元数据缺失")
        return 1

    # ---- 2. 构建数据集 ----
    rc = run([PY, "-u", "build_inat_dataset.py", "--level", args.level,
              "--min-test", str(args.min_test), "--min-train", str(args.min_train),
              "--max-per-class", str(args.max_per_class)],
             LOGS / "pipeline.log")
    if rc != 0:
        log(f"build_inat_dataset 失败 (rc={rc})，请查看 pipeline.log")
        return 1

    cls_meta = ROOT / "data" / "inat_dataset" / f"{args.level}_classes.json"
    meta = json.loads(cls_meta.read_text(encoding="utf-8"))
    log(f"数据集: {len(meta['classes'])} 类 | 训练 {meta['train_photos']} 图 | "
        f"验证 {meta['val_photos']} 图 | **仙本那测试 {meta['test_photos']} 图**")
    log(f"类别: {meta['classes']}")

    # ---- 3. 下载图片 ----
    if not args.skip_download:
        rc = run([PY, "-u", "download_inat_images.py", "--level", args.level,
                  "--split", "all", "--workers", "12"],
                 LOGS / "pipeline.log")
        if rc != 0:
            log(f"图片下载失败 (rc={rc})，请查看 pipeline.log")
            return 1

    img_root = ROOT / "data" / "inat_dataset" / "images"
    for s in ("train", "val", "test"):
        d = img_root / s
        n = sum(1 for _ in d.rglob("*") if _.is_file()) if d.exists() else 0
        log(f"  {s}: {n} 张")

    # ---- 4. 等 GPU ----
    wait_gpu()

    # ---- 5. 训练印太属级模型 ----
    rc = run([PY, "-u", "train.py", "--task", "species_ip",
              "--data-dir", str(img_root),
              "--img-size", str(args.img_size), "--batch-size", "24",
              "--epochs", str(args.epochs), "--freeze-epochs", "2",
              "--patience", "8", "--workers", "4"],
             LOGS / "species_ip_train.log")
    if rc != 0:
        log(f"训练失败 (rc={rc})，请查看 species_ip_train.log")
        return 1

    # ---- 6. 汇总 ----
    rep = ROOT / "reports" / "species_ip" / "metrics.json"
    if rep.exists():
        j = json.loads(rep.read_text(encoding="utf-8"))
        log("=" * 60)
        log("【最终结果】印太属级识别模型")
        log(f"  类别数        : {len(j['classes'])}")
        log(f"  仙本那测试 Top-1: {j['test_top1']:.2%}   ← 目标指标")
        log(f"  仙本那测试 宏F1 : {j['test_macro_f1']:.4f}")
        b = j["selective_prediction"]["best_meeting_target"]
        if b:
            log(f"  99.9% 口径    : 置信度≥{b['threshold']} 时覆盖率 {b['coverage']:.1%}")
        log("=" * 60)
    log("流水线完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
