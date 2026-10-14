"""检查并修复 WXML 数据绑定的花括号问题。

背景（真实事故）：pages/ai/ai.wxml 的「环境数据」「综合研判」两张卡片把绑定写成了
`wx:if="{view.climate}"`、`{view.climate.baaLabel}` 这种**单花括号**，
小程序要求 `{{ }}`。单括号会被当作**字面文本**：
  · 页面上原样显示 `{view.climate.baaLabel}`
  · `style="width: {view.restoration.recovery}%"` 宽度失效
  · `wx:if` 拿到非空字符串 → 恒为真，卡片永远显示

覆盖三类问题：
  A. `{expr}`    —— 两侧都不是双花括号（最常见的整片写错）
  B. `{expr}}`   —— 缺一个**开**括号
  C. `{{expr}`   —— 缺一个**闭**括号

用法：
    python tools/fix_wxml_braces.py            # 只报告（有问题退出码 1，可当闸门）
    python tools/fix_wxml_braces.py --apply    # 实际修复（UTF-8 无 BOM 写回）
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # 仓库根（脚本在 tools/ 下）

# A. 单花括号：两侧都不成对
PAT_A = re.compile(r"(?<!\{)\{([A-Za-z_][^{}\n]*)\}(?!\})")
# B. 缺开括号：{expr}}  （第一个 { 后面不是 {，表达式后跟 }}
PAT_B = re.compile(r"(?<!\{)\{(?!\{)([A-Za-z_][^{}\n]*)\}\}")
# C. 缺闭括号：{{expr}  （{{ 开头，单个 } 结尾）
PAT_C = re.compile(r"\{\{([A-Za-z_][^{}\n]*)\}(?!\})")

KINDS = [(PAT_A, "单花括号（两侧都缺）"), (PAT_B, "缺一个开括号"), (PAT_C, "缺一个闭括号")]


def strip_comments(txt):
    """把 <!-- ... --> 注释内容替换成等长空白（保留换行与偏移量）。

    为什么必须跳过注释：注释里写接口样例（如 `GET /corals/{id}`）会被当成"单花括号"
    误报，闸门因此长期飘红，真问题反而被淹没。
    """
    def repl(m):
        body = m.group(0)
        return "".join("\n" if c == "\n" else " " for c in body)
    return re.sub(r"<!--.*?-->", repl, txt, flags=re.S)


def scan(path):
    """返回 [(行号, 片段, 类型)]，按行号排序去重。"""
    txt = path.read_text(encoding="utf-8")
    scan_txt = strip_comments(txt)
    hits = []
    for pat, kind in KINDS:
        for m in pat.finditer(scan_txt):
            line = scan_txt.count("\n", 0, m.start()) + 1
            hits.append((line, m.group(0), kind))
    # 同一处可能被多个模式命中，按 (行号, 片段) 去重
    uniq = sorted(set(hits))
    return txt, uniq


def fix(txt):
    for pat, _ in KINDS:
        txt = pat.sub(lambda m: "{{" + m.group(1) + "}}", txt)
    return txt


def main():
    apply = "--apply" in sys.argv
    files = sorted(ROOT.glob("pages/**/*.wxml")) + sorted(ROOT.glob("components/**/*.wxml"))
    total = 0
    for f in files:
        txt, hits = scan(f)
        if not hits:
            continue
        print(f"\n{f.relative_to(ROOT)}：发现 {len(hits)} 处")
        for line, frag, kind in hits[:10]:
            print(f"   L{line} [{kind}]: {frag}")
        if len(hits) > 10:
            print(f"   … 其余 {len(hits) - 10} 处")
        total += len(hits)
        if apply:
            fixed = fix(txt)
            f.write_bytes(fixed.encode("utf-8"))    # UTF-8、无 BOM
            print(f"   → 已修复，剩余 {len(scan(f)[1])} 处")

    # 配平自检：{{ 与 }} 数量必须相等
    for f in files:
        t = f.read_text(encoding="utf-8")
        o, c = t.count("{{"), t.count("}}")
        if o != c:
            print(f"\n⚠️ {f.relative_to(ROOT)} 花括号不配平：'{{{{'={o}  '}}}}'={c}")

    print(f"\n合计 {total} 处")
    if not apply and total:
        print("加 --apply 才会真正修改")
        sys.exit(1)
    if not total:
        print("✅ 未发现花括号绑定问题")


if __name__ == "__main__":
    main()
