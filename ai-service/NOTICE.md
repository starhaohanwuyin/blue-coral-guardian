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

## 图片来源与致谢（推文配图，2026-10）

以下图片来自 Wikimedia Commons，均为公有领域或 CC 许可，已本地化到 `web/mp/assets/img/`：

| 文件 | 许可 | 来源 |
|---|---|---|
| tweet_restore.jpg | Public domain | https://commons.wikimedia.org/wiki/File:FKNMS_-_coral_nursery_%2827367671414%29.jpg |
| tweet_edu.jpg | Public domain | https://commons.wikimedia.org/wiki/File:Biscayne_National_Park_V-snorkel_entry.jpg |
| tweet_survey.jpg | Public domain | https://commons.wikimedia.org/wiki/File:NOAA_diver_Structure-from-Motion_%28SfM%29_survey_Swains_Island_2023.png |
| tweet_reef2.jpg | Public domain | https://commons.wikimedia.org/wiki/File:Baker_Island_reef_Anthias_2023.png |
| tweet_sst.jpg | Public domain | https://commons.wikimedia.org/wiki/File:Satellite_sensor_derived_sea_surface_temperature_anomalies_%282268-609%29.jpg |
| tweet_bleach1.jpg | CC BY-SA 2.0 | https://commons.wikimedia.org/wiki/File:Bleached_Staghorn_Coral.jpg |
| tweet_bleach4.jpg | Public domain | https://commons.wikimedia.org/wiki/File:Coral_bleaching.png |
| tweet_transect.jpg | Public domain | https://commons.wikimedia.org/wiki/File:Divers_install_monitoring_instruments_on_coral_reef.jpg |
| tweet_bleach3.jpg | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Colorful_Coral_Bleaching.jpg |
| tweet_ocean.jpg | Public domain | https://commons.wikimedia.org/wiki/File:Aegean_Sea_%28MODIS_2018-07-17%29.jpg |
| tweet_coast.jpg | Public domain | https://commons.wikimedia.org/wiki/File:Maldives_island_beach_1.jpg |
| tweet_gbr.jpg | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Aerial_View_of_Great_Barrier_Reef%2C_Queensland_%28Ank_Kumar%29_02.jpg |
| tweet_buoy.jpg | CC BY 4.0 | https://commons.wikimedia.org/wiki/File:D%C3%A9ploiement_de_bou%C3%A9es_PIRATA_et_d%27un_profileur_Argo_APEX_%28Ifremer_00651-76357%29.jpg |

## 图片来源与致谢（联网扩充的珊瑚种类，2026-10）

以下照片来自 Wikimedia Commons（公有领域或 CC 许可），已本地化到 `web/mp/assets/img/`：

