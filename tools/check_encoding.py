"""检查小程序源码的编码与行尾是否干净（防止"ANSI 往返改写"事故复发）。

背景：本会话曾用 PowerShell `Get-Content -Raw` → `Set-Content -Encoding UTF8`
改 pages/ai/ai.js，结果中文按系统 ANSI(936) 误解码、文件头多了 BOM、
`node --check` 直接语法错误，且一度提交。此脚本作为闸门：

检查项
  1. **BOM**：.js/.wxml/.wxss/.json 一律不应有 UTF-8 BOM
  2. **行尾混用**：同一文件不得既有 CRLF 又有 LF
  3. **可解码性**：必须能按 UTF-8 严格解码（否则就是被 ANSI 重编码过）

用法：
    python tools/check_encoding.py          # 检查（有问题退出码 1）
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTS = {".js", ".wxml", ".wxss", ".json", ".md"}
SKIP_DIRS = {".git", "node_modules", "miniprogram_npm"}

problems = []
checked = 0
for p in ROOT.rglob("*"):
    if p.is_dir() or p.suffix.lower() not in EXTS:
        continue
    if any(part in SKIP_DIRS for part in p.parts):
        continue
    checked += 1
    raw = p.read_bytes()
    rel = p.relative_to(ROOT)
    if raw[:3] == b"\xef\xbb\xbf":
        problems.append(f"{rel}: 含 UTF-8 BOM")
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as e:
        problems.append(f"{rel}: 不是合法 UTF-8（{e.reason} @ byte {e.start}）—— 疑似被 ANSI 重编码")
        continue
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    if crlf and lf:
        problems.append(f"{rel}: 行尾混用（CRLF {crlf} 行 / LF {lf} 行）")

print(f"已检查 {checked} 个文件")
if problems:
    print("\n❌ 编码/行尾问题：")
    for x in problems:
        print("  · " + x)
    print("\n修复建议：用 Python 的 read_text/write_text(encoding='utf-8') 重写该文件；"
          "不要用 PowerShell 的 Get-Content/Set-Content 往返改含中文的源码。")
    sys.exit(1)
print("✅ 编码与行尾均干净")
