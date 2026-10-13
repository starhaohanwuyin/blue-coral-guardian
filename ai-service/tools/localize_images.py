"""把小程序 mock 数据里的外部配图一次性下载到本地，并改写**网页版副本**的引用，
使网页版彻底不依赖任何外部平台（断网/无代理也能正常显示图片）。

用法（在有网或挂代理的机器上跑一次即可）：
    python tools/localize_images.py            # 下载 + 改写网页副本
    python tools/localize_images.py --dry-run  # 只看会下载哪些
    python tools/localize_images.py --also-mini # 连小程序源码(blue_coral)一起改写

说明：
  · 图片存到 coral_ml/web/mp/assets/img/<hash>.<ext>，URL 改成 /mp/assets/img/xxx
  · 只改写 coral_ml/web/mp/ 下的副本；--also-mini 才会动 blue_coral 源码
  · 失败会如实列出（不会静默跳过），可重跑（已下载的跳过）
"""
import argparse
import hashlib
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
MP = WEB / "mp"
BC = ROOT.parent / "blue_coral"
ASSETS = MP / "assets" / "img"

URL_RE = re.compile(r"https?://[^\s\"'`)]+")
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif")


def targets(also_mini: bool):
    files = []
    for p in list(MP.rglob("*.js")) + list(MP.rglob("*.css")) + list(MP.rglob("*.json")):
        files.append(p)
    if also_mini and BC.exists():
        for pat in ("utils/*.js", "pages/**/*.js", "pages/**/*.wxml", "pages/**/*.wxss", "*.wxss"):
            files += [q for q in BC.glob(pat) if q.is_file()]
    return sorted(set(files))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--also-mini", action="store_true")
    a = ap.parse_args()
    ASSETS.mkdir(parents=True, exist_ok=True)

    urls = {}          # url -> 本地相对路径（/mp/assets/img/xxx）
    for f in targets(a.also_mini):
        try:
            txt = f.read_text(encoding="utf-8")
        except Exception:
            continue
        for u in URL_RE.findall(txt):
            if u.lower().endswith(IMG_EXT) or "/image/" in u or "unsplash" in u:
                if "127.0.0.1" in u or "localhost" in u or "10.0." in u:
                    continue
                urls.setdefault(u, None)

    print(f"发现 {len(urls)} 个外部图片 URL（dry-run 只列出，不下载）\n")
    ok = bad = 0
    for u in sorted(urls):
        name = hashlib.sha1(u.encode()).hexdigest()[:16]
        ext = pathlib.Path(u.split("?")[0]).suffix.lower() or ".jpg"
        if ext not in IMG_EXT:
            ext = ".jpg"
        local = ASSETS / (name + ext)
        rel = "/mp/assets/img/" + local.name
        if local.exists():
            urls[u] = rel
            print(f"  ⏭  已存在 {local.name}  ← {u[:70]}")
            ok += 1
            continue
        if a.dry_run:
            print(f"  ·  将下载 {local.name}  ← {u[:70]}")
            continue
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            local.write_bytes(data)
            urls[u] = rel
            ok += 1
            print(f"  ✅ {len(data)//1024} KB → {local.name}  ← {u[:60]}")
        except Exception as e:
            bad += 1
            print(f"  ❌ 失败 {u[:70]}  （{type(e).__name__}: {str(e)[:60]}）")

    if a.dry_run:
        print(f"\n（dry-run 结束：{len(urls)} 个待下载）")
        return 0

    # 改写引用（只改写 web/mp 副本；--also-mini 才动源码）
    changed = 0
    for f in targets(a.also_mini):
        try:
            txt = f.read_text(encoding="utf-8")
        except Exception:
            continue
        new = txt
        for u, rel in urls.items():
            if rel:
                new = new.replace(u, rel)
        if new != txt:
            f.write_text(new, encoding="utf-8")
            changed += 1
    print(f"\n下载成功 {ok} 张，失败 {bad} 张；改写文件 {changed} 个")
    if bad:
        print("⚠️ 有失败项：通常是网络/代理问题，挂上代理后重跑本脚本即可（已下载的会跳过）")
    print("提示：改写后刷新浏览器即可（图片变为 /mp/assets/img/… 本地文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
