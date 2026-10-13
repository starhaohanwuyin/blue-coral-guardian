"""把小程序静态资源转换成网页端运行时需要的产物。

产物（输出到 coral_ml/web/mp/）：
    manifest.json          页面清单 + tabBar 配置
    templates/<p>.json     WXML 解析成的模板树（运行时求值渲染）
    pages/<p>.js           页面 JS（原样复制，由 mp.js 提供 Page/require/wx shim）
    utils/*.js             共享模块（原样复制）
    styles/<p>.css         WXSS 转换成的 CSS（rpx → calc(N * var(--rpx))）
    styles/app.css         app.wxss + custom-tab-bar 的样式

⚠️ 转换是"结构无损"的（标签/属性/表达式原样保留），**不做语义改写**：
   表达式在浏览器里用 new Function 求值，所以 WXML 里的 JS 写法要能在浏览器里跑。
"""
import json
import pathlib
import re

import ast as _ast  # noqa: F401  (仅为提示：本文件不依赖 ast)
sys_path = pathlib.Path(__file__).resolve()
BC = sys_path.parent.parent.parent / "miniprogram"       # 小程序源码（合并后的目录名）
OUT = sys_path.parent.parent / "web" / "mp"              # coral_ml/web/mp

TAG_MAP = {
    "view": "div", "text": "span", "image": "img", "scroll-view": "div",
    "swiper": "div", "swiper-item": "div", "navigator": "a", "block": "block",
    "button": "button", "input": "input", "textarea": "textarea",
    "progress": "progress", "rich-text": "div", "cover-view": "div", "cover-image": "img",
    "movable-area": "div", "movable-view": "div", "video": "video", "canvas": "canvas",
    "picker": "div", "switch": "div", "checkbox": "div", "radio": "div", "label": "label",
    "form": "form", "icon": "span", "official-account": "div", "open-data": "div",
    "web-view": "iframe", "slot": "div", "camera": "div", "image-cropper": "div",
    "van-icon": "span", "van-button": "button",
}
VOID = {"img", "input", "br", "hr", "textarea"}


def tokenize(wxml: str):
    """把 WXML 拆成 token 流；对含 & < 的 {{}} 属性值容错。"""
    out, i, n = [], 0, len(wxml)
    tag_re = re.compile(r"<\s*(/?)\s*([\w:-]+)((?:\"[^\"]*\"|'[^']*'|[^>\"'])*?)(/?)\s*>", re.S)
    while i < n:
        if wxml.startswith("<!--", i):
            j = wxml.find("-->", i)
            i = (j + 3) if j >= 0 else n
            continue
        m = tag_re.match(wxml, i)
        if m:
            out.append(("tag", m.group(1) == "/", m.group(2), m.group(3) or "", bool(m.group(4))))
            i = m.end()
            continue
        j = wxml.find("<", i)
        j = n if j < 0 else j
        if j > i:
            out.append(("text", wxml[i:j]))
        i = j
    return out


def parse_attrs(s: str) -> dict:
    a = {}
    for m in re.finditer(r"([:\w.-]+)\s*=\s*\"([^\"]*)\"", s or ""):
        a[m.group(1)] = m.group(2)
    for m in re.finditer(r"([:\w.-]+)\s*=\s*'([^']*)'", s or ""):
        a.setdefault(m.group(1), m.group(2))
    # 无值属性（布尔属性）：hidden / disabled / checked，以及**关键的 wx:else**
    # ⚠️ wx:else 在 WXML 里不带值，若漏解析会让 else 分支无条件渲染（踩过）
    for m in re.finditer(r"(?:^|\s)(wx:else|wx:if|wx:elif|hidden|disabled|checked)(?=\s|/?$)", s or ""):
        a.setdefault(m.group(1), "")
    return a


def build_tree(wxml: str):
    """WXML → 模板树（嵌套 dict）。"""
    tokens = tokenize(wxml)
    root = {"t": "block", "a": {}, "c": []}
    stack = [root]
    for tok in tokens:
        if tok[0] == "text":
            txt = tok[1]
            if txt.strip():
                stack[-1]["c"].append({"x": txt})
            continue
        _, closing, name, attr_s, selfclose = tok
        if closing:
            if len(stack) > 1:
                stack.pop()
            continue
        a = parse_attrs(attr_s)
        node = {"t": name, "a": a, "c": []}
        for k, key in (("wx:if", "i"), ("wx:elif", "e"), ("wx:else", "l"),
                       ("wx:for", "f"), ("wx:for-item", "fi"), ("wx:for-index", "fx")):
            if k in a:
                node[key] = a[k]
        stack[-1]["c"].append(node)
        if not selfclose and name not in ("input", "image", "img", "br"):
            stack.append(node)
    return root


