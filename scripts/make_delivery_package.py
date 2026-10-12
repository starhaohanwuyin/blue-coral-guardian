"""一键打包「交付给队友」的部署包。

为什么需要它：模型权重（~530 MB）和气候档案（~8 MB）都**不在 Git 仓库里**
（`.gitignore` 排除了 `weights/` 与 `data/`），而队友只克隆仓库是跑不起 AI 的。
本脚本把该给的东西凑成一份，并生成自包含的《交付说明.md》。

用法：
    python make_delivery_package.py                 # 只报告（不复制任何文件）
    python make_delivery_package.py --build         # 复制到 delivery/
    python make_delivery_package.py --build --zip   # 再打成 delivery.zip
    python make_delivery_package.py --build --no-photos   # 不含样例图（省 ~76 MB）

⚠️ 打包内容里**没有**密钥：模型权重是训练产物，NOAA 数据是公有领域（US Gov work）。
"""
import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "delivery"

# ⚠️ 只打**运行必需**的文件：**不含** `last.pt`（训练末轮检查点）、
#    `yolo_coral/best_640r0.pt`（R0 中间产物）、`yolov9c.pt`（预训练基线）。
#    这三类合计约 311 MB，服务运行完全用不到（服务只加载 segformer + species_ip/best.pt
#    + bleaching_all/best.pt + yolo_coral/best.pt）。加 `--full` 可打完整版（归档用）。
WEIGHTS = [
    ("weights/segformer_coralscapes", "礁区语义分割（40 类底栖，含 id2label/label2color）"),
    ("weights/species_ip/best.pt", "珊瑚属识别（34 属，类别名内嵌在权重里）"),
    ("weights/bleaching_all/best.pt", "白化状态识别（三分类，多域联合模型）"),
    ("weights/yolo_coral/best.pt", "个体计数 YOLOv9c（P3 附加能力）"),
    # P16：共识弃权需要第二个白化模型；缺失时服务会安静降级（consensus=null），不影响其它功能。
    #      `--no-consensus` 可跳过（省约 106 MB）。
    ("weights/bleaching_all_multidomain2/best.pt",
     "第二白化模型（共识弃权用；实测与线上模型分歧率 22.8%，域内覆盖率 92-98%；可选）"),
]
# 默认排除的冗余文件（打完整版时包含）
REDUNDANT = [
    "weights/species_ip/last.pt",
    "weights/bleaching_all/last.pt",
    "weights/yolo_coral/best_640r0.pt",
    "weights/yolo_coral/yolov9c.pt",
]
FULL_WEIGHTS = [
    ("weights/segformer_coralscapes", "礁区语义分割"),
    ("weights/species_ip", "珊瑚属识别（含 last.pt）"),
    ("weights/bleaching_all", "白化状态识别（含 last.pt）"),
    ("weights/yolo_coral", "个体计数（含中间产物）"),
]
CLIMATE = [
    ("data/noaa/climate_index.json", "气候快速索引（环境卡片查询用，~4 MB）"),
    ("data/noaa/site_profiles.json", "41 年投放时间窗档案（建议避开月份/风险等级，~4 MB）"),
]
PHOTOS = ("data/semporna_photos", "样例图 180 张（识别页「示例图片」按钮用，可选）")

