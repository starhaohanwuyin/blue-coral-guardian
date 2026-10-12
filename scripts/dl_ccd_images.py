"""下载 CoralConditionDataset 的水下图像（Google Drive 文件夹）。

背景：该数据集的**标签与元数据**在 GitHub（已入库分析，见 `analyze_ccd_indopacific.py`），
但**图像**放在 Google Drive 的 `coral_images.zip`。国内网络常无法直连 Drive，
所以本脚本先试 `gdown`（能处理 Drive 文件夹），失败时给出**手工下载指引**而不是报个看不懂的错。

用法：
    python dl_ccd_images.py                 # 尝试下载到 data/raw/CoralConditionDataset/images/
    python dl_ccd_images.py --check         # 只看能不能连上 Drive（不下载）
"""
import argparse
import pathlib
import shutil
import subprocess
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "raw" / "CoralConditionDataset" / "images"
DRIVE_FOLDER = "https://drive.google.com/drive/folders/1yjvVGSXuFRcO3b0SehyeAHzMtCHhI6S1"


def drive_reachable(timeout=20):
    try:
        with urllib.request.urlopen(urllib.request.Request(
                "https://drive.google.com/", headers={"User-Agent": "Mozilla/5.0"}), timeout=timeout) as r:
            return r.status, None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:80]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只测连通性")
    a = ap.parse_args()

    st, err = drive_reachable()
    print(f"Google Drive 连通性: {'✅ HTTP ' + str(st) if st else '❌ ' + str(err)}")
    if a.check:
        return 0

    if DEST.exists() and any(DEST.rglob("*.jpg")):
        n = len(list(DEST.rglob("*.jpg")))
        print(f"✅ 图像已存在：{n} 张（{DEST}）")
        return 0

    if st is None:
        print("\n❌ 当前网络无法访问 Google Drive，无法自动下载。请任选一种手工方式：\n")
        print(f"  ① 能上外网的机器/浏览器打开共享文件夹：{DRIVE_FOLDER}")
        print("     下载 coral_images.zip → 解压到：")
        print(f"     {DEST}")
        print("  ② 或用镜像/代理后重跑本脚本：python dl_ccd_images.py")
        print("  ③ 若队友能拿到该 zip，直接让他发给你（解压到上面同一路径即可）")
        print("\n提示：标签/元数据**已经可用**（不需要图像就能跑 analyze_ccd_indopacific.py）；")
        print("      只有「评我们模型在印太域的表现」和「域适配微调」才需要图像。")
        return 2

    gdown = shutil.which("gdown")
    if not gdown:
        print("\n⚠️ 未安装 gdown（处理 Drive 文件夹最省事）。先装：pip install gdown")
        print("   装好后重跑：python dl_ccd_images.py")
        return 3

    DEST.mkdir(parents=True, exist_ok=True)
    print(f"\n开始用 gdown 下载文件夹 → {DEST}")
    r = subprocess.run([gdown, "--folder", DRIVE_FOLDER, "-O", str(DEST), "--remaining-ok"],
                       cwd=str(ROOT))
    if r.returncode != 0:
        print("❌ gdown 下载失败（多为网络/配额限制）。请按上面的手工指引操作。")
        return r.returncode
    zips = list(DEST.rglob("*.zip"))
    for z in zips:
        print(f"解压 {z.name} …")
        shutil.unpack_archive(str(z), str(DEST))
    n = len(list(DEST.rglob("*.jpg")))
    print(f"✅ 完成：{n} 张图像在 {DEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
