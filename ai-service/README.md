# 蓝珊 · 珊瑚礁智能评估（coral_ml）

> 深度学习部分：礁区覆盖率分割、珊瑚属识别、白化状态评估，以及与实地/卫星数据的交叉验证。
> 小程序端在 `../blue_coral`。

**用途限定：本项目仅用于学术研究与竞赛，非商业用途。** 详见 [NOTICE.md](NOTICE.md)。

---

## 一、能做什么

输入一张礁区照片，输出：

| 输出 | 模型 | 实测指标 |
|---|---|---|
| **礁区覆盖率**（活/白化/死亡/藻类/沙砾，百分比） | Coralscapes SegFormer-B2 语义分割 | mIoU **0.548**（官方验证集 166 张）|
| **珊瑚属**（34 属） | ConvNeXt-Tiny 属级分类 | 仙本那留出集 Top-1 **86.12%**（地理隔离）|
| **白化状态**（健康/白化/死亡） | ConvNeXt-Tiny 白化分类 | 第三方独立数据 **98.21%** |
| **拍摄条件自检** | 图像统计（对比度） | 降质集上 5/5 正确 |
| **海表热压力**（环境数据插件）| NOAA CRW v3.1 5km | **1985–2025 共 41 年**（DHW / HotSpot / 官方 BAA 全部逐日），覆盖仙本那 |
| **修复优先级 + 保育报告**（综合研判插件）| 规则型决策支持启发式 | 可解释，不报准确率 |
| **修复模拟**（10 年恢复轨迹）| 逻辑斯蒂增长 + 热浪致死 | 示意性推演，非预测 |
| **水下图像增强** | 传统 CV + **CNN（U-Net）** | 三方对比见 `reports/enhance_compare.json` |
| **珊瑚个体数量 + 位置**（P3 附加能力）| YOLOv9c 单类检测 | mAP@0.5 **0.4217**（官方 val 166 张）|
| **投放时间窗建议**（往年白化预警记录）| NOAA CRW DHW/HotSpot **1985–2025（41 年）** 聚合 + 规则 | 544 格点：**35 个不建议投放**（≥3 次严重白化事件）/ 421 个需避开风险月 / **88 个 41 年从未达警戒**；**仅热压力维度**，非效果评估 |
| **热压力序列的外部一致性核对**（P4 前置）| 41 年 DHW 序列 × Reef Check Malaysia 报告记载的白化事件年表（事件级）| 2024 排**第 1**、2020 第 2、2016 第 3（与报告"沙巴 2024 历史最高、2020 显著白化"一致）；半岛的 2019 事件在我们（仙本那）网格仅 1.8% 格点警戒 → **区域保真度**旁证；`reports/p4_event_timeline.json` |

**核心外部验证**：模型在仙本那 180 张照片上的活珊瑚覆盖估计 **39.71%**，
与 Reef Check Malaysia 2024 实地调查的区域平均 **39.56%** 相差 **0.15 个百分点**。

> ⚠️ **两个"插件"容易被漏读**：**环境数据插件**（NOAA 热压力）与**综合研判插件**
> （修复优先级 + 保育报告 + 10 年模拟）**都在交付范围内且已接入小程序页面**，只是它们不是"模型"，
> 所以不在这张模型表里。其中修复优先级是**规则型决策支持**：可用、可解释，但**不报准确率**——
> 因为"该优先修复哪个点位"是价值判断，**不存在客观真值**，这与"能力做不到"是两回事。
> 完整的「能力与交付边界」见 [docs/项目交接与续接指引.md](docs/项目交接与续接指引.md) **§1.6**。

---

## 二、快速开始

### 1. 启动评估服务

```bash
cd scripts
python serve_fusion.py --port 8000
```

等待约 40–90 秒（加载分割 + 属分类 + 白化分类 + 个体计数四个模型），看到
`Uvicorn running on http://0.0.0.0:8000` 即为就绪。

### 2. 健康检查

```bash
curl http://127.0.0.1:8000/health
```

关键字段：
```json
{"status":"ok","segmentation":"loaded","species":"loaded",
 "segModel":"segformer_coralscapes","segCalibrated":true,"categories":40,
 "coralCounter":"loaded"}
```

> ⚠️ `segCalibrated` 必须为 `true`。若为 `false` 说明加载了未校准的实验权重，
> 覆盖率会偏高约 13 个百分点。

### 3. 端到端自检（推荐）

```bash
python scripts/e2e_check.py
```
期望输出 `通过 25/25`（缺计数模型或投放档案时，相应检查会跳过：21/21 → 17/17）。

### 4. 单张照片评估

```bash
python scripts/segment_coral.py --image /path/to/coral.jpg --json
```

