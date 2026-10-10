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
| **海表热压力**（环境数据插件）| NOAA CRW v3.1 5km | 2023–2025 三年，覆盖仙本那 |
| **修复优先级 + 保育报告**（综合研判插件）| 规则型决策支持启发式 | 可解释，不报准确率 |
| **修复模拟**（10 年恢复轨迹）| 逻辑斯蒂增长 + 热浪致死 | 示意性推演，非预测 |
| **水下图像增强** | 传统 CV + **CNN（U-Net）** | 三方对比见 `reports/enhance_compare.json` |

**核心外部验证**：模型在仙本那 180 张照片上的活珊瑚覆盖估计 **39.71%**，
与 Reef Check Malaysia 2024 实地调查的区域平均 **39.56%** 相差 **0.15 个百分点**。

---

## 二、快速开始

### 1. 启动评估服务

```bash
cd scripts
python serve_fusion.py --port 8000
```

等待约 40–60 秒（加载分割 + 属分类 + 白化分类三个模型），看到
`Uvicorn running on http://0.0.0.0:8000` 即为就绪。

### 2. 健康检查

```bash
curl http://127.0.0.1:8000/health
```

关键字段：
```json
{"status":"ok","segmentation":"loaded","species":"loaded",
 "segModel":"segformer_coralscapes","segCalibrated":true,"categories":40}
```

> ⚠️ `segCalibrated` 必须为 `true`。若为 `false` 说明加载了未校准的实验权重，
> 覆盖率会偏高约 13 个百分点。

### 3. 端到端自检（推荐）

```bash
python scripts/e2e_check.py
```
期望输出 `通过 15/15`。

### 4. 单张照片评估

```bash
python scripts/segment_coral.py --image /path/to/coral.jpg --json
```

---

## 三、接口

| 端点 | 说明 |
|---|---|
| `GET /health` | 服务与模型状态 |
| `POST /analyze` | 上传图片 → 覆盖率 + 珊瑚属 + 白化状态 + 拍摄条件 |
| `POST /analyze_base64` | 同上，base64 传图 |
| `GET /sample?set=semporna&index=0` | 样例图（`semporna` / `bleached` / `healthy`），供无图时演示 |

`/analyze` 返回结构：

```json
{
  "cover": {"alivePct":0.3966,"bleachedPct":0.0312,"deadPct":0.0205,
            "algaePct":0.10,"substratePct":0.3983,"coralTotalPct":0.4483,
            "bleachingShareOfCoral":0.0696},
  "coralRegion": {"reliable":true,"top":[{"genus":"Acropora","confidence":0.78}]},
  "bleaching": {"label":"bleached","labelCn":"白化","confidence":0.96,"reliable":true},
  "captureQuality": {"level":"good","usable":true,"contrast":0.23,
                     "thresholds":{"goodContrast":0.0306,"warnContrast":0.0243}},
  "inferenceMs": 620
}
```

---

## 四、目录结构

```
coral_ml/
├── scripts/            训练与评估脚本
├── docs/               方案、核验、答辩要点、评估方法与局限
├── reports/            结果 JSON（报告的权威数据源）
├── dsh-skill/          DSH Agent 插件（3 个工具）
├── NOTICE.md           许可证与合规声明
├── data/               数据集（已 gitignore，约 13 GB）
└── weights/            模型权重（已 gitignore，约 1.1 GB）
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
| `cross_validate.py` | 星地交叉验证 |
| `validate_site_level.py` | 站点级验证 |
| `e2e_check.py` | 端到端自检（15 项）|
| `resume_all.py` | **一键状态体检 / 续跑** |
| `make_report.py` | 自动生成汇总报告（读 JSON，无人工誊抄）|

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
| 原 Kaggle 域 | 88.78% | 91.26% |
| 印太域（印尼） | 42.31% | 82.95% |

### 5.4 使用边界（**重要**）

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
| 关键依赖 | torchvision / fastapi / uvicorn / pyarrow / pillow / numpy |

---

## 九、引用

- **Coralscapes**：Sauder et al. (2025). *The Coralscapes Dataset*. arXiv:2503.20000
- **Reef Check Malaysia**：Szereday et al. (2025). DOI 10.5281/zenodo.15290515
- **NOAA Coral Reef Watch**：https://coralreefwatch.noaa.gov
- **iNaturalist**：https://www.inaturalist.org
