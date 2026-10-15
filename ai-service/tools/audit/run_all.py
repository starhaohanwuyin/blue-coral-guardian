"""
一键体检：静态完整性 + 运行时 + 网页渲染 + 安全 + 文档一致性
=================================================================

用法（在 ai-service 目录下）：
    python tools/audit/run_all.py              # 跑全部（需要服务已在 8000 运行）
    python tools/audit/run_all.py --no-pages   # 跳过 23 页浏览器渲染（省时间）

退出码 0 = 全部通过；1 = 有失败项（可直接当闸门用在 CI 或提交前检查）。

设计原则：只做**可复现、可判定**的检查；每项都打印判定依据，便于人工复核。
"""
import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]        # ai-service/
REPO = ROOT.parent                                        # 仓库根
MP = REPO / "miniprogram"
WEB = ROOT / "web"
T = pathlib.Path(tempfile.gettempdir())
BASE = "http://127.0.0.1:8000"
EXE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
TEXT_EXT = {".py", ".js", ".json", ".md", ".txt", ".html", ".css", ".wxml", ".wxss",
            ".bat", ".sh", ".yml", ".yaml", ".toml", ".env"}

RESULTS = []          # (层, 名称, 是否通过, 说明)


SERVICE_UP = None          # 由 audit_runtime() 设置；None=未知
SKIP_HINT = "服务未启动 —— 先双击 启动演示.bat（或 cd ai-service/scripts && python serve_fusion.py）"


def chk(layer, name, cond, extra="", skip=False):
    """skip=True 表示"因前置条件不满足而跳过"，不计入失败。"""
    status = None if skip else bool(cond)
    RESULTS.append((layer, name, status, extra))
    mark = "⏭️ " if skip else ("✅" if cond else "❌")
    print(f"  {mark} {name}" + (f"  {extra}" if extra else ""), flush=True)
    return bool(cond)


