"""
综合研判插件：礁区修复优先级 + 珊瑚苗投放建议 + 保育报告
================================================================
融合两类数据：
    ① 图像研判（Model A/B）：活珊瑚 / 白化 / 死亡 / 藻类覆盖率、珊瑚属多样性
    ② 环境数据插件：NOAA 海温、DHW、白化预警等级（BAA）、热压力趋势

输出：
    · 恢复潜力（Recovery Potential）—— 该海域能否自行恢复、苗能否存活
    · 紧迫度（Urgency）—— 现在需不需要干预
    · 修复优先级（Restoration Priority）—— 综合排序键
    · 苗投放适宜度（Seedling Suitability）—— 指导珊瑚苗投放
    · 自动生成的保育报告

════════════════════════════════════════════════════════════════
⚠️ 定位声明（务必与结果一并引用）
────────────────────────────────────────────────────────────────
本模块输出的是 **基于规则的决策支持启发式（rule-based decision
support heuristic）**，不是经过验证的预测模型。

· 评分维度与权重来自 NOAA CRW 公开标准与珊瑚礁修复文献的通行做法
· 但「哪个点位该优先修复」是**价值判断**，不存在客观 ground truth
· 因此本项目 **不报告任何"准确率"**，只报告评分构成与依据
· 用途：为人工决策**提供排序参考与理由**，不替代专业评估
════════════════════════════════════════════════════════════════

用法：
    from restoration_priority import assess
    r = assess(cover={...}, climate={...}, coral_region={...}, capture_quality={...})
"""
import json
from pathlib import Path

try:
    from climate_context import context_for
    from restoration_simulation import simulate as run_simulation, report_text as sim_report_text
except ImportError:  # 允许独立运行
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from climate_context import context_for
    from restoration_simulation import simulate as run_simulation, report_text as sim_report_text

# ---------------------------------------------------------------- 参考基准
# 各维度的「参考满值」：达到该值即认为该维度满分。
# 依据：Reef Check Malaysia 2024 仙本那区域平均活珊瑚覆盖 39.56%
#       → 取 0.40 作为"健康礁区"参考线。
REF = {
    "alive": 0.40,       # 活珊瑚覆盖率参考满值
    "dead": 0.20,        # 死亡率参考上限（超过则结构完整性 0 分）
    "algae": 0.30,       # 藻类覆盖率参考上限（超过则竞争压力 0 分）
    "bleached": 0.15,    # 白化率参考上限（占珊瑚总量）
    "genusCount": 8,     # 属多样性参考满值
}

# 权重（全部可解释、可调整）
W_RECOVERY = {
    "coralStock": 0.30,   # 活珊瑚存量：恢复的种源
    "structure": 0.20,    # 结构完整性：低死亡 → 框架还在
    "lowAlgae": 0.20,     # 藻类竞争低：幼体有附着空间
    "diversity": 0.15,    # 属多样性：抗逆性与遗传多样性
    "lowThermal": 0.15,   # 低热应激：未来不会反复白化
}
W_URGENCY = {
    "bleaching": 0.40,    # 白化程度：正在发生的威胁
    "mortality": 0.30,    # 死亡率：已发生的损失
    "thermal": 0.30,      # 热应激等级：环境压力
}

# 综合权重：恢复潜力为主（用户要求"优先选择恢复潜力高的海域"）
W_PRIORITY_RECOVERY = 0.55
W_PRIORITY_URGENCY = 0.45


def _clamp01(x):
    return max(0.0, min(1.0, float(x)))


def _s(v, nd=1):
    return round(float(v), nd)


def recovery_potential(cover, climate, genus_count):
    """恢复潜力 0–100：这片海域能否自行恢复 / 投放的苗能否存活。"""
    alive = float(cover.get("alivePct") or 0)
    dead = float(cover.get("deadPct") or 0)
    algae = float(cover.get("algaePct") or 0)
    baa = float(climate.get("baa") or 0)

    parts = {
        "coralStock": _clamp01(alive / REF["alive"]),
        "structure": _clamp01(1 - dead / REF["dead"]),
        "lowAlgae": _clamp01(1 - algae / REF["algae"]),
        "diversity": _clamp01(genus_count / REF["genusCount"]),
        "lowThermal": _clamp01(1 - baa / 4.0),
    }
    score = sum(parts[k] * W_RECOVERY[k] for k in W_RECOVERY) * 100
    return score, {k: _s(v * 100, 1) for k, v in parts.items()}


