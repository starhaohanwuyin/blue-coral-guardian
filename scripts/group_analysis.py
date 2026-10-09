"""
类群归并分析
================================================================
细粒度识别的客观难点：部分物种在自然光水下照片里肉眼都难分
（例如同为脑珊瑚科的 Diploria strigosa 与 Colpophyllia natans）。
学术界通行做法是给出「分层评估」：

  物种级（30 类）  →  属/类群级（归并易混类）→  功能群级

本脚本从已有混淆矩阵直接换算各层级的准确率，无需重新训练。

用法：
    python group_analysis.py --task species
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 可选的归并方案（按"证据强度"递进）
SCENARIOS = {
    "物种级(30类)": [],

    "① 归并脑珊瑚科": [
        ["Diploria Strigosa", "Colpophyllia Natans"],
    ],

    "② + 归并真叶珊瑚属": [
        ["Diploria Strigosa", "Colpophyllia Natans"],
        ["Euphyllia", "Euphyllia Divisa", "Heliofungia actiniformis"],
    ],

    "③ + 归并菇珊瑚类": [
        ["Diploria Strigosa", "Colpophyllia Natans"],
        ["Euphyllia", "Euphyllia Divisa", "Heliofungia actiniformis"],
        ["Discosoma", "Rhodactis", "Ricordea"],
    ],

    "④ + 归并团块珊瑚类": [
        ["Diploria Strigosa", "Colpophyllia Natans"],
        ["Euphyllia", "Euphyllia Divisa", "Heliofungia actiniformis"],
        ["Discosoma", "Rhodactis", "Ricordea"],
        ["Siderastrea Siderea", "Porites", "Montastraea Cavernosa", "Meandrina Meandrites"],
    ],
}


def macro_f1(conf):
    n = conf.shape[0]
    f1s = []
    for c in range(n):
        tp = conf[c, c]
        fp = conf[:, c].sum() - tp
        fn = conf[c, :].sum() - tp
        if tp + fp + fn == 0:
            continue
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(0.0 if p + r == 0 else 2 * p * r / (p + r))
    return sum(f1s) / len(f1s) if f1s else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="species")
    args = ap.parse_args()

    rep = json.loads((ROOT / "reports" / args.task / "metrics.json").read_text(encoding="utf-8"))
    classes = rep["classes"]
    conf0 = rep["confusion_matrix"]
    idx = {c: i for i, c in enumerate(classes)}
    total = sum(sum(row) for row in conf0)

    print(f"任务: {args.task}   类别数: {len(classes)}   测试样本: {total}")
    print("=" * 74)
    print(f"{'评估层级':<26}{'类数':>6}{'Top-1':>12}{'宏F1':>10}")
    print("-" * 74)

    out = {}
    for name, groups in SCENARIOS.items():
        # 构造 类 → 组 的映射
        gid = {}
        next_id = 0
        for g in groups:
            for c in g:
                if c in idx:
                    gid[c] = next_id
            next_id += 1
        for c in classes:
            if c not in gid:
                gid[c] = next_id
                next_id += 1

        # 把混淆矩阵折叠到组级
        n = next_id
        conf = [[0] * n for _ in range(n)]
        for i, ci in enumerate(classes):
            for k, ck in enumerate(classes):
                if conf0[i][k]:
                    conf[gid[ci]][gid[ck]] += conf0[i][k]

        import numpy as np
        arr = np.array(conf)
        top1 = float(np.trace(arr) / arr.sum())
        mf1 = macro_f1(arr)
        out[name] = {"n_classes": n, "top1": round(top1, 6), "macro_f1": round(mf1, 6)}
        print(f"{name:<26}{n:>6}{top1:>12.2%}{mf1:>10.4f}")

    print("=" * 74)
    base = out["物种级(30类)"]["top1"]
    for k, v in out.items():
        if k != "物种级(30类)":
            print(f"  {k}: {base:.2%} → {v['top1']:.2%}  (+{(v['top1']-base)*100:.2f} 个百分点)")

    p = ROOT / "reports" / args.task / "group_analysis.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写入: {p}")


if __name__ == "__main__":
    main()