---

## 三、接口

| 端点 | 说明 |
|---|---|
| `GET /health` | 服务与模型状态 |
| `POST /analyze` | 上传图片 → 覆盖率 + 珊瑚属 + 白化状态 + 拍摄条件 + **个体计数** |
| `POST /analyze_base64` | 同上，base64 传图 |
| **`POST /count`** | **只做珊瑚个体计数**（P3 附加；不跑分割/分类，可选 `conf`/`iou`）|
| **`GET /climate/profile?lat=&lon=`** | **投放时间窗档案**：往年白化预警记录 → 建议避开月份 / 稳定性判定（网格外返回 `ok=false`）|
| `GET /sample?set=semporna&index=0` | 样例图（`semporna` / `bleached` / `healthy`），供无图时演示 |
| **`GET /corals`** | **珊瑚图鉴列表**（SQLite 图鉴库；`q=` 搜索、`genus=` 属筛选、`limit/offset` 分页）|
| `GET /corals/stats` | 图鉴统计（总数 / 属数 / 科数 / 属清单）|
| `GET /corals/{id}` | 单条详情（基础档案 / 形态识别 / 生物习性 / 生存威胁 四大板块字段）|
| `POST /corals` · `PUT /corals/{id}` · `DELETE /corals/{id}` | 图鉴增改删（单条）|
| `POST /corals/import` | **批量上传**（JSON / CSV / TSV，表头中英文都认）|
| **`GET /admin.html`** | **珊瑚图鉴数据后台**：上传、搜索、删除、导出，手机/电脑浏览器都能开 |

### 珊瑚图鉴数据库（科普页的「珊瑚种类」）

科普页与「全部种类」页的种类数据**不是写死在代码里的**，而是读 SQLite 图鉴库：

```
tools/gen_coral_catalog.py   →  data/corals/coral_species.json   种子数据（原版精编 12 条，入 git）
                             →  data/corals/corals.db            首次启动自动建库并灌种子（不入 git）
/admin.html 上传 或 POST /corals/import  → 即写即生效，页面刷新就能看到
小程序 / 网页版 GET /corals              ← 连不上服务时自动退回本地 24 条演示数据
```

要加自己的种类：打开 `http://127.0.0.1:8000/admin.html` → 下载 CSV 模板 → 填好上传即可
（也可直接传 JSON）。字段与命令行用法见 [docs/珊瑚图鉴数据库.md](docs/珊瑚图鉴数据库.md)。

`/analyze` 返回结构：

```json
{
  "cover": {"alivePct":0.3966,"bleachedPct":0.0312,"deadPct":0.0205,
            "algaePct":0.10,"substratePct":0.3983,"coralTotalPct":0.4483,
            "bleachingShareOfCoral":0.0696},
  "coralRegion": {"reliable":true,"top":[{"genus":"Acropora","confidence":0.78}]},
  "bleaching": {"label":"bleached","labelCn":"白化","confidence":0.96,"reliable":true},
  "coralCount": {"count":16,"threshold":{"conf":0.20,"iou":0.5,"imgsz":896},
                 "boxes":[{"x0":0,"y0":0,"x1":0,"y1":0,"confidence":0.9}],"elapsedMs":85.2},
  "captureQuality": {"level":"good","usable":true,"contrast":0.23,
                     "thresholds":{"goodContrast":0.0306,"warnContrast":0.0243}},
  "inferenceMs": 620
}
```

> **P3 是纯新增**：`coralCount` 是新增键，`/count` 是新增端点；原有键的名称、类型与
> 取值口径**完全未变**（可用 `python scripts/verify_serve_additive.py` 复跑比对证明）。
> 不需要计数时，`POST /analyze?count=false` 可跳过，响应里 `coralCount` 为 `null`。
>
> 带 `lat/lon` 时还会新增三个键：`deployment`（往年热压力档案）、
> `restoration.deploymentAdvice`（**投放建议**：`verdict` 一句结论 + 三条依据 + `summaryText` 可直接展示）
> 与 `restoration.reportEn`（**英文保育报告**，与中文 `report` 逐节对齐、数值一致）。
> **既有 `report` 正文一字未改**，新增信息只在上述新字段里（中英文都是自动生成）。

---

## 四、目录结构

```
ai-service/
├── scripts/            训练与评估脚本
├── docs/               方案、核验、答辩要点、评估方法与局限
├── reports/            结果 JSON（报告的权威数据源）
├── dsh-skill/          DSH Agent 插件（1 个 Skill + 6 个工具）
├── NOTICE.md           许可证与合规声明
├── data/               数据集（已 gitignore，约 16.9 GB）
└── weights/            模型权重（已 gitignore，约 2.8 GB）
```

