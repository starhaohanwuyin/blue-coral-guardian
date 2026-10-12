"""下载 CoralConditionDataset 的图像（Google Drive）。

实测（2026-10-12）：直连 Drive 需要可用网络；`gdown` 能处理 Drive 文件夹。
本脚本给出**按需下载**的三条路径，避免一上来就拉 4.6 GB：

| 参数 | 文件 | 大小 | 用途 |
|---|---|---|---|
| `--external` | coral_image_external.zip | 80 MB | **印太外部测试集（Arafura/Darwin）** ← 通常只要这个 |
| `--dry` | coral_images_dry.zip | 3.27 GB | 干季训练/测试瓦片（微调用）|
| `--wet` | coral_images_wet.rar | 1.33 GB | 湿季图像（需额外 rar 解压工具）|
| （无参数）| 整个文件夹 | 4.67 GB | 全部下载 |

用法：
    python dl_ccd_images.py --check          # 只测连通性
    python dl_ccd_images.py --external       # 下 80 MB 测试集（推荐先跑这个）
    python dl_ccd_images.py --dry            # 下 3.27 GB 训练瓦片
"""
import argparse
import pathlib
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "raw" / "CoralConditionDataset"
DRIVE_FOLDER = "https://drive.google.com/drive/folders/1yjvVGSXuFRcO3b0SehyeAHzMtCHhI6S1"
FILES = {
    "external": ("1BJVJX-wJXyh2rBYK_jrKjsrxejS0159P", "coral_image_external.zip", "external"),
    "dry": ("1QFqlCFL4cY8mn2yS6LPYJmjRcwRwSrAQ", "coral_images_dry.zip", "dry"),
    "wet": ("1cbmTZ9-y7B51PPFyStSZhJNgeqD7WTwA", "coral_images_wet.rar", "wet"),
}


def drive_reachable(timeout=20):
    try:
        with urllib.request.urlopen(urllib.request.Request(
                "https://drive.google.com/", headers={"User-Agent": "Mozilla/5.0"}), timeout=timeout) as r:
            return r.status, None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:80]}"


def manual_help():
    print("\n❌ 当前网络访问不了 Google Drive。手工方式（任选）：")
    print(f"  ① 能上外网的机器/浏览器打开：{DRIVE_FOLDER}")
    print("     下载所需 zip → 放到：")
    print(f"     {DEST}")
    print("  ② 或让队友下好发你，放到同一路径")
    print("  ③ 换网络/代理后重跑本脚本")
    print("\n  提示：标签与元数据在 GitHub 仓库里（已随仓库克隆），"
          "**没有图像也能跑** analyze_ccd_indopacific.py（状况基线分析）。")


def gdown(fid, name):
    if not shutil.which("gdown") and subprocess.run(
            [sys.executable, "-c", "import gdown"], capture_output=True).returncode != 0:
        print("  安装 gdown …")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "gdown"], check=False)
    out = DEST / name
    if out.exists() and out.stat().st_size > 1024 * 1024:
        print(f"  ✅ 已存在，跳过：{name}  {out.stat().st_size/1024/1024:.1f} MB")
        return out
    print(f"  下载 {name} …")
    r = subprocess.run([sys.executable, "-m", "gdown", fid, "-O", str(out), "--no-cookies"],
                       cwd=str(DEST))
    if r.returncode != 0 or not out.exists():
        print(f"  ❌ 下载失败：{name}")
        return None
    print(f"  ✅ {name}  {out.stat().st_size/1024/1024:.1f} MB")
    return out


def unzip(path, subdir):
    if path.suffix.lower() != ".zip":
        print(f"  （{path.name} 不是 zip，需用 rar 工具解压到 {DEST/subdir}）")
        return
    target = DEST / subdir
    target.mkdir(parents=True, exist_ok=True)
    print(f"  解压 → {target} …")
    with zipfile.ZipFile(path) as z:
        z.extractall(target)
    imgs = sum(1 for _ in target.rglob("*.jpg"))
    print(f"  ✅ 解压完成，{imgs} 张 jpg")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--external", action="store_true", help="只下 80 MB 的印太外部测试集（推荐）")
    ap.add_argument("--dry", action="store_true", help="只下 3.27 GB 干季瓦片（微调用）")
    ap.add_argument("--wet", action="store_true", help="只下 1.33 GB 湿季图像（rar）")
    a = ap.parse_args()

    st, err = drive_reachable()
    print(f"Google Drive 连通性: {'✅ HTTP ' + str(st) if st else '❌ ' + str(err)}")
    if a.check:
        return 0 if st else 2
    if st is None:
        manual_help()
        return 2

    DEST.mkdir(parents=True, exist_ok=True)
    picks = [k for k in ("external", "dry", "wet") if getattr(a, k)]
    if not picks:
        if input("未指定 --external/--dry/--wet，将下载**全部 4.67 GB**，继续？[y/N] ").strip().lower() != "y":
            print("已取消。建议先跑：python dl_ccd_images.py --external")
            return 0
        picks = ["external", "dry", "wet"]

    for k in picks:
        fid, name, subdir = FILES[k]
        p = gdown(fid, name)
        if p:
            unzip(p, subdir)
    print("\n完成。下一步：")
    print("  评测印太域：python scripts/eval_bleaching_indopacific.py --source external")
    if "dry" in picks:
        print("  域自适应微调：python scripts/finetune_bleaching_indopacific.py --epochs 3 --workers 6")
    return 0


if __name__ == "__main__":
    sys.exit(main())