def urgency(cover, climate):
    """紧迫度 0–100：现在需不需要干预。白化率按「占珊瑚总量」计。"""
    coral_total = float(cover.get("coralTotalPct") or 0)
    bleached = float(cover.get("bleachedPct") or 0)
    dead = float(cover.get("deadPct") or 0)
    baa = float(climate.get("baa") or 0)

    bleach_ratio = (bleached / coral_total) if coral_total > 1e-6 else 0.0
    parts = {
        "bleaching": _clamp01(bleach_ratio / REF["bleached"]),
        "mortality": _clamp01(dead / REF["dead"]),
        "thermal": _clamp01(baa / 4.0),
    }
    score = sum(parts[k] * W_URGENCY[k] for k in W_URGENCY) * 100
    return score, {k: _s(v * 100, 1) for k, v in parts.items()}


def grade(priority: float):
    if priority >= 75:
        return "一级 · 优先投放", "urgent"
    if priority >= 60:
        return "二级 · 建议投放", "high"
    if priority >= 45:
        return "三级 · 可观察", "medium"
    return "四级 · 暂缓", "low"


def _report_text(p, cover, climate, genus, quality, cell):
    """自动生成中文保育报告。"""
    L = []
    L.append("【礁区保育研判报告】")
    L.append("")
    if cell:
        L.append(f"一、点位与气候背景")
        L.append(f"    经纬度：{cell.get('gridCell', {}).get('lat')}°N "
                 f"{cell.get('gridCell', {}).get('lon')}°E（最近 NOAA 5km 格点）")
        L.append(f"    评估年份：{climate.get('year')}")
        if climate.get("dhwMax") is None:
            # 网格外：如实说明"无数据"，不打印 None 让人误以为有值
            L.append(f"    海表热压力：**无数据**（{climate.get('note') or climate.get('baaLabel')}）")
            L.append(f"    说明：该坐标不在本项目 NOAA 网格覆盖范围内，"
                     f"本次研判**未使用**热压力维度。")
        else:
            L.append(f"    海表热压力：DHW 峰值 {climate.get('dhwMax')}，"
                     f"白化预警等级「{climate.get('baaLabel')}」（{climate.get('baa')}/4）")
            L.append(f"    热浪天数：DHW≥4 共 {climate.get('daysDhwGe4')} 天，"
                     f"DHW≥8 共 {climate.get('daysDhwGe8')} 天")
            if climate.get("anomalyNote"):
                L.append(f"    年度对比：{climate['anomalyNote']}")
            L.append(f"    气候解读：{climate.get('verdict')}")
        L.append("")

    L.append("二、图像研判结果")
    L.append(f"    活珊瑚覆盖率：{cover.get('alivePct', 0):.2%}")
    L.append(f"    白化珊瑚占比：{cover.get('bleachedPct', 0):.2%}"
             f"（占珊瑚总量 {p['bleachRatioOfCoral']:.1%}）")
    L.append(f"    死亡珊瑚占比：{cover.get('deadPct', 0):.2%}")
    L.append(f"    藻类覆盖    ：{cover.get('algaePct', 0):.2%}")
    L.append(f"    珊瑚总覆盖  ：{cover.get('coralTotalPct', 0):.2%}")
    if genus:
        L.append(f"    主要珊瑚属  ：{genus}")
    L.append("")

    L.append("三、研判结论")
    L.append(f"    恢复潜力：{p['recovery']['score']:.1f}/100  "
             f"（{'高' if p['recovery']['score'] >= 65 else '中' if p['recovery']['score'] >= 45 else '低'}）")
    L.append(f"    修复紧迫度：{p['urgency']['score']:.1f}/100  "
             f"（{'高' if p['urgency']['score'] >= 65 else '中' if p['urgency']['score'] >= 45 else '低'}）")
    L.append(f"    修复优先级：{p['priority']:.1f}/100 → 【{p['gradeLabel']}】")
    L.append(f"    苗投放适宜度：{p['seedlingSuitability']:.1f}/100")
    L.append("")
    L.append(f"    主要依据：{p['reasoning']}")
    L.append("")

    L.append("四、行动建议")
    for a in p["actions"]:
        L.append(f"    · {a}")
    L.append("")

    if not quality.get("usable", True):
        L.append(f"⚠️ 数据质量提示：{quality.get('message', '拍摄条件不佳')}")
        L.append("    本次评分已按数据质量降级，建议重拍后复评。")
        L.append("")

    if p.get("simulation"):
        L.append("五、修复模拟（10 年恢复轨迹 · 示意性）")
        sim = p["simulation"]
        L.append(f"    起始覆盖 {sim['startAlive']:.2%}，年增长率 r={sim['growthRateUsed']:.3f}，"
                 f"容纳量 K={sim['params']['K']:.0%}")
        for nm, sc in sim["scenarios"].items():
            L.append(f"    · {nm}：{sim['startAlive']:.1%} → {sc['finalAlive']:.1%}"
                     f"（{sc['deltaVsStart']:+.1%}）")
        L.append("    ⚠️ 示意性推演，未做本地参数标定，不得作为预测使用。")
        L.append("")

    L.append("六、定位声明")
    L.append("    本报告由规则型决策支持启发式自动生成，评分维度与权重来自")
    L.append("    NOAA CRW 公开标准与珊瑚礁修复文献的通行做法。")
    L.append("    「优先修复哪个点位」属价值判断，不存在客观标准答案，")
    L.append("    故本报告不提供准确率指标，仅供人工决策参考，不替代专业评估。")
    return "\n".join(L)


