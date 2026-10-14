import argparse
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
import hashlib
import json
import pathlib
import re

import ast as _ast  # noqa: F401  (仅为提示：本文件不依赖 ast)
sys_path = pathlib.Path(__file__).resolve()
BC = sys_path.parent.parent.parent / "miniprogram"       # 小程序源码（合并后的目录名）
OUT = sys_path.parent.parent / "web" / "mp"              # coral_ml/web/mp

# 中英对照表（唯一真源在 miniprogram/tools/i18n_phrases.json）：用于生成页面的英文导航标题
try:
    PHRASES = json.loads((BC / "tools" / "i18n_phrases.json").read_text(encoding="utf-8"))
except Exception:                                          # noqa: BLE001
    PHRASES = {}

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
    # ⚠️ 必须把**负号**一起吃进 calc：`right:-4rpx` 若转成 `-calc(4*var(--rpx))`
    #    是非法 CSS，整条声明会被浏览器丢弃 —— 徽章位置、动画位移、负边距全都会失效
    #    （实测 profile 编辑徽章因此跑到头像左侧并压住用户名，共 23 处负值 rpx）。
    css = re.sub(r"(-?(?:\d+\.?\d*|\.\d+))rpx",
                 lambda m: f"calc({m.group(1)} * var(--rpx))", wxss)

    # 标签名替换**只能作用于选择器部分**：
    # 若对整份 CSS 无差别替换，`-webkit-background-clip: text` 里的值 text 会被换成 span
    # → 非法被丢弃 → "渐变文字"变成纯色块 + 文字透明不可见（实测首页 logo 就是这个问题）。
    parts, buf, depth = [], [], 0
    for ch in css:
        if ch == "{":
            parts.append(_tag_sel("".join(buf))); parts.append("{"); buf = []; depth += 1
        elif ch == "}":
            parts.append("".join(buf)); parts.append("}"); buf = []; depth = max(0, depth - 1)
        else:
            buf.append(ch)
    parts.append("".join(buf))
    css = "".join(parts)

    # page 选择器 → .coral-page（HTML 里没有 page 元素；不改则 page{} 里的 15 个
    # CSS 变量（--primary/--accent/…）全部失效，用变量写颜色/渐变的地方会整条作废，
    # 例如首页"查看我的珊瑚"按钮的渐变背景消失、白字变成看不见。
    # ⚠️ 必须用 re.M：规则前面常有注释行，`^` 不加 MULTILINE 匹配不到。
    css = re.sub(r"(?m)(^|\})\s*page\s*\{", lambda m: (m.group(1) or "") + "\n.coral-page{", css)
    # 小程序里 <image> 默认是 inline-block（不是 block）：强行 display:block 会改变
    # 横滑卡片、图文混排的布局导致错位；这里只保证不溢出、基线对齐与小程序一致。
    # 图片的填充方式（aspectFill 等）由运行时的 mode → object-fit 映射负责。
    css += "\n.coral-page img{max-width:100%;vertical-align:middle;}\n"
    return css


def _tag_sel(sel: str) -> str:
    """只对选择器片段做小程序标签名 → HTML 标签名替换。"""
    sel = re.sub(r"(?<![\w.\-#])view(?![\w-])", "div", sel)
    sel = re.sub(r"(?<![\w.\-#])text(?![\w-])", "span", sel)
    sel = re.sub(r"(?<![\w.\-#])image(?![\w-])", "img", sel)
    sel = re.sub(r"(?<![\w.\-#])scroll-view(?![\w-])", "div", sel)
    return sel