| 物种 | 文件 | 许可 | 作者 | 来源页 |
|---|---|---|---|---|
| 强壮鹿角珊瑚（Acropora valida） | species_acropora-valida.jpg | CC BY 3.0 | David Witherall and Lyka | https://commons.wikimedia.org/wiki/File:Acropora_valida.jpeg |
| 多孔鹿角珊瑚（Acropora millepora） | species_acropora-millepora.jpg | CC BY-SA 4.0 | MDC Seamarc Maldives | https://commons.wikimedia.org/wiki/File:Acropora_millepora_Maldives.jpg |
| 指状鹿角珊瑚（Acropora digitifera） | species_acropora-digitifera.jpg | CC BY-SA 4.0 | MDC Seamarc Maldives | https://commons.wikimedia.org/wiki/File:Acropora_digitifera_Maldives_2.jpg |
| 美丽鹿角珊瑚（Acropora formosa） | species_acropora-formosa.jpg | CC BY 2.0 | Paul Asman and Jill Lenoble | https://commons.wikimedia.org/wiki/File:Plausibly_staghorn_coral_Acropora_formosa_%287504783684%29.jpg |
| 鼻形轴孔珊瑚（Acropora nasuta） | species_acropora-nasuta.jpg | CC BY-SA 3.0 | Nhobgood | https://commons.wikimedia.org/wiki/File:Acropora_nasuta_%28Hard_coral%29.jpg |
| 矛枝轴孔珊瑚（Acropora aspera） | species_acropora-aspera.jpg | CC BY 3.0 | Michelle Jonker | https://commons.wikimedia.org/wiki/File:Acropora_aspera.JPG |
| 柔枝轴孔珊瑚（Acropora tenuis） | species_acropora-tenuis.jpg | CC BY-SA 4.0 | MDC Seamarc Maldives | https://commons.wikimedia.org/wiki/File:Acropora_tenuis_Maldives.jpg |
| 黍形轴孔珊瑚（Acropora cerealis） | species_acropora-cerealis.jpg | CC BY 3.0 | Kate Osborne | https://commons.wikimedia.org/wiki/File:Acropora_cerealis.jpg |
| 佛州轴孔珊瑚（Acropora florida） | species_acropora-florida.jpg | CC BY-SA 3.0 | A. C. Tatarinov | https://commons.wikimedia.org/wiki/File:Acropora_florida.jpg |
| 篱枝轴孔珊瑚（Isopora palifera） | species_isopora-palifera.jpg | CC BY-SA 4.0 | MDC Seamarc Maldives | https://commons.wikimedia.org/wiki/File:Acropora_palifera_Maldives.jpg |
| 细枝鹿角珊瑚（Pocillopora damicornis） | species_pocillopora-damicornis.jpg | CC BY-SA 3.0 | User:Haplochromis | https://commons.wikimedia.org/wiki/File:Pocillopora_damicornis.jpg |
| 疣鹿角珊瑚（Pocillopora verrucosa） | species_pocillopora-verrucosa.jpg | CC BY-SA 3.0 | Philippe Bourjon | https://commons.wikimedia.org/wiki/File:Pocillopora_verrucosa_R%C3%A9union.jpg |
| 多曲杯形珊瑚（Pocillopora meandrina） | species_pocillopora-meandrina.jpg | CC BY-SA 4.0 | Brocken Inaglory | https://commons.wikimedia.org/wiki/File:Pocillopora_meandrina_with_a_resident_fish.jpg |
| 巨枝鹿角珊瑚（Pocillopora eydouxi） | species_pocillopora-eydouxi.jpg | CC BY 2.0 | Paul Asman and Jill Lenoble | https://commons.wikimedia.org/wiki/File:Black-axil_and_bluegreen_chromis%2C_Chromis_atripectoralis_and_C._viridis_%287669151820%29.jpg |
| 箭排孔珊瑚（Seriatopora hystrix） | species_seriatopora-hystrix.jpg | CC BY-SA 3.0 | Faol | https://commons.wikimedia.org/wiki/File:Seriatopora_hystrix.jpg |
| 浅杯排孔珊瑚（Seriatopora caliendrum） | species_seriatopora-caliendrum.jpg | CC BY 2.0 | Will Thomas | https://commons.wikimedia.org/wiki/File:Seriatopora_caliendrum%2C_verde.jpg |
| 萼形柱珊瑚（Stylophora pistillata） | species_stylophora-pistillata.jpg | CC BY 4.0 | Kate Osborne | https://commons.wikimedia.org/wiki/File:Euphyllia_cristata%2C_septa.jpg |
| 澄黄滨珊瑚（Porites lutea） | species_porites-lutea.jpg | CC BY-SA 3.0 | Philippe Bourjon | https://commons.wikimedia.org/wiki/File:Porites_lutea.jpg |
| 团块滨珊瑚（Porites lobata） | species_porites-lobata.jpg | Public domain | not specified | https://commons.wikimedia.org/wiki/File:Lisianski_coral_lrg.jpg |
| 柱形微孔珊瑚（Porites cylindrica） | species_porites-cylindrica.jpg | Public domain | NPS photo - Larry Basch | https://commons.wikimedia.org/wiki/File:Porites_cylindrica_en_Samoa.jpg |
| 澳洲微孔珊瑚（Porites australiensis） | species_porites-australiensis.jpg | Public domain | NPS photo - Jim Maragos | https://commons.wikimedia.org/wiki/File:Porites_australiensis%2C_Guam.jpg |
| 万花筒珊瑚（Goniopora lobata） | species_goniopora-lobata.jpg | CC BY-SA 4.0 | Diego Delso | https://commons.wikimedia.org/wiki/File:Coral_%28Goniopora_lobata%29%2C_islas_Ad_Dimaniyat%2C_Om%C3%A1n%2C_2024-08-13%2C_DD_129.jpg |
| 隐藏角菊珊瑚（Favites abdita） | species_favites-abdita.jpg | Public domain | Stickpen | https://commons.wikimedia.org/wiki/File:Favitesabdita.jpg |
| 五边角菊珊瑚（Favites pentagona） | species_favites-pentagona.jpg | CC BY-SA 3.0 | Bondolo | https://commons.wikimedia.org/wiki/File:Favites_pentagona.JPG |
| 实心角菊珊瑚（Favites halicora） | species_favites-halicora.jpg | CC BY-SA 4.0 | Ahmed Abdul Rahman for MDC Seamarc Maldives | https://commons.wikimedia.org/wiki/File:Favites_halicora_Maldives.JPG |
| 环菊珊瑚（Dipsastraea speciosa） | species_dipsastraea-speciosa.jpg | Public domain | James Maragos/USFWS | https://commons.wikimedia.org/wiki/File:Favia_speciosa.jpg |
| 正菊珊瑚（Dipsastraea favus） | species_dipsastraea-favus.jpg | CC BY-SA 4.0 | Diego Delso | https://commons.wikimedia.org/wiki/File:Coral_%28Favia_favus%29%2C_parque_nacional_Ras_Muhammad%2C_Egipto%2C_2022-03-27%2C_DD_117.jpg |
| 网状菊花珊瑚（Goniastrea retiformis） | species_goniastrea-retiformis.jpg | CC BY-SA 3.0 | Hectonichus | https://commons.wikimedia.org/wiki/File:Faviidae_-_Goniastrea_retiformis.JPG |
| 翼形角星珊瑚（Goniastrea pectinata） | species_goniastrea-pectinata.jpg | CC BY-SA 4.0 | Diego Delso | https://commons.wikimedia.org/wiki/File:Coral_%28Goniastrea_pectinata%29%2C_mar_Rojo%2C_Egipto%2C_2023-04-15%2C_DD_41.jpg |
| 大脑纹珊瑚（Platygyra daedalea） | species_platygyra-daedalea.jpg | CC BY-SA 4.0 | Philippe Bourjon | https://commons.wikimedia.org/wiki/File:Platygyra_daedalea_R%C3%A9union.jpg |
| 中国脑纹珊瑚（Platygyra sinensis） | species_platygyra-sinensis.jpg | CC BY-SA 4.0 | MDC Seamarc Maldives | https://commons.wikimedia.org/wiki/File:Platygira_sinensis_Maldives.JPG |
| 细枝碓珊瑚（Hydnophora rigida） | species_hydnophora-rigida.jpg | CC BY-SA 3.0 | Randi Rotjan | https://commons.wikimedia.org/wiki/File:Rotjan_-_Kanton_Day_1_%28187%29.JPG |
| 大碓珊瑚（Hydnophora exesa） | species_hydnophora-exesa.jpg | CC BY 3.0 | Ryan McMinds | https://commons.wikimedia.org/wiki/File:Hydnophora_exesa%2C_Lizard.jpeg |
| 联合瓣叶珊瑚（Lobophyllia hemprichii） | species_lobophyllia-hemprichii.jpg | CC BY-SA 3.0 | Petra | https://commons.wikimedia.org/wiki/File:Lobophyllia_hemprichii.jpg |
| 束形瓣叶珊瑚（Lobophyllia corymbosa） | species_lobophyllia-corymbosa.jpg | CC BY-SA 4.0 | Diego Delso | https://commons.wikimedia.org/wiki/File:Coral_%28Lobophyllia_corymbosa%29%2C_mar_Rojo%2C_Egipto%2C_2023-04-18%2C_DD_165.jpg |
| 直纹合叶珊瑚（Symphyllia recta） | species_symphyllia-recta.jpg | CC BY 2.0 | Paul Asman and Jill Lenoble | https://commons.wikimedia.org/wiki/File:Dusky_anemonefish_Amphiprion_melanopus_%287663521478%29.jpg |
| 大棘星珊瑚（Acanthastrea echinata） | species_acanthastrea-echinata.jpg | CC BY-SA 3.0 | Philippe Bourjon | https://commons.wikimedia.org/wiki/File:Acanthastrea_echinata.jpg |
| 丛生盔形珊瑚（Galaxea fascicularis） | species_galaxea-fascicularis.jpg | CC BY-SA 4.0 | Diego Delso | https://commons.wikimedia.org/wiki/File:Coral_%28Galaxea_fascicularis%29%2C_mar_Rojo%2C_Egipto%2C_2023-04-18%2C_DD_129.jpg |
| 星形棘杯珊瑚（Galaxea astreata） | species_galaxea-astreata.jpg | CC BY 2.0 | Samuel Chow | https://commons.wikimedia.org/wiki/File:Coral_%28Galaxea_Astreata%29.png |
| 束形真叶珊瑚（Euphyllia glabrescens） | species_euphyllia-glabrescens.jpg | CC BY 2.0 | Ryan Boren | https://commons.wikimedia.org/wiki/File:Euphyllia_glabrescens.jpg |
| 肾形真叶珊瑚（Euphyllia ancora） | species_euphyllia-ancora.jpg | CC BY-SA 3.0 | Shizhao | https://commons.wikimedia.org/wiki/File:Plerogyra_sinuosa%2C_Beijing.jpg |
| 陀螺珊瑚（Turbinaria peltata） | species_turbinaria-peltata.jpg | CC BY-SA 4.0 | Emőke Dénes | https://commons.wikimedia.org/wiki/File:Turbinaria_peltata_-_1.jpg |
| 膜形盘珊瑚（Turbinaria mesenterina） | species_turbinaria-mesenterina.jpg | CC BY-SA 2.0 | Richard Ling | https://commons.wikimedia.org/wiki/File:Turbinaria_mesenterina.jpg |
| 肾形盘珊瑚（Turbinaria reniformis） | species_turbinaria-reniformis.jpg | CC BY-SA 4.0 | Diego Delso | https://commons.wikimedia.org/wiki/File:Coral_%28Turbinaria_reniformis%29%2C_parque_nacional_Ras_Muhammad%2C_Egipto%2C_2022-03-28%2C_DD_132.jpg |
| 短管星珊瑚（Tubastraea coccinea） | species_tubastraea-coccinea.jpg | CC BY-SA 4.0 | Diego Delso | https://commons.wikimedia.org/wiki/File:Coral_sol_%28Tubastraea_coccinea%29%2C_Cabo_Pulmo%2C_Baja_California%2C_M%C3%A9xico%2C_2024-12-19%2C_DD_22.jpg |
| 真蕈珊瑚（Fungia fungites） | species_fungia-fungites.jpg | Public domain | Stickpen | https://commons.wikimedia.org/wiki/File:Fungiafungites.jpg |
| 棘状梳蕈珊瑚（Ctenactis echinata） | species_ctenactis-echinata.jpg | CC BY-SA 4.0 | Diego Delso | https://commons.wikimedia.org/wiki/File:Coral_plato_%28Ctenactis_echinata%29%2C_mar_Rojo%2C_Egipto%2C_2023-04-16%2C_DD_52.jpg |
| 同双星珊瑚（Diploastrea heliopora） | species_diploastrea-heliopora.jpg | CC BY-SA 3.0 | Nhobgood Nick Hobgood | https://commons.wikimedia.org/wiki/File:Helcogramma_striata_%28Neon_triplefin%29_on_Diploastrea_heliopora_%28Hard_coral%29.jpg |
| 板叶千孔珊瑚（Millepora platyphylla） | species_millepora-platyphylla.jpg | CC BY 3.0 | Esv - Eduard Solà Vázquez | https://commons.wikimedia.org/wiki/File:Millepora_platyphylla.JPG |
| 蓝绿肉质软珊瑚（Sarcophyton glaucum） | species_sarcophyton-glaucum.jpg | CC BY-SA 3.0 | Alexander Vasenin | https://commons.wikimedia.org/wiki/File:Sarcophyton_glaucum_at_Shaab_Angosh_reef.JPG |
| 杯形肉质软珊瑚（Sarcophyton ehrenbergi） | species_sarcophyton-ehrenbergi.jpg | CC BY 2.0 | Rickard Zerpe | https://commons.wikimedia.org/wiki/File:False_Toadstool_Coral_%28Sarcophyton_ehrenbergi%29_%2848737740742%29.jpg |
| 柔指形软珊瑚（Sinularia flexibilis） | species_sinularia-flexibilis.jpg | CC BY-SA 3.0 | Nhobgood Nick Hobgood | https://commons.wikimedia.org/wiki/File:Sinularia_flexibilis_%28Slimy_leather_coral%29.jpg |
| 多指形软珊瑚（Sinularia polydactyla） | species_sinularia-polydactyla.jpg | CC BY 2.0 | Derek Keats from Johannesburg, South Africa | https://commons.wikimedia.org/wiki/File:Finger_leather_coral%2C_Sinularia_polydactyla_%286165871011%29.jpg |
| 隔板叶形软珊瑚（Lobophytum crassum） | species_lobophytum-crassum.jpg | CC BY-SA 4.0 | Diego Delso | https://commons.wikimedia.org/wiki/File:Coral_%28Lobophytum_crassum%29%2C_Zanz%C3%ADbar%2C_Tanzania%2C_2024-05-29%2C_DD_54.jpg |
| 红扇珊瑚（Melithaea ochracea） | species_melithaea-ochracea.jpg | CC BY-SA 3.0 | Anders Poulsen, Deep Blue (http://www.colours.dk/) | https://commons.wikimedia.org/wiki/File:Melithaea_ochracea2.jpg |
| 圆冠珊瑚（Cynarina lacrymalis） | species_cynarina-lacrymalis.jpg | CC BY-SA 3.0 | Alexander Vasenin | https://commons.wikimedia.org/wiki/File:Cynarina_lacrymalis_at_Bima_bay.JPG |

## 图片来源与致谢（联网扩充的珊瑚种类，2026-10）

以下照片来自 Wikimedia Commons（公有领域或 CC 许可），已本地化到 `web/mp/assets/img/`：

| 物种 | 文件 | 许可 | 作者 | 来源页 |
|---|---|---|---|---|
| 指表孔珊瑚（Montipora digitata） | species_montipora-digitata.jpg | Public domain | No machine-readable author provided. Haplochromis assumed (based on co | https://commons.wikimedia.org/wiki/File:Montipora_digitata.jpg |
| 头状蔷薇珊瑚（Montipora capitata） | species_montipora-capitata.jpg | Public domain | Dr. Dwayne Meadows, NOAA/NMFS/OPR | https://commons.wikimedia.org/wiki/File:Reef0607.jpg |
| 瘿叶表孔珊瑚（Montipora aequituberculata） | species_montipora-aequituberculata.jpg | Public domain | U.S. Fish and Wildlife Service Headquarters | https://commons.wikimedia.org/wiki/File:Montipora_aequituberculata.jpg |
| 叶形表孔珊瑚（Montipora foliosa） | species_montipora-foliosa.jpg | Public domain | Albert Kok at Dutch Wikipedia

(Original text: Albert Kok) | https://commons.wikimedia.org/wiki/File:Montipora2.jpg |
| 斯氏角孔珊瑚（Goniopora stokesi） | species_goniopora-stokesi.jpg | CC BY-SA 4.0 | Diego Delso | https://commons.wikimedia.org/wiki/File:Coral_%28Goniopora_stokesi%29%2C_Mah%C3%A9%2C_Seychelles%2C_2025-09-08%2C_DD_76.jpg |
| 片形绳纹珊瑚（Merulina ampliata） | species_merulina-ampliata.jpg | Public domain | NPS photo - Larry Basch | https://commons.wikimedia.org/wiki/File:Merulina_ampliata%2C_margen_colonia.jpg |
| 片形棘孔珊瑚（Echinopora lamellosa） | species_echinopora-lamellosa.jpg | Public domain | NPS - Larry Basch | https://commons.wikimedia.org/wiki/File:Echinopora_lamellosa.jpg |
| 豪勋爵棘星珊瑚（Acanthastrea lordhowensis） | species_acanthastrea-lordhowensis.jpg | CC BY 2.5 | Haplochromis | https://commons.wikimedia.org/wiki/File:Acanthastrea_lordhowensis.jpg |
| 泡纹珊瑚（Physogyra lichtensteini） | species_physogyra-lichtensteini.jpg | CC BY-SA 3.0 | Petra | https://commons.wikimedia.org/wiki/File:Physogyra_Lichtensteini.jpg |
| 分叉真叶珊瑚（Euphyllia divisa） | species_euphyllia-divisa.jpg | CC BY-SA 3.0 | Gdiggers | https://commons.wikimedia.org/wiki/File:Euphyllia_divisa.jpg |
| 双叶珊瑚（Catalaphyllia jardinei） | species_catalaphyllia-jardinei.jpg | CC BY-SA 3.0 | Tappinen | https://commons.wikimedia.org/wiki/File:Catalaphyllia_short.JPG |
| 石芝珊瑚（Fungia scutaria） | species_fungia-scutaria.jpg | Public domain | Dr. Dwayne Meadows, NOAA/NMFS/OPR | https://commons.wikimedia.org/wiki/File:Fungia_scutaria_1.jpg |
| 十字牡丹珊瑚（Pavona decussata） | species_pavona-decussata.jpg | CC BY-SA 3.0 | Haplochromis | https://commons.wikimedia.org/wiki/File:Skeleton_Pavona_decussata_2.JPG |
| 绣球雀屏珊瑚（Pavona cactus） | species_pavona-cactus.jpg | CC0 | Wmpearl | https://commons.wikimedia.org/wiki/File:Potato_chip_coral_%28Pavona_cactus%29%2C_Waikiki_Aquarium.JPG |
| 变形雀屏珊瑚（Pavona varians） | species_pavona-varians.jpg | CC BY-SA 4.0 | Philippe Bourjon | https://commons.wikimedia.org/wiki/File:Pavona_varians.jpg |
| 环形波纹珊瑚（Pachyseris speciosa） | species_pachyseris-speciosa.jpg | CC BY-SA 4.0 | Diego Delso | https://commons.wikimedia.org/wiki/File:Coral_%28Pachyseris_speciosa%29%2C_mar_Rojo%2C_Egipto%2C_2023-04-16%2C_DD_02.jpg |
| 指形沙珊瑚（Psammocora digitata） | species_psammocora-digitata.jpg | CC BY-SA 4.0 | Chaloklum Diving | https://commons.wikimedia.org/wiki/File:Psammocora-digitata_-_coral-phallic.jpg |
| 二叉火珊瑚（Millepora dichotoma） | species_millepora-dichotoma.jpg | CC BY-SA 4.0 | Diego Delso | https://commons.wikimedia.org/wiki/File:Coral_de_fuego_%28Millepora_dichotoma%29%2C_mar_Rojo%2C_Egipto%2C_2023-04-15%2C_DD_143.jpg |
| 苍珊瑚（Heliopora coerulea） | species_heliopora-coerulea.jpg | CC BY-SA 3.0 | Kinkreet | https://commons.wikimedia.org/wiki/File:Blue_coral_-_Heliopora_coerulea.jpg |
| 伞状软珊瑚（Xenia umbellata） | species_xenia-umbellata.jpg | CC BY-SA 4.0 | Diego Delso | https://commons.wikimedia.org/wiki/File:Coral_pulsante_%28Xenia_umbellata%29%2C_Ras_Katy%2C_Sharm_el-Sheij%2C_Egipto%2C_2022-03-26%2C_DD_96.jpg |
| 海扇柳珊瑚（Gorgonia ventalina） | species_gorgonia-ventalina.jpg | CC BY 2.0 | James St. John | https://commons.wikimedia.org/wiki/File:File%3AGorgonia_ventalina%2C_French_Bay.jpg |
| 粗叶珊瑚（Trachyphyllia geoffroyi） | species_trachyphyllia-geoffroyi.jpg | CC BY-SA 4.0 | Diego Delso | https://commons.wikimedia.org/wiki/File:Coral_%28Trachyphyllia_geoffroyi%29%2C_Anilao%2C_Filipinas%2C_2023-08-21%2C_DD_147.jpg |

## 图片来源与致谢（联网扩充的珊瑚种类，第三批 / iNaturalist）

> 每条照片取自该物种在 iNaturalist 的分类单元代表照片，与条目一一对应；仅收录 CC / CC0 授权。

| 物种 | 学名 | 文件 | 许可 | 作者/来源 | 分类单元页 |
|---|---|---|---|---|---|
| Acanthastrea pachysepta | Acanthastrea pachysepta | species_acanthastrea-pachysepta.jpg | cc-by-nc | (c) Damien Brouste, some rights reserved (CC BY-NC), uploaded by Damien Brouste | https://www.inaturalist.org/taxa/519989 |
| Acanthastrea rotundoflora | Acanthastrea rotundoflora | species_acanthastrea-rotundoflora.jpg | cc-by-nc | (c) New Heaven Reef Conservation Program, some rights reserved (CC BY-NC), uploaded by New Heaven Reef Conservation Program | https://www.inaturalist.org/taxa/503609 |
| Acanthastrea brevis | Acanthastrea brevis | species_acanthastrea-brevis.jpg | cc-by-nc | (c) David Obura, some rights reserved (CC BY-NC), uploaded by David Obura | https://www.inaturalist.org/taxa/503615 |
| 掌状鹿角珊瑚 | Acropora palmata | species_acropora-palmata.jpg | cc-by | (c) Ryan McMinds, some rights reserved (CC BY) | https://www.inaturalist.org/taxa/93312 |
| 芽生鹿角珊瑚 | Acropora gemmifera | species_acropora-gemmifera.jpg | cc-by-nc | (c) Rachel Andres-Beck, some rights reserved (CC BY-NC), uploaded by Rachel Andres-Beck | https://www.inaturalist.org/taxa/93260 |
| 美麗軸孔珊瑚 | Acropora muricata | species_acropora-muricata.jpg | cc-by | (c) Ryan McMinds, some rights reserved (CC BY) | https://www.inaturalist.org/taxa/368558 |
| 單獨軸孔珊瑚 | Acropora solitaryensis | species_acropora-solitaryensis.jpg | cc-by-nc | (c) hokoonwong, some rights reserved (CC BY-NC), uploaded by hokoonwong | https://www.inaturalist.org/taxa/93351 |
| 蒿状鹿角珊瑚 | Acropora abrotanoides | species_acropora-abrotanoides.jpg | cc-by-nc | (c) krkzv, some rights reserved (CC BY-NC), uploaded by krkzv | https://www.inaturalist.org/taxa/93216 |
| 亨氏鹿角珊瑚 | Acropora hemprichii | species_acropora-hemprichii.jpg | cc-by-nc | (c) Claudia Pogoreutz, some rights reserved (CC BY-NC), uploaded by Claudia Pogoreutz | https://www.inaturalist.org/taxa/93268 |
| 格纹鹿角珊瑚 | Acropora clathrata | species_acropora-clathrata.jpg | cc-by-nc | (c) CORDENOS Thierry, some rights reserved (CC BY-NC), uploaded by CORDENOS Thierry | https://www.inaturalist.org/taxa/93236 |
| 多育鹿角珊瑚 | Acropora prolifera | species_acropora-prolifera.jpg | cc-by-nc | (c) Donají Graham, some rights reserved (CC BY-NC), uploaded by Donají Graham | https://www.inaturalist.org/taxa/212460 |
| 粗壮鹿角珊瑚 | Acropora robusta | species_acropora-robusta.jpg | cc-by-nc-nd | (c) Blogie Robillo, some rights reserved (CC BY-NC-ND), uploaded by Blogie Robillo | https://www.inaturalist.org/taxa/93335 |
| 球头鹿角珊瑚 | Acropora globiceps | species_acropora-globiceps.jpg | cc-by-nc | (c) Leona Kustra, some rights reserved (CC BY-NC), uploaded by Leona Kustra | https://www.inaturalist.org/taxa/93262 |
| Acropora spathulata | Acropora spathulata | species_acropora-spathulata.jpg | cc-by-nc | (c) Peter, some rights reserved (CC BY-NC), uploaded by Peter | https://www.inaturalist.org/taxa/93352 |
| 秀丽鹿角珊瑚 | Acropora pulchra | species_acropora-pulchra.jpg | cc-by-nc-sa | (c) Ashton Williams, some rights reserved (CC BY-NC-SA), uploaded by Ashton Williams | https://www.inaturalist.org/taxa/93331 |
| 维纳斯鹿角珊瑚 | Acropora cytherea | species_acropora-cytherea.jpg | cc-by-nc | (c) Jacopo Cristoni, some rights reserved (CC BY-NC), uploaded by Jacopo Cristoni | https://www.inaturalist.org/taxa/93240 |
| 匍匐鹿角珊瑚 | Acropora sarmentosa | species_acropora-sarmentosa.jpg | cc-by-nc | (c) Anne Hoggett, some rights reserved (CC BY-NC), uploaded by Anne Hoggett | https://www.inaturalist.org/taxa/93343 |
| 多口鹿角珊瑚 | Acropora polystoma | species_acropora-polystoma.jpg | cc-by-sa | (c) Ewout Knoester, some rights reserved (CC BY-SA), uploaded by Ewout Knoester | https://www.inaturalist.org/taxa/93327 |
| Acropora kenti | Acropora kenti | species_acropora-kenti.jpg | cc-by-nc-sa | (c) Matthew Connors, some rights reserved (CC BY-NC-SA), uploaded by Matthew Connors | https://www.inaturalist.org/taxa/1640061 |
| Acropora valenciennesi | Acropora valenciennesi | species_acropora-valenciennesi.jpg | cc-by-nc | (c) Jens Sommer-Knudsen, some rights reserved (CC BY-NC), uploaded by Jens Sommer-Knudsen | https://www.inaturalist.org/taxa/93373 |
| 刺鹿角珊瑚 | Acropora echinata | species_acropora-echinata.jpg | cc-by-nc | (c) Ingo Rogalla, some rights reserved (CC BY-NC), uploaded by Ingo Rogalla | https://www.inaturalist.org/taxa/93248 |
| 绳状鹿角珊瑚 | Acropora loripes | species_acropora-loripes.jpg | cc-by-nc | (c) Albert Kang, some rights reserved (CC BY-NC), uploaded by Albert Kang | https://www.inaturalist.org/taxa/93290 |
| 叉开鹿角珊瑚 | Acropora divaricata | species_acropora-divaricata.jpg | cc-by-nc | (c) martyhing, some rights reserved (CC BY-NC), uploaded by martyhing | https://www.inaturalist.org/taxa/93245 |
| 中间鹿角珊瑚 | Acropora intermedia | species_acropora-intermedia.jpg | cc-by-nc | (c) Anne Hoggett, some rights reserved (CC BY-NC), uploaded by Anne Hoggett | https://www.inaturalist.org/taxa/205265 |
| 长杯鹿角珊瑚 | Acropora longicyathus | species_acropora-longicyathus.jpg | cc-by-nc | (c) Mark Rosenstein, some rights reserved (CC BY-NC), uploaded by Mark Rosenstein | https://www.inaturalist.org/taxa/93289 |
| Acropora bifaria | Acropora bifaria | species_acropora-bifaria.jpg | cc-by-nc | (c) caleidoskopable, some rights reserved (CC BY-NC), uploaded by caleidoskopable | https://www.inaturalist.org/taxa/1640059 |
| 颗粒鹿角珊瑚 | Acropora granulosa | species_acropora-granulosa.jpg | cc-by-nc-sa | (c) Ashton Williams, some rights reserved (CC BY-NC-SA), uploaded by Ashton Williams | https://www.inaturalist.org/taxa/93265 |
| Acropora hoeksemai | Acropora hoeksemai | species_acropora-hoeksemai.jpg | cc-by-nc | (c) Nicolas Lagière, some rights reserved (CC BY-NC), uploaded by Nicolas Lagière | https://www.inaturalist.org/taxa/93269 |
| 严峻鹿角珊瑚 | Acropora austera | species_acropora-austera.jpg | cc-by-nc | (c) juju98, some rights reserved (CC BY-NC), uploaded by juju98 | https://www.inaturalist.org/taxa/93224 |
| 卡罗琳鹿角珊瑚 | Acropora caroliniana | species_acropora-caroliniana.jpg | cc-by-nc | (c) Amy Groundwater, some rights reserved (CC BY-NC), uploaded by Amy Groundwater | https://www.inaturalist.org/taxa/93232 |
| 杨氏鹿角珊瑚 | Acropora yongei | species_acropora-yongei.jpg | cc-by-nc-sa | (c) Cheryl Gilbert, some rights reserved (CC BY-NC-SA), uploaded by Cheryl Gilbert | https://www.inaturalist.org/taxa/93383 |
| 宽星鹿角珊瑚 | Acropora latistella | species_acropora-latistella.jpg | cc-by-nc | (c) David Obura, some rights reserved (CC BY-NC), uploaded by David Obura | https://www.inaturalist.org/taxa/93284 |
| 三毛亞軸孔珊瑚 | Acropora samoensis | species_acropora-samoensis.jpg | cc-by | (c) botanygirl, some rights reserved (CC BY), uploaded by botanygirl | https://www.inaturalist.org/taxa/93342 |
| Acropora eurystoma | Acropora eurystoma | species_acropora-eurystoma.jpg | cc-by-nc | (c) martind, some rights reserved (CC BY-NC), uploaded by martind | https://www.inaturalist.org/taxa/1425450 |
| 多刺鹿角珊瑚 | Acropora horrida | species_acropora-horrida.jpg | cc-by-nc | (c) David Obura, some rights reserved (CC BY-NC), uploaded by David Obura | https://www.inaturalist.org/taxa/93270 |
| 叉角軸孔珊瑚 | Acropora anthocercis | species_acropora-anthocercis.jpg | cc-by-nc | (c) David Obura，保留部分权利（CC BY-NC）, 由 David Obura 上传 | https://www.inaturalist.org/taxa/93220 |
| Acropora pharaonis | Acropora pharaonis | species_acropora-pharaonis.jpg | cc-by-nc | (c) Luis P. B., some rights reserved (CC BY-NC), uploaded by Luis P. B. | https://www.inaturalist.org/taxa/93321 |
| Acropora palmerae | Acropora palmerae | species_acropora-palmerae.jpg | cc-by-nc-sa | (c) Ashton Williams, some rights reserved (CC BY-NC-SA), uploaded by Ashton Williams | https://www.inaturalist.org/taxa/93313 |
| Acropora microphthalma | Acropora microphthalma | species_acropora-microphthalma.jpg | cc-by-sa | (c) Ewout Knoester, some rights reserved (CC BY-SA), uploaded by Ewout Knoester | https://www.inaturalist.org/taxa/93298 |
| 多恩鹿角珊瑚 | Acropora donei | species_acropora-donei.jpg | cc-by-nc | (c) David Obura, some rights reserved (CC BY-NC), uploaded by David Obura | https://www.inaturalist.org/taxa/93246 |
| Acropora desalwii | Acropora desalwii | species_acropora-desalwii.jpg | cc-by-nc | (c) Damien Brouste, some rights reserved (CC BY-NC), uploaded by Damien Brouste | https://www.inaturalist.org/taxa/93243 |
| 近无毛鹿角珊瑚 | Acropora subglabra | species_acropora-subglabra.jpg | cc-by | (c) luluchouette, some rights reserved (CC BY), uploaded by luluchouette | https://www.inaturalist.org/taxa/93358 |
| 矮小鹿角珊瑚 | Acropora nana | species_acropora-nana.jpg | cc-by | (c) 
Kerryn Johns, some rights reserved (CC BY) | https://www.inaturalist.org/taxa/93304 |
| Acropora pichoni | Acropora pichoni | species_acropora-pichoni.jpg | cc-by-nc | (c) uwkwaj, some rights reserved (CC BY-NC), uploaded by uwkwaj | https://www.inaturalist.org/taxa/93322 |
| Acropora verweyi | Acropora verweyi | species_acropora-verweyi.jpg | cc-by-nc | (c) nmi_fishguy, some rights reserved (CC BY-NC), uploaded by nmi_fishguy | https://www.inaturalist.org/taxa/93379 |
| Acropora arabensis | Acropora arabensis | species_acropora-arabensis.jpg | cc-by-nc | (c) Ingo Rogalla, some rights reserved (CC BY-NC), uploaded by Ingo Rogalla | https://www.inaturalist.org/taxa/93222 |
| 乳头鹿角珊瑚 | Acropora papillare | species_acropora-papillare.jpg | cc-by-nc | (c) Tomas Cedhagen, some rights reserved (CC BY-NC), uploaded by Tomas Cedhagen | https://www.inaturalist.org/taxa/93315 |
| Acropora uogi | Acropora uogi | species_acropora-uogi.jpg | cc-by-nc | (c) Natalie Scott, some rights reserved (CC BY-NC), uploaded by Natalie Scott | https://www.inaturalist.org/taxa/1640068 |
| 卷柏鹿角珊瑚 | Acropora selago | species_acropora-selago.jpg | cc-by-nc | (c) Anne Hoggett, some rights reserved (CC BY-NC), uploaded by Anne Hoggett | https://www.inaturalist.org/taxa/93348 |
| Acropora elegans | Acropora elegans | species_acropora-elegans.jpg | cc-by-nc | (c) Tomas Cedhagen, some rights reserved (CC BY-NC), uploaded by Tomas Cedhagen | https://www.inaturalist.org/taxa/93250 |
| 大型鹿角珊瑚 | Acropora grandis | species_acropora-grandis.jpg | cc-by-nc | (c) Damien Brouste, some rights reserved (CC BY-NC), uploaded by Damien Brouste | https://www.inaturalist.org/taxa/93264 |
| 洛坎鹿角珊瑚 | Acropora lokani | species_acropora-lokani.jpg | cc-by-nc | (c) Gita Alisa, some rights reserved (CC BY-NC), uploaded by Gita Alisa | https://www.inaturalist.org/taxa/93288 |
| Acropora squarrosa | Acropora squarrosa | species_acropora-squarrosa.jpg | cc-by-nc | (c) Ingo Rogalla, some rights reserved (CC BY-NC), uploaded by Ingo Rogalla | https://www.inaturalist.org/taxa/93355 |
| Acropora downingi | Acropora downingi | species_acropora-downingi.jpg | cc-by-nc-sa | (c) Tamsin Carlisle, some rights reserved (CC BY-NC-SA), uploaded by Tamsin Carlisle | https://www.inaturalist.org/taxa/93247 |
| 灰绿鹿角珊瑚 | Acropora glauca | species_acropora-glauca.jpg | cc-by-nc | (c) Sol Yoder, some rights reserved (CC BY-NC), uploaded by Sol Yoder | https://www.inaturalist.org/taxa/93261 |
| Acropora striata | Acropora striata | species_acropora-striata.jpg | cc-by-nc | (c) Gita Alisa, some rights reserved (CC BY-NC), uploaded by Gita Alisa | https://www.inaturalist.org/taxa/93357 |
| Acropora jacquelineae | Acropora jacquelineae | species_acropora-jacquelineae.jpg | cc-by-nc-nd | (c) Blogie Robillo, some rights reserved (CC BY-NC-ND), uploaded by Blogie Robillo | https://www.inaturalist.org/taxa/93277 |
| 阿布罗柳斯鹿角珊瑚 | Acropora abrolhosensis | species_acropora-abrolhosensis.jpg | cc-by-nc | (c) Tomas Cedhagen, some rights reserved (CC BY-NC), uploaded by Tomas Cedhagen | https://www.inaturalist.org/taxa/93215 |
| Acropora branchi | Acropora branchi | species_acropora-branchi.jpg | cc-by-nc | (c) brentch, some rights reserved (CC BY-NC) | https://www.inaturalist.org/taxa/93228 |
| Acropora macrostoma | Acropora macrostoma | species_acropora-macrostoma.jpg | cc-by-nc | (c) Lisa_James, some rights reserved (CC BY-NC), uploaded by Lisa_James | https://www.inaturalist.org/taxa/1640060 |
| Acropora tenuissima | Acropora tenuissima | species_acropora-tenuissima.jpg | cc-by | (c) Tim, some rights reserved (CC BY), uploaded by Tim | https://www.inaturalist.org/taxa/1640064 |
| Acropora awi | Acropora awi | species_acropora-awi.jpg | cc-by-nc | (c) Ryan Yue Wah Chan, some rights reserved (CC BY-NC), uploaded by Ryan Yue Wah Chan | https://www.inaturalist.org/taxa/93225 |
| 穗状鹿角珊瑚 | Acropora spicifera | species_acropora-spicifera.jpg | cc-by-nc | (c) Febrianne S, some rights reserved (CC BY-NC), uploaded by Febrianne S | https://www.inaturalist.org/taxa/93354 |
| Acropora indonesia | Acropora indonesia | species_acropora-indonesia.jpg | cc-by-nc | (c) Nicolas Lagière, some rights reserved (CC BY-NC), uploaded by Nicolas Lagière | https://www.inaturalist.org/taxa/93273 |
| 蓟鹿角珊瑚 | Acropora carduus | species_acropora-carduus.jpg | cc-by-nc | (c) matalaut, some rights reserved (CC BY-NC), uploaded by matalaut | https://www.inaturalist.org/taxa/93231 |
| Acropora kirstyae | Acropora kirstyae | species_acropora-kirstyae.jpg | cc-by-nc | (c) Damien Brouste, some rights reserved (CC BY-NC), uploaded by Damien Brouste | https://www.inaturalist.org/taxa/93281 |
| 显著鹿角珊瑚 | Acropora insignis | species_acropora-insignis.jpg | cc-by-nc | (c) Anne Hoggett, some rights reserved (CC BY-NC), uploaded by Anne Hoggett | https://www.inaturalist.org/taxa/93275 |
| Acropora tumida | Acropora tumida | species_acropora-tumida.jpg | cc-by-nc | (c) even928, some rights reserved (CC BY-NC) | https://www.inaturalist.org/taxa/93370 |
| 埃氏鹿角珊瑚 | Acropora elseyi | species_acropora-elseyi.jpg | cc-by-nc-sa | (c) Matthew Connors, some rights reserved (CC BY-NC-SA), uploaded by Matthew Connors | https://www.inaturalist.org/taxa/93252 |
| Acropora rudis | Acropora rudis | species_acropora-rudis.jpg | cc-by-nc | (c) Tomas Cedhagen, some rights reserved (CC BY-NC), uploaded by Tomas Cedhagen | https://www.inaturalist.org/taxa/93339 |
| Acropora appressa | Acropora appressa | species_acropora-appressa.jpg | cc-by-nc | (c) David Obura, some rights reserved (CC BY-NC), uploaded by David Obura | https://www.inaturalist.org/taxa/93221 |
| Acropora nyinggulu | Acropora nyinggulu | species_acropora-nyinggulu.jpg | cc-by-nc | (c) Tim Karnasuta, some rights reserved (CC BY-NC), uploaded by Tim Karnasuta | https://www.inaturalist.org/taxa/1640070 |
| 渐尖鹿角珊瑚 | Acropora acuminata | species_acropora-acuminata.jpg | cc-by | (c) 
Kate Osborne, some rights reserved (CC BY) | https://www.inaturalist.org/taxa/93218 |
| Acropora tersa | Acropora tersa | species_acropora-tersa.jpg | cc-by-nc | (c) RikeF, some rights reserved (CC BY-NC), uploaded by RikeF | https://www.inaturalist.org/taxa/1640069 |
| Acropora subulata | Acropora subulata | species_acropora-subulata.jpg | cc-by-nc | (c) Tomas Cedhagen, some rights reserved (CC BY-NC), uploaded by Tomas Cedhagen | https://www.inaturalist.org/taxa/93359 |
| Acropora chesterfieldensis | Acropora chesterfieldensis | species_acropora-chesterfieldensis.jpg | cc-by-nc | (c) Tilali, some rights reserved (CC BY-NC), uploaded by Tilali | https://www.inaturalist.org/taxa/93235 |
| Acropora multiacuta | Acropora multiacuta | species_acropora-multiacuta.jpg | cc-by-nc | (c) Alvin Chelliah, some rights reserved (CC BY-NC), uploaded by Alvin Chelliah | https://www.inaturalist.org/taxa/93303 |
| Acropora kosurini | Acropora kosurini | species_acropora-kosurini.jpg | cc-by-nc | (c) Tomas Cedhagen, some rights reserved (CC BY-NC), uploaded by Tomas Cedhagen | https://www.inaturalist.org/taxa/93282 |
| Acropora halmaherae | Acropora halmaherae | species_acropora-halmaherae.jpg | cc-by-nc | (c) nabayu5, some rights reserved (CC BY-NC) | https://www.inaturalist.org/taxa/93267 |
| Acropora natalensis | Acropora natalensis | species_acropora-natalensis.jpg | cc-by-nc | (c) David Obura, some rights reserved (CC BY-NC), uploaded by David Obura | https://www.inaturalist.org/taxa/93306 |
| Acropora willisae | Acropora willisae | species_acropora-willisae.jpg | cc-by-nc | (c) Gita Alisa, some rights reserved (CC BY-NC), uploaded by Gita Alisa | https://www.inaturalist.org/taxa/93382 |
| Acropora suharsonoi | Acropora suharsonoi | species_acropora-suharsonoi.jpg | cc-by-nc | (c) Gita Alisa, some rights reserved (CC BY-NC), uploaded by Gita Alisa | https://www.inaturalist.org/taxa/93360 |
| Acropora tortuosa | Acropora tortuosa | species_acropora-tortuosa.jpg | cc-by-nc | (c) Damien Brouste, some rights reserved (CC BY-NC), uploaded by Damien Brouste | https://www.inaturalist.org/taxa/93369 |
| Acropora exquisita | Acropora exquisita | species_acropora-exquisita.jpg | cc-by-nc | (c) Tomas Cedhagen, some rights reserved (CC BY-NC), uploaded by Tomas Cedhagen | https://www.inaturalist.org/taxa/93253 |
| Acropora harriottae | Acropora harriottae | species_acropora-harriottae.jpg | cc-by-nc | (c) Euan Thomas, some rights reserved (CC BY-NC), uploaded by Euan Thomas | https://www.inaturalist.org/taxa/1640072 |
| Acropora kalindae | Acropora kalindae | species_acropora-kalindae.jpg | cc-by-nc | (c) danewattle, some rights reserved (CC BY-NC) | https://www.inaturalist.org/taxa/1640071 |
| Acropora squamata | Acropora squamata | species_acropora-squamata.jpg | cc-by-nc | (c) Febrianne S, some rights reserved (CC BY-NC), uploaded by Febrianne S | https://www.inaturalist.org/taxa/1650297 |
| Acropora lovelli | Acropora lovelli | species_acropora-lovelli.jpg | cc-by-nc | (c) Tomas Cedhagen, some rights reserved (CC BY-NC), uploaded by Tomas Cedhagen | https://www.inaturalist.org/taxa/93291 |
| 厚实梳石芝珊瑚 | Ctenactis crassa | species_ctenactis-crassa.jpg | cc-by-nc | (c) 107120830535687523870, some rights reserved (CC BY-NC), uploaded by 107120830535687523870 | https://www.inaturalist.org/taxa/98737 |
| Ctenactis albitentaculata | Ctenactis albitentaculata | species_ctenactis-albitentaculata.jpg | cc-by-nc-nd | (c) Blogie Robillo, some rights reserved (CC BY-NC-ND), uploaded by Blogie Robillo | https://www.inaturalist.org/taxa/98736 |
| Diploria labyrinthiformis | Diploria labyrinthiformis | species_diploria-labyrinthiformis.jpg | cc-by-nc-sa | (c) Steven Severinghaus, some rights reserved (CC BY-NC-SA) | https://www.inaturalist.org/taxa/504638 |
| Dipsastraea laxa | Dipsastraea laxa | species_dipsastraea-laxa.jpg | cc-by-nc | (c) Rafi Amar, some rights reserved (CC BY-NC), uploaded by Rafi Amar | https://www.inaturalist.org/taxa/662531 |
| Dipsastraea lizardensis | Dipsastraea lizardensis | species_dipsastraea-lizardensis.jpg | cc-by-nc | (c) Giverny, some rights reserved (CC BY-NC), uploaded by Giverny | https://www.inaturalist.org/taxa/712353 |
| Dipsastraea matthaii | Dipsastraea matthaii | species_dipsastraea-matthaii.jpg | cc-by-nc | (c) David Spencer Muirhead, some rights reserved (CC BY-NC), uploaded by David Spencer Muirhead | https://www.inaturalist.org/taxa/503522 |
| Dipsastraea pallida | Dipsastraea pallida | species_dipsastraea-pallida.jpg | cc-by-nc-nd | (c) Blogie Robillo, some rights reserved (CC BY-NC-ND), uploaded by Blogie Robillo | https://www.inaturalist.org/taxa/472803 |
| Dipsastraea lacuna | Dipsastraea lacuna | species_dipsastraea-lacuna.jpg | cc-by-nc | (c) Denis Makhnovsky, some rights reserved (CC BY-NC), uploaded by Denis Makhnovsky | https://www.inaturalist.org/taxa/503806 |
| 奇异双星珊瑚 | Dipsastraea mirabilis | species_dipsastraea-mirabilis.jpg | cc-by-nc | (c) Damien Brouste, some rights reserved (CC BY-NC), uploaded by Damien Brouste | https://www.inaturalist.org/taxa/1437073 |
| Dipsastraea laddi | Dipsastraea laddi | species_dipsastraea-laddi.jpg | cc-by-nc-nd | (c) diverosa, some rights reserved (CC BY-NC-ND) | https://www.inaturalist.org/taxa/503812 |
| Dipsastraea faviaformis | Dipsastraea faviaformis | species_dipsastraea-faviaformis.jpg | cc-by-nc | (c) Albert Kang, some rights reserved (CC BY-NC), uploaded by Albert Kang | https://www.inaturalist.org/taxa/519971 |
| Dipsastraea truncata | Dipsastraea truncata | species_dipsastraea-truncata.jpg | cc-by-nc | (c) Isabella Fenstermaker, some rights reserved (CC BY-NC), uploaded by Isabella Fenstermaker | https://www.inaturalist.org/taxa/732813 |
| 多刺刺孔珊瑚 | Echinopora horrida | species_echinopora-horrida.jpg | cc-by-nc | (c) Damien Brouste, some rights reserved (CC BY-NC), uploaded by Damien Brouste | https://www.inaturalist.org/taxa/503561 |
| Echinopora hirsutissima | Echinopora hirsutissima | species_echinopora-hirsutissima.jpg | cc-by-nc | (c) Hamadi Mwamlavya, some rights reserved (CC BY-NC), uploaded by Hamadi Mwamlavya | https://www.inaturalist.org/taxa/503560 |
| 芽棘孔珊瑚（寶石刺孔珊瑚） | Echinopora gemmacea | species_echinopora-gemmacea.jpg | cc-by-nc | (c) Anne Hoggett, some rights reserved (CC BY-NC), uploaded by Anne Hoggett | https://www.inaturalist.org/taxa/503568 |
| Echinopora forskaliana | Echinopora forskaliana | species_echinopora-forskaliana.jpg | cc-by | (c) Tom Heijnen, some rights reserved (CC BY), uploaded by Tom Heijnen | https://www.inaturalist.org/taxa/503565 |
| 太平洋棘孔珊瑚 | Echinopora pacificus | species_echinopora-pacificus.jpg | cc-by-nc-sa | (c) Ashton Williams, some rights reserved (CC BY-NC-SA), uploaded by Ashton Williams | https://www.inaturalist.org/taxa/503563 |
| Echinopora mammiformis | Echinopora mammiformis | species_echinopora-mammiformis.jpg | cc-by | (c) Ryan McMinds, some rights reserved (CC BY) | https://www.inaturalist.org/taxa/503566 |
| Echinopora fruticulosa | Echinopora fruticulosa | species_echinopora-fruticulosa.jpg | cc-by-nc | (c) Claudia Pogoreutz, some rights reserved (CC BY-NC), uploaded by Claudia Pogoreutz | https://www.inaturalist.org/taxa/503555 |
| Echinopora taylorae | Echinopora taylorae | species_echinopora-taylorae.jpg | cc-by-nc-nd | (c) sea-kangaroo, some rights reserved (CC BY-NC-ND), uploaded by sea-kangaroo | https://www.inaturalist.org/taxa/503564 |
| Euphyllia fimbriata | Euphyllia fimbriata | species_euphyllia-fimbriata.jpg | cc-by-nc-sa | (c) Lucas Thompson, some rights reserved (CC BY-NC-SA) | https://www.inaturalist.org/taxa/472802 |
| Favites vasta | Favites vasta | species_favites-vasta.jpg | cc-by-nc | (c) Krylenko VV, some rights reserved (CC BY-NC), uploaded by Krylenko VV | https://www.inaturalist.org/taxa/503660 |
| Favites rotundata | Favites rotundata | species_favites-rotundata.jpg | cc-by-nc | (c) Febrianne S, some rights reserved (CC BY-NC), uploaded by Febrianne S | https://www.inaturalist.org/taxa/705795 |
| Favites magnistellata | Favites magnistellata | species_favites-magnistellata.jpg | cc-by | (c) Ryan McMinds, some rights reserved (CC BY) | https://www.inaturalist.org/taxa/503662 |
| Favites valenciennesi | Favites valenciennesi | species_favites-valenciennesi.jpg | cc-by-nc | (c) saraptor, certains droits réservés (CC BY-NC) | https://www.inaturalist.org/taxa/503663 |
| Favites flexuosa | Favites flexuosa | species_favites-flexuosa.jpg | cc-by-nc-sa | (c) J. Martin Crossley, some rights reserved (CC BY-NC-SA), uploaded by J. Martin Crossley | https://www.inaturalist.org/taxa/503668 |
| Favites colemani | Favites colemani | species_favites-colemani.jpg | cc-by-nc | (c) krkzv, some rights reserved (CC BY-NC), uploaded by krkzv | https://www.inaturalist.org/taxa/503661 |
| Favites stylifera | Favites stylifera | species_favites-stylifera.jpg | cc-by-nc | (c) Juan José Areso, some rights reserved (CC BY-NC), uploaded by Juan José Areso | https://www.inaturalist.org/taxa/503653 |
| Favites complanata | Favites complanata | species_favites-complanata.jpg | cc-by-nc | (c) David Obura, some rights reserved (CC BY-NC), uploaded by David Obura | https://www.inaturalist.org/taxa/503666 |
| 粗糙盔形珊瑚 | Galaxea horrescens | species_galaxea-horrescens.jpg | cc-by-nc | (c) Damien Brouste, some rights reserved (CC BY-NC), uploaded by Damien Brouste | https://www.inaturalist.org/taxa/503686 |
| Galaxea longisepta | Galaxea longisepta | species_galaxea-longisepta.jpg | cc-by-nc | (c) Damien Brouste, some rights reserved (CC BY-NC), uploaded by Damien Brouste | https://www.inaturalist.org/taxa/503692 |
| Galaxea paucisepta | Galaxea paucisepta | species_galaxea-paucisepta.jpg | cc-by-nc | (c) Silki Anisa Hidayat, some rights reserved (CC BY-NC), uploaded by Silki Anisa Hidayat | https://www.inaturalist.org/taxa/503685 |
| Galaxea cryptoramosa | Galaxea cryptoramosa | species_galaxea-cryptoramosa.jpg | cc-by-nc | (c) Tomas Cedhagen, some rights reserved (CC BY-NC), uploaded by Tomas Cedhagen | https://www.inaturalist.org/taxa/503690 |
| Goniastrea stelligera | Goniastrea stelligera | species_goniastrea-stelligera.jpg | cc-by-nc | (c) Rino, some rights reserved (CC BY-NC), uploaded by Rino | https://www.inaturalist.org/taxa/503631 |
| Goniastrea minuta | Goniastrea minuta | species_goniastrea-minuta.jpg | cc-by | (c) Lin Scott, some rights reserved (CC BY), uploaded by Lin Scott | https://www.inaturalist.org/taxa/503625 |
| Goniastrea thecata | Goniastrea thecata | species_goniastrea-thecata.jpg | cc-by-nc | (c) Denis Makhnovsky, some rights reserved (CC BY-NC), uploaded by Denis Makhnovsky | https://www.inaturalist.org/taxa/503628 |
| 艾氏角星珊瑚 | Goniastrea edwardsi | species_goniastrea-edwardsi.jpg | cc-by-nc-sa | (c) Ashton Williams, some rights reserved (CC BY-NC-SA), uploaded by Ashton Williams | https://www.inaturalist.org/taxa/503642 |
| Goniastrea favulus | Goniastrea favulus | species_goniastrea-favulus.jpg | cc-by-nc | (c) Andy Pearce 🕊, some rights reserved (CC BY-NC), uploaded by Andy Pearce 🕊 | https://www.inaturalist.org/taxa/503632 |
| Goniopora fruticosa | Goniopora fruticosa | species_goniopora-fruticosa.jpg | cc-by-nc | (c) Anne Hoggett, some rights reserved (CC BY-NC), uploaded by Anne Hoggett | https://www.inaturalist.org/taxa/101735 |
| Goniopora tenuidens | Goniopora tenuidens | species_goniopora-tenuidens.jpg | cc-by-nc | (c) Tony Strazzari, some rights reserved (CC BY-NC), uploaded by Tony Strazzari | https://www.inaturalist.org/taxa/101751 |
| Goniopora pedunculata | Goniopora pedunculata | species_goniopora-pedunculata.jpg | cc-by-nc | (c) Febrianne S, some rights reserved (CC BY-NC), uploaded by Febrianne S | https://www.inaturalist.org/taxa/1584608 |
| Goniopora djiboutiensis | Goniopora djiboutiensis | species_goniopora-djiboutiensis.jpg | cc-by-sa | (c) Nhobgood, some rights reserved (CC BY-SA) | https://www.inaturalist.org/taxa/101733 |
| Goniopora palmensis | Goniopora palmensis | species_goniopora-palmensis.jpg | cc-by-nc | (c) Tomas Cedhagen, some rights reserved (CC BY-NC), uploaded by Tomas Cedhagen | https://www.inaturalist.org/taxa/101739 |
| 纤细角孔珊瑚 | Goniopora tenella | species_goniopora-tenella.jpg | cc-by-nc | (c) Tomas Cedhagen, some rights reserved (CC BY-NC), uploaded by Tomas Cedhagen | https://www.inaturalist.org/taxa/101750 |
| Goniopora pandoraensis | Goniopora pandoraensis | species_goniopora-pandoraensis.jpg | cc-by-nc | (c) Tomas Cedhagen, some rights reserved (CC BY-NC), uploaded by Tomas Cedhagen | https://www.inaturalist.org/taxa/101740 |
| Goniopora burgosi | Goniopora burgosi | species_goniopora-burgosi.jpg | cc-by-nc | (c) Tomas Cedhagen, some rights reserved (CC BY-NC), uploaded by Tomas Cedhagen | https://www.inaturalist.org/taxa/101729 |
| Goniopora pendulus | Goniopora pendulus | species_goniopora-pendulus.jpg | cc-by-nc | (c) Tomas Cedhagen, some rights reserved (CC BY-NC), uploaded by Tomas Cedhagen | https://www.inaturalist.org/taxa/101742 |