def css_convert(wxss: str) -> str:
    """WXSS → CSS：rpx 自适应、标签名替换、page → body 容器。"""
    css = re.sub(r"(\d+(?:\.\d+)?)rpx", lambda m: f"calc({m.group(1)} * var(--rpx))", wxss)
    css = re.sub(r"(?<![\w.\-#])view(?![\w-])", "div", css)
    css = re.sub(r"(?<![\w.\-#])text(?![\w-])", "span", css)
    css = re.sub(r"(?<![\w.\-#])image(?![\w-])", "img", css)
    css = re.sub(r"(?<![\w.\-#])scroll-view(?![\w-])", "div", css)
    css = re.sub(r"(^|\})\s*page\s*\{", lambda m: m.group(1) + "\n.coral-page{", css)
    # 小程序里 img 默认是块，且默认 object-fit 类似 aspectFill
    css += "\n.coral-page img{display:block;max-width:100%;}\n"
    return css


def main():
    app = json.loads((BC / "app.json").read_text(encoding="utf-8"))
    pages = app.get("pages", [])
    (OUT / "templates").mkdir(parents=True, exist_ok=True)
    (OUT / "pages").mkdir(parents=True, exist_ok=True)
    (OUT / "styles").mkdir(parents=True, exist_ok=True)
    (OUT / "utils").mkdir(parents=True, exist_ok=True)

    manifest = {"pages": [], "tabBar": app.get("tabBar", {}), "window": app.get("window", {})}
    for full in pages:
        name = full.split("/")[-1]
        d = BC / pathlib.Path(full).parent          # app.json 里是 pages/index/index，目录是 pages/index
        wxml = next(d.glob("*.wxml"))
        wxss = next(d.glob("*.wxss"), None)
        js = next(d.glob("*.js"))
        cfg = next(d.glob("*.json"), None)
        title = ""
        if cfg:
            try:
                title = json.loads(cfg.read_text(encoding="utf-8")).get("navigationBarTitleText", "")
            except Exception:
                title = ""
        tree = build_tree(wxml.read_text(encoding="utf-8"))
        (OUT / "templates" / f"{name}.json").write_text(
            json.dumps(tree, ensure_ascii=False), encoding="utf-8")
        if wxss:
            (OUT / "styles" / f"{name}.css").write_text(
                css_convert(wxss.read_text(encoding="utf-8")), encoding="utf-8")
        # ⚠️ 必须保持小程序原来的目录深度：页面里写的是 require('../../utils/xxx.js')，
        #    只有放在 pages/<name>/<name>.js 才能解析到 mp/utils/xxx.js（否则要改源码）
        pdir = OUT / "pages" / name
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / f"{name}.js").write_text(js.read_text(encoding="utf-8"), encoding="utf-8")
        manifest["pages"].append({"route": full, "name": name, "title": title})
        print(f"  ✅ {name:<18} 模板节点 {len(json.dumps(tree))//100} 百字节  {title}")

    # 共享模块 + 全局样式
    for f in (BC / "utils").glob("*.js"):
        (OUT / "utils" / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    # app.js 放在 mp 根：它内部 require('./utils/config.js') 才能解析
    (OUT / "app.js").write_text((BC / "app.js").read_text(encoding="utf-8"), encoding="utf-8")
    css = ""
    for f in (BC / "app.wxss", BC / "custom-tab-bar" / "index.wxss"):
        if f.exists():
            css += f"\n/* ==== {f.name} ==== */\n" + css_convert(f.read_text(encoding="utf-8"))
    (OUT / "styles" / "app.css").write_text(css, encoding="utf-8")
    manifest["utils"] = [f.name for f in (BC / "utils").glob("*.js")]
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 共 {len(manifest['pages'])} 页 → {OUT}")
    print(f"   tabBar: {[i.get('text') for i in manifest['tabBar'].get('list', [])]}")


if __name__ == "__main__":
    main()
