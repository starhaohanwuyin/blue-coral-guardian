"""P4 第二步可行性判定：能否用 iNat 照片做"按时间/点位的白化率"分析？

已具备（脚本会实测并记录）：
  ① 观察日期（observed_on）覆盖率
  ② 坐标（lat/lon）
  ③ 本地图片可按 obs_id 前缀匹配

缺什么（决定结论）：
  ④ 可靠的**白化标签**：我们的白化分类器在印太域不可用（召回 42.31%，低于多数类基线 85.23%，
     见 reports/protocol_* 与手册 §4），所以拿它给 iNat 照片打白化标签＝在测量模型偏差而非现实
  ⑤ 采样平稳性：iNat 观察量逐年暴增，与气候变化混淆

→ 本脚本把上述证据量化，输出 verdict（允许/不允许），避免后人做出误导性分析。
"""
import json
import pathlib
from collections import Counter

ROOT = pathlib.Path(r"D:\大学作业\广东海洋大学的珊瑚评测小程序\coral_ml")
OUT = ROOT / "reports/p4_step2_feasibility.json"

# ---------- ① 日期与采样趋势 ----------
manifests = {
    "inat/semporna.json": "records",
    "inat/coraltriangle.json": "records",
    "inat_dataset/genus_test.json": "photos",
    "inat_dataset/genus_train.json": "photos",
    "inat_dataset/genus_val.json": "photos",
}
date_stats = {}
for rel, key in manifests.items():
    p = ROOT / "data" / rel
    if not p.exists():
        continue
    rows = json.loads(p.read_text(encoding="utf-8")).get(key) or []
    dates = [r.get("observed_on") for r in rows if r.get("observed_on")]
    yrs = Counter(str(d)[:4] for d in dates)
    latlon = sum(1 for r in rows if r.get("lat") is not None and r.get("lon") is not None)
    date_stats[rel] = {
        "records": len(rows), "withDate": len(dates),
        "coverage": round(len(dates) / max(len(rows), 1), 3),
        "withLatLon": latlon,
        "yearCounts": dict(sorted(yrs.items())),
    }

# ---------- ③ 本地图片匹配率（按 obs_id 前缀） ----------
img_dir = ROOT / "data/inat_dataset/images"
match = None
if img_dir.exists():
    files = list(img_dir.rglob("*.jpg"))          # ⚠️ 图片在 train/val/test 子目录下，必须递归
    prefixes = {f.name.split("_")[0] for f in files}
    test_rows = json.loads((ROOT / "data/inat_dataset/genus_test.json").read_text(encoding="utf-8"))["photos"]
    hit = sum(1 for r in test_rows if str(r.get("obs_id")) in prefixes)
    match = {"imagesOnDisk": len(files), "uniqueObsPrefixes": len(prefixes),
             "testRecords": len(test_rows), "matched": hit,
             "matchRate": round(hit / max(len(test_rows), 1), 3),
             "convention": "文件名前缀 = obs_id（如 144599556_71165.jpg）"}

# ---------- ④ 白化分类器的域外有效性（取自本项目报告，注意区分同域/跨域） ----------
def load(p):
    f = ROOT / "reports" / p
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def summarize(j):
    if not j:
        return None
    pc = j.get("perClass") or {}
    tot = sum(v.get("n", 0) for v in pc.values()) or 1
    maj = max(pc.items(), key=lambda kv: kv[1].get("n", 0)) if pc else (None, {})
    bleached = None
    for k, v in pc.items():
        if k.lower().startswith("bleach"):
            bleached = {"n": v.get("n"), "recall": v.get("recall"), "precision": v.get("precision")}
    return {"split": j.get("split"), "n": j.get("n_samples"), "top1": j.get("top1"),
            "macroF1": j.get("macroF1"),
            "majorityBaseline": round(maj[1].get("n", 0) / tot, 4),
            "majorityClass": maj[0], "bleachedClass": bleached}


ip_same = summarize(load("protocol_bleaching_ip_test.json"))        # bleaching_ip 同域 test
ip_cross = summarize(load("protocol_bleaching_ip_test_ip.json"))    # bleaching_ip 跨域 test_ip
new_clean = summarize(load("protocol_bleaching_new_test_clean.json"))

# ⚠️ 服务实际部署的是 bleaching_all（serve_fusion.py 的 BLEACH_DIRS[0]），它的 test_ip 指标
#    存在 decision_rules_bleaching_all_test_ip.json / cross_domain_bleaching_all.json，
#    与 bleaching_ip 的协议文件是**不同模型**，不能混引。
all_cross = load("decision_rules_bleaching_all_test_ip.json") or {}
mcnemar = load("mcnemar_bleaching_all_vs_bleaching_ip_test_ip.json") or {}
all_argmax = (all_cross.get("results") or {}).get("A_argmax") or {}
deployed = {
    "model": "bleaching_all（服务部署）",
    "split": all_cross.get("split"), "n": all_cross.get("n"),
    "accuracy": all_argmax.get("accuracy"),
    "bleachedRecall": ((all_argmax.get("perClass") or {}).get("bleached") or {}).get("recall"),
    "majorityBaseline": 150 / 176,           # test_ip 里 healthy 150/176
    "source": "reports/decision_rules_bleaching_all_test_ip.json",
    "vsBaseline": "低于多数类基线" if (all_argmax.get("accuracy") or 1) < 150 / 176 else "等于/高于基线",
}
mcnemar_summary = {"modelA": mcnemar.get("modelA"), "modelB": mcnemar.get("modelB"),
                   "accA": mcnemar.get("accA"), "accB": mcnemar.get("accB"),
                   "p_exact": (mcnemar.get("mcnemar") or {}).get("p_exact"),
                   "significant": (mcnemar.get("mcnemar") or {}).get("significant_0.05"),
                   "note": "两模型在 test_ip 上的差异不显著 → 换模型也救不了该域"}

