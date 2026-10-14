# -*- coding: utf-8 -*-
"""把「页面级中英文」接到每个还没接的页面（幂等，可重复跑）。

做的事（每个页面 JS 两处）：
  1) 加一行 require：const pageI18n = require('../../utils/page-i18n.js')
  2) Page({ ... })  →  Page(pageI18n.wrap({ ... }))
包上之后：页面自动拿到整本词条 t（WXML 的 {{t.xxx}} 直接可用）、
setData 的数据按短语表翻译、语言切换后 onShow 自动重渲染。

用法：
    python tools/i18n_wire.py            # 接线（跳过已接的）
    python tools/i18n_wire.py --check    # 只列出还没接的
"""
import argparse
import io
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REQUIRE = "const pageI18n = require('../../utils/page-i18n.js')"


def page_js_files():
    app = json.loads((ROOT / "app.json").read_text(encoding="utf-8"))
    out = []
    for p in app.get("pages", []):
        d = ROOT / pathlib.Path(p).parent
        out += sorted(d.glob("*.js"))
    cb = ROOT / "custom-tab-bar" / "index.js"
    if cb.exists():
        out.append(cb)
    return out


def wire(f, check_only=False):
    src = f.read_text(encoding="utf-8")
    if "page-i18n" in src:
        return "已接"
    if "Page(" not in src:
        return "无 Page()"
    close = src.rindex("})")
    new = src[:close] + "}))" + src[close + 2:]
    new = new.replace("Page({", "Page(pageI18n.wrap({", 1)
    # require 放在 Page( 之前
    idx = new.index("Page(pageI18n.wrap({")
    new = new[:idx] + REQUIRE + "\n\n" + new[idx:]
    if check_only:
        return "待接"
    f.write_text(new, encoding="utf-8")
    return "已接(新)"


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="给页面接上中英文")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    todo = []
    for f in page_js_files():
        st = wire(f, check_only=a.check)
        rel = str(f.relative_to(ROOT))
        if st in ("待接", "已接(新)"):
            todo.append(rel)
        print("%-46s %s" % (rel, st))
    print("\n%s %d 个页面" % ("待接" if a.check else "本次接线", len(todo)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
