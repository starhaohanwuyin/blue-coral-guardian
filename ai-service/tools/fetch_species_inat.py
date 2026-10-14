# -*- coding: utf-8 -*-
"""用 iNaturalist 扩充珊瑚物种 —— 每个物种配**它自己的**实拍照片（一一对应）。

为什么用 iNaturalist：
  · 它的分类单元（taxon）就是物种，`default_photo` 是该物种的代表照片 →
    照片与物种天然一一对应，不需要我们猜；
  · 支持 `locale=zh`，能直接取到中文学名/俗名（取不到才按「种加词意译＋属名」兜底）；
  · 照片带许可与作者（CC / CC0），写进 NOTICE.md 备查。

详情页四大板块文字来自 tools/gen_coral_catalog.py 的形态模板（按属推形态码），
与既有条目同一口径。

用法：
    python tools/fetch_species_inat.py --scan            # 先看每个属能补多少
    python tools/fetch_species_inat.py --limit 120       # 抓取并下载照片
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
API = "https://api.inaturalist.org/v1"
UA = {"User-Agent": "LanShanCoralCatalog/1.0 (academic coral reef project; contact: coral-research@example.org)"}

# 种加词 → 中文（意译）。项目既有条目就是这个规范，取不到 iNat 中文名时用它兜底。
EPITHET = {
    "valida": "强壮", "millepora": "多孔", "digitifera": "指状", "formosa": "美丽",
    "nasuta": "鼻形", "aspera": "矛枝", "tenuis": "柔枝", "cerealis": "黍形",
    "florida": "佛州", "humilis": "短小", "hyacinthus": "风信子", "aculeus": "尖刺",
    "echinata": "刺", "muricata": "粗糙", "palmata": "掌状", "cervicornis": "鹿角状",
    "prolifera": "多育", "pulchra": "秀丽", "robusta": "粗壮", "secale": "黑麦",
    "divaricata": "叉开", "gemmifera": "芽生", "glauca": "灰绿", "grandis": "大型",
    "horrida": "多刺", "intermedia": "中间", "latistella": "宽星", "listeri": "李斯特",
    "longicyathus": "长杯", "loripes": "绳状", "microclados": "细枝", "nobilis": "高贵",
    "papillare": "乳头", "polystoma": "多口", "sarmentosa": "匍匐", "selago": "卷柏",
    "spicifera": "穗状", "subglabra": "近无毛", "tenella": "纤细", "vermiculata": "虫纹",
    "yongei": "杨氏", "cactus": "仙人掌", "decussata": "交叉", "varians": "多变",
    "lobata": "裂片", "lutea": "黄色", "cylindrica": "柱状", "australiensis": "澳洲",
    "damicornis": "鹿角", "eydouxi": "埃氏", "meandrina": "脑纹", "verrucosa": "疣状",
    "capitata": "头状", "foliosa": "叶状", "aequituberculata": "等瘤", "digitata": "指形",
    "abdita": "隐", "halicora": "盐", "pentagona": "五角", "favus": "蜂巢",
    "speciosa": "美丽", "fungites": "蘑菇", "scutaria": "盾形", "astreata": "星状",
    "fascicularis": "束状", "pectinata": "栉状", "retiformis": "网形", "stokesi": "斯托克斯",
    "coerulea": "蓝色", "exesa": "啃蚀", "rigida": "坚硬", "palifera": "杯状",
    "corymbosa": "伞房", "hemprichii": "亨氏", "crassum": "厚", "ochracea": "赭色",
    "ampliata": "扩大", "dichotoma": "二歧", "platyphylla": "宽叶", "coccinea": "猩红",
    "mesenterina": "肠状", "peltata": "盾状", "reniformis": "肾形", "umbellata": "伞形",
    "lacrymalis": "泪滴", "jardinei": "贾丁氏", "divisa": "分裂", "glabrescens": "近光滑",
    "ancora": "锚形", "heliopora": "日孔", "lordhowensis": "豪勋爵", "insignis": "显著",
    "micropthalma": "小眼", "rostellata": "喙状", "moluccensis": "摩鹿加",
    "cylindricus": "圆柱", "lictor": "侍从", "pocillifera": "杯状", "secunda": "偏侧",
    "amakusensis": "天草", "multiplicata": "多褶", "hemprichi": "亨氏",
    "palauensis": "帕劳", "rotumana": "罗图马", "samoaensis": "萨摩亚",
    "acuminata": "渐尖", "anthocercis": "花尾", "austera": "严峻", "clathrata": "格纹",
    "cophodactyla": "钝指", "cytherea": "维纳斯", "donei": "多恩", "elseyi": "埃尔斯",
    "globiceps": "球头", "granulosa": "颗粒", "inermis": "无刺", "lutkeni": "卢特肯",
    "magnifica": "华丽", "abrotanoides": "蒿状", "elseyi": "埃氏", "polystoma": "多口",
    "grandiflora": "大花", "brueggemanni": "布氏", "crassa": "厚实", "horrescens": "粗糙",
    "pollicaris": "拇指", "tetrahedra": "四面", "tuberculosa": "瘤状", "danai": "达纳",
    "danafusiformis": "纺锤", "parilis": "相似", "abrolhosensis": "阿布罗柳斯",
    "kimbeensis": "金贝", "lokani": "洛坎", "mirabilis": "奇异", "monticulosa": "丘状",
    "nana": "矮小", "plumosa": "羽状", "carduus": "蓟", "caroliniana": "卡罗琳",
    "flabellata": "扇形", "reticulata": "网状", "prostrata": "平卧", "cf": "近似",
    # —— 第二批（iNaturalist 补充物种）用到的种加词 ——
    "albitentaculata": "白触手", "appressa": "紧贴", "arabensis": "阿拉伯", "awi": "阿维",
    "bifaria": "双列", "branchi": "布兰奇", "brevis": "短", "burgosi": "布尔戈斯",
    "chesterfieldensis": "切斯特菲尔德", "colemani": "科尔曼", "complanata": "扁平",
    "cryptoramosa": "隐枝", "desalwii": "德萨尔维", "djiboutiensis": "吉布提",
    "downingi": "唐宁", "elegans": "优雅", "eurystoma": "宽口", "exquisita": "精致",
    "faviaformis": "蜂巢状", "favulus": "小蜂巢", "fimbriata": "流苏", "flexuosa": "弯曲",
    "forskaliana": "福斯卡尔", "fruticosa": "灌木状", "fruticulosa": "小灌木",
    "halmaherae": "哈马黑拉", "harriottae": "哈里奥特", "hirsutissima": "极毛",
    "hoeksemai": "霍克塞马", "indonesia": "印尼", "jacquelineae": "杰奎琳",
    "kalindae": "卡林达", "kenti": "肯特", "kirstyae": "柯丝蒂", "kosurini": "科苏林",
    "labyrinthiformis": "迷宫状", "lacuna": "腔隙", "laddi": "拉德", "laxa": "疏松",
    "lizardensis": "蜥蜴岛", "longisepta": "长隔片", "lovelli": "洛弗尔",
    "macrostoma": "大口", "magnistellata": "大星", "mammiformis": "乳突状",
    "matthaii": "马泰", "microphthalma": "小眼", "minuta": "微小", "multiacuta": "多尖",
    "natalensis": "纳塔尔", "nyinggulu": "宁古鲁", "pachysepta": "厚隔片",
    "pallida": "苍白", "palmensis": "帕尔马", "palmerae": "帕尔默", "pandoraensis": "潘多拉",
    "paucisepta": "少隔片", "pedunculata": "具柄", "pendulus": "下垂", "pharaonis": "法老",
    "pichoni": "皮雄", "rotundata": "圆钝", "rotundoflora": "圆花", "rudis": "粗糙",
    "spathulata": "匙形", "squamata": "鳞状", "squarrosa": "鳞片状", "stelligera": "星状",
    "striata": "条纹", "stylifera": "具柱", "subulata": "钻形", "suharsonoi": "苏哈索诺",
    "taylorae": "泰勒", "tenuidens": "细齿", "tenuissima": "极细", "tersa": "洁净",
    "thecata": "杯状", "tortuosa": "扭曲", "truncata": "截形", "tumida": "肿胀",
    "uogi": "乌奥吉", "valenciennesi": "瓦朗谢讷", "vasta": "广阔", "verweyi": "维尔韦",
    "willisae": "威利斯",
}


def load_gen():
    path = pathlib.Path(__file__).resolve().parent / "gen_coral_catalog.py"
    spec = importlib.util.spec_from_file_location("gen_coral_catalog", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def get_json(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def get_bytes(url, timeout=90):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")


def seed_state():
    data = json.loads(SEED.read_text(encoding="utf-8"))
    have, maps = {}, {}
    for it in data.get("items", []):
        have[(it.get("latin") or "").strip().lower()] = it
        g = (it.get("genus") or "").strip()
        if not g:
            continue
        d = maps.setdefault(g, {})
        for f in ("form", "group", "dist", "bleachingRisk", "family", "genusCn", "protection"):
            if it.get(f) and f not in d:
                d[f] = it[f]
    return have, maps


def genus_id(genus):
    """iNaturalist 里该属的 taxon id（只认名字完全匹配的属级分类单元）。"""
    d = get_json(API + "/taxa?rank=genus&per_page=10&q=" + urllib.parse.quote(genus))
    for t in d.get("results", []):
        if (t.get("name") or "").lower() == genus.lower():
            return t["id"]
    return None


def genus_species(gid, max_pages=3):
    """该属下的物种（带代表照片）。locale=zh 时尽量取中文名。"""
    out, page = [], 1
    while page <= max_pages:
        d = get_json(API + "/taxa?rank=species&parent_id=%d&per_page=200&page=%d&locale=zh" % (gid, page))
        out += d.get("results", [])
        if len(d.get("results", [])) < 200:
            break
        page += 1
        time.sleep(0.1)
    return out


def pick_photo(taxon):
    """取该物种的代表照片（优先 large，其次 medium），并保留许可与作者。"""
    ph = taxon.get("default_photo") or {}
    url = ph.get("large_url") or ph.get("medium_url") or ph.get("url") or ""
    return {
        "url": url,
        "license": ph.get("license_code") or "all rights reserved",
        "attrib": ph.get("attribution") or "",
        "page": (ph.get("attribution") or "") and "" or "",
        "taxon_url": "https://www.inaturalist.org/taxa/%s" % taxon.get("id", ""),
    }


def zh_name(taxon, genus_cn):
    """中文名优先级：iNat 中文俗名 > iNat 中文名 > 「种加词意译＋属名」 > 英文俗名 > 拉丁名。"""
    names = []
    for n in (taxon.get("names") or []):
        if (n.get("locale") or "").startswith("zh"):
            names.append(n.get("name"))
    if taxon.get("preferred_common_name"):
        names.insert(0, taxon["preferred_common_name"])
    for n in names:
        if n and re.search("[\u4e00-\u9fff]", n):
            return n
    latin = taxon.get("name") or ""
    parts = latin.split()
    if len(parts) >= 2 and parts[1] in EPITHET:
        return EPITHET[parts[1]] + genus_cn.replace("属", "")
    return taxon.get("preferred_common_name") or latin


def build_entry(taxon, gen, maps):
    latin = taxon.get("name", "")
    genus = latin.split()[0]
    gmap = maps.get(genus, {})
    form = gmap.get("form") or "M"
    attr = gen.FORM_ATTR[form]
    genus_cn = gmap.get("genusCn") or genus
    name = zh_name(taxon, genus_cn)
    family = gmap.get("family") or ""
    protection, pnote = gen.protection_for("S")
    return {
        "id": "species-" + slug(latin),
        "name": name,
        "latin": latin,
        "genus": genus,
        "genusCn": genus_cn,
        "family": family,
        "level": "species",
        "group": gmap.get("group") or "造礁石珊瑚",
        "desc": "%s（%s），%s" % (name, latin, gen.FORM_CN.get(form, "")),
        "dist": gmap.get("dist") or "印度-太平洋",
        "bleachingRisk": gmap.get("bleachingRisk") or "中",
        "reefBuilding": True,
        "aiGenus": True,
        "featured": False,
        "imgKey": "",
        "imgUrl": "/mp/assets/img/species_%s.jpg" % slug(latin),
        "imageNote": ("照片来自 iNaturalist（该物种分类单元的代表照片，与条目一一对应），"
                      "已本地化到项目内"),
        "tags": [],
        "source": "物种信息：iNaturalist；照片：iNaturalist（含许可与作者）",
        "form": form,
        "formCn": gen.FORM_CN.get(form, ""),
        "alias": taxon.get("preferred_common_name") or "",
        "taxonomy": gen.taxonomy_of(family or "石珊瑚目 Scleractinia", genus, name),
        "protection": protection,
        "protectionNote": pnote,
        "colonyForm": "%s；%s（%s）" % (gen.FORM_CN.get(form, ""), name, latin),
        "sizeCm": attr["size"],
        "colorDesc": gen.COLORS.get(form, ""),
        "idFeature": "%s（%s）：%s" % (name, latin, gen.FORM_CN.get(form, "")),
        "depthM": attr["depth"],
        "tempSal": "适宜水温 23–29 ℃（短期可耐受 18–32 ℃）；盐度 34–36 ‰（最适 35 ‰）",
        "growthRate": attr["growth"],
        "symbiosis": attr["symb"],
        "companions": attr["mates"],
        "feeding": attr["feed"],
        "threats": attr["threat"],
        "population": attr["pop"],
    }


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="用 iNaturalist 扩充珊瑚物种（照片一一对应）")
    ap.add_argument("--limit", type=int, default=120)
    ap.add_argument("--scan", action="store_true", help="只看每个属能补多少")
    ap.add_argument("--prune", action="store_true",
                    help="清理 web/mp/assets/img 下没被任何条目引用的 species_*.jpg")
    ap.add_argument("--rename", action="store_true",
                    help="给「中文名缺失（用拉丁名兜底）」的条目补规范中文名（不动照片、不联网）")
    ap.add_argument("--genera", default="", help="逗号分隔属名（默认：种子里的属）")
    ap.add_argument("--out", default="data/corals/new_species.json")
    a = ap.parse_args()

    gen = load_gen()
    have, maps = seed_state()
    if a.prune:
        keep = set()
        for it in have.values():
            u = it.get("imgUrl") or ""
            if u:
                keep.add(u.rsplit("/", 1)[-1])
        new_path = ROOT / a.out
        if new_path.exists():
            for it in json.loads(new_path.read_text(encoding="utf-8")).get("items", []):
                keep.add((it.get("imgUrl") or "").rsplit("/", 1)[-1])
        removed = 0
        for f in sorted(IMG_DIR.glob("species_*.jpg")):
            if f.name not in keep:
                f.unlink()
                removed += 1
        print("已清理未被引用的物种照片 %d 个（保留 %d 个）" % (removed, len(keep)))
        return 0
    if a.rename:
        new_path = ROOT / a.out
        data = json.loads(new_path.read_text(encoding="utf-8"))
        gen2 = load_gen()
        fixed = 0
        for e in data.get("items", []):
            parts = (e.get("latin") or "").split()
            if len(parts) != 2 or e.get("name") != e.get("latin"):
                continue
            if parts[1] not in EPITHET:
                continue
            genus_cn = (e.get("genusCn") or parts[0]).replace("属", "")
            name = EPITHET[parts[1]] + genus_cn
            form = e.get("form") or "M"
            family = e.get("family") or "石珊瑚目 Scleractinia"
            e["name"] = name
            e["desc"] = "%s（%s），%s" % (name, e["latin"], gen2.FORM_CN.get(form, ""))
            e["colonyForm"] = "%s；%s（%s）" % (gen2.FORM_CN.get(form, ""), name, e["latin"])
            e["idFeature"] = "%s（%s）：%s" % (name, e["latin"], gen2.FORM_CN.get(form, ""))
            e["taxonomy"] = gen2.taxonomy_of(family, parts[0], name)
            fixed += 1
        new_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print("已补中文名 %d 条 → %s" % (fixed, new_path))
        return 0
    genera = ([g.strip() for g in a.genera.split(",") if g.strip()] if a.genera
              else sorted(maps))

    entries, notice, fail, tried = [], [], 0, 0
    for g in genera:
        gid = genus_id(g)
        if not gid:
            if a.scan:
                print("   %-20s 找不到 iNat 属级分类单元" % g)
            continue
        species = genus_species(gid)
        new = [t for t in species
               if (t.get("name") or "").lower() not in have and len((t.get("name") or "").split()) == 2]
        if a.scan:
            withphoto = [t for t in new if pick_photo(t)["url"]]
            print("   %-20s 物种 %3d  未收录 %3d  有照片 %3d" % (g, len(species), len(new), len(withphoto)))
            continue
        for t in new:
            if len(entries) >= a.limit:
                break
            ph = pick_photo(t)
            # 只收 CC / CC0 授权的照片：iNaturalist 上没标许可的是「版权所有」，不能就这么用
            if not ph["url"] or not str(ph["license"]).startswith("cc"):
                continue
            tried += 1
            e = build_entry(t, gen, maps)
            e["imageNote"] = ("照片来自 iNaturalist（%s%s），与条目一一对应，已本地化到项目内"
                              % (ph["license"], ("，" + ph["attrib"]) if ph["attrib"] else ""))
            dest = IMG_DIR / ("species_%s.jpg" % slug(e["latin"]))
            try:
                blob = get_bytes(ph["url"])
                if len(blob) < 5000:
                    raise ValueError("照片过小")
                dest.write_bytes(blob)
                notice.append((e["name"], e["latin"], dest.name, ph["license"],
                               ph["attrib"] or "-", ph["taxon_url"]))
                entries.append(e)
                print("  %-24s %-30s ← %4d KB  %s" % (e["name"], e["latin"], len(blob) // 1024,
                                                      ph["license"]))
            except Exception as ex:                            # noqa: BLE001
                fail += 1
                print("  跳过 %s：%s" % (e["latin"], str(ex)[:60]))
            time.sleep(0.12)
        if len(entries) >= a.limit:
            break

    if a.scan:
        return 0
    out = pathlib.Path(a.out)
    if not out.is_absolute():
        out = ROOT / a.out
    out.write_text(json.dumps({"schema": 2, "items": entries}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("\n新增 %d 条（尝试 %d，失败 %d）→ %s" % (len(entries), tried, fail, out))
    if notice:
        add_notice(notice)
    print("下一步：python scripts/coral_catalog.py --import " + a.out)
    return 0


def add_notice(rows):
    """把照片来源/许可/作者追加到 NOTICE.md（合规留痕；重复运行不会写第二遍）。"""
    text = NOTICE.read_text(encoding="utf-8")
    if "第三批" in text:
        print("NOTICE.md 已有第三批记录，跳过")
        return
    head = ("\n## 图片来源与致谢（联网扩充的珊瑚种类，第三批 / iNaturalist）\n\n"
            "> 每条照片取自该物种在 iNaturalist 的分类单元代表照片，与条目一一对应；"
            "仅收录 CC / CC0 授权。\n\n"
            "| 物种 | 学名 | 文件 | 许可 | 作者/来源 | 分类单元页 |\n|---|---|---|---|---|---|\n")
    lines = ["| %s | %s | %s | %s | %s | %s |" % r for r in rows]
    NOTICE.write_text(text.rstrip() + "\n" + head + "\n".join(lines) + "\n", encoding="utf-8")
    print("NOTICE.md 已追加 %d 条 iNaturalist 图片来源" % len(rows))


if __name__ == "__main__":
    sys.exit(main())
