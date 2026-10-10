# dsh-coral-skill

DSH Agent 插件：把 `coral_ml/scripts/serve_fusion.py` 的推理能力包装成 **1 个 Skill + 6 个工具**，
供 Agent 自主调度。

> ⚠️ 本项目仅用于学术研究与竞赛，非商业用途。所有结论仅供参考，不替代专业珊瑚礁评估。

## 依赖的服务

先启动生产服务（默认 `http://127.0.0.1:8000`，可用环境变量 `CORAL_API_BASE` 覆盖）：

```bash
cd coral_ml/scripts && python serve_fusion.py --port 8000
```

服务共 10 个端点；本插件用到其中 6 个：
`/analyze`、`/count`、`/climate`、`/climate/profile`、`/priority`、`/health`。

## 工具（6 个）

| 工具 | 作用 | 依赖端点 |
|---|---|---|
| `identify_coral` | 珊瑚**属**（34 属，属级非种级）+ 白化状态 + 覆盖率 | `POST /analyze` |
| `assess_coral_cover` | 详细覆盖率评估 | `POST /analyze` |
| `coral_service_status` | 服务与模型状态（只读） | `GET /health` |
| `get_climate_context` | NOAA 海表热压力（DHW / BAA / HotSpot / SSTA / SST）| `GET /climate` |
| **`get_deployment_advice`** | **投放建议**：往年白化预警记录 → 建议避开哪几个月 | `GET /climate/profile` |
| `assess_restoration_priority` | 修复优先级 + 中文保育报告 + `deploymentAdvice` | `POST /priority` |

## 能力边界（Agent 汇报时必须一并说明）

| 项 | 限制 |
|---|---|
| 覆盖率 | 仅**区域尺度**；站点级不成立；≤8m 可用、**≥15m 完全失效** |
| 属级 | **34 属**（属级，非种级），长尾属弱，受 iNaturalist 采样偏置影响 |
| 白化 | 整图级结论；**印太域召回仅 42.31%，不可用于印尼照片** |
| 个体计数 | 真值为掩膜连通域（**自动标注**），紧贴个体合并 → 偏少；**跨域未验证** |
| 气候数据 | 仅 4.025–5.025°N × 118.025–119.525°E、**2023–2025 历史值**（非实时）；**网格外返回 `ok=false`** |
| 投放建议 | **只有热压力一个维度**；**不是投放效果评估**（项目无投放后存活率数据）|

## 安装

```bash
dsh plugin --profile desktop add "file:<仓库路径>/coral_ml/dsh-skill"
```

卸载：`dsh plugin --profile desktop remove dsh-coral-skill`
