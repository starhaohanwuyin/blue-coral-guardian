# -*- coding: utf-8 -*-
"""英文排版风险体检 —— 找出「切成英文后容易挤/错位/溢出」的位置。

判别：同一个位置中文很短、英文明显更长（>= 阈值倍）时，固定宽度的按钮/标签/卡片
最容易变形。输出「页面 + 元素 class + 中文 + 英文」，方便逐个加 .lang-en 适配规则。

用法：
    python tools/i18n_layout_risk.py            # 默认阈值 1.8
    python tools/i18n_layout_risk.py 2.5        # 只看更极端的
"""
import io
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PH = json.loads((ROOT / "tools" / "i18n_phrases.json").read_text(encoding="utf-8"))
NODE = re.compile(r"<([a-zA-Z-]+)([^>]*)>\{\{t\.(p[a-z0-9]+)\}\}</\1>")
CLS = re.compile('class="([^"]*)"')


def key_for(zh):
    """与 utils/i18n.js 的 phKey() 同一算法（FNV-1a / UTF-16 码元 → base36）。"""
    h = 0x811C9DC5
    data = zh.encode("utf-16-le")
    for i in range(0, len(data), 2):
        h ^= (data[i] | (data[i + 1] << 8))
        h = (h * 0x01000193) & 0xFFFFFFFF
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while h:
        out = digits[h % 36] + out
        h //= 36
    return "p" + (out or "0")


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ratio_min = float(sys.argv[1]) if len(sys.argv) > 1 else 1.8
    rev = {key_for(z): z for z in PH}
    rows = []
    for f in sorted(ROOT.glob("pages/*/*.wxml")):
        txt = f.read_text(encoding="utf-8")
        for m in NODE.finditer(txt):
            zh = rev.get(m.group(3))
            if not zh:
                continue
            en = PH[zh]
            if len(en) / max(1, len(zh)) >= ratio_min and len(zh) <= 14:
                c = CLS.search(m.group(2))
                rows.append((round(len(en) / max(1, len(zh)), 1), f.parent.name,
                             (c.group(1).strip() if c else "(no class)"), zh, en))
    rows.sort(reverse=True)
    print("英文长度 >= 中文 %.1f 倍的位置：%d 处" % (ratio_min, len(rows)))
    for r in rows:
        print("  x%-4s %-12s %-28s %s -> %s" % (r[0], r[1], r[2][:28], r[3], r[4][:40]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
