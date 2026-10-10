"""
小程序全页面冒烟测试
================================================================
逐个打开 app.json 中的每个页面，检查：
  1. 页面能否成功编译并打开（open_page 返回 success）
  2. 控制台是否出现新的报错（TypeError / undefined / error 等）

用法：
    python smoke_test.py
    python smoke_test.py --only pages/ai/ai
"""
import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

BC = Path(r"D:\大学作业\广东海洋大学的珊瑚评测小程序\blue_coral")
CLI = r"C:\Program Files (x86)\Tencent\微信web开发者工具\wechatide.cmd"
# ⚠️ token 不硬编码（避免凭证进仓库）：在开发者工具「设置 → 安全设置 → 服务端口」
#    可查看，通过环境变量传入。注意 DevTools 重启后 token 会重新生成。
TOKEN = os.environ.get("WECHAT_IDE_TOKEN", "")
if not TOKEN:
    raise SystemExit(
        "缺少 WECHAT_IDE_TOKEN 环境变量。\n"
        "  1) 打开微信开发者工具 → 设置 → 安全设置 → 开启「服务端口」\n"
        "  2) 复制其中的 token，然后设置环境变量：\n"
        "     PowerShell:  $env:WECHAT_IDE_TOKEN='<你的token>'\n"
        "     bash:        export WECHAT_IDE_TOKEN='<你的token>'\n"
        "  3) 重新运行本脚本"
    )

# 忽略的已知噪声（开发者工具自身的路由/懒加载提示）
NOISE = [
    "Lazy code loading",
    "WeChatLib:",
    "routeDone with a webviewId",
    "routeDone",
    "SystemError (appServiceSDKScriptError)",
    "[system]",
    "getSystemInfo",
    "wx.getUserInfo",
    "deprecated",
]
ERROR_PAT = re.compile(r"TypeError|ReferenceError|is not a function|Cannot read|undefined is not|"
                       r"\[error\]|Failed to", re.I)


def cli(*args, timeout=90):
    cmd = [CLI, "-c", "dsh", *args, "--project", str(BC), "--token", TOKEN]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace", shell=False)
        return (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return ""
    except Exception as e:
        return f"CLI_ERROR {e}"


def console_text():
    out = cli("get_simulator_console", "--command", ".")
    m = re.search(r'"result"\s*:\s*"(.*?)"\s*\n\s*\}', out, re.S)
    if not m:
        m = re.search(r'"result"\s*:\s*"(.*)', out, re.S)
    if not m:
        return ""
    raw = m.group(1)
    try:
        return json.loads('"' + raw.replace('"', '\\"') + '"')
    except Exception:
        return raw


def is_noise(line):
    return any(n in line for n in NOISE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--wait", type=float, default=3.5)
    args = ap.parse_args()

    app = json.loads((BC / "app.json").read_text(encoding="utf-8"))
    pages = app.get("pages", [])
    if args.only:
        pages = [p for p in pages if p == args.only]

    print(f"冒烟测试 {len(pages)} 个页面")
    print("=" * 74)
    results = []
    seen_errors = set()
    for i, p in enumerate(pages, 1):
        out = cli("simulator_open_page", "--page", p)
        ok = '"success": true' in out
        time.sleep(args.wait)
        txt = console_text()
        errs = []
        for line in re.split(r"\\n|\n", txt):
            line = line.strip()
            if not line or is_noise(line):
                continue
            if ERROR_PAT.search(line):
                key = line[:120]
                if key not in seen_errors:
                    seen_errors.add(key)
                    errs.append(key)
        mark = "✅" if (ok and not errs) else ("⚠️" if ok else "❌")
        results.append((p, ok, errs))
        print(f"{i:2d}. {mark} {p:<40} open={'Y' if ok else 'N'} 新报错={len(errs)}")
        for e in errs[:2]:
            print(f"        {e[:110]}")

    print("=" * 74)
    good = sum(1 for _, ok, e in results if ok and not e)
    print(f"通过 {good}/{len(results)}")
    bad = [(p, ok, e) for p, ok, e in results if not ok or e]
    if bad:
        print("\n需关注：")
        for p, ok, e in bad:
            print(f"  {p}: open={ok} errs={e[:2]}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
