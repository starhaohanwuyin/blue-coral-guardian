"""印太域珊瑚状况分析（CoralConditionDataset，泰国 Koh Tao）。

数据：`data/raw/CoralConditionDataset/`（GitHub XL-SHAO/CoralConditionDataset，MIT）
  · code/datasets/{train_set_fully_supervision,test_set,winter_data_test_set}.json
      —— 每个瓦片 9 个多标签（0/1）
  · tabular_data/annotations.csv   —— patchid → 单标签
  · tabular_data/surveys_metadata.csv —— 调查日期/站点/经纬度/深度/水温

为什么做：项目最大的已知短板是「**印太域白化不可用**」（跨域 top1 = 多数类基线，
bleached 召回仅 42.31%）。这份数据来自**印太（泰国湾）**且有"受损/死亡"标签，
是补这个短板最直接的外部数据；本脚本先把它能提供的**状况基线与季节差异**量化出来，
并给出与我们三分类（健康/白化/死亡）的映射 —— 等图像到位即可直接做域适配评测。

输出：reports/ccd_indopacific_condition.json
"""
import csv
import json
import pathlib
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
CCD = ROOT / "data" / "raw" / "CoralConditionDataset" / "CoralConditionDataset-main"
OUT = ROOT / "reports" / "ccd_indopacific_condition.json"

LABELS = {0: "Background", 1: "Healthy coral", 2: "Compromised coral", 3: "Dead coral",
          4: "Rubble", 5: "Competition", 6: "Disease", 7: "Predation", 8: "Physical issues"}
# 映射到本项目的三分类口径（白化/健康/死亡）
MAP3 = {1: "healthy", 2: "bleached", 3: "dead"}


def load_set(name):
    p = CCD / "code" / "datasets" / f"{name}.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def label_stats(rows):
    """多标签统计：每类出现次数与占比（按瓦片计）。"""
    n = len(rows) or 1
    cnt = Counter()
    per_tile = Counter()
    for r in rows:
        k = 0
        for lab in LABELS:
            if int(r.get(str(lab), 0)) == 1:
                cnt[lab] += 1
                k += 1
        per_tile[k] += 1
    return {
        "tiles": len(rows),
        "perLabelCount": {LABELS[l]: cnt[l] for l in LABELS},
        "perLabelFrac": {LABELS[l]: round(cnt[l] / n, 4) for l in LABELS},
        "labelsPerTile": dict(sorted(per_tile.items())),
    }


def season_stats(rows, meta):
    """按调查（site+date）聚合：标签占比 vs 深度/水温。"""
    by_site_date = defaultdict(list)
    for r in rows:
        tid = str(r.get("tileid", ""))
        parts = tid.split("_")
        # tileid 形如 HWB_0029_12_20230926_0005_35 → site, surveyid, transect, date
        if len(parts) >= 4:
            by_site_date[(parts[0], parts[3])].append(r)
    out = []
    for (site, date), rs in sorted(by_site_date.items()):
        m = meta.get((site, date), {})
        st = label_stats(rs)
        out.append({
            "site": site, "date": date, "tiles": st["tiles"],
            "depth": m.get("depth"), "temp": m.get("temp"), "camera": m.get("camera"),
            "compromisedFrac": st["perLabelFrac"].get("Compromised coral"),
            "deadFrac": st["perLabelFrac"].get("Dead coral"),
            "healthyFrac": st["perLabelFrac"].get("Healthy coral"),
        })
    return out


