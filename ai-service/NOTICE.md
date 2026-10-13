# 使用声明与许可证清单（NOTICE）

## ⚠️ 项目性质：仅限研究 / 竞赛用途，非商业

本项目所有模型权重、数据集与衍生结果**仅用于学术研究、课程作业与竞赛**，
**不得用于任何商业用途**。原因：本项目训练数据中包含大量
**CC BY-NC（禁止商业使用）** 许可的影像。

对外展示、论文、答辩材料中**必须明示**本限制。

---

## 训练数据许可证清单

| 数据源 | 规模 | 许可证 | 可否商用 | 用途 |
|---|---|---|---|---|
| **iNaturalist 仙本那** | 587 观察 / 1319 图 | 混合：**cc-by-nc 456 (78%)**、cc-by-sa 107、cc-by 3、nc-nd 7、nc-sa 2、none 12 | ❌ **含 NC，不可商用** | 种类识别**测试集** |
| **iNaturalist 珊瑚大三角** | 16,245 观察 | 同上（以 NC 为主） | ❌ 含 NC | 种类识别**训练集** |
| **Coralscapes** | 2075 图 / 39 类 | **Apache-2.0** | ✅ 可商用 | 分割模型训练 |
| **CORAL_INDO V2** | 7011 图（印尼） | 见 Kaggle 数据集页 | ⚠️ 需核实 | 白化域适配 |
| **bhd-corals / bleached-corals-detection / healthy-and-bleached** | 2,847 图 | 见 Kaggle 各数据集页 | ⚠️ 需核实 | 白化基础训练 |
| **tdros/corals** | 3757 图 | 见 HF 数据集页 | ⚠️ 需核实 | （已弃用，加勒比域不匹配） |
| **NOAA CRW / ERDDAP** | 1985–今 | 美国联邦政府作品（公有领域） | ✅ | 环境热压力数据 |
| **Reef Check Malaysia 报告** | 43 份 PDF | 报告注明可用于教育/非营利，**禁止转售** | ❌ 不可商用 | 实地验证数据 |
| **NOAA 太平洋底栖 YOLO11m** | 模型 | 待核实（经第三方重分发） | ⚠️ | 骨干初始化 |

---

## 模型与衍生成果

| 产物 | 训练数据 | 许可约束 |
|---|---|---|
| `weights/segformer_coralscapes` | Coralscapes (Apache-2.0) | ✅ 无 NC 约束 |
| `weights/bleaching_ip` | Kaggle 白化集 + CORAL_INDO | ⚠️ 待核实 |
| `weights/species_ip`（待训） | iNaturalist（含 NC） | ❌ **不可商用** |

---

## 合规要求（必须遵守）

1. **对外材料标注**：论文、答辩、Demo 页须注明「本研究仅用于学术与竞赛目的，非商业用途」
2. **图像归属**：使用 iNaturalist 影像时保留 `coral_ml/data/inat_dataset/ATTRIBUTION.csv` 中的作者与许可信息
3. **不得转售**：不得转售 Reef Check Malaysia 报告或其内容
4. **若未来需商业化**：必须重新用 CC0/CC-BY/CC-BY-SA/Apache-2.0 数据训练，
   或逐一联系权利人取得授权

---

## 引用要求

使用本项目涉及的数据时，请引用原始出处：

- **Coralscapes**：Sauder, J., Domazetoski, V., Banc-Prandi, G., Perna, G., Meibom, A., & Tuia, D. (2025).
  *The Coralscapes Dataset: Semantic Scene Understanding in Coral Reefs.* arXiv:2503.20000.
  https://doi.org/10.5281/zenodo.15061505
- **Reef Check Malaysia 白化报告**：Szereday, S. et al. (2025).
  *The 4th global coral bleaching event in Malaysia: insights, outcomes, and paths forward.*
  https://doi.org/10.5281/zenodo.15290515
- **NOAA Coral Reef Watch**：NOAA Coral Reef Watch (2026). *NOAA Coral Reef Watch 5km Product Suite v3.1.*
  https://coralreefwatch.noaa.gov
- **iNaturalist**：iNaturalist contributors, iNaturalist (2026). https://www.inaturalist.org