def main():
    global OUT                              # 允许 --out 指向别处（做一致性比对时用）
    ap = argparse.ArgumentParser(description="把小程序页面构建成网页版运行时产物")
    ap.add_argument("--out", default="", help="输出目录（默认 web/mp）")
    args = ap.parse_args()
    if args.out:
        OUT = pathlib.Path(args.out).resolve()

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
        # titleEn：导航栏标题的英文（运行时的标题也跟着语言切）。
        # 译文来自 miniprogram/tools/i18n_phrases.json（中英对照的唯一真源）。
        manifest["pages"].append({"route": full, "name": name, "title": title,
                                  "titleEn": PHRASES.get(title, title)})
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

    # ⚠️ 关键一步：套用「外部图片 → 本地文件」映射。
    #    否则每次重建都会把 utils/mock.js 里的图片地址还原成外部 CDN，
    #    把 localize_images.py 做过的本地化覆盖掉（离线演示就会裂图）。
    applied = apply_image_map(OUT)
    stamp = stamp_index_cache_buster(OUT)
    print(f"✅ 共 {len(manifest['pages'])} 页 → {OUT}")
    print(f"   tabBar: {[i.get('text') for i in manifest['tabBar'].get('list', [])]}")
    print(f"   图片本地化: 套用映射 {applied} 处（映射表 tools/image_map.json）")
    if stamp:
        print(f"   缓存版本号: index.html 的 ?v={stamp}（运行时的 /mp/** 请求都会带上它）")


def stamp_index_cache_buster(out_dir: pathlib.Path) -> str:
    """把 web/index.html 里 mp.js / app.css 的 ?v= 换成新的构建戳。

    为什么需要：运行时代码、模板、样式以前都是裸 URL，浏览器启发式缓存会长期给旧文件，
    表现为「代码改了、页面上还是旧的」。mp.js 会读这个版本号并拼到所有 /mp/** 请求上，
    于是版本号一变，整套前端立刻重新抓取（普通刷新即可，不必清缓存）。
    只有输出到默认的 web/ 时才动 index.html（--out 到临时目录做比对时不碰）。
    """
    index = out_dir.parent / "index.html"
    if not index.exists():
        return ""
    pattern = re.compile(r'(\./[^"\']*\.(?:js|css)\?v=)[^"\']*')
    try:
        text = index.read_text(encoding="utf-8")
    except Exception:                                          # noqa: BLE001
        return ""
    if not pattern.search(text):
        return ""
    stamp = build_stamp(out_dir)
    index.write_text(pattern.sub(lambda m: m.group(1) + stamp, text), encoding="utf-8")
    return stamp


def build_stamp(out_dir: pathlib.Path) -> str:
    """按**产物内容**算版本号（而不是时间戳）。

    原来用 int(time.time())：每次构建都会改 index.html，仓库里天天出现"只改了版本号"的
    无意义 diff，也看不出真正的内容变化。改成内容哈希后：
      · 源码没变 → 重建零差异（CI/复跑可校验）
      · 源码一变 → 版本号必变 → 浏览器普通刷新即拿到新代码（缓存穿透照旧有效）
    覆盖范围：mp.js（运行时）＋ web/mp 下全部模板/样式/脚本/清单。
    """
    h = hashlib.sha1()
    files = [out_dir.parent / "mp.js"]
    files += sorted(p for p in out_dir.rglob("*") if p.is_file())
    for p in files:
        if not p.exists():
            continue
        h.update(p.relative_to(out_dir.parent).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:6]



def apply_image_map(out_dir: pathlib.Path) -> int:
    """按 tools/image_map.json 把构建产物里的外部图片 URL 换成本地路径。"""
    map_file = pathlib.Path(__file__).resolve().parent / "image_map.json"
    if not map_file.exists():
        print("   [提示] 未找到 tools/image_map.json，跳过图片本地化（图片将指向外部 CDN）")
        return 0
    try:
        mapping = json.loads(map_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"   [警告] image_map.json 解析失败：{e}")
        return 0
    n = 0
    for p in list(out_dir.rglob("*.js")) + list(out_dir.rglob("*.json")) + list(out_dir.rglob("*.css")):
        if "assets" in p.parts or p.name == "image_map.json":
            continue
        try:
            t = p.read_text(encoding="utf-8")
        except Exception:
            continue
        o = t
        for url, local in mapping.items():
            if url in t:
                t = t.replace(url, local)
        if t != o:
            p.write_text(t, encoding="utf-8")
            n += 1
    return n


if __name__ == "__main__":
    main()
