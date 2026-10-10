"""修复 WXML 里的单花括号数据绑定（应为双花括号）。

背景：pages/ai/ai.wxml 的「环境数据」「综合研判」两张卡片把绑定写成了
`wx:if="{view.climate}"`、`{view.climate.baaLabel}` 这种**单花括号**，
小程序要求 `{{ }}`。单括号会被当作**字面文本**：
  · 页面上原样显示 `{view.climate.baaLabel}`
  · `style="width: {view.restoration.recovery}%"` 宽度失效
  · `wx:if` 拿到非空字符串 → 恒为真，卡片永远显示

用法：
    python fix_wxml_braces.py            # 只报告（dry-run）
    python fix_wxml_braces.py --apply    # 实际修改（UTF-8 写入，不加 BOM）
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # 仓库根（脚本在 tools/ 下）
# 单花括号绑定：{ 后面紧跟标识符，且整体不是 {{...}}
PAT = re.compile(r"(?<!\{)\{([A-Za-z_][^}\n]*)\}(?!\})")


def scan(path):
    txt = path.read_text(encoding="utf-8")
    out = []
    for m in PAT.finditer(txt):
        line = txt.count("\n", 0, m.start()) + 1
        out.append((line, m.group(0)))
    return txt, out


def main():
    apply = "--apply" in sys.argv
    files = sorted(ROOT.glob("pages/**/*.wxml")) + sorted(ROOT.glob("components/**/*.wxml"))
    total = 0
    for f in files:
        txt, hits = scan(f)
        if not hits:
            continue
        rel = f.relative_to(ROOT)
        print(f"\n{rel}：发现 {len(hits)} 处单花括号绑定")
        for line, frag in hits[:8]:
            print(f"   L{line}: {frag}")
        if len(hits) > 8:
            print(f"   … 其余 {len(hits) - 8} 处")
        total += len(hits)
        if apply:
            fixed = PAT.sub(lambda m: "{{" + m.group(1) + "}}", txt)
            # 保留原行尾风格（全 LF 或全 CRLF），并以 UTF-8 无 BOM 写回
            f.write_bytes(fixed.encode("utf-8"))
            after = PAT.findall(fixed)
            print(f"   → 已修复，剩余单花括号 {len(after)} 处")
    print(f"\n合计 {total} 处")
    if not apply and total:
        print("加 --apply 才会真正修改")


if __name__ == "__main__":
    main()