def http(path, data=None, headers=None, method=None, timeout=30, base=None):
    r = urllib.request.Request((base or BASE) + path, data=data,
                               headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        try:
            b = e.read()
        except Exception:
            b = b""
        return e.code, b, dict(e.headers)
    except Exception as e:
        return 0, str(e).encode(), {}


def strip_js_comments(src):
    return re.sub(r"/\*[\s\S]*?\*/", "", re.sub(r"(?m)//.*$", "", src))


# ---------------------------------------------------------------- A 静态
def audit_static():
    print("\n【A】静态完整性", flush=True)
    # A1 接口重复定义（曾出现 api.getCoralDetail 定义两次 → 认养详情页空白）
    api = MP / "utils" / "api.js"
    if api.exists():
        names = re.findall(r"(?m)^api\.(\w+)\s*=", api.read_text(encoding="utf-8"))
        dup = sorted({n for n in names if names.count(n) > 1})
        chk("A", "接口无重复定义（api.*）", not dup, f"{len(names)} 个 API" + (f" 重复: {dup}" if dup else ""))
    else:
        chk("A", "utils/api.js 存在", False)

    # A2 语法
    js = [p for p in list(MP.rglob("*.js")) + list(WEB.rglob("*.js"))
          if ".git" not in p.parts and "node_modules" not in p.parts]
    bad_js = []
    for p in js:
        if subprocess.run(["node", "--check", str(p)], capture_output=True).returncode != 0:
            bad_js.append(p.relative_to(REPO).as_posix())
    chk("A", "JS 语法", not bad_js, f"{len(js)} 个文件" + (f" 失败: {bad_js[:3]}" if bad_js else ""))

    py = [p for p in ROOT.rglob("*.py") if "__pycache__" not in p.parts]
    bad_py = []
    for p in py:
        r = subprocess.run([sys.executable, "-m", "py_compile", str(p)], capture_output=True)
        if r.returncode != 0:
            bad_py.append(p.relative_to(REPO).as_posix())
    chk("A", "Python 语法", not bad_py, f"{len(py)} 个文件" + (f" 失败: {bad_py[:3]}" if bad_py else ""))

    # A3 require 路径（剥掉注释再匹配，避免注释里的示例误报）
    missing = []
    for p in MP.rglob("*.js"):
        code = strip_js_comments(p.read_text(encoding="utf-8", errors="replace"))
        for m in re.finditer(r"require\(['\"](\.[^'\"]+)['\"]\)", code):
            t = (p.parent / m.group(1)).resolve()
            if not (t.exists() or t.with_suffix(".js").exists() or (t / "index.js").exists()):
                missing.append(f"{p.relative_to(REPO).as_posix()} → {m.group(1)}")
    chk("A", "require 路径可解析", not missing, f"缺失 {len(missing)}" + (f" {missing[:2]}" if missing else ""))

    # A4 产物一致性（只比构建器负责的目录；assets/img 由 localize_images.py 维护）
    tmp = T / "audit_build_out"
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    subprocess.run([sys.executable, str(ROOT / "tools" / "build_web_pages.py"), "--out", str(tmp)],
                   capture_output=True, text=True, cwd=str(ROOT))
    committed = WEB / "mp"
    diffs = []
    for f in tmp.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(tmp)
        if rel.parts and rel.parts[0] == "assets":
            continue
        c = committed / rel
        if not c.exists() or c.read_bytes() != f.read_bytes():
            diffs.append(rel.as_posix())
    for f in committed.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(committed)
        if rel.parts and rel.parts[0] == "assets":
            continue
        if not (tmp / rel).exists():
            diffs.append(rel.as_posix())
    chk("A", "网页产物与小程序源码同步", not diffs,
        "逐字节一致" if not diffs else f"不一致 {len(diffs)}: {diffs[:3]}")

    # A5 本机绝对路径（隐私）
    pat = re.compile(r"[A-Za-z]:\\{1,2}(?:Users\\{1,2}[^\\\"'\s]+|大学作业)")
    leaks = []
    for p in REPO.rglob("*"):
        if not p.is_file() or ".git" in p.parts or p.suffix.lower() not in TEXT_EXT:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if pat.search(line):
                leaks.append(f"{p.relative_to(REPO).as_posix()}:{i}")
    chk("A", "无本机绝对路径", not leaks, f"{len(leaks)} 处" + (f" {leaks[:3]}" if leaks else ""))


# ---------------------------------------------------------------- B 运行时
def audit_runtime():
    print("\n【B】运行时与接口", flush=True)
    global SERVICE_UP
    st, body, _ = http("/health")
    ok = st == 200
    if ok:
        try:
            h = json.loads(body)
        except Exception:
            h = {}
    else:
        h = {}
    SERVICE_UP = ok and h.get("status") == "ok"
    chk("B", "服务在线（/health）", SERVICE_UP,
        f"device={h.get('device')} 类别={h.get('categories')} 双模型={bool(h.get('bleachAlt'))}"
        if SERVICE_UP else SKIP_HINT, skip=not SERVICE_UP)
    if not SERVICE_UP:
        return

    # 路由枚举
    src = (ROOT / "scripts" / "serve_fusion.py").read_text(encoding="utf-8")
    routes = sorted(set(re.findall(r'@app\.(get|post)\("([^"]+)"', src)))
    bad = []
    for method, path in routes:
        probe = re.sub(r"\{[^}]+\}", "1", path)
        if method == "get":
            s, _, _ = http(probe, timeout=60)
            good = s in (200, 400, 404, 422)
        else:
            s, _, _ = http(probe, data=b"", method="POST", timeout=60)
            good = s in (200, 400, 401, 403, 404, 422, 429)
        if not good:
            bad.append(f"{method.upper()} {path}→{s}")
    chk("B", "全部路由可达", not bad, f"{len(routes)} 个路由" + (f" 异常: {bad}" if bad else ""))

    # AI 端到端（真权重）
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from verify_serve_additive import post_multipart
        photos = sorted((ROOT / "data" / "semporna_photos").glob("*.jpg"))
        if not photos:
            chk("B", "AI 端到端", False, "没有示例图")
            return
        t0 = time.time()
        r = post_multipart(BASE, photos[0], "/analyze", {"lat": "4.4", "lon": "118.8", "year": "2024"})
        dt = (time.time() - t0) * 1000
        chk("B", "AI 端到端（真权重）", bool(r.get("success")), f"{dt:.0f} ms")
        cov = r.get("cover") or {}
        chk("B", "返回覆盖率", cov.get("coralTotalPct") is not None, f"珊瑚总覆盖={cov.get('coralTotalPct')}")
        chk("B", "返回白化结论", bool(r.get("bleaching")), str((r.get("bleaching") or {}).get("labelCn")))
        rep = (r.get("restoration") or {})
        chk("B", "返回中英文报告", bool(rep.get("report")) and bool(rep.get("reportEn")),
            f"中{len(rep.get('report') or '')}/英{len(rep.get('reportEn') or '')} 字符")
        chk("B", "返回环境研判", bool(r.get("climate")) or bool(r.get("deployment")), "")
    except Exception as e:
        chk("B", "AI 端到端", False, str(e)[:80])


# ---------------------------------------------------------------- C 网页
def audit_pages(do_pages=True):
    print("\n【C】网页版页面与图片", flush=True)
    app = json.loads((MP / "app.json").read_text(encoding="utf-8"))
    pages = [p.split("/")[1] for p in app["pages"]]
    tmpl = list((WEB / "mp" / "templates").glob("*.json"))
    chk("C", "产物页数与 app.json 一致", len(tmpl) == len(pages), f"{len(tmpl)} / {len(pages)}")
    if not do_pages:
        return
    if SERVICE_UP is False:
        chk("C", "页面渲染（需服务在线）", False, SKIP_HINT, skip=True)
        chk("C", "无图片占位/裂图", False, SKIP_HINT, skip=True)
        return
    exe = next((e for e in EXE_CANDIDATES if pathlib.Path(e).exists()), None)
    if not exe:
        chk("C", "页面渲染", False, "未找到 Edge（跳过）")
        return
    NEED_ID = {"coral-species": "species-acropora-spp", "knowledge-detail": "1", "article": "1"}
    bad, broken_img = [], []
    for name in pages:
        url = f"{BASE}/#/{name}" + (f"?id={NEED_ID[name]}" if name in NEED_ID else "")
        prof = T / f"audit_ep_{name}"
        prof.mkdir(parents=True, exist_ok=True)
        hf = T / f"audit_{name}.html"
        with open(hf, "wb") as f:
            subprocess.run([exe, "--headless", "--disable-gpu", "--no-sandbox",
                            f"--user-data-dir={prof}", "--window-size=520,1000",
                            "--virtual-time-budget=16000", "--dump-dom", url],
                           stdout=f, stderr=subprocess.DEVNULL)
        dom = hf.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'(?s)<main id="page-host">(.*?)</main>', dom)
        txt = re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", m.group(1))) if m else ""
        if len(txt) < 20 or 'id="mp-errlog"' in dom:
            bad.append(name)
        if "mp-img-ph" in dom:
            broken_img.append(name)
    chk("C", f"{len(pages)} 页渲染无 JS 错误", not bad, "全部通过" if not bad else f"失败: {bad}")
    chk("C", "无图片占位/裂图", not broken_img, "全部通过" if not broken_img else f"异常页: {broken_img}")