### 关键脚本

| 脚本 | 用途 |
|---|---|
| `serve_fusion.py` | **生产推理服务**（覆盖率 + 属 + 白化 + 拍摄条件自检）|
| `segment_coral.py` | 分割推理（默认 1024px）|
| `train.py` | 分类模型训练（支持 `--resume` / `--subset-frac` 交叉验证）|
| `evaluate_protocol.py` | **完整评估协议**：Top-1 + 聚类 CI + ECE + 覆盖率曲线 |
| `eval_segmentation_miou.py` | 分割 mIoU（Coralscapes 官方验证集）|
| `mcnemar_test.py` | 模型间显著性检验（McNemar）|
| `error_attribution.py` | 错误归因 + 拒识曲线 |
| `phash_audit.py` | 近重复审计（跨 split 泄漏检测）|
| `degrade_underwater.py` | 物理水下降质（使用边界实验）|
| `cache_noaa.py` | NOAA CRW 数据离线缓存（PacIOOS 镜像）|
| **`climate_site_profile.py`** | **投放时间窗档案**（往年白化预警记录 → 逐年峰值 / 风险月份 / 稳定性 / 建议避开月份）|
| `cross_validate.py` | 星地交叉验证 |
| `validate_site_level.py` | 站点级验证 |
| `e2e_check.py` | 端到端自检（19 项；计数模型未训练时 15 项且跳过计数）|
| `resume_all.py` | **一键状态体检 / 续跑**（26 阶段：R0 训练 / R1 微调 / 工作点评估 / 两个代码闸门）|
| `make_report.py` | 自动生成汇总报告（读 JSON，无人工誊抄）|
| **`build_yolo_coral_dataset.py`** | **P3**：Coralscapes 掩膜 → 个体框 → YOLO 数据集 |
| **`train_yolo_coral.py`** | **P3**：YOLOv9c 训练 + 评估（mAP / 逐图计数误差）|
| **`count_coral_yolo.py`** | **P3**：个体计数推理（CLI + 服务用 `CoralCounter`）|
| **`verify_serve_additive.py`** | **P3**：证明「只新增字段」的改动前后逐键比对 |

---

## 五、实测结果

完整结果见 **[reports/最终结果汇总.md](reports/最终结果汇总.md)**（自动生成）。

### 5.1 覆盖率（优势项）

| 项目 | 结果 |
|---|---|
| 分割 mIoU（1024px，166 张官方验证集）| **0.548** |
| 活珊瑚 IoU / 白化珊瑚 IoU | 0.711 / 0.786 |
| **星地验证** | 模型 **39.71%** vs RCM 实地 **39.56%** |

### 5.2 属级识别

| 项目 | 结果 |
|---|---|
| 类别数 / 测试样本 | 34 属 / 1,116 张（仙本那留出集）|
| Top-1 | **86.12%**（聚类 95% CI 83.33–88.88）|
| 宏 F1 / ECE | 0.8204 / 0.0294 |

### 5.3 白化状态

| 目标域 | 白化召回 | 二分类准确率 |
|---|---|---|
| 第三方独立数据集（Roboflow，剔除泄漏）| 96.77% | **98.21%** |

> 来源：`reports/new_bleaching_bleaching_all_test_clean168.json`（n=168，剔 89 张 pHash 跨 split 近重复）。
> 可脚本复现：`python scripts/eval_new_bleaching.py --task bleaching_all --split test --exclude-phash`。
| 原 Kaggle 域 | 88.78% | 91.26% |
| 印太域（印尼） | 42.31% | 82.95% |

> ⚠️ 上表为**服务实际部署的 `bleaching_all`**（`serve_fusion.py` 的 `BLEACH_DIRS[0]`）。
> 另一模型 `bleaching_ip` 在同一 `test_ip`（n=176）上准确率为 85.23%＝多数类基线 85.23%，
> 两者差异 **McNemar p=0.424 不显著** —— 引用时务必写明是哪个模型（见 `reports/mcnemar_bleaching_all_vs_bleaching_ip_test_ip.json`）。

### 5.4 珊瑚个体计数（P3 · 附加能力）

| 项目 | 结果 |
|---|---|
| **mAP@0.5**（官方 val 166 张，单类 `coral`）| **0.4217**（验收线 0.35）|
| mAP@0.5:0.95 / precision / recall | 0.2757 / 0.4929 / 0.4375 |
| 个体数总量偏差 / 逐图 MAE（conf=0.20）| **+2.3%**（真值 4254 vs 预测 4350）/ 9.43 个 |
| 训练集（官方 train 全 9 分片）| 1517 张 / 32976 个个体框 |
| 泄漏隔离 | train 22 个站点 vs val 3 个站点，**不重叠** |

