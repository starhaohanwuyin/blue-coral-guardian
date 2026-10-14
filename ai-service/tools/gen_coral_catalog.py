# -*- coding: utf-8 -*-
"""生成珊瑚图鉴种子数据 → data/corals/coral_species.json

⚠️ 2026-10 回退说明：图鉴默认就是**原来那 12 条精编种类**（6 条精选 + 6 条），
配图用原来的实物图（`imgKey` → miniprogram/utils/mock.js 的 IMG，
网页端构建时会被本地化成 /mp/assets/img/*.jpg）。之前那套 300+ 条自动扩展表已删除。

要加自己的种类：后台 /admin.html 上传，或在 SPECIES 里加一行后重新生成：

    python tools/gen_coral_catalog.py        # 重新生成种子 JSON
    python scripts/coral_catalog.py --reload # 把种子灌进 SQLite（补齐缺失项）
    python scripts/coral_catalog.py --stats
"""
import io
import json
import pathlib
import sys
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "corals" / "coral_species.json"

# 组别 → 中文名
GROUP_CN = {"S": "造礁石珊瑚", "s": "非造礁石珊瑚", "A": "软珊瑚",
            "H": "水螅珊瑚", "Z": "柳珊瑚"}

# 群落形态代码 → 中文名
FORM_CN = {"B": "分枝状", "M": "块状 / 团块状", "P": "板状 / 桌状", "F": "叶片状 / 薄层状",
           "U": "单体 / 游离型", "S": "肉质软体", "G": "扇形 / 鞭状分枝",
           "H": "水螅型骨架", "Z": "纽扣状小群体"}

# 形态 → 详情页「形态识别 / 生物习性 / 生存威胁」的属级通性
FORM_ATTR = {
    "B": {"size": "群体直径 20–60 cm，分枝长 10–40 cm",
          "depth": "1–20 m（多数 2–10 m）", "growth": "快，分枝延长约 3–10 cm/年",
          "symb": "与虫黄藻强共生，约 80%–90% 能量来自虫黄藻光合产物",
          "mates": "礁区小型鱼类、虾蟹、蛇尾类、隐藻与钻孔生物",
          "threat": "海水升温引发白化；风暴折断；沉积与富营养化；观赏贸易采集"},
    "M": {"size": "群体直径 30–100 cm，大者可超过 2 m",
          "depth": "0–30 m（浑浊水域可更深）", "growth": "慢，约 0.5–2 cm/年，寿命可达数百年",
          "symb": "与虫黄藻稳定共生，钙化慢但礁体骨架贡献最大",
          "mates": "钻孔海绵与多毛类、礁区鱼类、虾蟹、藻类附生群落",
          "threat": "白化后恢复慢；海洋酸化降低钙化速率；锚泊与踩踏；沉积埋压"},
    "P": {"size": "叶片直径 20–80 cm，可层叠成多层结构",
          "depth": "2–25 m，常见于稍浑浊的礁坡与泻湖",
          "growth": "中等，边缘扩展约 1–4 cm/年",
          "symb": "与虫黄藻共生，单面受光结构提高了光能利用效率",
          "mates": "礁区鱼类、甲壳类、腹足类，叶片下方常为幼鱼庇护所",
          "threat": "高温白化；沉积物覆盖受光面；波浪与水流的物理破坏"},
    "U": {"size": "单体直径 5–30 cm（多数 10–20 cm）",
          "depth": "1–25 m，常见于沙底与礁坪",
          "growth": "较慢，约 0.5–2 cm/年",
          "symb": "与虫黄藻共生；成体多游离生活，可借水流或触手翻转体位",
          "mates": "沙底小型生物、共生蟹与螺，幼体期常附着于礁石",
          "threat": "高温白化；被沉积物掩埋；采集与踩踏；游离个体易被风浪翻覆"},
    "F": {"size": "叶片直径 15–50 cm，厚度数毫米至 1 cm",
          "depth": "1–30 m，弱光礁坡与洞穴口也能生长", "growth": "中等，约 1–5 cm/年",
          "symb": "与虫黄藻共生，薄层结构适合弱光环境下的光捕获",
          "mates": "礁坡鱼类、虾蟹、隐避性无脊椎动物",
          "threat": "对白化与沉积最敏感；酸化使薄片结构变脆；潜水触碰易折断"},
    "S": {"size": "群体高 10–60 cm，伞面直径可达 30 cm 以上",
          "depth": "2–30 m，多生于中等水流与弱光处",
          "growth": "较快，10–60 mm/年（受水流与营养影响大）",
          "symb": "多数含虫黄藻（共生型）；棘穗类等少数无共生藻，靠捕食浮游生物",
          "mates": "小型鱼类、虾蟹、海葵鱼与共生甲壳类",
          "threat": "高温与浊度升高导致的胁迫；水族采集压力；物理撕裂"},
    "G": {"size": "群体高 20–100 cm，扇形面宽 20–80 cm",
          "depth": "3–40 m，强流与弱光礁坡常见",
          "growth": "中等，约 1–5 cm/年（随流场与饵料供给变化）",
          "symb": "多为异养过滤摄食，不依赖虫黄藻；部分种类含共生藻",
          "mates": "常作为鱼类产卵场、蛇尾与共生虾的栖息支架",
          "threat": "拖网与锚链物理折断；沉积堵孔；采集制作工艺品"},
    "H": {"size": "群体高 10–60 cm，分枝或叶片状",
          "depth": "0–20 m", "growth": "较快，分枝约 2–10 cm/年",
          "symb": "与虫黄藻共生（水螅虫体内共生），是唯一常见造礁的水螅类",
          "mates": "礁区鱼类、虾蟹；触手刺细胞对潜水者有蜇伤风险",
          "threat": "高温同样会白化；风暴折断；沉积；触碰蜇伤后的清理破坏"},
}