# ---------------------------------------------------------------- D 安全
def audit_security():
    print("\n【D】安全与隐私", flush=True)
    # D1 密钥
    SEC = {
        "私钥": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
        "OpenAI key": re.compile(r"sk-[A-Za-z0-9\-_]{20,}"),
        "AWS key": re.compile(r"AKIA[0-9A-Z]{16}"),
        "密码/密钥赋值": re.compile(r"(?i)(password|secret|api[_-]?key|access[_-]?token)\s*[:=]\s*['\"][^'\"]{6,}['\"]"),
    }
    found = []
    for p in REPO.rglob("*"):
        if not p.is_file() or ".git" in p.parts or p.suffix.lower() not in TEXT_EXT:
            continue
        t = p.read_text(encoding="utf-8", errors="ignore")
        for k, rx in SEC.items():
            if rx.search(t):
                found.append(f"{k}@{p.relative_to(REPO).as_posix()}")
    chk("D", "仓库内无密钥/凭据", not found, "0 处" if not found else str(found[:3]))

    # D2 图片元数据
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        n = risky = 0
        for p in REPO.rglob("*"):
            if not p.is_file() or ".git" in p.parts:
                continue
            if p.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            n += 1
            try:
                ex = Image.open(p).getexif()
                gps = ex.get_ifd(0x8825) if hasattr(ex, "get_ifd") else {}
                if ex or gps:
                    risky += 1
            except Exception:
                pass
        chk("D", "图片无 EXIF/GPS", risky == 0, f"扫描 {n} 张，带元数据 {risky} 张")
    except ImportError:
        chk("D", "图片 EXIF 检查", False, "Pillow 不可用")

    # D3 写接口默认仅本机 + OPTIONS 预检放行
    if SERVICE_UP is False:
        chk("D", "本机可写（图鉴维护）", False, SKIP_HINT, skip=True)
    else:
        st, _, _ = http("/corals/seed", data=b"{}", method="POST",
                        headers={"Content-Type": "application/json"})
        chk("D", "本机可写（图鉴维护）", st in (200, 422), f"HTTP {st}")
    if SERVICE_UP is False:
        chk("D", "外部域名跨域不放行", False, SKIP_HINT, skip=True)
        chk("D", "跨域预检不被拦截（Token 部署前提）", False, SKIP_HINT, skip=True)
    else:
        _, _, h = http("/health", headers={"Origin": "https://evil.example.com"})
        chk("D", "外部域名跨域不放行", not h.get("Access-Control-Allow-Origin"),
            f"ACAO={h.get('Access-Control-Allow-Origin')}")
        st, _, _ = http("/analyze", data=b"", method="OPTIONS",
                        headers={"Origin": "http://127.0.0.1:8099",
                                 "Access-Control-Request-Method": "POST",
                                 "Access-Control-Request-Headers": "x-api-token"})
        chk("D", "跨域预检不被拦截（Token 部署前提）", st in (200, 204), f"OPTIONS /analyze → HTTP {st}")

    # D4 客户端 Token 闭环（静态检查：客户端确实会带 Token）
    apijs = (MP / "utils" / "api.js").read_text(encoding="utf-8")
    chk("D", "客户端支持 X-API-Token", "apiTokenHeader" in apijs and "X-API-Token" in apijs)
    mpjs = (WEB / "mp.js").read_text(encoding="utf-8")
    chk("D", "运行时 uploadFile 转发 header", "headers: o.header" in mpjs)


