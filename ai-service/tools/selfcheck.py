"""演示前自检：一条命令确认"这台机器现在能不能直接演示"。

    python ai-service/tools/selfcheck.py

检查项：Python/依赖 → 模型权重 → 数据 → 网页资源 → 端口/服务状态
输出最后给出一句话结论 + 该做什么。
"""
import importlib
import json
import pathlib
import socket
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve()
ROOT = HERE.parent.parent                      # ai-service/
REPO = ROOT.parent                             # 仓库根
W = ROOT / "weights"

ok = warn = bad = 0


def line(status, name, detail=""):
    global ok, warn, bad
    icon = {"ok": "✅", "warn": "⚠️ ", "bad": "❌"}[status]
    if status == "ok":
        ok += 1
    elif status == "warn":
        warn += 1
    else:
        bad += 1
    print(f"  {icon} {name:<46} {detail}")


print("=" * 76)
print("  蓝珊·珊瑚卫士 —— 演示前自检")
print("=" * 76)

# ① 运行环境
print("\n【1/5】运行环境")
v = sys.version_info
line("ok" if v >= (3, 10) else "bad", "Python 版本", f"{v.major}.{v.minor}.{v.micro}")
for mod, name in [("torch", "PyTorch"), ("torchvision", "torchvision"),
                  ("fastapi", "FastAPI"), ("uvicorn", "Uvicorn"),
                  ("PIL", "Pillow"), ("numpy", "NumPy")]:
    try:
        m = importlib.import_module(mod)
        ver = getattr(m, "__version__", "")
        line("ok", f"依赖 {name}", ver)
    except Exception:
        line("bad", f"依赖 {name} 缺失", "→ 运行：pip install -r requirements.txt")
try:
    import torch
    if torch.cuda.is_available():
        line("ok", "GPU 可用", torch.cuda.get_device_name(0))
    else:
        line("warn", "GPU 不可用（CPU 推理）", "约 5–10 秒/张，演示仍可进行")
except Exception:
    pass

# ② 模型权重
print("\n【2/5】模型权重（约 470 MB）")
need = [
    ("weights/segformer_coralscapes/model.safetensors", 100),
    ("weights/species_ip/best.pt", 100),
    ("weights/bleaching_all/best.pt", 100),
    ("weights/bleaching_all_multidomain2/best.pt", 100),
    ("weights/yolo_coral/best.pt", 45),
]
missing = 0
for rel, mb in need:
    p = ROOT / rel
    if p.exists() and p.stat().st_size > mb * 1024 * 1024 * 0.8:
        line("ok", rel, f"{p.stat().st_size/1024/1024:.1f} MB")
    else:
        missing += 1
        line("bad", rel, "缺失 → 运行 python tools/download_weights.py")

# ③ 数据
print("\n【3/5】演示数据")
for rel, min_mb in [("data/noaa/climate_index.json", 1.0), ("data/noaa/site_profiles.json", 1.0)]:
    p = ROOT / rel
    if p.exists() and p.stat().st_size > min_mb * 1024 * 1024:
        line("ok", rel, f"{p.stat().st_size/1024/1024:.2f} MB")
    else:
        line("bad", rel, "缺失（环境卡片会显示无数据）")
photos = list((ROOT / "data" / "semporna_photos").glob("*.jpg")) if (ROOT / "data" / "semporna_photos").exists() else []
line("ok" if photos else "warn", "示例照片（演示用按钮）", f"{len(photos)} 张" if photos else "无（可手动上传照片）")

# ④ 网页资源
print("\n【4/5】网页版资源")
for rel in ["web/index.html", "web/lite.html", "web/mp.js", "web/mp/manifest.json"]:
    line("ok" if (ROOT / rel).exists() else "bad", rel)
tpl = list((ROOT / "web" / "mp" / "templates").glob("*.json"))
imgs = list((ROOT / "web" / "mp" / "assets" / "img").glob("*"))
# 页数**动态读取** app.json：以前写死 22，小程序后来加了页面就会假报警
try:
    _pages = json.loads((ROOT.parent / "miniprogram" / "app.json").read_text(encoding="utf-8"))["pages"]
except Exception:                                              # noqa: BLE001
    _pages = []
_want = len(_pages) or 22
line("ok" if len(tpl) == _want else "warn", f"{_want} 页模板", f"{len(tpl)} 个")
line("ok" if imgs else "warn", "本地配图（离线可用）", f"{len(imgs)} 张")

# 珊瑚图鉴数据库（科普页「珊瑚种类」的数据源，可在 /admin.html 自行上传维护）
try:
    import sqlite3
    _db = ROOT / "data" / "corals" / "corals.db"
    if _db.exists():
        _con = sqlite3.connect(str(_db))
        _n = _con.execute("SELECT COUNT(*) FROM corals").fetchone()[0]
        _con.close()
        line("ok", "珊瑚图鉴数据库", f"{_n} 条 · 后台 /admin.html 可上传")
    elif (ROOT / "data" / "corals" / "coral_species.json").exists():
        line("warn", "珊瑚图鉴数据库尚未建库", "→ 启动一次服务即自动灌种子（348 条）")
    else:
        line("warn", "珊瑚图鉴种子数据缺失",
             "→ python tools/gen_coral_catalog.py")
except Exception as _e:
    line("warn", "珊瑚图鉴数据库读取失败", str(_e)[:48])

# ⑤ 端口与服务
print("\n【5/5】服务状态")


def port_busy(port=8000):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def health():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=3) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


h = health()
if h:
    line("ok", "AI 服务在线", f"设备={h.get('device')} 共识模型={h.get('bleachAlt')}")
    line("ok" if h.get("segCalibrated") else "warn", "分割模型已校准", str(h.get("segCalibrated")))
    line("ok" if (h.get("coralCatalog") or 0) > 0 else "warn", "珊瑚图鉴接口在线",
         f"{h.get('coralCatalog')} 条")
elif port_busy():
    line("warn", "端口 8000 被占用但不是本服务", "换个端口：--port 8001")
else:
    line("warn", "AI 服务未启动", "→ cd ai-service/scripts && python serve_fusion.py --host 0.0.0.0 --port 8000")

# 结论
print("\n" + "=" * 76)
print(f"  自检结果：✅ {ok} 项通过 / ⚠️ {warn} 项提醒 / ❌ {bad} 项缺失")
print("=" * 76)
if bad:
    print("  ❌ 还不能直接演示：先按上面 ❌ 的提示补齐（通常是权重没下载）。")
    sys.exit(1)
if not h:
    print("  ✅ 环境就绪。现在启动服务即可演示：")
    print("       cd ai-service/scripts")
    print("       python serve_fusion.py --host 0.0.0.0 --port 8000")
    print("     然后浏览器打开 http://127.0.0.1:8000/")
else:
    print("  ✅✅ 一切就绪，直接演示：浏览器打开 http://127.0.0.1:8000/")
sys.exit(0)