def deployment_summary(cover, coral_region, quality, priority, seedling, window,
                       has_coords=True):
    """把「图像侧现状 + 热压力历史 + 苗投放适宜度」合成**一句可直接引用的投放建议**。

    ⚠️ 只用项目确实有的数据：图像侧（覆盖率/白化/死亡/属）与热压力历史（NOAA）。
    **不预测投放效果** —— 项目没有投放后的存活率数据，故只给"该不该投、避开哪几个月"的建议。
    """
    alive = float(cover.get("alivePct") or 0)
    bleach = float(cover.get("bleachedPct") or 0)
    dead = float(cover.get("deadPct") or 0)
    algae = float(cover.get("algaePct") or 0)
    total = float(cover.get("coralTotalPct") or 0)
    top = coral_region.get("top") or []
    genus = top[0].get("genus") if top else None
    genus_txt = f"，优势属 {genus}（{top[0].get('confidence', 0):.0%}）" if genus else ""

    reasons = [
        f"①图像现状：活珊瑚 {alive:.1%}、白化 {bleach:.1%}、死亡 {dead:.1%}、"
        f"藻类 {algae:.1%}、珊瑚总覆盖 {total:.1%}{genus_txt}",
    ]
    if window:
        reasons.append(f"②热压力历史（2023–2025）：{window['label']}；"
                       f"达到警戒的年份 {window.get('alertYears') or '无'}"
                       f"（严重档 {window.get('severeYears') or '无'}）；"
                       f"建议避开 {window.get('avoidMonths') or '无'} 月")
    else:
        reasons.append("②热压力历史：无数据（坐标不在 NOAA 网格覆盖范围内）")
    reasons.append(f"③苗投放适宜度：{seedling:.0f}/100（综合恢复潜力与紧迫度）")

    avoid = (window or {}).get("avoidMonths") or []
    safe = (window or {}).get("safeMonths") or []
    avoid_txt = "、".join(f"{m} 月" for m in avoid)          # 不带"避开"前缀，避免拼接重复
    months_txt = f"避开 {avoid_txt}" if avoid_txt else ""

    # 结论：先看数据是否可用 → 再看热压力历史 → 再看图像现状
    if not quality.get("usable", True):
        verdict = "**建议重拍后再评估**：本次照片拍摄条件不足，覆盖率结论不可靠，暂不建议据此投放。"
    elif (window or {}).get("riskLevel") == "high":
        verdict = ("**不建议在此投放**：近 3 年年年达到白化警戒（DHW≥4）"
                   + (f"，如必须投放应{months_txt}" if months_txt else "") + "。")
    elif total < 0.10 and dead + algae > 0.4:
        verdict = ("**不建议直接投放**：现状珊瑚覆盖过低（"
                   f"{total:.1%}）且死亡+藻类占比高（{dead + algae:.1%}），建议先做环境改良。")
    elif (window or {}).get("riskLevel") == "medium":
        verdict = ("**可以投放，但必须避开高风险月份**（" + (months_txt or "见风险月份") + "）："
                   f"热压力维度为「{window['label']}」。")
    elif window:
        verdict = ("**建议投放**：近 3 年热压力未达警戒，"
                   + (f"且 {('、'.join(f'{m} 月' for m in safe))} 无风险信号；" if safe else "")
                   + f"现状活珊瑚 {alive:.1%}、珊瑚总覆盖 {total:.1%}。")
    else:
        # 没有热压力依据时：图像维度仍可判，但**不能**给出完整投放结论
        tail = ("该坐标不在 NOAA 网格内，**缺少季节窗口与历史热压力依据**，不作为最终投放结论。"
                if has_coords else
                "**未提供经纬度**，无法给出季节窗口与历史热压力依据，不作为最终投放结论。")
        verdict = (f"**图像维度可投放**：现状活珊瑚 {alive:.1%}、珊瑚总覆盖 {total:.1%}；⚠️ 但{tail}")

    return {
        "verdict": verdict,
        "reasons": reasons,
        "avoidMonths": avoid,
        "recommendedMonths": safe,
        "seedlingSuitability": round(float(seedling), 1),
        "priority": round(float(priority), 1),
        # 可直接展示/照念的整段文本（放在**新字段**里，避免改动已有的 report 字段）
        "summaryText": "\n".join(
            ["【投放建议】", f"    {verdict}"]
            + [f"    {r}" for r in reasons]
            + ["    ⚠️ 依据 = 图像侧实测指标 + 往年热压力记录；**不是投放效果预测**"
               "（项目无投放后存活率数据）。热压力样本仅 2023–2025、5km 格点。"]),
        "note": ("依据 = 图像侧实测指标 + 往年热压力记录；**不是投放效果预测**"
                 "（项目无投放后存活率数据）。热压力样本仅 2023–2025、5km 格点。"),
    }


