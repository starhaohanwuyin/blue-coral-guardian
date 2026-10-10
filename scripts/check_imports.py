"""导入检查闸门：把 scripts/ 下每个模块**真正 import 一遍**。

比 `py_compile` 强一档：
  · `py_compile` 只证明"语法合法"
  · 本检查会执行模块级代码，能抓到 **NameError / 缺文件 / 常量拼错 / 缺 import**
    这类"语法合法但一跑就错"的问题
  · 实例：修可移植性时用了 `os.environ` 却忘了 `import os`，py_compile 完全查不出来

用法：
    python check_imports.py          # 有问题退出码 1
"""
import contextlib
import importlib.util
import io
import pathlib
import sys
import traceback

SCRIPTS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))


def main() -> int:
    ok, fail = [], []
    for p in sorted(SCRIPTS.glob("*.py")):
        name = p.stem
        try:
            spec = importlib.util.spec_from_file_location(f"chk_{name}", p)
            mod = importlib.util.module_from_spec(spec)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                spec.loader.exec_module(mod)
            ok.append(name)
        except SystemExit:
            ok.append(name)                 # 模块级 sys.exit（如缺参数）不算失败
        except Exception as e:
            tb = traceback.format_exc().strip().splitlines()
            fail.append((name, f"{type(e).__name__}: {e}", tb[-3].strip() if len(tb) >= 3 else ""))

    print(f"已导入 {len(ok) + len(fail)} 个脚本；失败 {len(fail)} 个")
    for n, err, line in fail:
        print(f"  ❌ {n}: {err}")
        if line:
            print(f"       {line}")
    if fail:
        print("\n提示：这类错误 py_compile 查不出来（语法合法、运行才错）。")
        return 1
    print("✅ 全部脚本可正常导入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