# 科 → （亚纲, 目）：用于拼「生物分类」
FAMILY_TAX = {
    "鹿角珊瑚科": ("六放珊瑚亚纲 Hexacorallia", "石珊瑚目 Scleractinia"),
    "蜂巢珊瑚科": ("六放珊瑚亚纲 Hexacorallia", "石珊瑚目 Scleractinia"),
    "石芝珊瑚科": ("六放珊瑚亚纲 Hexacorallia", "石珊瑚目 Scleractinia"),
    "滨珊瑚科": ("六放珊瑚亚纲 Hexacorallia", "石珊瑚目 Scleractinia"),
    "泡珊瑚科": ("六放珊瑚亚纲 Hexacorallia", "石珊瑚目 Scleractinia"),
    "千孔螅科": ("水螅纲 Hydrozoa", "千孔螅目 Anthoathecata"),
    "笙珊瑚科": ("八放珊瑚亚纲 Octocorallia", "匍匐珊瑚目 Stolonifera"),
    "伞软珊瑚科": ("八放珊瑚亚纲 Octocorallia", "软珊瑚目 Alcyonacea"),
    "柳珊瑚科": ("八放珊瑚亚纲 Octocorallia", "柳珊瑚目 Malacalcyonacea"),
}
PROTECT_NOTE = "按类群给出的默认等级；具体到种请以 CITES 附录与《国家重点保护野生动物名录》为准"

# 原来的 12 条：中文名 | 拉丁名 | 分布 | 配图键 | 形态 | 科 | 类群 | 原文描述 | 白化敏感度
SPECIES = [
    ("鹿角珊瑚", "Acropora spp.", "Indo-Pacific、海洋", "coral1", "B",
     "鹿角珊瑚科 Acroporidae", "S",
     "分枝状造礁珊瑚，海洋最常见的珊瑚属，分支如鹿角般伸展", "高"),
    ("脑珊瑚", "Diploria spp.", "全球热带海域", "tech2", "M",
     "蜂巢珊瑚科 Merulinidae", "S",
     "球形或块状，表面沟回纹路如大脑，生长缓慢但寿命极长", "中"),
    ("蘑菇珊瑚", "Fungia spp.", "印度-太平洋", "coral3", "U",
     "石芝珊瑚科 Fungiidae", "s",
     "单体型珊瑚，形如蘑菇，可自由移动，是少数能移动珊瑚", "中"),
    ("软珊瑚", "Alcyonacea", "全球热带亚热带", "coral2", "S",
     "伞软珊瑚科 Alcyoniidae", "A",
     "无石灰质骨骼，柔软随水流摆动，色彩丰富形态优美", "中"),
    ("柳珊瑚", "Gorgonia spp.", "海洋、加勒比海", "tech4", "G",
     "柳珊瑚科 Gorgoniidae", "Z",
     "扇形分枝如柳条，常见于海流较强区域，是海洋生物栖息地", "中"),
    ("笙珊瑚", "Tubipora musica", "印度-太平洋", "tech5", "B",
     "笙珊瑚科 Tubiporidae", "A",
     "管状骨骼并联如笙管，鲜红或绿色，极具观赏价值", "中"),
    ("火珊瑚", "Millepora spp.", "全球热带海域", "coral1", "H",
     "千孔螅科 Milleporidae", "H",
     "触手含刺细胞，触碰如火烧，是造礁珊瑚中唯一的水螅珊瑚", "高"),
    ("桌珊瑚", "Acropora hyacinthus", "印度-太平洋", "tech2", "P",
     "鹿角珊瑚科 Acroporidae", "S",
     "平板状展开如水中圆桌，是鹿角珊瑚属中形态最独特的品种", "高"),
    ("玫瑰珊瑚", "Euphyllia spp.", "印度-太平洋", "coral3", "B",
     "泡珊瑚科 Euphylliidae", "S",
     "花瓣状触手排列如玫瑰，色彩艳丽，是水族馆最受欢迎的品种", "中"),
    ("柱珊瑚", "Porites spp.", "全球热带海域", "tech1", "M",
     "滨珊瑚科 Poritidae", "S",
     "圆柱形直立生长，生长极缓慢但寿命可达数百年，是礁石骨架主要构建者", "中"),
    ("气泡珊瑚", "Plerogyra sinuosa", "印度-太平洋", "tech5", "M",
     "泡珊瑚科 Euphylliidae", "S",
     "表面布满气泡状共生藻，白天膨胀如葡萄串，是珊瑚礁中最独特的景观", "中"),
    ("短小鹿角珊瑚", "Acropora humilis", "海洋", "coral2", "B",
     "鹿角珊瑚科 Acroporidae", "S",
     "蓝珊科技珊瑚2号杂交亲本之一，耐高温品种，可耐受+1℃高温", "高"),
]
# 前 6 条是原来的「热门种类」（科普页横滑展示的就是它们）
FEATURED = ["鹿角珊瑚", "脑珊瑚", "蘑菇珊瑚", "软珊瑚", "柳珊瑚", "笙珊瑚"]

