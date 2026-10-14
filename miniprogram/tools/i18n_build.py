# -*- coding: utf-8 -*-
"""中英双语构建器 —— 一份短语表，自动铺到 WXML 与运行时。

源文件：tools/i18n_phrases.json   {"中文": "English", ...}（人工维护，唯一真源）
产物：
  ① utils/i18n-phrases.js   运行时的「整串翻译表」（内容类文案靠它：文章正文、题目、商品名…）
  ② 各页 *.wxml             精确匹配的中文文本节点/属性 → {{t.p<hash>}}

WXML 里的词条名是**中文串的哈希**（FNV-1a / UTF-16 码元，与 utils/i18n.js 里的
autoDict() 用同一套算法），所以短语表增删不会让已有引用错位。

用法：
    python tools/i18n_build.py            # 生成 + 重写
    python tools/i18n_build.py --check    # 只报告还有多少没覆盖（不写文件）
    python tools/i18n_build.py --unmatched   # 列出匹配不到的（含混合插值的句子，需手工改）
"""
import argparse
import io
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent          # miniprogram/
PHRASES = pathlib.Path(__file__).resolve().parent / "i18n_phrases.json"
I18N = ROOT / "utils" / "i18n.js"
PH_JS = ROOT / "utils" / "i18n-phrases.js"
CJK = re.compile("[\u4e00-\u9fff]")
TEXT_NODE = re.compile(r">([^<>{}]+)<")
ATTR_VAL = re.compile(r'(placeholder|title|aria-label)="([^"{}]*)"')
COMMENT = re.compile("<" + "!--.*?--" + ">", re.S)


def load_phrases():
    return json.loads(PHRASES.read_text(encoding="utf-8"))


def page_files():
    app = json.loads((ROOT / "app.json").read_text(encoding="utf-8"))
    files = []
    for p in app.get("pages", []):
        d = ROOT / pathlib.Path(p).parent
        files += sorted(d.glob("*.wxml"))
    for extra in ("custom-tab-bar",):
        d = ROOT / extra
        if d.exists():
            files += sorted(d.glob("*.wxml"))
    return files


def key_for(zh):
    """与运行时 autoDict() 一致的词条名：FNV-1a over UTF-16 code units → base36。"""
    h = 0x811C9DC5
    data = zh.encode("utf-16-le")
    for i in range(0, len(data), 2):
        unit = data[i] | (data[i + 1] << 8)
        h ^= unit
        h = (h * 0x01000193) & 0xFFFFFFFF
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    n = h
    while n:
        out = digits[n % 36] + out
        n //= 36
    return "p" + (out or "0")


def build_phrases_js(phrases):
    lines = ["/**",
             " * 中文 → 英文（整串精确匹配）。自动生成，请勿手改：",
             " * 源文件 tools/i18n_phrases.json，改动后跑 python tools/i18n_build.py",
             " */",
             "module.exports = {"]
    for zh in sorted(phrases):
        lines.append("  %s: %s," % (json.dumps(zh, ensure_ascii=False),
                                    json.dumps(phrases[zh], ensure_ascii=False)))
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def build_mapping(phrases):
    return {zh: key_for(zh) for zh in phrases}


def rewrite_wxml(files, mapping, check_only=False, collect_unmatched=None):
    changed = []
    for f in files:
        text = f.read_text(encoding="utf-8")

        def rep_text(m):
            inner = m.group(1)
            s = inner.strip()
            k = mapping.get(s)
            if not k:
                # 跨行的文本节点：把内部空白折叠成单空格再查一次（短语表按折叠后的写法维护）
                norm = re.sub(r"\s+", " ", s)
                if norm != s:
                    k = mapping.get(norm)
                    s = norm
            if not k:
                if collect_unmatched is not None and s and CJK.search(s):
                    collect_unmatched.append((str(f.relative_to(ROOT)), s))
                return m.group(0)
            lead = inner[:len(inner) - len(inner.lstrip())]
            tail = inner[len(inner.rstrip()):]
            return ">" + lead + "{{t." + k + "}}" + tail + "<"

        def rep_attr(m):
            name, val = m.group(1), m.group(2)
            k = mapping.get(val.strip())
            if not k:
                return m.group(0)
            return name + '="{{t.' + k + '}}"'

        new = ATTR_VAL.sub(rep_attr, TEXT_NODE.sub(rep_text, text))
        if not check_only and new != text:
            f.write_text(new, encoding="utf-8")
            changed.append(str(f.relative_to(ROOT)))
    return changed


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="中英双语构建器")
    ap.add_argument("--check", action="store_true", help="只报告，不写文件")
    ap.add_argument("--unmatched", action="store_true", help="列出匹配不到的文案")
    a = ap.parse_args()
    phrases = load_phrases()
    mapping = build_mapping(phrases)
    if not a.check:
        PH_JS.write_text(build_phrases_js(phrases), encoding="utf-8")
    unmatched = []
    files = page_files()
    changed = rewrite_wxml(files, mapping, check_only=a.check,
                           collect_unmatched=unmatched if a.unmatched else None)
    print("短语表 %d 条 · WXML %d 个文件%s" % (
        len(phrases), len(files), "（--check 未写文件）" if a.check else ""))
    if changed:
        print("已重写: " + ", ".join(changed))
    if a.unmatched and unmatched:
        print("匹配不到的 %d 处（多为含 {{}} 插值的句子，需手工改）:" % len(unmatched))
        for f, s in unmatched[:80]:
            print("  %-46s %s" % (f, s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