README = """# 交付说明（蓝珊 · 珊瑚卫士 AI 服务）

本包由 `coral_ml/scripts/make_delivery_package.py` 生成。**模型权重与气候数据不在 Git 仓库里**
（体积原因），所以必须用这个包补齐，否则服务跑不起来（或环境卡片没有数据）。

## 一、准备仓库

```bash
git clone https://github.com/starhaohanwuyin/blue-coral-ml.git
cd blue-coral-ml
```

## 二、把本包的内容放进仓库

```
blue-coral-ml/
├── scripts/
├── weights/            ← 用本包的 weights/ 覆盖/放入
└── data/
    ├── noaa/           ← 放入本包的 climate_index.json 与 site_profiles.json
    └── semporna_photos/ ← （可选）样例图
```

> ⚠️ **别漏了 `data/noaa/` 这两个 JSON**：少了它们，识别页的「环境数据 · 海表热压力」
> 卡片会显示"无数据"，投放建议也没有。它们只有约 8 MB。

## 三、装依赖并启动

```bash
pip install -r requirements.txt
cd scripts
python serve_fusion.py --host 0.0.0.0 --port 8000
```

- 首次启动要加载 4 个模型，**等 40–90 秒**，看到 `Uvicorn running on http://0.0.0.0:8000` 即就绪。
- 有 NVIDIA 显卡：先按 https://pytorch.org 装 CUDA 版 torch，再 `pip install -r requirements.txt`。
  没显卡：直接装，会自动用 CPU（约 5–10 秒/张）。

## 四、验证

```bash
curl http://127.0.0.1:8000/health
```

期望（关键字段）：

```json
{"status":"ok","segCalibrated":true,"categories":40,...}
```

- **`segCalibrated` 必须是 `true`**；若是 `false`，说明放错了实验权重，覆盖率会偏高约 13 个百分点。
- 再试一条环境数据（验证气候档案有没有放对）：
  ```bash
  curl "http://127.0.0.1:8000/climate?lat=4.4&lon=118.8&year=2024"
  ```
  应返回 `"ok":true` 与 `"baaLabel":"白化警报一级"`（2024 年该点位）。

## 五、和小程序连起来

- 开发者工具里跑：小程序会自动连 `http://127.0.0.1:8000`（`utils/config.js` 里按环境自动选择）。
- **真机预览**：手机与电脑要在同一 Wi-Fi，把 `utils/config.js` 里的 `CORAL_API`
  改成电脑局域网地址（如 `http://192.168.1.20:8000`），并用 `--host 0.0.0.0` 启动服务。

## 五点五、共识弃权（P16，可选但推荐）

服务会加载**两个**白化模型：`bleaching_all`（主，多域 D4）+ `bleaching_all_multidomain2`（第二，多域 D2），
按**三档**给结论（接口字段 `bleaching.consensus.severity`）：

| 档位 | 触发条件 | 小程序显示 |
|---|---|---|
| `agree` | 两模型判定一致 | ✓ 双模型一致（绿）|
| `review` | 分歧，且**有一个模型很自信**（主模型 <90% 或第二模型 ≥85%）| 🔍 建议人工复核（橙）|
| `note` | 其余分歧（主模型高置信、第二模型低置信）| ℹ️ 第二模型持不同意见，仅供参考（青）|

- **实测**：真实照片上两模型分歧率约 **57%**（第二模型是印太域版，在仙本那照片上偏向"死亡"），
  三档抽检分布约 一致 23% / 仅供参考 30% / 建议复核 47%。
- **若觉得提示过密**：启动前设 `$env:DISABLE_BLEACH_CONSENSUS = '1'`（PowerShell；cmd 用 `set DISABLE_BLEACH_CONSENSUS=1`）（不加载第二模型，App 不再出现提示）；
  或打包时用 `--no-consensus` 不带该权重。缺失/关闭时服务都安静降级（`consensus: null`），其它功能不受影响。

## 六、少了什么会怎样（自检表）

| 缺失 | 现象 | 补法 |
|---|---|---|
| `weights/segformer_coralscapes` | 服务启动报错/分割不可用 | 必须有 |
| `weights/species_ip` | 属级识别不可用 | 必须有 |
| `weights/bleaching_all` | 白化识别不可用 | 必须有 |
| `weights/yolo_coral` | 只有"个体计数"字段缺失，其余正常 | 可选 |
| `data/noaa/climate_index.json` | 环境卡片"无数据" | 必须有 |
| `data/noaa/site_profiles.json` | 无投放建议/历史档案 | 必须有 |
| `ultralytics` 未装 | 个体计数不可用（`pip install ultralytics`）| 可选 |
| `data/semporna_photos` | 示例图片按钮无图 | 可选 |
"""


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} GB"


