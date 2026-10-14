# -*- coding: utf-8 -*-
"""中英文覆盖审计 —— 找出「切到英文后还是中文」的页面与文案。

判定口径：
  ① WXML 里写死的中文（文本节点 + placeholder/title 等属性）→ 需要改成 {{t.xxx}}
  ② JS 数据里的中文（页面内容来自数组）→ 需要英文块（mock.js 的 EN）
  ③ 是否已 require i18n（页面根本没接的话，切换语言不会有任何反应）

用法：
    python tools/i18n_audit.py                 # 汇总表
    python tools/i18n_audit.py --dump adopt    # 打印某页写死的中文清单
    python tools/i18n_audit.py --json out.json # 导出结果
"""
import argparse
import io
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent          # miniprogram/
CJK = re.compile("[\u4e00-\u9fff]")
# 注意：不要直接写 HTML 注释字面量，用拼接躲开补丁工具对 "<!--" 的解析
COMMENT = re.compile("<" + "!--.*?--" + ">", re.S)
MUSTACHE = re.compile(r"\{\{.*?\}\}", re.S)
ATTR = re.compile(r'\s(?:placeholder|title|aria-label|label)="([^"]*)"')
STRING = re.compile(r"'([^'\\\n]*)'")


def load_dict():
    """收集 i18n.js 的 DICT 里出现过的中文，作为「已翻译」白名单。"""
    src = (ROOT / "utils" / "i18n.js").read_text(encoding="utf-8")
    body = src.split("const DICT = {", 1)[-1].split("\n}", 1)[0]
    return set(STRING.findall(body))


def wxml_literals(text):
    """WXML 中写死的中文（文本节点 + 指定属性），忽略注释与 {{}} 表达式。"""
    out = []
    clean = COMMENT.sub("", text)
    for line_no, line in enumerate(clean.splitlines(), 1):
        stripped = MUSTACHE.sub("", line)
        for m in ATTR.finditer(stripped):
            if CJK.search(m.group(1)):
                out.append((line_no, m.group(1).strip()))
        chunk = re.sub(r"<[^>]*>", "\x00", stripped)
        for piece in chunk.split("\x00"):
            piece = piece.strip()
            if piece and CJK.search(piece):
                out.append((line_no, piece))
    return out


def js_literals(text):
    return [s for s in STRING.findall(text) if CJK.search(s) and len(s) > 1]


def audit():
    known = load_dict()
    pages = json.loads((ROOT / "app.json").read_text(encoding="utf-8"))["pages"]
    rows = []
    for p in pages:
        d = ROOT / pathlib.Path(p).parent
        w = next(d.glob("*.wxml")).read_text(encoding="utf-8")
        j = next(d.glob("*.js")).read_text(encoding="utf-8")
        wl = wxml_literals(w)
        jl = js_literals(j)
        rows.append({
            "page": p,
            "wxml": len(wl),
            "wxml_new": sum(1 for _, s in wl if s not in known),
            "js": len(jl),
            "js_new": len([s for s in jl if s not in known]),
            "uses_i18n": "i18n" in j,
            "literals": wl,
        })
    return rows


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="中英文覆盖审计")
    ap.add_argument("--dump", default="", help="打印某页写死的中文")
    ap.add_argument("--json", dest="json_out", default="", help="导出完整结果")
    a = ap.parse_args()
    rows = audit()
    if a.json_out:
        out = [{k: v for k, v in r.items() if k != "literals"} for r in rows]
        pathlib.Path(a.json_out).write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print("已导出 " + a.json_out)
    if a.dump:
        for r in [x for x in rows if a.dump in x["page"]]:
            print("=== " + r["page"] + " ===")
            for line_no, s in r["literals"]:
                print("  %4d  %s" % (line_no, s))
        return 0
    tw = sum(r["wxml"] for r in rows)
    tn = sum(r["wxml_new"] for r in rows)
    print("页面 %d 个 · 写死中文(WXML) %d 处，DICT 里没有的 %d 处" % (len(rows), tw, tn))
    print("%-34s %5s %5s %5s %5s %s" % ("page", "wxml", "新", "js", "js新", "接i18n"))
    for r in sorted(rows, key=lambda x: -x["wxml_new"]):
        print("%-34s %5d %5d %5d %5d %s" % (r["page"], r["wxml"], r["wxml_new"],
                                            r["js"], r["js_new"],
                                            "Y" if r["uses_i18n"] else "-"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
