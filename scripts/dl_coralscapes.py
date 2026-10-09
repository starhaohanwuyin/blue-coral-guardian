"""
稳健下载 Coralscapes 分片（curl 断点续传 + 重试）
================================================================
huggingface_hub 的 httpx 在镜像断连时无法续传（实测 400MB 文件只传了 633KB 就失败），
改用 curl -C - 续传，并在失败后自动重试直到文件完整。

用法：
    python dl_coralscapes.py --shards validation-00000-of-00001.parquet train-00000-of-00009.parquet
    python dl_coralscapes.py --all-train      # 全部 9 个训练分片
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DST = ROOT / "data" / "raw" / "coralscapes" / "data"
BASE = "https://hf-mirror.com/datasets/EPFL-ECEO/coralscapes/resolve/main/data"

# 已知文件大小（用于校验完整性），来自 HF tree API
EXPECTED = {
    "validation-00000-of-00001.parquet": 386_810_000,
    "train-00000-of-00009.parquet": 450_100_000,
    "train-00001-of-00009.parquet": 427_300_000,
    "train-00002-of-00009.parquet": 481_500_000,
    "train-00003-of-00009.parquet": 423_200_000,
    "train-00004-of-00009.parquet": 446_900_000,
    "train-00005-of-00009.parquet": 395_900_000,
    "train-00006-of-00009.parquet": 480_900_000,
    "train-00007-of-00009.parquet": 496_100_000,
    "train-00008-of-00009.parquet": 475_400_000,
    "test-00000-of-00003.parquet": 401_200_000,
}


def get_size(p: Path) -> int:
    return p.stat().st_size if p.exists() else 0


def download(name: str, max_rounds: int = 20) -> bool:
    DST.mkdir(parents=True, exist_ok=True)
    dst = DST / name
    expect = EXPECTED.get(name)
    for r in range(1, max_rounds + 1):
        cur = get_size(dst)
        if expect and cur >= expect * 0.995:
            print(f"  [完成] {name}  {cur/1024/1024:.1f} MB", flush=True)
            return True
        print(f"  [轮 {r}] {name}  当前 {cur/1024/1024:.1f} MB"
              + (f" / {expect/1024/1024:.1f} MB" if expect else ""), flush=True)
        cmd = ["curl.exe", "-L", "-C", "-", "--retry", "5", "--retry-delay", "2",
               "--retry-all-errors", "--connect-timeout", "20", "--max-time", "1800",
               "-s", "-o", str(dst), f"{BASE}/{name}"]
        rc = subprocess.run(cmd).returncode
        time.sleep(2)
    return get_size(dst) > 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shards", nargs="*", default=None)
    ap.add_argument("--all-train", action="store_true")
    args = ap.parse_args()

    if args.all_train:
        names = [f"train-{i:05d}-of-00009.parquet" for i in range(9)]
    elif args.shards:
        names = args.shards
    else:
        names = ["validation-00000-of-00001.parquet",
                 "train-00000-of-00009.parquet",
                 "train-00001-of-00009.parquet",
                 "train-00002-of-00009.parquet"]

    print(f"目标目录: {DST}")
    ok = 0
    for n in names:
        if download(n):
            ok += 1
    total = sum(f.stat().st_size for f in DST.glob("*.parquet"))
    print(f"\n完成 {ok}/{len(names)}  本地合计 {total/1024/1024/1024:.2f} GB")
    sys.exit(0 if ok == len(names) else 1)


if __name__ == "__main__":
    main()
