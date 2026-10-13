"""【已废弃 · 保留仅作历史参考】把小程序的 WXML/WXSS 机械转换为网页可用的 JS 模板与 CSS。

⚠️ 本脚本是早期尝试（逐页代码生成），因花括号记账难以维护而被取代。
   现在请使用 tools/build_web_pages.py（解析成模板树 + 运行时求值渲染），
   它才是 web/mp/ 产物的生成器。本文件保留是为了记录演进过程，不要再用。


设计要点（务实优先，转换后再手工修个别页面）：
  · WXML  →  JS 模板字符串（`…${expr}…`），支持 wx:for / wx:if / elif / else / block
  · WXSS  →  CSS，rpx → calc(N * var(--rpx))，view/text/image 等标签选择器一并替换
  · 事件  bindtap/catchtap → data-tap，由页面模块统一代理到页面方法
局限（转换后需人工核对）：
  · WXML 里的 wxs/自定义组件、slot、复杂 picker 需手工处理
  · 小程序 api（wx.*）不能直接搬，页面模块里另行适配

用法：
    python tools/wxml2html.py --page index            # 转换单页，打印结果到 stdout
    python tools/wxml2html.py --all --out ../web/pages  # 全量转换
"""
import argparse
import pathlib
import re
import sys

BC = pathlib.Path(r"D:\大学作业\广东海洋大学的珊瑚评测小程序\blue_coral")
TAG_MAP = {
    "view": "div", "text": "span", "image": "img", "scroll-view": "div",
    "swiper": "div", "swiper-item": "div", "navigator": "a", "block": None,  # None = 只做控制流，不输出标签
    "button": "button", "input": "input", "textarea": "textarea",
    "progress": "progress", "rich-text": "div", "cover-view": "div", "cover-image": "img",
    "movable-area": "div", "movable-view": "div", "video": "video", "canvas": "canvas",
    "picker": "div", "switch": "div", "checkbox": "div", "radio": "div", "label": "label",
    "form": "form", "icon": "span", "official-account": "div", "open-data": "div",
    "web-view": "iframe", "slot": "div", "camera": "div",
}
VOID = {"img", "input", "br", "hr"}

ATTR_MAP = {
    "bindtap": "data-tap", "catchtap": "data-tap", "bind:tap": "data-tap",
    "bindlongpress": "data-longpress", "catchlongpress": "data-longpress",
    "bindinput": "data-input", "bindchange": "data-change", "bindconfirm": "data-confirm",
    "bindsubmit": "data-submit", "bindscrolltolower": "data-scrolltolower",
    "bindscroll": "data-scroll", "bindload": "data-load", "binderror": "data-error",
    "bindblur": "data-blur", "bindfocus": "data-focus", "bindanimationfinish": "data-animfinish",
    "bindplay": "data-play", "bindpause": "data-pause", "bindended": "data-ended",
    "data-": "data-", "src": "src", "mode": "data-mode", "placeholder": "placeholder",
    "value": "value", "maxlength": "maxlength", "type": "type", "disabled": "disabled",
    "hidden": "hidden", "id": "id", "style": "style",
}


def split_tags(wxml: str):
    """把 WXML 拆成 [('open'|'close'|'text', ...)] 流；对含 & < 的属性值容错。"""
    out, i, n = [], 0, len(wxml)
    while i < n:
        if wxml[i] == "<":
            m = re.match(r"<!--.*?-->", wxml[i:], re.S)
            if m:
                i += m.end(); continue
            m = re.match(r"<\s*(/?)\s*([\w:-]+)((?:\"[^\"]*\"|'[^']*'|[^>\"'])*?)(/?)\s*>", wxml[i:], re.S)
            if m:
                closing, name, attrs, selfclose = m.group(1), m.group(2), m.group(3), m.group(4)
                out.append(("close" if closing else "open", name, attrs, bool(selfclose)))
                i += m.end(); continue
        j = wxml.find("<", i)
        if j < 0:
            out.append(("text", wxml[i:])); break
        if j > i:
            out.append(("text", wxml[i:j]))
        i = j
    return out


