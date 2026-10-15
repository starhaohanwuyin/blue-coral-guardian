"""
生成"算法层"图表（全部基于仓库既有评测结果，不重训、不改数字）
=================================================================

用法（在 ai-service 目录下）：
    python tools/make_algo_figures.py

输出到 ../docs/images/algo/ ：
    algo_arch.png          算法流水线示意
    algo_degradation.png   5 级降质下的覆盖率偏差（≤8m 可用 / 15m 失效）
    algo_calibration.png   可靠性（校准）曲线 —— 属模型 + 白化模型
    algo_rejection.png     拒识-自动化率权衡曲线
    algo_cross_domain.png  跨海域/跨数据集对比（宏 F1 + 白化类 F1）
    algo_confusion.png     34 属混淆 TOP 错配对 + 每类错误率

每张图右下角标注数据来源文件，便于评审核查。
"""
import json
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = pathlib.Path(__file__).resolve().parents[1]          # ai-service/
OUT = ROOT.parent / "docs" / "images" / "algo"
R = ROOT / "reports"

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 150
plt.rcParams["savefig.dpi"] = 150
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.25

C_ALIVE = "#2E7D32"
C_TOTAL = "#1565C0"
C_WARN = "#E65100"
C_BAD = "#C62828"


def load(name):
    return json.loads((R / name).read_text(encoding="utf-8"))


def save(fig, name, note):
    fig.text(0.99, 0.005, f"数据来源：{note}", ha="right", va="bottom",
             fontsize=6.5, color="#666666")
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  ✅ {name}")


# ---------------------------------------------------------------- 1 架构示意
def fig_arch():
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    ax.set_axis_off()
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 46)

    def box(x, y, w, h, text, color, fs=8.5, tc="white"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=1.4",
                                    linewidth=0, facecolor=color))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fs, color=tc, linespacing=1.5)

    def arrow(x1, y1, x2, y2, color="#90A4AE"):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                     mutation_scale=12, linewidth=1.4, color=color))

    ax.text(50, 43.5, "珊瑚卫士 · 算法层流水线", ha="center", fontsize=13, fontweight="bold")
    ax.text(50, 40.2, "一张水下照片 → 覆盖率 / 珊瑚属 / 白化状态 / 个体数 → 与环境数据耦合 → 可解释研判 + 中英报告",
            ha="center", fontsize=8.2, color="#555555")

    box(2, 24, 17, 12, "输入\n水下照片\n(手机/相机)", "#455A64")
    box(23, 24, 18, 12, "① 语义分割\nSegFormer-B2\n40 类底栖 · 1024px", "#1565C0")
    box(45, 24, 16, 12, "② 珊瑚属识别\nConvNeXt-Tiny\n34 属", "#00838F")
    box(65, 24, 16, 12, "③ 白化状态\n双模型共识\n健康/白化/死亡", "#6A1B9A")
    box(85, 24, 13, 12, "④ 个体计数\nYOLOv9c\n(附加)", "#4E342E")

    box(23, 8, 18, 11, "覆盖率输出\n活珊瑚/白化/死亡\n藻类/沙砾（6 功能群）", "#E3F2FD", fs=8, tc="#0D47A1")
    box(45, 8, 16, 11, "属级结论\n+ 置信度", "#E0F7FA", fs=8, tc="#006064")
    box(65, 8, 16, 11, "共识弃权\n一致→采信\n分歧→人工复核", "#F3E5F5", fs=7.6, tc="#4A148C")
    box(85, 8, 13, 11, "个体数\n+ 位置", "#EFEBE9", fs=8, tc="#3E2723")

    box(2, 8, 17, 11, "⑤ NOAA CRW\n41 年逐日\nDHW/HotSpot/BAA", "#FFF3E0", fs=8, tc="#E65100")

    for x in (32, 53, 73, 91.5):
        arrow(x, 24, x, 19)
    arrow(19, 30, 23, 30)
    arrow(41, 30, 45, 30)
    arrow(61, 30, 65, 30)
    arrow(81, 30, 85, 30)
    arrow(10.5, 19, 23, 13.5, "#E65100")

    box(30, 0.5, 46, 5.2, "⑥ 规则型保育研判（可解释）→ 修复优先级 / 投放时间窗 / 中英文报告",
        "#2E7D32", fs=8.6)
    for x in (32, 53, 73):
        arrow(x, 8, x, 5.8, "#78909C")
    arrow(85, 13.5, 76, 3.4, "#78909C")
    arrow(10.5, 8, 30, 3.0, "#E65100")

    save(fig, "algo_arch.png", "本仓库 代码结构（scripts/serve_fusion.py 等）")