> 📌 **计数工作点**：mAP 与置信度阈值无关，但**数出来几株**强相关 —— 默认 `conf=0.20` 时
> 总量偏差 +2.3%，而 `conf=0.25` 时会少算 15.7%。完整扫描见 `reports/yolo_coral_count_thresholds.json`。
> 服务推理长边为 **896**（分辨率扫描显示 896 与 1024 等价，取更快的 896）。

> ⚠️ **真值口径**：个体框由 Coralscapes **语义掩膜的同类连通域**自动导出（**非人工实例标注**），
> 且紧贴的同类珊瑚会合并成 1 个。因此上表是「与该自动真值的一致程度」，
> 不能等同于人工标注标准下的实例检测精度。详见 [docs/项目交接与续接指引.md](docs/项目交接与续接指引.md) §7.6。

### 5.5 使用边界（**重要**）

| 拍摄条件 | 活珊瑚估计误差 |
|---|---|
| ≤3m | −2.06 pt |
| 8m（典型潜水）| −3.01 pt ✅ 可用 |
| 15m 浑浊 | **−39.46 pt（完全失效）** ❌ |
| 20m 浑浊 | **−39.46 pt** ❌ |

> **建议：拍摄深度 ≤10m 或使用补光灯。** 两种分辨率（512/1024px）下结论一致，
> 说明失效源于水下光衰减的物理限制。

---

## 六、已知局限（务必与结论一并引用）

完整版见 **[docs/评估方法与局限.md](docs/评估方法与局限.md)**；
与原方案的技术选型差异见 **[docs/技术选型偏差说明.md](docs/技术选型偏差说明.md)**。

| 局限 | 说明 |
|---|---|
| **站点级验证不成立** | 覆盖率结论仅适用**区域尺度**；站点级存在 +11.7 pt 偏差（r=−0.56）|
| **无人类基线** | 无法回答"模型达到什么水平"，已声明为永久局限 |
| **无逐样本覆盖率误差** | 缺少像素级/样方级真值，需标准化样方照片 |
| **白化检测印太域召回偏低** | 仅 42.31%，根因是判别边界跨域错位 |
| **计数真值为自动标注** | 个体框来自掩膜连通域，紧贴个体合并 → 计数系统性偏少；跨域（仙本那实拍）未做实例级人工核验 |
| **气候数据只覆盖仙本那网格，且非实时** | 仅 4.025–5.025°N × 118.025–119.525°E，**1985–2025 共 41 年历史值（可选年份：2025/2024/2023/2020/2016/2010，接口支持任意年份）**；**网格外坐标直接返回 `ok=false`**（不给最近格点的值），也不能回答"现在热压力多少" |
| **投放建议只是热压力维度，且不是效果评估** | 风险月 = DHW≥4 ∪ HotSpot≥1；**样本 41 年（1985–2025，DHW 全部逐日）**、5km 格点非礁点；项目**没有投放后存活率数据**，因此"效果好"不能写；西缘格点 DHW 异常偏高（疑似近岸效应），引用前须实地核实 |
| β=6 工作点为测试集调参 | 该工作点指标偏乐观 |

---

## 七、复现流程

本仓库**不含数据与权重**（体积过大），可通过脚本重新生成：

```bash
# 0) 状态体检：查看哪些阶段已完成、下一步该做什么
python scripts/resume_all.py

# 1) 一键续跑所有未完成阶段（幂等，可反复运行）
python scripts/resume_all.py --run

# 2) 生成汇总报告
python scripts/make_report.py
```

数据下载阶段需要网络（iNaturalist / HuggingFace 镜像 / NOAA）。
部分境外源在国内需要镜像，脚本已内置重试与断点续传。

---

## 八、环境

| 项目 | 版本 |
|---|---|
| GPU | NVIDIA RTX 5060 Laptop 8GB |
| Python | 3.12 |
| PyTorch | 2.x + CUDA |
| transformers | 5.x（SegFormer）|
| 关键依赖 | torchvision / **ultralytics 8.4（YOLOv9c 个体计数）** / **scipy + opencv（连通域）** / fastapi / uvicorn / pyarrow / pillow / numpy |

---

## 九、引用

- **Coralscapes**：Sauder et al. (2025). *The Coralscapes Dataset*. arXiv:2503.20000
- **Reef Check Malaysia**：Szereday et al. (2025). DOI 10.5281/zenodo.15290515
- **NOAA Coral Reef Watch**：https://coralreefwatch.noaa.gov
- **iNaturalist**：https://www.inaturalist.org