COLORS = {  # 形态 → 配色词（与 imgKey 的实物图共同决定「外观颜色」文案）
    "B": "以橄榄黄 / 黄褐为主，分枝顶端常偏浅",
    "M": "以棕黄 / 褐橙为主，随光照深浅变化",
    "P": "以棕黄为主，边缘色浅",
    "U": "以明黄 / 米黄为主，沟纹处色深",
    "S": "以粉紫 / 米黄为主，柔软半透明",
    "G": "以朱红 / 橙黄为主，扇形网状",
    "H": "以米黄 / 黄褐为主",
}


def slug(text):
    keep = []
    for ch in str(text or "").lower():
        keep.append(ch if ch.isalnum() else "-")
    return "-".join([s for s in "".join(keep).split("-") if s])


def protection_for(grp):
    if grp in ("S", "s"):
        return ("CITES 附录 II；中国《国家重点保护野生动物名录》（2021）列为国家二级",
                PROTECT_NOTE)
    return ("未列入 CITES 附录 I；国内重点名录多数未收录（以官方名录为准）", PROTECT_NOTE)


def taxonomy_of(family, genus, name):
    cn_family = family.split(" ")[0]
    sub, order = FAMILY_TAX.get(cn_family,
                                ("六放珊瑚亚纲 Hexacorallia", "石珊瑚目 Scleractinia"))
    return ("动物界 Animalia → 刺胞动物门 Cnidaria → 珊瑚纲 Anthozoa → " +
            sub + " → " + order + " → " + family + " → " + name)


def build():
    rows = []
    for seq, (name, latin, dist, img_key, form, family, grp, desc, risk) in enumerate(SPECIES):
        a = FORM_ATTR[form]
        genus = latin.split(" ")[0]
        protection, pnote = protection_for(grp)
        rows.append({
            "id": "species-" + slug(latin),
            "name": name,
            "latin": latin,
            "genus": genus,
            "genusCn": "",
            "family": family,
            "level": "species",
            "group": GROUP_CN[grp],
            "desc": desc,
            "dist": dist,
            "bleachingRisk": risk,
            "reefBuilding": grp in ("S", "s"),
            "aiGenus": True,
            "featured": name in FEATURED,
            "imgKey": img_key,
            "imgUrl": "",
            "imageNote": "",
            "tags": [],
            "source": "原版精编图鉴（蓝珊）",
            "seq": seq,
            # 详情页四大板块
            "form": form,
            "formCn": FORM_CN[form],
            "alias": name + "（俗称）",
            "taxonomy": taxonomy_of(family, genus, name),
            "protection": protection,
            "protectionNote": pnote,
            "colonyForm": FORM_CN[form] + "；" + desc,
            "sizeCm": a["size"],
            "colorDesc": COLORS.get(form, ""),
            "idFeature": desc,
            "depthM": a["depth"],
            "tempSal": "适宜水温 23–29 ℃（短期可耐受 18–32 ℃）；盐度 34–36 ‰（最适 35 ‰）",
            "growthRate": a["growth"],
            "symbiosis": a["symb"],
            "companions": a["mates"],
            "threats": a["threat"],
            "hue": zlib.crc32(name.encode("utf-8")) % 360,
            "updatedAt": "",
        })
    return rows


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    rows = build()
    payload = {
        "schema": 1,
        "note": "图鉴种子 = 原版 12 条精编种类（配图用原来的实物图 imgKey）。"
                "要加种类请在 /admin.html 上传，或改本文件的 SPECIES 后重新生成。",
        "count": len(rows),
        "items": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("已生成 " + str(OUT))
    print("  条目 " + str(len(rows)) + "（精选 " +
          str(sum(1 for r in rows if r["featured"])) + "）· 配图全部为原来的实物图（imgKey）")


if __name__ == "__main__":
    main()
