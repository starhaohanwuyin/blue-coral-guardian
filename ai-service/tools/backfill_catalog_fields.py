# -*- coding: utf-8 -*-
"""给图鉴种子补齐「详情页四大板块」里后加的字段（只补空值，不覆盖已有内容）。

背景：详情页字段分两批来
  · 12 条精编种类 —— tools/gen_coral_catalog.py 按形态模板生成；
  · 联网扩充的条目 —— 直接写在 data/corals/coral_species.json 里，没有模板覆盖。
所以后加的字段（捕食方式 feeding、野外种群现状 population、外观颜色 colorDesc）
需要按「形态码」补一遍，本脚本就是干这个的。

用法：
    python tools/backfill_catalog_fields.py            # 就地补种子 JSON
    python tools/backfill_catalog_fields.py --dry-run  # 只看会补哪些，不写文件

补完种子后，让数据库也吃到：
    python scripts/coral_catalog.py --backfill
"""
import argparse
import importlib.util
import io
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "corals" / "coral_species.json"


def load_gen():
    """把同目录的 gen_coral_catalog.py 当模块加载，复用它的形态模板（单一真源）。"""
    path = pathlib.Path(__file__).resolve().parent / "gen_coral_catalog.py"
    spec = importlib.util.spec_from_file_location("gen_coral_catalog", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PLACEHOLDER = ("（俗称）", "（中文名）", "（网络资料）")


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="补齐图鉴种子里后加的详情字段")
    ap.add_argument("--dry-run", action="store_true", help="只统计，不写文件")
    args = ap.parse_args()

    gen = load_gen()
    data = json.loads(OUT.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else data
    filled = {"colorDesc": 0, "feeding": 0, "population": 0, "alias": 0}

    for it in items or []:
        form = str(it.get("form") or "M")
        attr = gen.FORM_ATTR.get(form) or gen.FORM_ATTR["M"]
        if not it.get("colorDesc"):
            it["colorDesc"] = gen.COLORS.get(form, gen.COLORS["M"])
            filled["colorDesc"] += 1
        if not it.get("feeding"):
            it["feeding"] = attr["feed"]
            filled["feeding"] += 1
        if not it.get("population"):
            it["population"] = attr["pop"]
            filled["population"] += 1
        alias = str(it.get("alias") or "").strip()
        if (not alias) or alias.endswith(PLACEHOLDER):
            new = gen.ALIASES.get(it.get("name") or "", "")
            if new != alias:
                it["alias"] = new
                filled["alias"] += 1

    print("共 " + str(len(items or [])) + " 条，补写统计：" + json.dumps(filled, ensure_ascii=False))
    if args.dry_run:
        print("（dry-run，未写文件）")
        return 0
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("已写回 " + str(OUT))
    print("提示：再跑 python scripts/coral_catalog.py --backfill 让 SQLite 里的空字段也补上")
    return 0


if __name__ == "__main__":
    sys.exit(main())