def to_js_expr(expr: str) -> str:
    """{{a.b}} -> ${a.b}；顺带把小程序的写法转换成 JS。"""
    e = expr.strip()
    e = re.sub(r"\bwx:if\b", "", e)
    return e


def interp(text: str) -> str:
    """文本里的 {{ }} 转成 ${ }（用于 JS 模板字符串）。"""
    return re.sub(r"\{\{(.*?)\}\}", lambda m: "${" + to_js_expr(m.group(1)) + "}", text, flags=re.S)


def parse_attrs(attrs: str):
    out = {}
    for m in re.finditer(r"([:\w.-]+)\s*=\s*\"([^\"]*)\"", attrs or ""):
        out[m.group(1)] = m.group(2)
    if "disabled" in (attrs or ""):
        out.setdefault("disabled", "true")
    return out


def render_node(node, depth, ctx_names):
    """递归把一个 WXML 节点转成 JS 代码片段（模板字符串拼接）。"""
    kind = node[0]
    if kind == "text":
        t = node[1]
        if not t.strip():
            return [repr(t)] if t else []
        return ["`" + interp(t).replace("`", "\\`") + "`"]
    _, name, attrs, selfclose = node
    a = parse_attrs(attrs)

    # 控制流
    stmts = []
    if "wx:if" in a:
        stmts.append(("if", to_js_expr(a["wx:if"].strip("{} "))))
    if "wx:elif" in a:
        stmts.append(("elif", to_js_expr(a["wx:elif"].strip("{} "))))
    if "wx:else" in a:
        stmts.append(("else", None))
    loop = None
    if "wx:for" in a:
        arr = to_js_expr(a["wx:for"].strip("{} "))
        item = a.get("wx:for-item", "item")
        idx = a.get("wx:for-index", "index")
        loop = (arr, item, idx)
    return stmts, loop, name, a, selfclose


