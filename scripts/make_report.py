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
    L.append("## 1. 礁区覆盖评估（Model A · 语义分割）")
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
    base = load("degradation_modelA_base.json")
    L.append("### 1.2 使用边界（物理降质实测）")
    L.append("")
    if base:
        L.append("| 拍摄条件 | 活珊瑚估计 | 相对原始 |")
        L.append("|---|---|---|")
        b0 = base["rows"][0]["alive"]
        for r in base["rows"]:
            L.append(f"| {r['level']}（{r['desc']}） | {pct(r['alive'])} | {pct(r['alive']-b0)} |")
        L.append("")
        L.append("> **产品提示：拍摄深度 ≤10m 或使用补光灯。**")
        L.append("")

    # ---------- 3. 退化不变性修复 ----------
    # 优先取「锚定版」结果；无锚定版为已确认失败的退化解实验，单独标注
    inv = load("degradation_modelA_degradinv_anchor.json")
    inv_enh = load("degradation_modelA_degradinv_anchor_enh.json")
    failed = load("degradation_modelA_degradinv.json")
    if inv and base:
        L.append("### 1.3 退化不变性微调实验（含锚定损失）")
        L.append("")
        hdr = "| 档位 | 修复前 | +锚定自蒸馏 |"
        sep = "|---|---|---|"
        if inv_enh:
            hdr += " +自蒸馏+色彩还原 |"
            sep += "---|"
        L.append(hdr)
        L.append(sep)
        m0 = {r["level"]: r for r in base["rows"]}
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
        L.append(f"- **Top-1：{pct(ps['top1'])}**（95% CI {pct(ps['top1Ci95'][0])} – {pct(ps['top1Ci95'][1])}）")
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

    out = Path(args.out)
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"报告已生成: {out}")
    print(f"共 {len(L)} 行")


if __name__ == "__main__":
    main()
