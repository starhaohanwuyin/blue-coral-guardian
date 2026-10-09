# 蓝珊 · 珊瑚识别模型与服务（coral_ml）

微信小程序「珊瑚识别」页背后的完整 AI 链路：**数据 → 训练 → 推理服务 → DSH Skill → 小程序页面**。

目标（本项目范围内只做两件事）：
1. **识别是什么珊瑚** —— 30 类种级分类
2. **评估珊瑚白化程度** —— 健康 / 白化 / 死亡 三分类

---

## 一、数据来源（均为实际下载并验证过）

| 用途 | 数据集 | 来源 | 规模 | 许可 |
|---|---|---|---|---|
| **珊瑚种类** | `tdros/corals` | HuggingFace | 3757 张 / 30 类 | 见数据集页 |
| **白化程度** | `sonainjamil/bhd-corals` | Kaggle | Healthy 712 / Bleached 720 / Dead 150 | 见数据集页 |
| 白化扩充 | `sonainjamil/bleached-corals-detection` | Kaggle | Bleached 184 / Unbleached 158 | 见数据集页 |
| 白化扩充 | `vencerlanz09/healthy-and-bleached-corals-image-classification` | Kaggle | bleached 485 / healthy 438 | 见数据集页 |
| 分割（未用于本次训练） | The Coralscapes Dataset | Zenodo `10.5281/zenodo.15061505` | 2075 图 / 39 类 / 红海 | **Apache-2.0** |
| 环境数据（未用于本次训练） | NOAA CRW v3.1 5km | CoastWatch ERDDAP | 1985-04-01 ~ 今，0.05° | 公有领域 |

> **为什么白化只做 3 档而不是 4 档**：现有公开数据只有 Healthy / Bleached / Dead 三档，
> 「轻度/严重」没有任何标注数据支撑，硬分档等于编造标签。3 档同时正好对应
> 项目简介里写的"精准区分**活珊瑚、白化珊瑚、死亡珊瑚**"。

### 环境数据（NOAA）已验证可用

```
# 仙本那区域日序列（DHW / HotSpot / SSTA / 白化预警），1985 → 今
https://coastwatch.pfeg.noaa.gov/erddap/griddap/NOAA_DHW.csv?CRW_DHW,CRW_HOTSPOT,CRW_SSTANOMALY,CRW_BAA[(1985-04-01):1:(2026-10-06)][(5.0):1:(4.0)][(118.0):1:(119.5)]
```

实测（2024-08-01，仙本那外海）：**DHW = 4.77 ~ 5.89 °C-weeks**，已超过 CRW 的 4 °C-weeks「显著白化」阈值 ——
可与 2024 年当地实地调查（平均白化 14%、部分点位 69.2%）形成完整的证据链。

---

## 二、目录结构

```
coral_ml/
├── data/
│   ├── raw/                原始下载数据（不入库）
│   └── processed/<task>/{train,val,test}/<class>/   整理后的 ImageFolder 结构
├── scripts/
│   ├── split_data.py       数据整理：MD5 去重 + 类别映射 + 分层划分（防泄漏）
│   ├── train.py            训练：迁移学习 + 两阶段 + 温度标定 + 选择性预测评估
│   ├── serve.py            推理服务：FastAPI，一次返回种类 + 白化
│   └── map_bleaching.json  白化类名映射（3 个数据集类名归一）
├── weights/<task>/best.pt  模型权重
├── reports/<task>/         metrics.json / confusion_matrix.csv
└── dsh-skill/              DSH Skill 插件（1 Skill + 2 工具）
```

---

## 三、完整流程

```bash
# 0) 配置 Kaggle 凭据（一次性）
#    把 token 写入  C:\Users\<你>\.kaggle\access_token

# 1) 下载数据
kaggle datasets download -d sonainjamil/bhd-corals -p data/raw
kaggle datasets download -d sonainjamil/bleached-corals-detection -p data/raw
kaggle datasets download -d vencerlanz09/healthy-and-bleached-corals-image-classification -p data/raw
#   种类数据（HuggingFace，单文件 data.zip）
curl -L -C - -o data/raw/tdros_corals/data.zip \
  https://huggingface.co/datasets/tdros/corals/resolve/main/data.zip

# 2) 整理 + 划分（关键：去重与分层，避免指标虚高）
python scripts/split_data.py --task bleaching \
  --src data/raw/bhd-corals \
  --src data/raw/bleached-corals-detection \
  --src data/raw/healthy-and-bleached-corals-image-classification \
  --map-file scripts/map_bleaching.json

python scripts/split_data.py --task species --src data/raw/tdros_corals_extract/corals

# 3) 训练（RTX 5060 8GB 实测可用）
python -u scripts/train.py --task bleaching --img-size 224 --epochs 35 --batch-size 32
python -u scripts/train.py --task species   --img-size 288 --epochs 24 --batch-size 24
#   被中断后用 --resume 接着跑（每轮都会存 last.pt）

# 4) 启动推理服务
python scripts/serve.py --port 8000
#   GET  /health
#   POST /predict          (multipart: file=<image>)
#   POST /predict_base64
```

---

## 四、指标口径（重要）

**不要报"整体测试集 99.9%"** —— 那只能靠数据泄漏（同一段视频的相邻帧同时落进训练集和测试集）造出来。
本项目提供的是**选择性预测（selective prediction）**口径，真实且可复核：

| 口径 | 含义 |
|---|---|
| Top-1 准确率 | 全部测试样本的整体准确率（如实报） |
| 宏平均 F1 | 类别不均衡下的稳健指标 |
| **高置信区间准确率** | 置信度 ≥ 阈值 θ 的样本上的准确率，并**必须同时给出覆盖率** |
| 拒识率 | 低于 θ 自动标记「需人工复核」的比例 |

`train.py` 会输出 coverage–accuracy 曲线，并自动找出「达到目标准确率所需的最小阈值与对应覆盖率」。
推理服务会把 `needReview` 字段一路传给小程序，页面显式展示 —— 这样既拿到漂亮数字，
又兑现了项目简介里"明确误差范围与不确定性、划定安全使用边界"的承诺。

---

## 五、DSH Skill 插件

`dsh-skill/` 是一个标准 Cordis 插件 bundle：

- **Skill**：`coral-identification`（珊瑚种类识别与白化程度评估）
- **Tool**：`identify_coral(image_path)` —— 双任务识别，返回置信度与是否需人工复核
- **Tool**：`coral_service_status()` —— 查询服务与模型状态（只读）

安装到 DSH profile：

```bash
dsh plugin --profile desktop add "file:D:\大学作业\广东海洋大学的珊瑚评测小程序\coral_ml\dsh-skill"
```

服务地址通过环境变量 `CORAL_API_BASE` 指定（默认 `http://127.0.0.1:8000`）。

---

## 六、小程序接入

`blue_coral/utils/config.js`：

```js
CORAL_API: 'http://127.0.0.1:8000',  // 珊瑚识别服务
USE_REAL_AI: true,                   // false 时用本地演示数据
```

`blue_coral/pages/ai/` 已按新结果结构重写：上传 → 识别 → 「珊瑚种类」+「白化程度」双卡片，
含 Top-3 候选、三档概率条、需复核提示与免责声明，并把识别历史持久化到本机。

> ⚠️ 开发期小程序直连 `127.0.0.1` 可行（`urlCheck: false`）；
> **真机与发布必须换成 HTTPS 已备案域名**。
