# -*- coding: utf-8 -*-
"""把 tools/quiz_bank.json 同步进 utils/mock.js 的 quizQuestions（题库的唯一编辑入口）。

改题流程：
    1) 编辑 tools/quiz_bank.json（q / options[4] / answer 索引 / explain）
    2) python tools/sync_quiz_bank.py
    3) 在 ai-service 下 python tools/build_web_pages.py 重新生成网页产物

用法：
    python tools/sync_quiz_bank.py --check    # 只对比，不写文件
"""
import argparse
import io
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BANK = pathlib.Path(__file__).resolve().parent / "quiz_bank.json"
MOCK = ROOT / "utils" / "mock.js"


def render(questions):
    lines = ["const quizQuestions = [",
             "  /* ===== 题库（源文件 tools/quiz_bank.json，改完跑 tools/sync_quiz_bank.py）=====",
             "   * 每次进入随机抽 5 题、选项也会打乱（见 pages/quiz/quiz.js）*/"]
    for q in questions:
        opts = ", ".join("'%s'" % o.replace("'", "\\'") for o in q["options"])
        lines.append("  { q: '%s'," % q["q"].replace("'", "\\'"))
        lines.append("    options: [%s], answer: %d," % (opts, int(q["answer"])))
        lines.append("    explain: '%s' }," % q["explain"].replace("'", "\\'"))
    lines.append("]")
    return "\n".join(lines)


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="同步知识问答题库")
    ap.add_argument("--check", action="store_true", help="只检查是否已同步")
    a = ap.parse_args()

    bank = json.loads(BANK.read_text(encoding="utf-8"))
    qs = bank["questions"]
    for i, q in enumerate(qs, 1):
        assert q.get("q") and len(q.get("options", [])) == 4, "第 %d 题结构不对" % i
        assert 0 <= int(q.get("answer", -1)) <= 3, "第 %d 题 answer 越界" % i
        assert q.get("explain"), "第 %d 题缺解析" % i

    src = MOCK.read_text(encoding="utf-8")
    start = src.index("const quizQuestions = [")
    end = src.index("\n]", start) + 2
    new_block = render(qs)
    same = src[start:end] == new_block
    print("题库 %d 题；mock.js %s" % (len(qs), "已同步" if same else "需要更新"))
    if a.check or same:
        return 0
    MOCK.write_text(src[:start] + new_block + src[end:], encoding="utf-8")
    print("已写入 utils/mock.js（记得重建网页产物）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
