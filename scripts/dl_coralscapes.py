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

# ⚠️ 已修的 bug：原表数值比**真实字节数低约 4.9%**（疑似把 Windows 显示的 MiB 当字节记了），
#    于是「大小 ≥ 预期×0.995」这条判据会把**只下到 ~95% 的残片当成完整**。
#    现在：① 已知文件填**真实字节数**；② 真正的完整性判据改为**读 parquet footer**
#    （见 parquet_ok()），大小只当快速早筛。
#    末尾三个 test 分片未下载过，故不填（由 footer 判据兜底）。
EXPECTED = {
    "validation-00000-of-00001.parquet": 405_616_835,
    "train-00000-of-00009.parquet": 471_962_413,
    "train-00001-of-00009.parquet": 448_022_029,
    "train-00002-of-00009.parquet": 504_852_201,
    "train-00003-of-00009.parquet": 443_807_216,
    "train-00004-of-00009.parquet": 468_562_974,
    "train-00005-of-00009.parquet": 415_150_694,
    "train-00006-of-00009.parquet": 504_281_776,
    "train-00007-of-00009.parquet": 520_213_271,
    "train-00008-of-00009.parquet": 498_469_209,
    "test-00000-of-00003.parquet": 401_200_000,
}


def parquet_ok(p: Path) -> bool:
    """结构完整性判据：parquet footer 可读且行数 > 0。

    文件被截断时尾部 magic 必然缺失，pyarrow 会直接报错 —— 这是比"看大小"可靠得多的判据。
    """
    try:
        import pyarrow.parquet as pq
        return pq.ParquetFile(str(p)).metadata.num_rows > 0
    except Exception:
        return False


def get_size(p: Path) -> int:
    return p.stat().st_size if p.exists() else 0


def download(name: str, max_rounds: int = 20, max_time: int = 600) -> bool:
    """max_time：单轮 curl 上限（秒）。原为 1800，实测镜像会「先给 1–4MB/s、
    随后掉到 200KB/s 并长时间不推进」，30 分钟的单轮上限会把重试拖死；
    缩短到 10 分钟后由 `-C -` 续传，整体更快也更稳。"""
    DST.mkdir(parents=True, exist_ok=True)
    dst = DST / name
    expect = EXPECTED.get(name)
    for r in range(1, max_rounds + 1):
        cur = get_size(dst)
        if cur and parquet_ok(dst):          # 结构完整才算完成（不看大小）
            print(f"  [完成] {name}  {cur/1024/1024:.1f} MB", flush=True)
            return True
        print(f"  [轮 {r}] {name}  当前 {cur/1024/1024:.1f} MB"
              + (f" / {expect/1024/1024:.1f} MB" if expect else ""), flush=True)
        cmd = ["curl.exe", "-L", "-C", "-", "--retry", "5", "--retry-delay", "2",
               "--retry-all-errors", "--connect-timeout", "20", "--max-time", str(max_time),
               "-s", "-o", str(dst), f"{BASE}/{name}"]
        rc = subprocess.run(cmd).returncode
        time.sleep(2)
    ok = parquet_ok(dst)
    if not ok:
        print(f"  [未完成] {name} 仍无法读取 parquet footer（{get_size(dst)/1024/1024:.1f} MB）")
    return ok


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
