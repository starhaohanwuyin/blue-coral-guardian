"""
「只新增字段」回归证明（P3 要求 4）
============================================================
P3 给 serve_fusion.py 加了新字段（coralCount / /health.coralCounter / POST /count），
要求**既有输出一字不改**。本脚本用同一张图、同一组参数，分别抓取
「改动前」与「改动后」服务的 /analyze 响应，然后逐键递归比对。

用法：
    # ① 旧服务仍在运行时（改动前）抓基线
    python verify_serve_additive.py --capture reports/serve_before_p3.json

    # ② 重启加载新代码的服务后抓新响应并比对
    python verify_serve_additive.py --capture reports/serve_after_p3.json
    python verify_serve_additive.py --compare reports/serve_before_p3.json reports/serve_after_p3.json

判定：
    · 既有键「缺失」或「数值变化超出容差」→ 失败（退码 1）
    · 只多出新键 → 成功（并列出新增键）
    · 计时类字段（inferenceMs / elapsedMs）不参与比对
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
VOLATILE = {"inferenceMs", "elapsedMs", "countMs"}
FLOAT_TOL = 1e-4          # 覆盖率等小数值的容差（0.01 个百分点）


def fetch_sample(api, aset="semporna", index=0, timeout=60) -> Path:
    req = Request(f"{api}/sample?set={aset}&index={index}",
                  headers={"User-Agent": "verify-additive/1.0"})
    with urlopen(req, timeout=timeout) as r:
        b = r.read()
        name = r.headers.get("X-Sample-Name", f"{aset}_{index}.jpg")
    p = Path(tempfile.gettempdir()) / f"verify_{aset}_{index}_{name}"
    p.write_bytes(b)
    return p


def post_multipart(api, path: Path, endpoint="/analyze", fields=None, timeout=180):
    boundary = "----verifyadditive"
    parts = []
    for k, v in (fields or {}).items():
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode() + path.read_bytes() + b"\r\n" + b"".join(parts) + f"--{boundary}--\r\n".encode()
    req = Request(f"{api}{endpoint}", data=body, method="POST",
                  headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                           "User-Agent": "verify-additive/1.0"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def capture(api, out: Path):
    img = fetch_sample(api, "semporna", 0)
    print(f"样例图: {img}")
    cases = {"plain": {}, "withGeo": {"lat": 4.4, "lon": 118.8, "year": 2024}}
    result = {}
    for name, fields in cases.items():
        print(f"  POST /analyze ({name}) ...", flush=True)
        result[name] = post_multipart(api, img, "/analyze", fields)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"已保存: {out}")
    return 0


def diff(before, after, path="", out=None, added=None, maxdiff=None):
    """递归比对；返回 (缺失/变化列表, 新增键列表)。

    ⚠️ 修过的 bug：`added` 必须像 `out` 一样**传引用下去**，否则递归只保留顶层新增键，
    嵌套新增字段（如 `withGeo.climate.withinGrid`）会被静默丢掉 —— 而「只新增了哪些字段」
    恰恰是这项检查要回答的问题。
    """
    out = [] if out is None else out
    added = [] if added is None else added
    if isinstance(before, dict) and isinstance(after, dict):
        for k, v in before.items():
            if k in VOLATILE:
                continue
            p = f"{path}.{k}" if path else k
            if k not in after:
                out.append(f"缺少键 {p}")
            else:
                diff(v, after[k], p, out, added, maxdiff)
        for k in after:
            if k not in before:
                added.append(f"{path}.{k}" if path else k)
    elif isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            out.append(f"列表长度变化 {path}: {len(before)} → {len(after)}")
        else:
            for i, (a, b) in enumerate(zip(before, after)):
                diff(a, b, f"{path}[{i}]", out, added, maxdiff)
    elif isinstance(before, bool) or isinstance(after, bool):
        if before != after:
            out.append(f"{path}: {before} → {after}")
    elif isinstance(before, (int, float)) and isinstance(after, (int, float)):
        d = abs(float(before) - float(after))
        if maxdiff is not None:
            maxdiff[0] = max(maxdiff[0], d)
        if d > FLOAT_TOL:
            out.append(f"{path}: {before} → {after}（差 {d:.6g}）")
    elif before != after:
        out.append(f"{path}: {before!r} → {after!r}")
    return out, added


def compare(before_file: Path, after_file: Path):
    b = json.loads(before_file.read_text(encoding="utf-8"))
    a = json.loads(after_file.read_text(encoding="utf-8"))
    problems, added = [], []
    maxdiff = [0.0]
    for case in b:
        if case not in a:
            problems.append(f"缺少用例 {case}")
            continue
        p, ad = diff(b[case], a[case], case, maxdiff=maxdiff)
        problems += p
        added += ad
    print("=" * 72)
    print("「只新增字段」回归比对")
    print("=" * 72)
    print(f"  既有键数值最大变化: {maxdiff[0]:.3g}（容差 {FLOAT_TOL:g}，计时字段已排除）")
    print(f"  新增键: {sorted(set(added)) or '无'}")
    if problems:
        print(f"\n  ❌ 既有输出被改动（{len(problems)} 处）：")
        for p in problems:
            print(f"     · {p}")
        return 1
    print("\n  ✅ 既有输出逐键一致（仅新增字段），满足「只新增字段」要求")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--capture", default=None, help="抓取当前服务响应到指定 JSON")
    ap.add_argument("--compare", nargs=2, default=None, metavar=("BEFORE", "AFTER"))
    args = ap.parse_args()
    if args.capture:
        return capture(args.api.rstrip("/"), Path(args.capture))
    if args.compare:
        return compare(Path(args.compare[0]), Path(args.compare[1]))
    ap.error("请指定 --capture 或 --compare")


if __name__ == "__main__":
    sys.exit(main())