# ---------- 判定 ----------
verdict = "not_viable"
reasons = [
    "照片级白化标签不可靠：**部署模型 bleaching_all** 在跨域印太留出（test_ip, n=176）上"
    f"总体准确率 {deployed.get('accuracy'):.4f} **低于**多数类基线 {deployed.get('majorityBaseline'):.4f}，"
    f"bleached 类召回仅 {deployed.get('bleachedRecall')}；"
    f"另一模型 bleaching_ip 为 {ip_cross.get('top1')}（= 基线），两者差异 McNemar p="
    f"{mcnemar_summary.get('p_exact')} **不显著**（换模型也救不了）→ "
    "拿它给 iNat 照片打白化标签＝在测量模型偏差而非现实；"
    "iNat 缓存元数据里也没有 iNat 自身的白化注释字段",
    "采样非平稳：iNat 观察量逐年暴增（2000→2026 约两个量级），年度白化率必然与『谁在什么时候上传』混淆",
    "观察者自选择：爱好者更愿意拍好看的珊瑚，白化照片的入样概率未知",
]
unblock = [
    "拿到**带日期的白化标注**（专家标注 iNat 照片的白化状态，或合作方提供带日期的白化调查记录）",
    "或先做域自适应，把白化分类器在印太域的 bleached 召回从 42.31% 提到可用水平（需要印尼/马来西亚域标注图像）",
]

report = {
    "task": "P4 第二步可行性：iNat 照片能否做按时间/点位的白化率分析",
    "dateAndCoordAvailability": date_stats,
    "localImageMatch": match,
    "bleachingClassifierDomainValidity": {
        "deployedModel_bleaching_all": deployed,
        "otherModel_bleaching_ip": ip_cross,
        "inDomainSameDomain_bleaching_ip": ip_same,
        "newDomainClean": new_clean,
        "modelComparison_mcnemar": mcnemar_summary,
        "note": ("⚠️ 别把两个模型混引：服务部署的是 **bleaching_all**（serve_fusion.py 的 BLEACH_DIRS[0]），"
                 "它在 test_ip 上 0.8295 < 基线 0.8523；`protocol_bleaching_ip_test_ip.json` 是"
                 "**bleaching_ip** 模型（0.8523 = 基线）；两者差异 McNemar p=0.424 不显著。"
                 "同域 test 的高分（0.9150）不可外推到印太域。"),
    },
    "verdict": verdict,
    "reasons": reasons,
    "whatWouldUnblock": unblock,
    "conclusion": ("P4 的**事件级**分析已可做且已完成（scripts/p4_event_timeline.py，"
                   "41 年 DHW 序列与实地报告事件年表一致）；**个体/站点级**因果在现有数据下不可做，"
                   "卡点是「没有可靠且带日期的白化标签」，不是缺日期。"),
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

print("① 日期/坐标可用性")
for k, v in date_stats.items():
    yrs = v["yearCounts"]
    span = f"{min(yrs)}–{max(yrs)}" if yrs else "—"
    print(f"   {k:<34} 记录 {v['records']:<6} 日期覆盖 {v['coverage']:.0%}  坐标 {v['withLatLon']:<6} 年份跨度 {span}")
print("\n③ 本地图片匹配（按 obs_id 前缀）")
print(f"   {match}")
print("\n④ 白化分类器：部署模型 vs 另一模型（同分片 test_ip，n=176）")
print(f"   部署 bleaching_all: 准确率 {deployed.get('accuracy'):.4f}  基线 {deployed.get('majorityBaseline'):.4f}"
      f"  bleached 召回 {deployed.get('bleachedRecall')}  → {deployed.get('vsBaseline')}")
if ip_cross:
    print(f"   另一 bleaching_ip : top1 {ip_cross.get('top1')}  bleached 召回 "
          f"{(ip_cross.get('bleachedClass') or {}).get('recall')}")
print(f"   两模型 McNemar p={mcnemar_summary.get('p_exact')}（显著={mcnemar_summary.get('significant')}）")
if ip_same:
    print(f"   参照（同域 test，不可外推）: top1 {ip_same.get('top1')}")
print(f"\n判定: {verdict}")
for r in reasons:
    print(f"   · {r}")
print(f"\n结果写入 {OUT}")