# ---------------------------------------------------------------- 2 降质曲线
def fig_degradation():
    rows = load("degradation_modelA_base.json")["rows"]
    labels = [f"{r['desc']}" for r in rows]
    alive = [r["alive"] * 100 for r in rows]
    total = [r["coral_total"] * 100 for r in rows]
    base_a, base_t = alive[0], total[0]

    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    x = range(len(rows))
    ax.axvspan(2.5, 4.5, color="#FFEBEE", zorder=0)
    ax.text(3.5, 34, "完全失效\n（预测为 0）", ha="center", fontsize=9, color=C_BAD)
    ax.plot(x, alive, "o-", color=C_ALIVE, linewidth=2.2, markersize=7, label="活珊瑚覆盖率")
    ax.plot(x, total, "s-", color=C_TOTAL, linewidth=2.2, markersize=6.5, label="珊瑚总覆盖")
    ax.axhline(base_a, color=C_ALIVE, linestyle=":", linewidth=1, alpha=0.6)
    ax.axhline(base_t, color=C_TOTAL, linestyle=":", linewidth=1, alpha=0.6)

    for i in (1, 2):
        ax.annotate(f"{alive[i]-base_a:+.1f}pt", (i, alive[i]), textcoords="offset points",
                    xytext=(0, -16), ha="center", fontsize=8.5, color=C_ALIVE, fontweight="bold")
        ax.annotate(f"{total[i]-base_t:+.1f}pt", (i, total[i]), textcoords="offset points",
                    xytext=(0, 9), ha="center", fontsize=8.5, color=C_TOTAL, fontweight="bold")
    ax.annotate("8m 时活珊瑚仅 −2.2pt\n（珊瑚总覆盖 −3.1pt）", xy=(2, alive[2]),
                xytext=(0.75, 20), fontsize=8.6, color="#333333",
                arrowprops=dict(arrowstyle="->", color="#666666", lw=1))

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=8.6)
    ax.set_ylabel("模型输出覆盖率（%）", fontsize=9.5)
    ax.set_ylim(-3, 48)
    ax.set_title("使用边界：水深 ≤8m 可用，15m 起完全失效（5 级降质 × 180 张实拍）",
                 fontsize=11, fontweight="bold")
    ax.legend(fontsize=9, loc="upper right")
    save(fig, "algo_degradation.png", "reports/degradation_modelA_base.json")


# ---------------------------------------------------------------- 3 校准曲线
def fig_calibration():
    genus = load("protocol_species_ip_test_clean.json")
    bleach = load("protocol_bleaching_new_test_clean.json")
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.3))
    for ax, d, title in [(axes[0], genus, "34 属识别（n=1,088）"),
                         (axes[1], bleach, "白化二分类（n=168）")]:
        bins = d.get("reliabilityBins") or []
        conf = [b["avgConf"] for b in bins]
        acc = [b["acc"] for b in bins]
        ns = [b["n"] for b in bins]
        sizes = [max(18, min(180, n * 4)) for n in ns]
        ax.plot([0, 1], [0, 1], "--", color="#9E9E9E", linewidth=1, label="完美校准")
        ax.scatter(conf, acc, s=sizes, color="#1565C0", alpha=0.75, zorder=3,
                   label="实测（点大小=样本数）")
        ax.bar(conf, [a - c for a, c in zip(acc, conf)], width=0.045, bottom=conf,
               color=C_BAD, alpha=0.35, label="校准偏差")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.02)
        ax.set_xlabel("模型置信度", fontsize=9)
        ax.set_ylabel("实际准确率", fontsize=9)
        ax.set_title(f"{title}\nECE = {d['ece']:.3f}（越低越可信）", fontsize=10.5)
        ax.legend(fontsize=7.8, loc="upper left")
    fig.suptitle("可靠性（校准）曲线：模型说的置信度和真实正确率有多接近",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0.02, 1, 0.94))
    save(fig, "algo_calibration.png",
         "protocol_species_ip_test_clean.json + protocol_bleaching_new_test_clean.json")


# ---------------------------------------------------------------- 4 拒识曲线
def fig_rejection():
    d = load("error_attribution_species_ip_test.json")
    rc = d["rejectionCurve"]
    auto = [p["automation"] * 100 for p in rc]
    acc = [p["autoAccuracy"] * 100 for p in rc]
    th = [p["threshold"] for p in rc]

    fig, ax = plt.subplots(figsize=(7.8, 4.5))
    ax.plot(auto, acc, "o-", color="#1565C0", linewidth=2.2, markersize=7)
    for a, c, t in zip(auto, acc, th):
        ax.annotate(f"阈值 {t:g}", (a, c), textcoords="offset points", xytext=(6, -12),
                    fontsize=8, color="#444444")
    ax.axhline(acc[0], color="#9E9E9E", linestyle=":", linewidth=1)
    ax.set_xlabel("自动判定比例（不转人工的比例，%）", fontsize=9.5)
    ax.set_ylabel("自动判定部分的准确率（%）", fontsize=9.5)
    ax.set_title("拒识-自动化权衡：把不确定的样本交给人工，剩下的更准",
                 fontsize=11, fontweight="bold")
    ax.set_ylim(min(acc) - 3, max(acc) + 3)
    ax.invert_xaxis()
    ax.text(0.98, 0.06,
            f"全自动：{acc[0]:.1f}%  →  转人工 {100-auto[-1]:.0f}% 后：{max(acc):.1f}%",
            transform=ax.transAxes, ha="right", fontsize=9, color="#333333",
            bbox=dict(boxstyle="round,pad=0.45", facecolor="#F5F5F5", edgecolor="#DDDDDD"))
    save(fig, "algo_rejection.png", "reports/error_attribution_species_ip_test.json")