def assess(cover, climate=None, coral_region=None, capture_quality=None,
           lat=None, lon=None, year=None, cell=None, profile=None):
    """
    cover:          {alivePct, bleachedPct, deadPct, algaePct, coralTotalPct, ...}
    climate:        由 climate_context.context_for() 返回；不给则用 lat/lon 查
    coral_region:   {top: [{genus, confidence}], reliable: bool}
    capture_quality:{level, usable, message, contrast}
    """
    cover = cover or {}
    coral_region = coral_region or {}
    capture_quality = capture_quality or {}

    # 环境数据：未提供则按坐标查询
    cell = cell or None
    if climate is None and lat is not None and lon is not None:
        climate = context_for(lat, lon, year)
        cell = climate
    # climate_context 在**网格外**会返回 ok=False（宁可报缺数据也不给最近的错格点）：
    # 这里要如实降级为「气候数据缺失」，并让报告文字说清原因，而不是打印一串 None。
    climate_available = bool(climate) and climate.get("ok") is not False
    if not climate_available:
        err = (climate or {}).get("error")
        climate = {"baa": 0, "baaLabel": "数据缺失", "dhwMax": None, "source": "无",
                   "year": (climate or {}).get("year") or year,
                   "note": err or "未提供坐标或环境数据"}

    # 历史热压力档案（往年白化预警记录 → 投放时间窗）。未提供则按坐标查。
    # 覆盖闸门与气候插件一致：网格外返回 ok=False，此时不产出投放建议。
    if profile is None and lat is not None and lon is not None:
        try:
            from climate_site_profile import profile_for as _profile_for
            profile = _profile_for(lat, lon)
        except Exception as e:                      # 档案缺失/损坏都不该拖垮主结果
            profile = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    top = coral_region.get("top") or []
    if coral_region.get("reliable") is False:
        top = []
    genus_list = [t.get("genus") for t in top if t.get("genus")]
    genus_count = len(genus_list)
    genus_txt = "、".join(f"{t.get('genus')}({t.get('confidence', 0):.0%})"
                          for t in top[:3]) if top else ""

    rec, rec_parts = recovery_potential(cover, climate, genus_count)
    urg, urg_parts = urgency(cover, climate)

    coral_total = float(cover.get("coralTotalPct") or 0)
    bleach_ratio = (float(cover.get("bleachedPct") or 0) / coral_total) if coral_total > 1e-6 else 0.0

    priority = W_PRIORITY_RECOVERY * rec + W_PRIORITY_URGENCY * urg
    # 苗投放适宜度：既要「能活」（恢复潜力），也要「需要」（紧迫度）
    seedling = rec * (0.6 + 0.4 * urg / 100.0)

    # 数据质量闸门：拍得差就不给高分
    quality_penalty = None
    if not capture_quality.get("usable", True):
        if priority > 50:
            quality_penalty = f"拍摄条件不佳（{capture_quality.get('level')}），优先级由 {priority:.1f} 降至 50"
            priority = 50.0
        if seedling > 50:
            seedling = 50.0

    grade_label, grade_key = grade(priority)

    # 生成依据说明
    drivers = sorted(
        [("恢复潜力", rec), ("紧迫度", urg)], key=lambda x: -x[1])
    weak = sorted(rec_parts.items(), key=lambda kv: kv[1])[:2]
    reasoning = (
        f"恢复潜力 {rec:.0f} 分，主要由 "
        + "、".join(f"{k}{v:.0f}" for k, v in
                    sorted(rec_parts.items(), key=lambda kv: -kv[1])[:2])
        + " 贡献；热应激维度受 NOAA 等级「"
        + str(climate.get("baaLabel")) + "」约束。"
        + f"紧迫度 {urg:.0f} 分，"
        + "、".join(f"{k}{v:.0f}" for k, v in
                    sorted(urg_parts.items(), key=lambda kv: -kv[1])[:2])
        + " 是主要来源。"
        + (f" 短板：{weak[0][0]} 仅 {weak[0][1]:.0f} 分。" if weak else "")
    )

    # 行动建议：按「约束优先级」组织，先给出真正的瓶颈，再谈投放时机
    #   逻辑：环境窗口（热压力）与场地条件（恢复潜力）是两个硬约束，
    #   任一不满足都不应投放；两者都满足才进入排序比较。
    actions = []
    baa = climate.get("baa", 0)
    thermal_ok = baa <= 1          # 无压力 / 白化观察 → 窗口期可用
    site_ok = rec >= 45            # 场地具备基本恢复条件

    # —— ① 硬约束判定：先回答「能不能投」 ——
    if not thermal_ok and not site_ok:
        actions.append(
            f"**双重不利，建议暂缓**：该海域处于「{climate.get('baaLabel')}」"
            f"（DHW 峰值 {climate.get('dhwMax')}），且场地恢复潜力仅 {rec:.0f} 分，"
            "当前投放存活率低，建议先做环境改良并等待热浪过后的窗口期")
    elif not thermal_ok:
        if baa >= 3:
            actions.append(
                f"**暂不宜投放**：该海域处于「{climate.get('baaLabel')}」"
                f"（DHW 峰值 {climate.get('dhwMax')}，DHW≥8 共 {climate.get('daysDhwGe8')} 天），"
                "建议等热浪过后（DHW 回落至 4 以下）再复评")
        else:
            actions.append(
                f"**建议苗圃暂养**：热压力为「{climate.get('baaLabel')}」，"
                "场地本身条件尚可，待本季热浪结束、确认无二次白化后投放")
    elif not site_ok:
        actions.append(
            f"**建议先做环境改良**：当前热窗口期合适，但场地恢复潜力仅 {rec:.0f} 分"
            + ("（藻类覆盖偏高，挤占幼体附着空间）"
               if float(cover.get("algaePct") or 0) > 0.20 else "（活珊瑚种源不足）")
            + "，建议清除藻类/补充基质后再投放，直接投放存活率有限")

    # —— ② 排序比较：能投的话，按最终优先级给出与评级一致的结论 ——
    if thermal_ok and site_ok:
        if priority >= 75:
            actions.append("恢复潜力与紧迫度双高——**本次研判的最优先投放区**，建议优先安排苗投放")
        elif priority >= 60:
            actions.append("综合条件良好——**建议投放区**，可安排常规规模投放并跟踪存活率")
        elif priority >= 45:
            actions.append("条件中等——列为**保育备选区**，建议先小规模试投或保持年度监测")
        else:
            actions.append("条件一般且压力不大，**暂不安排投放**，保持监测即可")

    # —— ③ 补充性建议 ——
    if bleach_ratio > 0.25:
        actions.append(f"白化占珊瑚总量 {bleach_ratio:.0%}，建议优先开展白化监测与共栖生物普查")
    if float(cover.get("algaePct") or 0) > 0.20 and site_ok:
        actions.append(
            f"藻类覆盖 {float(cover.get('algaePct')):.0%} 偏高，投放前建议先做小面积藻类清除")
    if not coral_region.get("reliable", True):
        actions.append("属级识别置信度不足，多样性维度已按 0 计，建议补拍珊瑚主体特写")
    if genus_count == 0:
        actions.append("本次未获得属级多样性信息，该维度权重已均摊至其他维度")

    # ---- 修复模拟：投放后的恢复轨迹（示意性）----
    sim = run_simulation(
        alive0=float(cover.get("alivePct") or 0),
        algae0=float(cover.get("algaePct") or 0),
        genus_count=genus_count,
        years=10,
        seedling=seedling,
    )
    sim_txt = sim_report_text(sim, cover, climate, seedling)

    # 投放时间窗：把「往年白化预警记录」转成一句可执行建议（网格外/档案缺失 → None）
    deployment_window = None
    if profile and profile.get("ok"):
        adv = profile.get("advice") or {}
        deployment_window = {
            "label": profile.get("label"),
            "riskLevel": profile.get("riskLevel"),
            "alertYears": profile.get("alertYears"),
            "severeYears": profile.get("severeYears"),
            "riskyMonths": profile.get("riskyMonths"),
            "heatMonths": profile.get("heatMonths"),
            "avoidMonths": profile.get("avoidMonths"),
            "safeMonths": profile.get("safeMonths"),
            "text": adv.get("text"),
            "note": profile.get("adviceNote"),
            "source": "reports/deployment_windows.json（NOAA CRW 2023–2025 日数据聚合）",
        }

    # 投放建议汇总：一句话结论 + 三条依据（供前端/汇报直接引用）
    deployment_advice = deployment_summary(cover, coral_region, capture_quality,
                                          priority, seedling, deployment_window,
                                          has_coords=(lat is not None and lon is not None))

    result = {
        "ok": True,
        # 新增（附加字段）：本次研判是否真的用到了气候数据
        "climateAvailable": climate_available,
        "method": "rule-based decision support heuristic（规则型决策支持启发式）",
        "simulation": sim,
        "simulationReport": sim_txt,
        "disclaimer": (
            "本结果为基于规则的决策支持参考，非经验证的预测模型，"
            "不提供准确率指标，不替代专业珊瑚礁评估。"
        ),
        "priority": _s(priority, 1),
        "grade": grade_key,
        "gradeLabel": grade_label,
        "seedlingSuitability": _s(seedling, 1),
        "recovery": {"score": _s(rec, 1), "components": rec_parts,
                     "weights": W_RECOVERY},
        "urgency": {"score": _s(urg, 1), "components": urg_parts,
                    "weights": W_URGENCY},
        "priorityWeights": {"recovery": W_PRIORITY_RECOVERY,
                            "urgency": W_PRIORITY_URGENCY},
        "bleachRatioOfCoral": _s(bleach_ratio, 4),
        "genusDiversity": {"count": genus_count, "genera": genus_list},
        "climate": {k: climate.get(k) for k in
                    ("year", "dhwMax", "baa", "baaLabel", "daysDhwGe4",
                     "daysDhwGe8", "peakDate", "verdict", "anomalyNote",
                     "gridCell", "source")},
        "qualityPenalty": quality_penalty,
        "reasoning": reasoning,
        "actions": actions,
        # 新增（附加字段）：历史热压力档案 → 投放时间窗建议（网格外或档案缺失时为 None）
        "deploymentWindow": deployment_window,
        # 新增（附加字段）：合成后的「投放建议」（一句结论 + 三条依据 + 月份）
        "deploymentAdvice": deployment_advice,
    }
    result["report"] = _report_text(result, cover, climate, genus_txt,
                                    capture_quality, cell)
    return result