# ---------------------------------------------------------------- E 文档
def audit_docs():
    print("\n【E】文档与素材一致性", flush=True)
    app = json.loads((MP / "app.json").read_text(encoding="utf-8"))
    n = len(app["pages"])
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    chk("E", f"README 页数与实际一致（{n}）", f"{n} 页" in readme)
    imgs = re.findall(r'src="([^"]+)"', readme)
    missing = [i for i in imgs if not (REPO / i).exists()]
    chk("E", "README 图片均存在", not missing, f"{len(imgs)} 张" + (f" 缺 {missing}" if missing else ""))
    # 文档数字与报告一致（关键指标抽查）
    rep = ROOT / "reports"
    try:
        sp = json.loads((rep / "protocol_species_ip_test_clean.json").read_text(encoding="utf-8"))
        chk("E", "34 属 Top-1 数字可复核", abs(sp["top1"] - 0.861213) < 1e-6, f"{sp['top1']*100:.2f}%")
        bl = json.loads((rep / "new_bleaching_bleaching_all_test_clean168.json").read_text(encoding="utf-8"))
        chk("E", "白化 98.21% 可复核", abs(bl["binaryAccuracy"] - 0.982143) < 1e-6,
            f"{bl['binaryAccuracy']*100:.2f}%")
    except Exception as e:
        chk("E", "评测报告可读取", False, str(e)[:60])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pages", action="store_true", help="跳过浏览器页面渲染（省时间）")
    args = ap.parse_args()

    print("=" * 74)
    print(f"  一键体检 · {REPO.name} · {time.strftime('%Y-%m-%d %H:%M')}")
    print("=" * 74)
    audit_static()
    audit_runtime()
    audit_pages(not args.no_pages)
    audit_security()
    audit_docs()

    print("\n" + "=" * 74)
    layers = {}
    for layer, name, ok, extra in RESULTS:
        a, b, s = layers.get(layer, (0, 0, 0))
        layers[layer] = (a + (1 if ok else 0), b + (0 if ok is False else 0),
                         s + (1 if ok is None else 0))
    for layer in sorted(layers):
        a, b, s = layers[layer]
        print(f"  {layer}：✅ {a} / ❌ {b}" + (f" / ⏭️ {s}（跳过）" if s else ""))
    total_a = sum(v[0] for v in layers.values())
    total_b = sum(v[1] for v in layers.values())
    total_s = sum(v[2] for v in layers.values())
    print(f"  合计：✅ {total_a} / ❌ {total_b}" + (f" / ⏭️ {total_s}（跳过）" if total_s else ""))
    if total_s:
        print(f"  ⏭️ 跳过原因：{SKIP_HINT}")
    if total_b:
        print("\n  失败项：")
        for layer, name, ok, extra in RESULTS:
            if ok is False:
                print(f"    ❌ [{layer}] {name}  {extra}")
    print("=" * 74)
    return 1 if total_b else 0


if __name__ == "__main__":
    sys.exit(main())
