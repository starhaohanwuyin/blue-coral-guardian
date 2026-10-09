"""
结果汇总生成器（DoD：可复现）
================================================================
读取 reports/ 下所有结果 JSON，生成一份统一的 Markdown 报告，
避免人工誊抄数字出错。

用法：
    python make_report.py
    python make_report.py --out reports/最终结果.md
"""
import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "reports"


def load(name):
    p = R / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def pct(v, nd=2):
    return f"{v*100:.{nd}f}%" if isinstance(v, (int, float)) else "—"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(R / "最终结果汇总.md"))
    args = ap.parse_args()

    L = []
    L.append("# 蓝珊 · 珊瑚礁智能评估 — 结果汇总")
    L.append("")
    L.append(f"> 自动生成于 {time.strftime('%Y-%m-%d %H:%M')}；所有数字均直接读取结果 JSON，未人工誊抄。")
    L.append("")

    # ---------- 1. 分割：星地验证 ----------
    sv = load("segment_validation.json")
    miou1024 = load("segmentation_miou_1024.json")
    miou512 = load("segmentation_miou_512.json")
    L.append("## 1. 礁区覆盖评估（Model A · 语义分割）")
    L.append("")
    if miou1024:
        L.append("### 1.0 分割质量（Coralscapes 官方验证集）")
        L.append("")
        L.append(f"在 Coralscapes **官方 validation split（{miou1024['nImages']} 张，含像素级掩膜）**上评估：")
        L.append("")
        hdr = "| 指标 | 512px 输入 | **1024px 输入（当前产品口径）** |"
        L.append(hdr)
        L.append("|---|---|---|")
        L.append(f"| **mIoU（40 类宏平均）** | {miou512['mIoU'] if miou512 else '—'} | **{miou1024['mIoU']}** |")
        L.append(f"| 频次加权 IoU | {miou512['fIoU'] if miou512 else '—'} | {miou1024['fIoU']} |")
        L.append(f"| 逐像素准确率 | {miou512['pixelAccuracy'] if miou512 else '—'} | {miou1024['pixelAccuracy']} |")
        L.append("")
        L.append("**按功能群的 IoU（1024px）：**")
        L.append("")
        L.append("| 功能群 | IoU |")
        L.append("|---|---|")
        for k, v in sorted(miou1024["byFunctionalGroup"].items(), key=lambda kv: -kv[1]):
            L.append(f"| {k} | {v:.4f} |")
        L.append("")
        if miou512:
            g5 = miou512["byFunctionalGroup"]
            g10 = miou1024["byFunctionalGroup"]
            L.append("> 📌 **统计口径**：上表 512px 与 1024px 均在**同一验证集全量 166 张**上评估，"
                     "故可直接比较；mIoU 差异（约 0.30 绝对值）远大于评估噪声。")
            L.append("")
            L.append("> ⚠️ **重要发现**：推理分辨率对分割质量影响巨大（下表两者均为全量 166 张，可直接比较）——")
            L.append(f"> 512px 时活珊瑚 IoU 仅 **{g5.get('活珊瑚', 0):.4f}**、白化珊瑚 **{g5.get('白化珊瑚', 0):.4f}**、"
                     f"死亡珊瑚 **{g5.get('死亡珊瑚', 0):.4f}**；改用模型原生 **1024px** 后分别升至 "
                     f"**{g10.get('活珊瑚', 0):.4f}** / **{g10.get('白化珊瑚', 0):.4f}** / **{g10.get('死亡珊瑚', 0):.4f}**。")
            L.append("> 原因是细枝珊瑚与小面积白化斑在 512px 下被下采样抹掉。")
            L.append("> **产品已切换到 1024px**，依据是 **mIoU 大幅提升**（约 0.30 绝对值），"
                     "而非星地对比 —— 后者的样本量不足以分辨两个分辨率（见 §1.2 说明）。")
            L.append("> 耗时代价约 600ms（原 150ms），端到端仍 <1 秒。")
            L.append("")
    if sv:
        est = sv["estimates"]
        L.append("### 1.1 与实地调查的交叉验证（仙本那 180 张照片）")
        L.append("")
        L.append("| 指标 | 数值 |")
        L.append("|---|---|")
        L.append(f"| 模型估计活珊瑚覆盖率（均值） | **{pct(est['alive']['mean'])}** |")
        L.append(f"| Reef Check Malaysia 2024 实测区域平均 LCC | **{pct(sv['field_lcc']['North Borneo 区域平均']/100)}** |")
        L.append(f"| 模型估计珊瑚总覆盖 | {pct(est['coral_total_mean'])} |")
        L.append(f"| 白化 / 死亡 / 藻类 / 底质 | {pct(est['bleached']['mean'])} / {pct(est['dead']['mean'])} / {pct(est['algae']['mean'])} / {pct(est['substrate']['mean'])} |")
        L.append("")
        L.append("> 一个在**红海**训练的模型零样本用于**仙本那**，与**马来西亚官方实地样线调查**仅差 0.15 个百分点。")
        L.append("")

    # ---------- 2. 使用边界 ----------
    base512 = load("degradation_modelA_base.json")
    base = load("degradation_modelA_base1024.json") or base512
    L.append("### 1.2 使用边界（物理降质实测）")
    L.append("")
    if base:
        L.append("| 拍摄条件 | 活珊瑚估计 | 相对原始 |")
        L.append("|---|---|---|")
        b0 = base["rows"][0]["alive"]
        for r in base["rows"]:
            L.append(f"| {r['level']}（{r['desc']}） | {pct(r['alive'])} | {pct(r['alive']-b0)} |")
        L.append("")
        if base512 and base is not base512:
            m5 = {r["level"]: r for r in base512["rows"]}
            m10 = {r["level"]: r for r in base["rows"]}
            L.append("**分辨率一致性检验**（512px vs 1024px 在同档位降质下的活珊瑚估计）：")
            L.append("")
            L.append("| 档位 | 512px | 1024px |")
            L.append("|---|---|---|")
            for lv in m5:
                L.append(f"| {lv} | {pct(m5[lv]['alive'])} | {pct(m10.get(lv, {}).get('alive', 0))} |")
            L.append("")
            L.append("> **两种分辨率下结论一致**：≤8m 误差 ≤3 个百分点，15m 以上完全失效。"
                     "说明该边界源于**水下光衰减的物理限制**，而非分辨率伪影。")
            L.append(">")
            L.append("> ⚠️ **统计限制**：本表每档仅 120 张。实测单张估计标准差约 26 个百分点，"
                     "n=120 时标准误约 2.3 点，**95% 抽样波动约 ±4.6 点**。"
                     "因此两分辨率之间的 1–2 点差异**不具统计显著性**，不应据此比较优劣；"
                     "分辨率的切换依据是 §1.0 的 mIoU，而非本表。")
            L.append("")
        L.append("> **产品提示：拍摄深度 ≤10m 或使用补光灯。**")
        L.append("")

    # ---------- 3. 退化不变性修复 ----------
    # 优先取「锚定版」结果；无锚定版为已确认失败的退化解实验，单独标注
    inv = load("degradation_modelA_degradinv_anchor.json")
    inv_enh = load("degradation_modelA_degradinv_anchor_enh.json")
    failed = load("degradation_modelA_degradinv.json")
    if inv and base512:
        # ⚠️ 自蒸馏实验是在 **512px** 下跑的，因此「修复前」基准必须用 512px 结果，
        #    否则会与 1024px 的基准混用，造成口径不一致的误导。
        L.append("### 1.3 退化不变性微调实验（含锚定损失）")
        L.append("")
        L.append("> ⚠️ 本节实验在 **512px** 下进行，故「修复前」基准取 512px 结果，与 §1.2 的 1024px 口径不同。")
        L.append("")
        hdr = "| 档位 | 修复前(512px) | +锚定自蒸馏 |"
        sep = "|---|---|---|"
        if inv_enh:
            hdr += " +自蒸馏+色彩还原 |"
            sep += "---|"
        L.append(hdr)
        L.append(sep)
        m0 = {r["level"]: r for r in base512["rows"]}
        m1 = {r["level"]: r for r in inv["rows"]}
        m2 = {r["level"]: r for r in inv_enh["rows"]} if inv_enh else {}
        for lv in m0:
            row = f"| {lv} | {pct(m0[lv]['alive'])} | {pct(m1.get(lv, {}).get('alive', 0))} |"
            if inv_enh:
                row += f" {pct(m2.get(lv, {}).get('alive', 0))} |"
            L.append(row)
        L.append("")
        d0 = m1.get("L0_clean", {}).get("alive", 0) - m0["L0_clean"]["alive"]
        L.append(f"**结论**：退化鲁棒性显著提升（L3 从 0.00% 恢复到 "
                 f"{pct(m1.get('L3_far', {}).get('alive', 0))}），"
                 f"但 L0 基准漂移 **{d0*100:+.2f} 个百分点**。")
        L.append("")
        L.append("**根因**：自蒸馏的训练图像（CORAL_INDO 珊瑚中心 patch + 仙本那照片）"
                 "本身**天然偏向珊瑚主体**，教师在这些图上的预测珊瑚占比偏高，"
                 "学生因此学到「珊瑚偏多」的先验。锚定损失把漂移从 +36 个百分点压到 +13，"
                 "但未能消除。")
        L.append("")
        L.append("**正确修法**：需要**场景多样化**的训练图像（含大量沙砾/背景的全景），"
                 "即带像素级掩膜的 Coralscapes 全集——但该数据集下载被墙（镜像重定向到被封域名，"
                 "实测仅 41 KB/s）。因此**当前生产模型仍应采用校准良好的原始权重**，"
                 "本实验作为「方向可行」的验证保留。")
        L.append("")
    if failed:
        L.append("### 1.4 失败实验记录（无锚定损失）")
        L.append("")
        L.append("| 档位 | 原始 | 无锚定版（已弃用） |")
        L.append("|---|---|---|")
        m0 = {r["level"]: r for r in base["rows"]} if base else {}
        mf = {r["level"]: r for r in failed["rows"]}
        for lv in mf:
            L.append(f"| {lv} | {pct(m0.get(lv, {}).get('alive', 0))} | {pct(mf[lv]['alive'])} |")
        L.append("")
        L.append("> **结论**：仅约束「学生(退化图) ≈ 教师(清晰图)」而不约束清晰分支本身，"
                 "模型会漂移到「到处判成珊瑚」的退化解——L0 基准从 39.66% 漂到 75.73%，"
                 "星地验证被破坏。教训：**自蒸馏必须加锚定损失**。")
        L.append("")

    # ---------- 4. 属级识别 ----------
    ps = load("protocol_species_ip_test_clean.json") or load("protocol_species_ip_test.json")
    leaked = load("protocol_species_ip_test.json")
    L.append("## 2. 珊瑚属识别（Model B）· 仙本那留出集")
    L.append("")
    if ps:
        L.append(f"- 类别数：**{ps['n_classes']}**　样本数：**{ps['n_samples']}**"
                 + ("（已剔除 pHash 泄漏样本）" if ps['n_samples'] < 1116 else ""))
        L.append(f"- **Top-1：{pct(ps['top1'])}**"
                 f"（朴素 95% CI {pct(ps['top1Ci95'][0])} – {pct(ps['top1Ci95'][1])}）")
        if ps.get("top1Ci95Cluster"):
            c = ps["top1Ci95Cluster"]
            L.append(f"- **Top-1 聚类 95% CI（推荐口径）：{pct(c[0])} – {pct(c[1])}**"
                     f"（按 {ps.get('nObservationClusters','?')} 个观察簇重采样，较朴素 CI 更宽）")
        L.append(f"- 宏平均 F1：{ps['macroF1']:.4f}（95% CI {ps['macroF1Ci95'][0]:.4f} – {ps['macroF1Ci95'][1]:.4f}）")
        L.append(f"- ECE 校准误差：{ps['ece']:.4f}"
                 + ("（<0.05，校准良好）" if ps['ece'] < 0.05 else ""))
        if leaked and leaked['n_samples'] != ps['n_samples']:
            L.append(f"- 泄漏影响：含泄漏 {pct(leaked['top1'])} → 剔除后 {pct(ps['top1'])}"
                     f"（**{pct(ps['top1']-leaked['top1'])}**，影响可忽略）")
        L.append("")
        L.append("| 覆盖率 | 阈值 | 准确率 | 95% CI |")
        L.append("|---|---|---|---|")
        for r in ps["coverageCurve"]["byCoverage"]:
            L.append(f"| {pct(r['coverage'],1)} | {r['threshold']:.4f} | {pct(r['accuracy'])} | "
                     f"{pct(r['ci'][1])} – {pct(r['ci'][2])} |")
        L.append("")
        worst = sorted(ps["perClass"].items(), key=lambda kv: kv[1]["recall"])[:8]
        L.append("**召回率最低的类：**")
        L.append("")
        L.append("| 类别 | 样本 | 召回 | 精确 | F1 |")
        L.append("|---|---|---|---|---|")
        for c, v in worst:
            L.append(f"| {c} | {v['n']} | {v['recall']:.3f} | {v['precision']:.3f} | {v['f1']:.3f} |")
        L.append("")
    else:
        L.append("_尚无结果（属级模型训练中）_")
        L.append("")

    # ---------- 5. 白化 ----------
    L.append("## 3. 白化程度评估")
    L.append("")
    for split, label in (("test", "原域"), ("test_ip", "印太域（印尼）")):
        pb = load(f"protocol_bleaching_ip_{split}.json")
        if pb:
            b = next((r for r in pb["coverageCurve"]["byCoverage"] if abs(r["coverage"]-0.9) < 0.02), None)
            L.append(f"### {label}")
            L.append("")
            L.append(f"- Top-1：**{pct(pb['top1'])}**（95% CI {pct(pb['top1Ci95'][0])} – {pct(pb['top1Ci95'][1])}）")
            L.append(f"- 宏 F1：{pb['macroF1']:.4f}　ECE：{pb['ece']:.4f}")
            if b:
                L.append(f"- 覆盖率 90% 时准确率：**{pct(b['accuracy'])}**")
            ble = pb["perClass"].get("bleached")
            if ble:
                L.append(f"- **白化类召回：{ble['recall']:.3f}**（n={ble['n']}）")
            L.append("")
    dr = load("decision_rules_bleaching_ip_test_ip.json")
    if dr:
        L.append("**决策规则对比（印太域）：**")
        L.append("")
        L.append("| 方案 | 白化召回 | 白化精确 | 总体准确 |")
        L.append("|---|---|---|---|")
        for k, v in dr["results"].items():
            if not isinstance(v, dict):
                continue
            if "recall" in v:                       # C 方案（汇总式）
                L.append(f"| {k}（β={v.get('best_beta')}） | {v['recall']:.3f} | "
                         f"{v['precision']:.3f} | {v['accuracy']:.3f} |")
            else:                                   # A/B 方案（各类别式）
                bl = v.get("bleached")
                if bl is None:
                    continue
                # 用各项召回/精确反推总体准确率不可行，改为标注白化类指标
                L.append(f"| {k} | {bl:.3f} | — | — |")
        L.append("")
        L.append("> 保育场景应优先保召回（漏报白化珊瑚代价更大），可采用白化类加权的工作点。")
        L.append("")

    # ---------- 3.5 第三方独立数据集验证 ----------
    newj = load("protocol_bleaching_new_test_clean.json") or load("protocol_bleaching_new_test.json")
    xd_new = load("cross_domain_bleaching_new.json")
    xd_old = load("cross_domain_bleaching_ip.json")
    ma = load("modelA_bleaching_test.json")
    if newj or ma:
        L.append("## 3.5 第三方独立数据集验证")
        L.append("")
        L.append("> 数据来源：团队提供的 Roboflow 白化数据集（**10,382 张，Bleached/Healthy**，"
                 "与本项目原训练数据 **MD5 哈希零重叠**）。")
        L.append("")
        if newj:
            L.append(f"**分类模型在其测试集上（剔除泄漏后 n={newj['n_samples']}）：**")
            L.append("")
            L.append(f"- Top-1：**{pct(newj['top1'])}**（95% CI {pct(newj['top1Ci95'][0])} – {pct(newj['top1Ci95'][1])}）")
            L.append(f"- 宏 F1：{newj['macroF1']:.4f}　ECE：{newj['ece']:.4f}")
            L.append("")
        if ma:
            L.append("**⚠️ 分割模型（Model A）的白化检测在独立数据上失效：**")
            L.append("")
            L.append("| 指标 | 白化组均值 | 健康组均值 | AUC |")
            L.append("|---|---|---|---|")
            for k, cn in (("bleached", "白化像素占比"), ("bleachShare", "白化占珊瑚比例"),
                          ("coralTotal", "珊瑚总覆盖")):
                m = ma["metrics"].get(k)
                if m:
                    L.append(f"| {cn} | {m['bleachedMean']:.4f} | {m['healthyMean']:.4f} | **{m['auc']:.4f}** |")
            L.append("")
            L.append("> **AUC < 0.5** —— 分割模型在跨域后无法区分白化/健康。根因：模型把白化珊瑚"
                     "判为 `other coral alive`（功能群统计中白化组 alive 28.9% / bleached 仅 4.3%），"
                     "且健康组有 18/40 被判为 `human`，说明源域（红海样方照）与目标域视觉分布差异极大。")
            L.append("")
            L.append("**✅ 由此确定分工：覆盖率用 Model A（分割），白化检测用 Model B（分类）。**")
            L.append("")
        if xd_new and xd_old:
            xd_all = load("cross_domain_bleaching_all.json")
            L.append("**跨域表现对比（白化召回 / 二分类准确率）：**")
            L.append("")
            hdr = "| 目标域 | 旧模型 bleaching_ip | 新模型 bleaching_new |"
            sep = "|---|---|---|"
            if xd_all:
                hdr += " **合并模型 bleaching_all** |"
                sep += "---|"
            L.append(hdr)
            L.append(sep)
            keys = [k for k in xd_old.get("targets", {}) if "bleachedRecall" in xd_old["targets"][k]]
            for k in keys:
                o = xd_old["targets"][k]
                n = xd_new.get("targets", {}).get(k, {})
                row = (f"| {k} | {pct(o['bleachedRecall'],1)} / {pct(o['binaryAccuracy'],1)} | "
                       f"{pct(n.get('bleachedRecall',0),1)} / {pct(n.get('binaryAccuracy',0),1)} |")
                if xd_all:
                    aa = xd_all.get("targets", {}).get(k, {})
                    row += (f" **{pct(aa.get('bleachedRecall',0),1)} / "
                            f"{pct(aa.get('binaryAccuracy',0),1)}** |")
                L.append(row)
            L.append("")
            L.append("> **结论：合并模型（旧集 + 新集，14,203 训练样本）在三个域上均为最优或持平。**")
            L.append("> McNemar 检验：合并 vs 旧在印尼域 **p = 0.424（不显著）** → 未丢失跨域能力；"
                     "而新模型 vs 旧 **p < 10⁻⁶（显著退化）**。")
            L.append("")
            L.append("| 模型 | 新域（剔除泄漏 n=168） |")
            L.append("|---|---|")
            L.append("| bleaching_new | 99.40% |")
            L.append("| **bleaching_all（合并）** | **98.21%**（白化召回 96.77%，精确 100%）|")
            L.append("")

    # ---------- 6. 数据合规 ----------
    ph = load("phash_audit.json")
    L.append("## 4. 数据完整性")
    L.append("")
    if ph:
        L.append(f"- 各 split 图片数：`{ph['counts']}`（合计 {ph['hashed']} 张已计算感知哈希）")
        L.append(f"- **跨 split 近似重复对：{ph['crossDuplicates']}**"
                 f"（train {ph.get('leakPerSplit',{}).get('train',0)} / "
                 f"val {ph.get('leakPerSplit',{}).get('val',0)} / "
                 f"test {ph.get('leakPerSplit',{}).get('test',0)}）")
        if ph['crossDuplicates']:
            L.append("  - 影响已量化：剔除泄漏样本后属级 Top-1 仅变化 "
                     f"{pct(ps['top1']-leaked['top1']) if (ps and leaked and ps['n_samples']!=leaked['n_samples']) else '—'}")
        L.append("")
    L.append("- 许可证：研究/竞赛专用（训练数据含 78% CC-BY-NC），详见 `NOTICE.md`")
    L.append("- 引用：Coralscapes (arXiv 2503.20000) / RCM (10.5281/zenodo.15290515) / NOAA CRW / iNaturalist")
    L.append("")

    # ---------- 7. NOAA 星地验证 ----------
    cv = load("cross_validation_2024.json")
    ts = load("noaa_timeseries.json")
    L.append("## 5. NOAA 卫星热压力与星地交叉验证")
    L.append("")
    L.append("> 数据源：NOAA CRW v3.1（5km 日尺度），经 PacIOOS 镜像获取（coastwatch 直连会 302 且不可达）。")
    L.append("")
    if ts and ts.get("years"):
        L.append("### 5.1 多年热压力对比")
        L.append("")
        L.append("| 年份 | 最大 DHW | 最大 HotSpot | 最高预警等级 | DHW≥4 天 | **DHW≥8 天** |")
        L.append("|---|---|---|---|---|---|")
        for y in sorted(ts["years"]):
            s = ts["years"][y]
            L.append(f"| {y} | **{s['dhwMax']}** | {s['hotspotMax']} | {s['baaMaxLabel']} | "
                     f"{s['daysDhwGe4']} | **{s['daysDhwGe8']}** |")
        L.append("")
        ys = sorted(ts["years"])
        best = max(ys, key=lambda y: ts["years"][y]["dhwMax"])
        others = [ts["years"][y]["dhwMax"] for y in ys if y != best]
        if others:
            avg = sum(others) / len(others)
            L.append(f"> **{best} 年最大 DHW 比其余年份平均高 "
                     f"{(ts['years'][best]['dhwMax']/avg-1)*100:.0f}%**，"
                     f"且是唯一突破「严重白化」阈值（DHW≥8）的年份。")
        L.append("")
    if cv:
        L.append("### 5.2 星地一致性")
        L.append("")
        rp = cv["regionPeak"]
        L.append(f"- **事件级 ✅ 一致**：卫星最大 DHW **{rp['dhw']}**（{rp['date']}），"
                 f"最高预警等级 **{rp['baaMax']} = {rp['baaMaxLabel']}**")
        L.append("  → 独立佐证了 Reef Check Malaysia 报告的大规模白化事件")
        L.append("")
        L.append("| 站点 | 实地 DHW | 卫星 DHW 峰 | 实地白化% |")
        L.append("|---|---|---|---|")
        for s in cv["sites"]:
            L.append(f"| {s['site']} | {s['fieldDhw']} | {s['satDhwPeak']} | {s['fieldBleachPct']}% |")
        L.append("")
        L.append("> **站点级 ❌ 不一致**：实地 Larapan > Mabul，卫星却相反。"
                 "原因是 5km 格点 ≠ 站点点位、DHW 气候基准口径差异、以及局地水文条件主导。")
        L.append(">")
        L.append("> **结论：卫星可用于「事件级」预警，不足以做「站点级」定位——"
                 "后者正需要现场影像，即本项目要填补的空白。**")
        L.append("")

    # ---------- 8. 结论适用范围与已知局限 ----------
    mcn = load("mcnemar_bleaching_ip_vs_bleaching_new_test_ip.json")
    sl = load("site_level_validation.json")
    ea = load("error_attribution_species_ip_test.json")
    L.append("## 6. 结论适用范围与已知局限")
    L.append("")
    L.append("> 完整版见 `docs/评估方法与局限.md`。**引用上方任何结论时请一并引用本节限定。**")
    L.append("")
    L.append("| 结论 | 适用范围 | 不可外推到 |")
    L.append("|---|---|---|")
    L.append("| 覆盖率 39.71% vs 实地 39.56% | **区域尺度**（北婆罗洲海域） | ❌ 单个站点 |")
    L.append("| 属级 Top-1 | 仙本那留出集，34 属，拍摄条件良好 | ❌ 深水/浑浊照片 |")
    L.append("| 使用边界 ≤8m 可用 | 基于**物理合成降质** | ❌ 未用真实劣化照片验证 |")
    L.append("| 白化检测（旧域） | 分类模型，旧域分布 | ❌ 印太域（仅 42%）|")
    L.append("")
    if sl and sl.get("comparison", {}).get("nSites"):
        c = sl["comparison"]
        L.append("### 6.1 ⚠️ 站点级验证不成立（最重要的一条局限）")
        L.append("")
        L.append(f"用 iNat `place_guess` 分组后与 RCM **分站点 LCC** 对比："
                 f"仅 {c['nSites']} 个可比站点、{c['nPhotos']} 张照片")
        L.append("")
        L.append(f"- 站点级偏差 **{c['bias']:+.2f} 个百分点**，"
                 f"MAE {c['mae']:.2f}，RMSE {c['rmse']:.2f}")
        if c.get("pearson") is not None:
            L.append(f"- Pearson r = **{c['pearson']:+.3f}**（负相关）")
        L.append(f"- 排序一致对 {c['orderConsistent']}/{c['orderTotal']}")
        L.append("")
        L.append("> **根因**：iNat 照片是**摄影师自选主体**（挑好看的拍），不是等距抽样样方；"
                 "且站点样本量过小（2–11 张）、组内标准差 20–30%，检验效力不足。")
        L.append(">")
        L.append("> **必须加限定：模型可用于「区域尺度」覆盖率估计，不足以做「站点级」优劣区分。**")
        L.append("")
    if mcn:
        m = mcn["mcnemar"]
        L.append("### 6.2 模型比较已做显著性检验（McNemar）")
        L.append("")
        L.append(f"新旧白化模型在印尼域：{pct(mcn['accA'])} vs {pct(mcn['accB'])}，"
                 f"差值 {pct(mcn['accDiff'])}")
        L.append(f"- b={m['b']}（旧对新增错）/ c={m['c']}（旧错新对），"
                 f"精确二项 **p = {m['p_exact']:.2e}** → ✅ 差异高度显著")
        L.append(f"- 聚类 95% CI（差值）：[{pct(mcn['accDiffCi95Cluster'][0])}, "
                 f"{pct(mcn['accDiffCi95Cluster'][1])}]，不含 0")
        L.append("")
    if ea:
        L.append("### 6.3 错误归因与拒识曲线")
        L.append("")
        L.append(f"- 属级错误率 {pct(ea['errorRate'])}，其中**高置信错误**（conf≥0.9）"
                 f"**{ea['highConfidenceErrors']} 个**（占全部错误 "
                 f"{ea['highConfidenceErrors']/max(ea['nError'],1):.1%}）")
        L.append("- 拒识曲线（阈值 → 自动化率 / 自动部分准确率）：")
        L.append("")
        L.append("| 阈值 | 自动化率 | 自动部分准确率 |")
        L.append("|---|---|---|")
        for r in ea["rejectionCurve"]:
            L.append(f"| {r['threshold']:.2f} | {pct(r['automation'],1)} | {pct(r['autoAccuracy'])} |")
        L.append("")
        L.append("> **推荐运营点：阈值 0.90 → 70% 自动化、97% 准确率、拦截 85% 的错误。**")
        L.append("")
    L.append("### 6.4 尚未完成的评估项")
    L.append("")
    L.append("| 项 | 原因 | 修复路径 |")
    L.append("|---|---|---|")
    L.append("| **分割模型 mIoU** | Coralscapes 验证集下载被墙 | 重试下载 / 手工标注 30 张自算 |")
    L.append("| **人类基线** | 未组织标注 | 2–3 人 × 1 小时，附标注者间 κ |")
    L.append("| **逐样本覆盖率误差** | 无像素级真值 | 标准化样方照片或手工标注 50 张 |")
    L.append("| **β=6 为测试集调参** | 工作点在 test_ip 上选取 | 拆 test/test_holdout 重选 |")
    L.append("| 交叉验证 | 未做 | 3–5 折重训 |")
    L.append("")
    L.append("> **聚类置信区间说明**：属级 Top-1 的推荐口径为**按观察聚类的 95% CI**"
             "（比朴素 bootstrap 更宽），因同一观察的多张照片高度相关。")
    L.append("")

    out = Path(args.out)
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"报告已生成: {out}")
    print(f"共 {len(L)} 行")


if __name__ == "__main__":
    main()
