# -*- coding: utf-8 -*-
"""从 Wikidata / Wikimedia Commons 批量补充珊瑚物种（含**一一对应**的实拍照片）。

为什么这么做：
  · 每条物种的照片来自 **该物种自己的 Wikidata 条目 P18**（= 维基百科词条首图），
    所以照片与物种天然一一对应，不会出现"A 种配 B 种照片"；
  · 照片统一缩到宽 900，落到 web/mp/assets/img/species_<属-种>.jpg，
    许可以及作者从 Commons 的 extmetadata 里取，写进 NOTICE.md 备查。

详情页四大板块的文字（形态/习性/威胁）来自 tools/gen_coral_catalog.py 的形态模板，
按属推断形态码（form）后套用，与原有 12 条精编保持一致的口径。

用法：
    python tools/fetch_coral_species.py --list            # 只统计能取到多少（不下载）
    python tools/fetch_coral_species.py --limit 120       # 取前 N 条并下载照片
    python tools/fetch_coral_species.py --limit 120 --out data/corals/new_species.json
然后：
    python scripts/coral_catalog.py --import data/corals/new_species.json
"""
import argparse
import importlib.util
import io
import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "web" / "mp" / "assets" / "img"
SEED = ROOT / "data" / "corals" / "coral_species.json"
NOTICE = ROOT / "NOTICE.md"
UA = {"User-Agent": "LanShanCoralCatalog/1.0 (academic coral reef project; contact: coral-research@example.org)"}
SCLERACTINIA = "Q195605"

SPARQL = """
SELECT ?taxon ?latin ?zh ?genusLabel ?familyLabel ?image WHERE {
  ?taxon wdt:P105 wd:Q7432 ; wdt:P171 ?genus ; wdt:P225 ?latin .
  ?genus wdt:P171 ?family . ?family wdt:P171 wd:%s .
  OPTIONAL { ?taxon wdt:P18 ?image }
  ?taxon rdfs:label ?zh . FILTER(lang(?zh) = "zh")
  FILTER NOT EXISTS { ?taxon wdt:P31 wd:Q310890 }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "zh,en". }
} LIMIT 900
""" % SCLERACTINIA

# 不限中文名：看「石珊瑚目下所有带照片的物种」有多少（决定扩充名单用）
SPARQL_POOL = """
SELECT ?taxon ?latin ?genusLabel ?familyLabel ?en WHERE {
  ?taxon wdt:P105 wd:Q7432 ; wdt:P171 ?genus ; wdt:P225 ?latin ; wdt:P18 ?img .
  ?genus wdt:P171 ?family . ?family wdt:P171 wd:%s .
  OPTIONAL { ?taxon rdfs:label ?en . FILTER(lang(?en) = "en") }
  FILTER NOT EXISTS { ?taxon wdt:P31 wd:Q310890 }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
} LIMIT 2000
""" % SCLERACTINIA


def load_gen():
    path = pathlib.Path(__file__).resolve().parent / "gen_coral_catalog.py"
    spec = importlib.util.spec_from_file_location("gen_coral_catalog", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def http_json(url, timeout=90):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def http_bytes(url, timeout=90):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), dict(r.headers)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")


def existing_slugs():
    """已有条目的 latin（小写）集合，避免重复添加。"""
    try:
        data = json.loads(SEED.read_text(encoding="utf-8"))
        items = data.get("items", [])
    except Exception:                                          # noqa: BLE001
        items = []
    out = {}
    for it in items:
        out[str(it.get("latin", "")).strip().lower()] = it
    return out


def genus_maps():
    """从现有条目里学出「属 → 形态码 / 类群 / 分布 / 白化敏感度 / 科 / 属中文名」。

    这样新条目的详情页口径与老条目一致（形态模板按 form 套用）。
    """
    data = json.loads(SEED.read_text(encoding="utf-8"))
    fields = ("form", "group", "dist", "bleachingRisk", "family", "genusCn", "protection")
    m = {}
    for it in data.get("items", []):
        g = (it.get("genus") or "").strip()
        if not g:
            continue
        d = m.setdefault(g, {})
        for f in fields:
            if it.get(f) and f not in d:
                d[f] = it[f]
    return m


