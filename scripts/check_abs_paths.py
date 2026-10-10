"""可移植性闸门：扫描被 git 跟踪的文件里是否残留**主机绝对路径**。

为什么需要：报告 JSON 与脚本里一旦写死 `D:\\大学作业\\...\\coral_ml\\...`，
换台机器/换目录就失效，还会把本机目录结构带进公开仓库（本人不小心踩过：
16 个报告 JSON、3 个脚本）。

用法：
    python check_abs_paths.py        # 有残留则退出码 1（文档里作为示例的路径可用 --allow-docs 放行）
"""
import argparse
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
# 主机绝对路径：Windows 盘符 或 Unix 家目录
PAT = re.compile(r"(?:[A-Za-z]:[\\/](?:大学作业|Users|用户)[^\s\"',)]{0,120}"
                 r"|/(?:Users|home)/[^\s\"',)]{0,120})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-docs", action="store_true",
                    help="文档里的示例路径不算问题（推荐：真交付物里不允许）")
    args = ap.parse_args()

    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    hits = []
    for f in files:
        if args.allow_docs and (f.startswith("docs/") or f.endswith(".md")):
            continue
        p = ROOT / f
        if not p.exists() or p.stat().st_size > 5_000_000:
            continue
        try:
            t = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for m in PAT.finditer(t):
            line = t.count("\n", 0, m.start()) + 1
            hits.append((f, line, m.group(0)[:100]))

    print(f"已扫描 {len(files)} 个被跟踪文件，命中主机绝对路径 {len(hits)} 处"
          + ("（已放行文档）" if args.allow_docs else ""))
    for f, line, frag in hits[:40]:
        print(f"  · {f}:{line}  {frag}")
    if len(hits) > 40:
        print(f"  … 其余 {len(hits) - 40} 处")
    if hits:
        print("\n修复：改用 os.environ.get(..., 默认值) 或按 __file__ 推导仓库相对路径；"
              "报告 JSON 用脚本内的 rel() 落盘。")
        return 1
    print("✅ 未发现主机绝对路径")
    return 0


if __name__ == "__main__":
    sys.exit(main())
