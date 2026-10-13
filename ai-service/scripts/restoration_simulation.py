"""
修复模拟：珊瑚苗投放后的恢复轨迹推演（原方案 Skill 3「修复模拟」）
================================================================
输入：当前覆盖率 + 修复优先级研判结果 + 该点位历史/未来热压力情景
输出：未来 N 年的珊瑚覆盖率推演曲线 + 情景对比

════════════════════════════════════════════════════════════════
⚠️ 重要定位声明
────────────────────────────────────────────────────────────────
这是一个 **示意性（illustrative）** 的生态推演模型：

· 采用文献中常见的**逻辑斯蒂增长 + 热浪致死**简化形式
· 参数取自公开文献的**中位数量级**，**未针对仙本那做参数标定**
· 没有真实修复后的逐年监测数据可用于验证
· **因此不得作为预测使用**，仅用于说明「投放 vs 不投放」「热浪情景」的
  相对差异，帮助理解决策方向

本模型**不输出任何准确率或置信区间**。
════════════════════════════════════════════════════════════════
"""
import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"

# ---------------------------------------------------------------- 参数
# 均取自公开文献的常见量级（珊瑚覆盖率年变化），未做本地标定
PARAMS = {
    # 内禀增长率 r（覆盖率的相对增长速率，每年）
    #   分枝状珊瑚恢复快（Acropora 可 10+ cm/yr），块状慢
    "r_branching": 0.18,
    "r_massive": 0.08,
    "r_mixed": 0.12,
    # 环境容纳量 K（健康礁区覆盖率上限）
    "K": 0.60,
    # 严重热浪（BAA>=3）时的珊瑚部分死亡率
    "mortality_severe": 0.15,    # 死亡 15% 的现有覆盖
    "mortality_alert2": 0.35,    # BAA=4 时更重
    "mortality_warning": 0.05,   # BAA=2 轻微
    # 苗投放：每单位适宜度的年增量（覆盖率绝对值）
    "seed_per_year": 0.020,
    # 藻类对恢复的抑制（藻类覆盖越高，有效增长率越低）
    "algae_penalty": 0.60,
}


def _growth_rate(alive, algae, genus_count, p=PARAMS):
    """按珊瑚形态与藻类压力给出有效增长率。"""
    if genus_count >= 6:
        base = p["r_mixed"]
    elif genus_count >= 3:
        base = (p["r_branching"] + p["r_massive"]) / 2
    else:
        base = p["r_massive"]
    # 藻类竞争抑制
    return base * (1 - p["algae_penalty"] * min(algae / 0.30, 1.0))


def simulate(alive0, algae0=0.10, genus_count=0, years=10,
             seedling=0.0, scenarios=None, p=PARAMS):
    """
    scenarios: {名称: [每年热浪等级(BAA)], ...}
               等级 0-4，长度应 >= years；缺省用「无热浪」
    返回 {情景: {"curve": [...], "finalAlive": x, "note": ...}}
    """
    scenarios = scenarios or {"无热浪（理想）": [0] * years,
                              "2024 型事件复现": [3] * years,
                              "五年一遇": [0, 0, 0, 0, 3] + [0] * max(0, years - 5)}
    r = _growth_rate(alive0, algae0, genus_count, p)
    out = {}
    for name, baa_seq in scenarios.items():
        c = alive0
        curve = [round(c, 4)]
        for t in range(years):
            baa = baa_seq[t] if t < len(baa_seq) else 0
            # ① 逻辑斯蒂生长
            growth = r * c * max(0.0, 1 - c / p["K"])
            # ② 苗投放增量（按适宜度缩放）
            seed = p["seed_per_year"] * max(0.0, min(seedling / 100.0, 1.0))
            # ③ 热浪致死
            if baa >= 4:
                mort = p["mortality_alert2"] * c
            elif baa >= 3:
                mort = p["mortality_severe"] * c
            elif baa == 2:
                mort = p["mortality_warning"] * c
            else:
                mort = 0.0
            c = max(0.0, min(p["K"], c + growth + seed - mort))
            curve.append(round(c, 4))
        out[name] = {
            "curve": curve,
            "finalAlive": round(curve[-1], 4),
            "deltaVsStart": round(curve[-1] - alive0, 4),
            "severeYears": sum(1 for b in baa_seq[:years] if b >= 3),
        }
    return {"startAlive": round(alive0, 4), "growthRateUsed": round(r, 4),
            "years": years, "scenarios": out, "params": p}


def report_text(sim, cover, climate, priority):
    L = ["【修复模拟 · 恢复轨迹推演（示意）】", ""]
    L.append(f"起始活珊瑚覆盖：{sim['startAlive']:.2%}")
    L.append(f"采用的年增长率 r：{sim['growthRateUsed']:.3f}"
             f"（由藻类压力与珊瑚属数推定）")
    L.append(f"环境容纳量 K：{sim['params']['K']:.0%}")
    if priority is not None:
        L.append(f"苗投放适宜度：{priority:.0f}/100 → 年投放增量 "
                 f"{sim['params']['seed_per_year'] * priority / 100:.2%}")
    L.append("")
    L.append("情景对比：")
    for name, s in sim["scenarios"].items():
        L.append(f"  · {name}：{sim['startAlive']:.1%} → {s['finalAlive']:.1%}"
                 f"（{s['deltaVsStart']:+.1%}）"
                 + (f"，其中 {s['severeYears']} 年遇严重热浪" if s["severeYears"] else ""))
    L.append("")
    L.append("逐年曲线（覆盖率）：")
    for name, s in sim["scenarios"].items():
        L.append(f"  {name}: " + " → ".join(f"{v:.1%}" for v in s["curve"]))
    L.append("")
    L.append("⚠️ 本模拟为**示意性推演**，采用文献常见量级的简化模型，"
             "未针对仙本那做参数标定，也无真实修复后监测数据可用于验证。"
             "**不得作为预测使用**，仅用于比较不同情景的相对差异。")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="修复模拟（示意性）")
    ap.add_argument("--alive", type=float, required=True)
    ap.add_argument("--algae", type=float, default=0.10)
    ap.add_argument("--genera", type=int, default=0, help="珊瑚属数量")
    ap.add_argument("--seedling", type=float, default=60.0, help="苗投放适宜度 0-100")
    ap.add_argument("--years", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    sim = simulate(args.alive, args.algae, args.genera, args.years, args.seedling)
    if args.json:
        print(json.dumps(sim, ensure_ascii=False, indent=2))
    else:
        print(report_text(sim, {}, {}, args.seedling))


if __name__ == "__main__":
    main()