def main():
    if not CCD.exists():
        print(f"❌ 找不到数据集目录：{CCD}")
        return 1

    meta = {}
    mp = CCD / "tabular_data" / "surveys_metadata.csv"
    if mp.exists():
        with mp.open(newline="", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                meta[(row.get("site", "").strip(), (row.get("survey_date") or "").strip())] = row

    sets = {
        "train_summer_2023": load_set("train_set_fully_supervision"),
        "test_summer_2023": load_set("test_set"),
        "test_winter_2024": load_set("winter_data_test_set"),
    }
    print("CoralConditionDataset（泰国 Koh Tao，印太域）")
    print("=" * 92)
    print(f"{'子集':<20}{'瓦片数':>8}   " + "".join(f"{LABELS[l][:11]:>13}" for l in (1, 2, 3, 4, 6)))
    for name, rows in sets.items():
        st = label_stats(rows)
        line = f"{name:<20}{st['tiles']:>8}   "
        for l in (1, 2, 3, 4, 6):
            line += f"{st['perLabelFrac'][LABELS[l]]:>12.1%} "
        print(line)

    # 夏 vs 冬（整体口径）—— ⚠️ 注意：这里的 s_summer / s_winter 命名刻意避开循环变量，
    #    否则 `for site in ...` 之类的循环会把它们覆盖（本脚本已踩过一次）
    s_summer = label_stats(sets["test_summer_2023"])
    s_winter = label_stats(sets["test_winter_2024"])
    print("\n夏（2023-08/09）vs 冬（2024-01）—— 同一海域、同一标注口径")
    print(f"{'类别':<20}{'夏季':>9}{'冬季':>9}{'差值':>9}")
    for l in LABELS:
        a, b = s_summer["perLabelFrac"][LABELS[l]], s_winter["perLabelFrac"][LABELS[l]]
        flag = "  ← 明显" if abs(b - a) >= 0.05 else ""
        print(f"{LABELS[l]:<20}{a:>8.1%}{b:>9.1%}{b - a:>+9.1%}{flag}")

    # 三分类口径（健康/白化(受损)/死亡）—— 与我们的模型输出可比
    # ⚠️ 这是**多标签**：同一瓦片可同时出现"健康"与"死亡"（瓦片内不同 patch），
    #    所以各类占比**不能相加**，只能各自按"含该标签的瓦片比例"理解。
    print("\n映射到本项目三分类（多标签：各类占比按瓦片计，**不可相加**）")
    three_stats = {}
    for name, rows in sets.items():
        n = len(rows) or 1
        has = {v: 0 for v in MAP3.values()}
        none3 = 0
        both_hd = 0
        for r in rows:
            hit = [MAP3[k] for k in MAP3 if int(r.get(str(k), 0)) == 1]
            for v in hit:
                has[v] += 1
            if not hit:
                none3 += 1
            if "healthy" in hit and "dead" in hit:
                both_hd += 1
        three_stats[name] = {
            "tiles": len(rows),
            "fracHealthy": round(has["healthy"] / n, 4),
            "fracCompromised": round(has["bleached"] / n, 4),
            "fracDead": round(has["dead"] / n, 4),
            "tilesWithNoneOfThree": none3,
            "tilesWithHealthyAndDead": both_hd,
            "note": "多标签；三类占比不可相加",
        }
        print(f"  {name:<20} 含健康 {has['healthy']/n:5.1%}  含受损 {has['bleached']/n:5.1%}  "
              f"含死亡 {has['dead']/n:5.1%}  （三者皆无 {none3} 瓦片；"
              f"同时含健康与死亡 {both_hd} 瓦片 ← 多标签的正常现象）")

    # 夏 vs 冬：**只比两个季节都出现过的站点**（否则差异被站点组成混淆）
    def site_of(rows):
        out = defaultdict(list)
        for r in rows:
            tid = str(r.get("tileid", ""))
            p = tid.split("_")
            if len(p) >= 4:
                out[(p[0], p[3])].append(r)
        return out

    smap, wmap = site_of(sets["test_summer_2023"]), site_of(sets["test_winter_2024"])
    common_sites = sorted({s for s, _ in smap} & {s for s, _ in wmap})
    print(f"\n夏冬**共有站点**配对比较（{len(common_sites)} 个站点: {common_sites}）")
    paired = []
    if common_sites:
        print(f"{'站点':<7}{'夏季瓦片':>9}{'冬季瓦片':>9}{'受损Δ':>10}{'死亡Δ':>10}{'病害Δ':>10}")
        for site in common_sites:
            rs = [r for (ss, _), v in smap.items() if ss == site for r in v]
            rw = [r for (ss, _), v in wmap.items() if ss == site for r in v]
            a, b = label_stats(rs), label_stats(rw)
            d = {k: round(b["perLabelFrac"][k] - a["perLabelFrac"][k], 4)
                 for k in ("Compromised coral", "Dead coral", "Disease", "Healthy coral")}
            paired.append({"site": site, "summerTiles": len(rs), "winterTiles": len(rw), "delta": d})
            print(f"{site:<7}{len(rs):>9}{len(rw):>9}{d['Compromised coral']:>+10.1%}"
                  f"{d['Dead coral']:>+10.1%}{d['Disease']:>+10.1%}")
    else:
        print("  ⚠️ 无共有站点 → 整体夏冬差异会被站点组成混淆，不能当作季节信号")

    per_survey = season_stats(sets["test_summer_2023"] + sets["test_winter_2024"], meta)
    print("\n按调查看（前 8 条，含深度/水温）")
    print(f"{'站点':<7}{'日期':<11}{'瓦片':>6}{'深度':>8}{'水温':>8}{'受损':>8}{'死亡':>8}")
    for r in per_survey[:8]:
        print(f"{r['site']:<7}{r['date']:<11}{r['tiles']:>6}{str(r['depth']):>8}{str(r['temp']):>8}"
              f"{r['compromisedFrac']:>8.1%}{r['deadFrac']:>8.1%}")

    payload = {
        "task": "印太域（泰国 Koh Tao）珊瑚状况基线 —— 用于校准/补强项目最大短板",
        "source": {
            "repo": "https://github.com/XL-SHAO/CoralConditionDataset",
            "license": "MIT",
            "paper": ["arXiv:2403.05930", "10.1002/aqc.4241"],
            "location": "Koh Tao, Thailand (Indo-Pacific)",
            "note": "图像在 Google Drive（本次网络不可达，未下载）；本报告只用标签与调查元数据",
        },
        "labels": LABELS,
        "mapToProjectThreeClass": MAP3,
        "subsets": {k: label_stats(v) for k, v in sets.items()},
        "threeClassView": three_stats,
        "pairedSitesSummerVsWinter": paired,
        "summerVsWinter": {
            "summer": s_summer["perLabelFrac"], "winter": s_winter["perLabelFrac"],
            "delta": {LABELS[l]: round(s_winter["perLabelFrac"][LABELS[l]] - s_summer["perLabelFrac"][LABELS[l]], 4)
                      for l in LABELS},
            "warning": "整体夏冬差异**混有站点组成差异**，只有 pairedSitesSummerVsWinter 才是配对结论",
        },
        "perSurvey": per_survey,
        "caveats": [
            "瓦片级多标签（不是整图三分类）：与项目「整张图白化程度」口径不同，需聚合或按瓦片评",
            "「Compromised coral」≈ 受损（含白化但不限于白化），映射到 bleedched 只是近似",
            "图像未下载（Google Drive 本次不可达），因此**尚无模型在该域的实测指标**",
            "站点在泰国湾（10.06N, 99.83E），不在项目 NOAA 网格（4.03–5.03N, 118.03–119.53E）内，"
            "因此不能直接用现有 41 年缓存做该站点的热压力关联",
        ],
        "nextSteps": [
            "下载 coral_images.zip（Google Drive / gdown）→ 转成本项目数据格式",
            "用项目三分类模型在该域评一次（预期会暴露跨域短板），再做 LoRA/域自适应微调",
            "补齐该站点的 NOAA DHW（10.06N, 99.83E）以做「状况 × 热压力」的季节分析",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