def dir_size(p: Path) -> int:
    if not p.exists():
        return 0
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="实际复制到 delivery/")
    ap.add_argument("--zip", action="store_true", help="再打成 delivery.zip")
    ap.add_argument("--no-photos", action="store_true", help="不含样例图")
    ap.add_argument("--no-consensus", action="store_true",
                    help="不含第二白化模型（省约 106 MB；共识弃权将降级为 consensus=null）")
    ap.add_argument("--full", action="store_true",
                    help="打完整版（含 last.pt / R0 / yolov9c 等冗余，约多 311 MB，仅供归档）")
    a = ap.parse_args()

    weights = FULL_WEIGHTS if a.full else WEIGHTS
    if a.no_consensus:          # 可选：不带第二白化模型（共识功能将降级）
        weights = [(r, d) for r, d in weights
                   if not any(k in r for k in ("multidomain2", "koh_tao"))]
    items = list(weights) + list(CLIMATE) + ([] if a.no_photos else [PHOTOS])
    total, missing, rows = 0, [], []
    for rel, desc in items:
        p = ROOT / rel
        size = dir_size(p)
        ok = p.exists() and size > 0
        if not ok:
            missing.append(rel)
        total += size
        rows.append((rel, desc, size, ok))

    print("=" * 78)
    print(f"交付包内容（目标目录 {OUT}）" + ("  【完整版】" if a.full else "  【精简版：只含运行必需】"))
    print("=" * 78)
    for rel, desc, size, ok in rows:
        print(f"  {'✅' if ok else '❌ 缺失'} {rel:<38} {human(size):>10}   {desc}")
    print(f"\n  合计: {human(total)}")
    if not a.full:
        skipped = sum(dir_size(ROOT / r) for r in REDUNDANT if (ROOT / r).exists())
        print(f"  已排除 {len([r for r in REDUNDANT if (ROOT / r).exists()])} 个非必需文件（{human(skipped)}）：")
        for r in REDUNDANT:
            if (ROOT / r).exists():
                print(f"     – {r}  ({human(dir_size(ROOT / r))})")
        print("     （想连它们一起打包：加 --full）")
    req = ROOT / "requirements.txt"
    print(f"  {'✅' if req.exists() else '❌'} requirements.txt（会让队友 pip install）")

    if missing:
        print(f"\n⚠️ 缺失 {len(missing)} 项，无法打包：{missing}")
        print("   若是权重缺失：确认训练产物还在（weights/ 目录），或改用外部分发的旧包。")
        return 1
    if not a.build:
        print("\n（当前是**只报告**模式；加 --build 才会真正复制）")
        return 0

    if OUT.exists():
        print(f"\n清空旧的 {OUT} …")
        shutil.rmtree(OUT)
    print(f"\n开始复制到 {OUT} …")
    for rel, desc, size, ok in rows:
        src, dst = ROOT / rel, OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        print(f"  → {rel}  ({human(size)})")
    (OUT / "requirements.txt").write_text(req.read_text(encoding="utf-8"), encoding="utf-8")
    (OUT / "交付说明.md").write_text(README, encoding="utf-8")
    print("  → requirements.txt")
    print("  → 交付说明.md")

    if a.zip:
        zp = ROOT / "delivery.zip"
        print(f"\n打包 {zp} …（体积大，需要一点时间）")
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as z:
            for f in OUT.rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(OUT))
        print(f"  ✅ {zp}  {human(zp.stat().st_size)}")

    print(f"\n完成。把 {OUT if not a.zip else ROOT / 'delivery.zip'} 发给队友即可"
          f"（连同 blue-coral-miniprogram 仓库的部署指南）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