def fetch_species():
    url = "https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(SPARQL)
    rows = http_json(url)["results"]["bindings"]
    out = []
    for x in rows:
        v = lambda k: (x.get(k) or {}).get("value", "")          # noqa: E731
        latin = v("latin").strip()
        if not latin or " " not in latin:
            continue
        out.append({
            "qid": v("taxon").rsplit("/", 1)[-1],
            "latin": latin,
            "zh": v("zh").strip(),
            "genusLabel": v("genusLabel").strip(),
            "familyLabel": v("familyLabel").strip(),
            "image": v("image").strip(),
        })
    return out


def commons_info(file_title):
    """取 Commons 文件的许可 / 作者 / 说明页链接（用于 NOTICE 备查）。"""
    name = file_title.split("/")[-1]
    q = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo"
         "&iiprop=extmetadata|url&titles=" + urllib.parse.quote("File:" + name))
    try:
        d = http_json(q)
        page = list(d["query"]["pages"].values())[0]
        md = page["imageinfo"][0]["extmetadata"]
        pick = lambda k: re.sub(r"<[^>]+>", "", md.get(k, {}).get("value", "")).strip()  # noqa: E731
        return {"license": pick("LicenseShortName"), "artist": pick("Artist"),
                "page": "https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(name)}
    except Exception as e:                                     # noqa: BLE001
        return {"license": "", "artist": "", "page": "", "err": str(e)[:60]}


def download_image(file_title, dest, width=900):
    name = file_title.split("/")[-1]
    url = ("https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(name)
           + "?width=%d" % width)
    blob, _ = http_bytes(url)
    if not blob or len(blob) < 5000:
        raise ValueError("照片太小，疑似占位图：%d 字节" % len(blob or b""))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(blob)
    return len(blob)


def build_entry(sp, gen, maps):
    latin = sp["latin"]
    genus = latin.split(" ")[0]
    gmap = maps.get(genus, {})
    form = gmap.get("form") or "M"
    attr = gen.FORM_ATTR.get(form, gen.FORM_ATTR["M"])
    family = gmap.get("family") or (sp.get("familyLabel") or "")
    zh = sp["zh"] or latin
    file_name = "species_%s.jpg" % slug(latin)
    img_url = "/mp/assets/img/" + file_name
    protection, pnote = gen.protection_for("S")
    return {
        "id": "species-" + slug(latin),
        "name": zh,
        "latin": latin,
        "genus": genus,
        "genusCn": gmap.get("genusCn", ""),
        "family": family,
        "level": "species",
        "group": gmap.get("group") or "造礁石珊瑚",
        "desc": "%s（%s），%s" % (zh, latin, attr.get("size", "")),
        "dist": gmap.get("dist") or "印度-太平洋",
        "bleachingRisk": gmap.get("bleachingRisk") or "中",
        "reefBuilding": True,
        "aiGenus": True,
        "featured": False,
        "imgKey": "",
        "imgUrl": img_url,
        "imageNote": "照片来自 Wikimedia Commons，与物种条目一一对应，已本地化到项目内",
        "tags": [],
        "source": "物种信息：Wikidata；照片：Wikimedia Commons",
        "form": form,
        "formCn": gen.FORM_CN.get(form, ""),
        "alias": "",
        "taxonomy": gen.taxonomy_of(family or "石珊瑚目 Scleractinia", genus, zh),
        "protection": protection,
        "protectionNote": pnote,
        "colonyForm": "%s；%s" % (gen.FORM_CN.get(form, ""), zh),
        "sizeCm": attr.get("size", ""),
        "colorDesc": gen.COLORS.get(form, ""),
        "idFeature": "%s（%s）：%s" % (zh, latin, gen.FORM_CN.get(form, "")),
        "depthM": attr.get("depth", ""),
        "tempSal": "适宜水温 23–29 ℃（短期可耐受 18–32 ℃）；盐度 34–36 ‰（最适 35 ‰）",
        "growthRate": attr.get("growth", ""),
        "symbiosis": attr.get("symb", ""),
        "companions": attr.get("mates", ""),
        "feeding": attr.get("feed", ""),
        "threats": attr.get("threat", ""),
        "population": attr.get("pop", ""),
        "file": file_name,
        "wd": sp["qid"],
    }


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="从 Wikidata/Commons 补充珊瑚物种与照片")
    ap.add_argument("--limit", type=int, default=0, help="最多新增多少条（0=不限）")
    ap.add_argument("--list", action="store_true", help="只统计，不下载")
    ap.add_argument("--pool", action="store_true", help="统计石珊瑚目下所有带照片的物种（含无中文名）")
    ap.add_argument("--out", default="data/corals/new_species.json")
    a = ap.parse_args()

    gen = load_gen()
    maps = genus_maps()
    have = existing_slugs()
    if a.pool:
        url = "https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(SPARQL_POOL)
        rows = http_json(url)["results"]["bindings"]
        cnt = {}
        for x in rows:
            g = (x.get("genusLabel") or {}).get("value", "") or "?"
            cnt[g] = cnt.get(g, 0) + 1
        print("石珊瑚目下带照片的物种：%d 条，属 %d 个" % (len(rows), len(cnt)))
        for g, n in sorted(cnt.items(), key=lambda kv: -kv[1])[:30]:
            print("   %-24s %d" % (g, n))
        return 0
    rows = fetch_species()
    print("Wikidata 取到物种 %d 条（带中文名），已有 %d 条" % (len(rows), len(have)))

    picked = []
    for sp in rows:
        key = sp["latin"].strip().lower()
        if key in have or not sp["zh"] or not sp["image"]:
            continue
        picked.append(sp)
    print("其中「有中文名 + 有照片 + 尚未收录」的 %d 条" % len(picked))
    if a.limit:
        picked = picked[:a.limit]
    if a.list:
        for sp in picked[:20]:
            print("  %s(%s) 属=%s 科=%s" % (sp["zh"], sp["latin"], sp["genusLabel"], sp["familyLabel"]))
        return 0

    entries, notice = [], []
    ok = fail = 0
    for i, sp in enumerate(picked, 1):
        e = build_entry(sp, gen, maps)
        dest = IMG_DIR / e["file"]
        try:
            if not dest.exists():
                size = download_image(sp["image"], dest)
            else:
                size = dest.stat().st_size
            info = commons_info(sp["image"])
            actual = "species_%s.jpg" % slug(sp["latin"])
            assert actual == e["file"], "照片文件名与物种不一致"
            notice.append((e["name"], e["latin"], e["file"], info.get("license", ""),
                           info.get("artist", ""), info.get("page", "")))
            e.pop("file")
            e.pop("wd")
            entries.append(e)
            ok += 1
            print("  [%d/%d] %s %s ← %d KB" % (i, len(picked), e["name"], e["latin"], size // 1024))
        except Exception as ex:                                # noqa: BLE001
            fail += 1
            print("  [%d/%d] 跳过 %s：%s" % (i, len(picked), sp["latin"], str(ex)[:70]))
        time.sleep(0.15)

    out = pathlib.Path(a.out)
    if not out.is_absolute():
        out = ROOT / out
    out.write_text(json.dumps({"schema": 2, "items": entries}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("\n新增 %d 条（失败 %d），已写 %s" % (ok, fail, out))
    if notice:
        add_notice(notice)
    print("下一步：python scripts/coral_catalog.py --import " + str(a.out))
    return 0


def add_notice(rows):
    """把新照片的来源/许可追加到 NOTICE.md（合规留痕）。"""
    text = NOTICE.read_text(encoding="utf-8")
    head = "\n## 图片来源与致谢（联网扩充的珊瑚种类，第二批）\n\n" \
           "| 物种 | 文件 | 许可 | 作者 | 来源页 |\n|---|---|---|---|---|\n"
    if "第二批" in text:
        print("NOTICE.md 已有第二批记录，跳过（避免重复）")
        return
    lines = ["| %s（%s） | %s | %s | %s | %s |" % r for r in rows]
    NOTICE.write_text(text.rstrip() + "\n" + head + "\n".join(lines) + "\n", encoding="utf-8")
    print("NOTICE.md 已追加 %d 条图片来源" % len(rows))


if __name__ == "__main__":
    sys.exit(main())