# ---------------------------------------------------------------- 5 跨海域对比
def fig_cross_domain():
    items = [
        ("太平洋岛屿\n(二分类)", "matrix_pacific_multidomain4.json"),
        ("Koh Tao 湿季\n(三分类)", "matrix_winter_multidomain4.json"),
        ("Arafura\n(三分类)", "matrix_external_multidomain4.json"),
    ]
    labels, macros, bleached, ns = [], [], [], []
    for lab, f in items:
        d = load(f)
        sl = d["singleLabel"]
        labels.append(lab)
        macros.append(sl["macroF1"])
        bleached.append(sl["perClass"]["bleached"]["f1"])
        ns.append(d.get("samplesEvaluated") or sl.get("samples"))

    import numpy as np
    x = np.arange(len(labels))
    w = 0.36
    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    b1 = ax.bar(x - w / 2, macros, w, label="宏 F1", color="#1565C0")
    b2 = ax.bar(x + w / 2, bleached, w, label="白化类 F1", color="#E65100")
    for bars, vals in ((b1, macros), (b2, bleached)):
        for rect, v in zip(bars, vals):
            ax.text(rect.get_x() + rect.get_width() / 2, v + 0.015, f"{v:.3f}",
                    ha="center", fontsize=8.6, fontweight="bold")
    for i, n in enumerate(ns):
        ax.text(i, 0.02, f"n={n}", ha="center", fontsize=8.2, color="#333333")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("F1", fontsize=9.5)
    ax.set_title("跨海域表现差异很大 —— 必须分海域、分指标看（指标口径已在图注写明）",
                 fontsize=10.6, fontweight="bold")
    ax.legend(fontsize=9, loc="upper right")
    save(fig, "algo_cross_domain.png",
         "reports/matrix_{pacific,winter,external}_multidomain4.json")


# ---------------------------------------------------------------- 6 混淆分析
def fig_confusion():
    d = load("error_attribution_species_ip_test.json")
    tc = d["topConfusions"][:10][::-1]
    pce = d["perClassError"]
    worst = sorted([(k, v) for k, v in pce.items() if v["n"] >= 8],
                   key=lambda kv: kv[1]["rate"])[-10:]

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.8))
    ax = axes[0]
    names = [f"{t['true']} → {t['pred']}" for t in tc]
    cnt = [t["count"] for t in tc]
    ax.barh(names, cnt, color="#C62828", alpha=0.85)
    for i, v in enumerate(cnt):
        ax.text(v + 0.06, i, str(v), va="center", fontsize=8)
    ax.set_xlabel("误判次数", fontsize=9)
    ax.set_title("最常混淆的属对（TOP 10）", fontsize=10.5)
    ax.tick_params(labelsize=8.2)
    ax.grid(axis="y", visible=False)

    ax = axes[1]
    names2 = [k for k, _ in worst]
    rates = [v["rate"] * 100 for _, v in worst]
    ns2 = [v["n"] for _, v in worst]
    ax.barh(names2, rates, color="#1565C0", alpha=0.85)
    for i, (r, n) in enumerate(zip(rates, ns2)):
        ax.text(r + 1, i, f"{r:.0f}%  (n={n})", va="center", fontsize=7.8)
    ax.set_xlabel("该类错误率（%）", fontsize=9)
    ax.set_xlim(0, max(rates) * 1.35)
    ax.set_title("错误率最高的属（只统计样本数 ≥8 的类）", fontsize=10.5)
    ax.tick_params(labelsize=8.2)
    ax.grid(axis="y", visible=False)

    fig.suptitle("错误归因：错在哪、为什么错（对应「建议人工复核」的拒识设计）",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0.02, 1, 0.93))
    save(fig, "algo_confusion.png", "reports/error_attribution_species_ip_test.json")


if __name__ == "__main__":
    print(f"输出目录：{OUT}")
    fig_arch()
    fig_degradation()
    fig_calibration()
    fig_rejection()
    fig_cross_domain()
    fig_confusion()
    print("完成。")