def convert(wxml: str) -> str:
    """把 WXML 转成一段 JS 表达式（返回 HTML 字符串的模板字面量拼接）。"""
    tokens = split_tags(wxml)
    out = []
    stack = []          # (tag, loop_vars)
    ctx_names = []
    indent = 0

    def pad():
        return "  " * indent

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok[0] == "text":
            if tok[1].strip():
                out.append(pad() + 'html += `' + interp(tok[1]).replace("`", "\\`") + '`;')
            i += 1
            continue
        if tok[0] == "close":
            # 找到匹配的开标签，处理收尾
            if stack:
                tag, loops, had_tag = stack.pop()
                if loops:
                    for _ in loops:
                        indent -= 2
                        out.append(pad() + "}")
                if had_tag:
                    indent -= 1
                for st in (stack[-1][3] if stack and len(stack[-1]) > 3 else []):
                    pass
            i += 1
            continue

        _, name, attrs, selfclose = tok
        stmts, loop, tagname, a, sc = render_node(tok, indent, ctx_names)
        # 控制流开始
        for kind, cond in stmts:
            if kind == "if":
                out.append(pad() + f"if ({cond}) {{"); indent += 1
            elif kind == "elif":
                indent -= 1; out.append(pad() + f"}} else if ({cond}) {{"); indent += 1
            elif kind == "else":
                indent -= 1; out.append(pad() + "} else {"); indent += 1
        cond_started = bool(stmts)

        loop_vars = []
        if loop:
            arr, item, idx = loop
            out.append(pad() + f"for (let {idx} = 0; {idx} < ({arr} || []).length; {idx}++) {{")
            out.append(pad() + f"  const {item} = ({arr})[{idx}];")
            indent += 1
            loop_vars.append(item)

        html_tag = TAG_MAP.get(tagname, tagname)
        had_tag = html_tag is not None
        if had_tag:
            parts = [f"<{html_tag}"]
            cls = a.get("class")
            if cls:
                parts.append(f' class="{interp(cls).replace("`", "")}"' if "{{" in cls else f' class="{cls}"')
            style = a.get("style")
            if style:
                parts.append(f' style="{style}"' if "{{" not in style else f' style="{interp(style)[2:-1]}"')
            for k, v in a.items():
                if k in ("class", "style", "wx:if", "wx:elif", "wx:else", "wx:for", "wx:for-item",
                         "wx:for-index", "wx:key", "mode"):
                    continue
                nk = ATTR_MAP.get(k, None)
                if nk and v and not v.startswith("{{") and k not in ("bindtap",) or (nk and v.startswith("{{")):
                    pass
                # 事件：bindtap="fn" -> data-tap="fn"；bindtap="{{fn}}" -> data-tap="${fn}"
                if nk:
                    val = interp(v) if "{{" in v else v
                    if val:
                        parts.append(f' {nk}="{val}"' if "{{" not in v else f' {nk}="{interp(v)}"')
                elif nk is None and k.startswith("data-"):
                    parts.append(f' {k}="{interp(v)[2:-1] if "{{" in v else v}"')
            if tagname == "image":
                src = a.get("src", "")
                if src:
                    parts = [p for p in parts if not p.startswith(" src=")]
                    parts.append(f' src="{interp(src)}"' if "{{" in src else f' src="{src}"')
                parts.append(' loading="lazy"')
            if tagname == "input" and a.get("value"):
                parts.append(f' value="{interp(a["value"])}"' if "{{" in a["value"] else f' value="{a["value"]}"')
            if tagname == "textarea" and a.get("value"):
                pass
            if tagname == "img":
                parts.append(" />")
            elif tagname == "input":
                parts.append(" />")
            else:
                parts.append(">")
            out.append(pad() + 'html += `' + "".join(parts) + '`;')
            indent += 1

        if not sc and had_tag:
            stack.append((tagname, loop_vars, had_tag, stmts))

        # 自闭合或空标签：立刻收尾
        if sc:
            if had_tag:
                indent -= 1
                out.append(pad() + f"html += `</{html_tag}>`;")
            if loop_vars:
                indent -= 1
                out.append(pad() + "}")
            if cond_started:
                indent -= 1
                out.append(pad() + "}")
        elif had_tag:
            # 关闭标签在遇到 close 时处理（这里记录一下，close 分支负责 append 结束标签）
            stack[-1] = (tagname, loop_vars, had_tag, stmts)
        i += 1

    body = "\n".join(out)
    return "let html = '';\n" + body + "\nreturn html;"


def rpx_to_css(wxss: str) -> str:
    """rpx → calc(N * var(--rpx))；标签选择器 view/text/image 换成 html 标签。"""
    css = wxss
    css = re.sub(r"(\d+(?:\.\d+)?)rpx", lambda m: f"calc({m.group(1)} * var(--rpx))", css)
    for k, v in (("view", "div"), ("text", "span"), ("image", "img"), ("scroll-view", "div")):
        css = re.sub(r"(?<![\w-])" + k + r"(?![\w-])", v, css)
    css = re.sub(r"(^|\})\s*page\s*\{", lambda m: m.group(1) + "\n.coral-page {", css)
    return css


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    pages = [a.page] if a.page else sorted(p.name for p in (BC / "pages").iterdir() if p.is_dir())
    for pg in pages:
        d = BC / "pages" / pg
        wxml = next(d.glob("*.wxml"), None)
        wxss = next(d.glob("*.wxss"), None)
        if not wxml:
            continue
        js = convert(wxml.read_text(encoding="utf-8"))
        print(f"===== {pg} =====")
        print(js[:1500] if a.page else f"  （{len(js.splitlines())} 行 JS）")
        if a.out:
            outd = pathlib.Path(a.out); outd.mkdir(parents=True, exist_ok=True)
            (outd / f"{pg}.tmpl.js").write_text(js, encoding="utf-8")
            if wxss:
                (outd / f"{pg}.css").write_text(rpx_to_css(wxss.read_text(encoding="utf-8")), encoding="utf-8")


if __name__ == "__main__":
    main()
