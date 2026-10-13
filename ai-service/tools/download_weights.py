"""首次运行前执行：从 GitHub Release 下载模型权重（约 470 MB）到正确位置。

为什么不在 Git 仓库里：模型权重单文件 106 MB，超过 GitHub 的 100 MB 单文件限制；
放在 Release 附件里（免费、单文件上限 2 GB），用脚本一键取回。

用法：
    cd ai-service
    python tools/download_weights.py            # 从 GitHub Release 下载缺失的权重
    python tools/download_weights.py --check    # 只检查，不下载
    python tools/download_weights.py --force    # 重新下载
    python tools/download_weights.py --from-dir D:\\path\\to\\去交付包\\weights
                                                # 离线：直接从交付包/已有 weights 目录拷贝
"""
import argparse
import pathlib
import shutil
import sys
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent          # ai-service/
WEIGHTS = ROOT / "weights"
REPO = "starhaohanwuyin/blue-coral-guardian"
TAG = "v1.0-models"
BASE = f"https://github.com/{REPO}/releases/download/{TAG}"

# 资产名 -> 解压/存放目标（相对 ai-service/）
ASSETS = [
    ("segformer_coralscapes.zip", "weights/segformer_coralscapes", "zip"),
    ("species_ip_best.pt", "weights/species_ip/best.pt", "file"),
    ("bleaching_all_best.pt", "weights/bleaching_all/best.pt", "file"),
    ("bleaching_all_multidomain2_best.pt", "weights/bleaching_all_multidomain2/best.pt", "file"),
    ("yolo_coral_best.pt", "weights/yolo_coral/best.pt", "file"),
]


def size_of(rel: str) -> int:
    p = ROOT / rel
    if p.is_dir():
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    return p.stat().st_size if p.exists() else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--from-dir", default="", help="离线：从已有的 weights 目录（如交付包）拷贝")
    a = ap.parse_args()

    print("=" * 68)
    print("  蓝珊·珊瑚卫士 —— 模型权重准备")
    print("=" * 68)

    # 离线模式：直接从本地 weights 目录拷贝（网络慢/无网时用）
    if a.from_dir:
        src = pathlib.Path(a.from_dir)
        if not src.exists():
            print(f"  ❌ 目录不存在：{src}")
            return 1
        print(f"  离线拷贝源：{src}\n")
        for rel_src, rel_dst in [("segformer_coralscapes", "weights/segformer_coralscapes"),
                                 ("species_ip", "weights/species_ip"),
                                 ("bleaching_all", "weights/bleaching_all"),
                                 ("bleaching_all_multidomain2", "weights/bleaching_all_multidomain2"),
                                 ("yolo_coral", "weights/yolo_coral")]:
            s, d = src / rel_src, ROOT / rel_dst
            if not s.exists():
                print(f"  ⚠️  源缺 {rel_src}")
                continue
            d.parent.mkdir(parents=True, exist_ok=True)
            if d.exists():
                shutil.rmtree(d)
            shutil.copytree(s, d)
            print(f"  ✅ {rel_dst}")
        print("\n完成（离线拷贝）。运行 tools/selfcheck.py 复核。")
        return 0

    missing = []
    for name, rel, kind in ASSETS:
        s = size_of(rel)
        got = (s > (1_000_000 if kind == "zip" else 10_000_000))
        if kind == "file" and not (ROOT / rel).exists():
            got = False
        print(f"  {'✅' if got else '❌'} {rel:<52} {s/1024/1024:6.1f} MB")
        if not got:
            missing.append((name, rel, kind))

    if a.check:
        print(f"\n{'全部就绪，可以直接演示' if not missing else f'缺 {len(missing)} 项，运行：python tools/download_weights.py'}")
        return 0 if not missing else 1
    if not missing:
        print("\n全部已就绪，无需下载。")
        return 0

    print(f"\n需要下载 {len(missing)} 个文件（约 470 MB）…")
    for name, rel, kind in missing:
        url = f"{BASE}/{name}"
        tmp = WEIGHTS / name
        tmp.parent.mkdir(parents=True, exist_ok=True)
        try:
            print(f"\n→ {name}")
            with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                done = 0
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        pct = done * 100 // total
                        print(f"\r   {pct:3d}%  {done/1024/1024:6.1f}/{total/1024/1024:.1f} MB", end="")
            print()
            if kind == "zip":
                dest = ROOT / rel
                dest.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(tmp) as z:
                    z.extractall(dest)
                tmp.unlink()
                print(f"   ✅ 已解压到 {rel}")
            else:
                dest = ROOT / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    dest.unlink()
                tmp.replace(dest)
                print(f"   ✅ 已放到 {rel}")
        except Exception as e:
            print(f"\n   ❌ 失败：{type(e).__name__}: {e}")
            print(f"      可手动下载：{url}")
            print(f"      下载后放到：{ROOT / rel}")
    print("\n完成。若仍有 ❌，可手动从 Release 页面下载：")
    print(f"   https://github.com/{REPO}/releases/tag/{TAG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