def main():
    import argparse
    ap = argparse.ArgumentParser(description="礁区修复优先级研判（规则型）")
    ap.add_argument("--alive", type=float, required=True, help="活珊瑚覆盖率 0-1")
    ap.add_argument("--bleached", type=float, default=0.0)
    ap.add_argument("--dead", type=float, default=0.0)
    ap.add_argument("--algae", type=float, default=0.0)
    ap.add_argument("--substrate", type=float, default=0.0)
    ap.add_argument("--genera", default="", help="逗号分隔的珊瑚属")
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--year", type=int)
    ap.add_argument("--quality", default="good", choices=["good", "warn", "poor"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    total = args.alive + args.bleached + args.dead
    cover = {"alivePct": args.alive, "bleachedPct": args.bleached,
             "deadPct": args.dead, "algaePct": args.algae,
             "substratePct": args.substrate, "coralTotalPct": total}
    gens = [g.strip() for g in args.genera.split(",") if g.strip()]
    region = {"reliable": bool(gens),
              "top": [{"genus": g, "confidence": 0.8} for g in gens]}

    r = assess(cover=cover, lat=args.lat, lon=args.lon, year=args.year,
               coral_region=region,
               capture_quality={"level": args.quality,
                                "usable": args.quality != "poor"})
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(r["report"])


if __name__ == "__main__":
    main()
