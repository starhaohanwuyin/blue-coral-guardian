/**
 * Mock 数据层
 * 完整提取自官网「蓝珊APP.html」的全部业务数据。
 * - USE_MOCK=true 时作为数据源（可独立演示，状态存于本机 storage）
 * - 接入真实后端后本文件不再被调用（仅作为字段结构参考/字段契约）
 */

const IMG = {
  coral1: '/mp/assets/img/bc257d2c5066896c.jpg',
  coral2: '/mp/assets/img/a48810b79a3a3e61.jpg',
  coral3: '/mp/assets/img/748dfe78516b3365.jpg',
  tech1: '/mp/assets/img/016a5d6a6d21175c.jpg',
  tech2: '/mp/assets/img/54d44d276e09fe7e.jpg',
  tech3: '/mp/assets/img/4fe413d0e11d5f12.jpg',
  tech4: '/mp/assets/img/e044b577c27bc08e.jpg',
  tech5: '/mp/assets/img/79c24e8335d5c9c6.jpg',
  /* 夏令营与 3D 打印底托：换成实拍图（同时放在小程序包内 assets/img/ 与网页 web/assets/img/，
     引用 /assets/img/xxx.jpg 两端都能解析） */
  camp: '/assets/img/camp_summer.jpg',
  basePrint: '/assets/img/base_3dprint.jpg',
  field: '/assets/img/field.jpg',            // 野外修复作业实拍
  coralNo2: '/assets/img/coral_no2.jpg',     // 珊瑚2号实拍
  wxRestore: '/mp/assets/img/tweet_restore.jpg',   // File:FKNMS_-_coral_nursery_%2827367671414%29.jpg  [Public domain]
  wxEdu: '/mp/assets/img/tweet_edu.jpg',   // File:Biscayne_National_Park_V-snorkel_entry.jpg  [Public domain]
  wxSurvey: '/mp/assets/img/tweet_survey.jpg',   // File:NOAA_diver_Structure-from-Motion_%28SfM%29_survey_Swains_Island_2023.png  [Public domain]
  wxReef: '/mp/assets/img/tweet_reef2.jpg',   // File:Baker_Island_reef_Anthias_2023.png  [Public domain]
  wxSst: '/mp/assets/img/tweet_sst.jpg',   // File:Satellite_sensor_derived_sea_surface_temperature_anomalies_%282268-609%29.jpg  [Public domain]
  wxBleach: '/mp/assets/img/tweet_bleach1.jpg',   // File:Bleached_Staghorn_Coral.jpg  [CC BY-SA 2.0]
  wxBleach2: '/mp/assets/img/tweet_bleach4.jpg',   // File:Coral_bleaching.png  [Public domain]
  wxTransect: '/mp/assets/img/tweet_transect.jpg',   // File:Divers_install_monitoring_instruments_on_coral_reef.jpg  [Public domain]
  wxReefColor: '/mp/assets/img/tweet_bleach3.jpg',   // File:Colorful_Coral_Bleaching.jpg  [CC BY-SA 4.0]
  wxOcean: '/mp/assets/img/tweet_ocean.jpg',   // File:Aegean_Sea_%28MODIS_2018-07-17%29.jpg  [Public domain]
  wxCoast: '/mp/assets/img/tweet_coast.jpg',   // File:Maldives_island_beach_1.jpg  [Public domain]
  wxGbr: '/mp/assets/img/tweet_gbr.jpg',   // File:Aerial_View_of_Great_Barrier_Reef%2C_Queensland_%28Ank_Kumar%29_02.jpg  [CC BY-SA 4.0]
  wxBuoy: '/mp/assets/img/tweet_buoy.jpg',   // File:D%C3%A9ploiement_de_bou%C3%A9es_PIRATA_et_d%27un_profileur_Argo_APEX_%28Ifremer_00651-76357%29.jpg  [CC BY 4.0]
}

/* ================= 首页 ================= */
/* ================= 微信公众号文章地址（有就填这里） =================
 * 本 App 的推文正文都在本地，`url` 是「原文 / 延伸阅读」的外链。
 * 如果你们有自己的公众号文章，把地址填到下面这张表（key = 推文 id）：
 *
 *     1: 'https://mp.weixin.qq.com/s/AbCdEfGhIjKl',
 *
 * 填了 → 这篇推文的链接换成公众号原文，来源名自动显示「微信公众号原文」；
 * 没填 → 保留 url 里现在那条（已验证可访问的权威来源）。
 * ⚠️ 别填 mp.weixin.qq.com/s/example1 这类占位地址——微信会打开「参数错误」页。
 */
const WX_LINKS = {
  // 1: '',
  // 2: '',
}

const homeData = {
  stats: [
    { num: '12,847', label: '累计认养(株)' },
    { num: '50.12%', label: '修复区覆盖率' },
    { num: '34', label: '可识别珊瑚属' },
    { num: '41', label: '气候样本(年)' }
  ],
  energy: { cur: 650, max: 1000 },
  carbon: {
    value: 186.5,
    unit: 'g CO₂',
    desc: '珊瑚礁每年可固定约225吨碳酸钙 ≈ 封存约100吨CO₂'
  },
  climate: {
    title: '气候与珊瑚',
    sub: '把海水热压力纳入修复决策',
    tag: '气候韧性',
    metrics: [
      { label: '2024年 DHW 峰值', value: '5.42' },
      { label: '白化预警等级', value: '警报一级' },
      { label: '热压力样本', value: '41 年' }
    ],
    desc: '海水比常年高 1℃ 并持续数周，就可能触发白化。本项目仙本那点位近 41 年中已有 3 年达到白化警戒，所以修复方案把「耐热选育」和「投放时间窗」放在一起考虑：既要种得活，也要挑对时候种。'
  },
  corals: [
    { id: 1, name: '蓝珊-001号', species: '柔枝鹿角珊瑚', date: '2026.03.15', growth: 65, img: IMG.coral1 },
    { id: 2, name: '蓝珊-002号', species: '短小鹿角珊瑚', date: '2026.04.22', growth: 42, img: IMG.coral2 },
    { id: 3, name: '蓝珊-003号', species: '陀螺珊瑚', date: '2026.05.10', growth: 28, img: IMG.coral3 }
  ],
  tech: [
    {
      img: IMG.tech1, label: '核心育种技术', title: '珊瑚2号有性杂交抗逆选育技术',
      desc: '筛选耐高温、耐酸化的海洋本土珊瑚亲本，通过种间定向杂交培育高抗逆珊瑚子代，种间杂交受精率＞95%，实验室高温酸化环境下成活率达98%，可耐受+1℃高温、pH↓1.18酸化环境。',
      tags: ['有性杂交', '抗逆选育', '受精率＞95%']
    },
    {
      img: IMG.tech2, label: '智能监测技术', title: '多模态AI水下智能识别监测系统',
      desc: '融合YOLOv9目标检测与SAM3图像分割模型，依托海洋珊瑚种质资源库，可自动识别20种以上海洋常见石珊瑚，识别准确率88%-96%，监测效率较人工提升30-50倍。',
      tags: ['YOLOv9', 'SAM3', 'AI识别', '实时监测']
    },
    {
      img: IMG.basePrint, label: '修复装备技术', title: '贝壳基免烧结3D打印导流式底托',
      desc: '以海洋固废贝壳粉为原料，采用免烧结精细化3D打印工艺制备，可定制仿生纹理结构与双层导流孔道，有效提升珊瑚虫附着成功率与幼苗生长速率。',
      tags: ['3D打印', '贝壳基材料', '绿色低碳']
    }
  ],
  teamIntro: '蓝珊科技汇聚了海洋生物、生态修复、AI技术等多领域专家，扎根海洋十余年，致力于珊瑚礁生态保护与修复。',
  team: [
    { name: '张教授', role: '首席科学家', desc: '珊瑚遗传育种方向，30年海洋生物研究经验', avatar: '/mp/assets/img/ba28e4d23e1b8e7f.jpg' },
    { name: '李博士', role: 'AI技术总监', desc: '计算机视觉专家，主导AI水下监测系统开发', avatar: '/mp/assets/img/81250769831a511e.jpg' },
    { name: '王工程师', role: '生态修复主管', desc: '负责海洋珊瑚礁修复基地的运维与管理', avatar: '/mp/assets/img/6db587e1e482132b.jpg' },
    { name: '陈老师', role: '科普教育总监', desc: '策划执行368场科普讲座，受益25682人', avatar: '/mp/assets/img/362b1244b42c1a7d.jpg' },
    { name: '刘经理', role: '项目经理', desc: '统筹夏令营及珊瑚认养项目运营', avatar: '/mp/assets/img/f61b0c45bdae3477.jpg' }
  ],
  teamDetail: [
    { name: '张教授', role: '首席科学家', desc: '珊瑚遗传育种方向，30年海洋生物研究经验。主持国家自然科学基金重点项目5项，发表SCI论文60余篇，培育出珊瑚2号等4个高抗逆品系。' },
    { name: '李博士', role: 'AI技术总监', desc: '计算机视觉与深度学习专家，主导开发基于YOLOv9+SAM3的水下珊瑚智能监测系统，识别准确率达88%-96%。' },
    { name: '王工程师', role: '生态修复主管', desc: '10年海洋生态修复经验，负责海洋珊瑚礁修复基地日常运维，主导完成15公顷珊瑚礁修复工程。' },
    { name: '陈老师', role: '科普教育总监', desc: '环境教育专业背景，累计策划执行科普讲座368场，受益人数25682人，设计"三阶九级"珊瑚礁科普课程体系。' },
    { name: '刘经理', role: '项目经理', desc: '统筹管理夏令营（累计43班次、1473名学生）和珊瑚认养项目运营，确保项目高质量交付。' }
  ],
  videoCaption: '蓝珊科技 · 海洋珊瑚礁修复纪录',
  /* 团队视频：文件在 ai-service/web/video/team.mp4（FastAPI 静态目录，网页版直接播）。
     小程序端请改成网络地址，或把视频放进 miniprogram/assets 后用 /assets/video/team.mp4 */
  videoUrl: '/video/team.mp4',
  /* 团队视频封面：本地图，两个端点路径一致
     （小程序取 miniprogram/assets/video/，网页版取 web/assets/video/，均解析为 /assets/video/…） */
  videoCover: '/assets/video/team-cover.jpg',
  /* 推文 & 资讯：每条都带「能打开的链接」（url + 来源名 urlName）。
     ⚠️ 换成自己公众号的文章地址时，只改这两处即可；正文放 paragraphs（可选）。 */
  articles: [
    { id: 1, title: '海洋珊瑚礁修复取得阶段性成果：覆盖率从30%提升至50%', date: '2026-07-15', tag: '项目进展',
      img: IMG.wxRestore, url: 'https://github.com/starhaohanwuyin/blue-coral-guardian',
      urlName: '项目开源仓库 · 修复成效与数据',
      paragraphs: [
        '深圳大鹏湾修复区活珊瑚覆盖率从修复前的 30.84% 提升到 50.12%，达到项目设定的 50% 阶段目标。',
        '【关键变化】',
        '• 修复区鱼类物种数由 23 种增加到 57 种，礁区食物网逐步恢复',
        '• 台风「山竹」期间，修复区后方沙滩侵蚀量减少约 62%，礁体起到了天然防波堤的作用',
        '• 野外种苗成活率稳定在 80% 以上',
        '【下一步】',
        '• 扩大修复面积，并把 NOAA 海水热压力数据纳入投放决策，挑热压力更低的时间窗作业'
      ] },
    { id: 2, title: '珊瑚2号新品系发布：受精率＞95%，成活率98%', date: '2026-07-08', tag: '技术突破',
      img: IMG.tech2, url: 'https://github.com/starhaohanwuyin/blue-coral-guardian/releases/tag/v1.0-models',
      urlName: '项目发布页 · 模型与权重',
      paragraphs: [
        '珊瑚2号（LT 品系，柔枝鹿角珊瑚 × 短小鹿角珊瑚）有性杂交子代完成选育并对外发布。',
        '【核心指标】',
        '• 种间杂交受精率 ＞ 95%',
        '• 实验室高温酸化胁迫下成活率达 98%（可耐受 +1℃、pH↓1.18）',
        '• 两年生长长度超过 20 厘米',
        '【意义】',
        '• 耐热子代是「气候韧性」在种源层面的落点：白化阈值更高，灾后恢复更快'
      ] },
    { id: 3, title: '2026年暑期夏令营招募启动！8城43班次等你来', date: '2026-06-20', tag: '活动招募',
      img: IMG.wxEdu, url: 'https://github.com/starhaohanwuyin/blue-coral-guardian#readme',
      urlName: '项目说明 · 科普与夏令营',
      paragraphs: [
        '2026 年暑期珊瑚夏令营开始招募，共 8 个城市、43 个班次。',
        '【课程内容】',
        '• 亲手种植珊瑚、水下观察、水质检测三门实践课',
        '• 科普讲座：珊瑚为什么会白化、气候变暖对礁区意味着什么',
        '• 每位营员会拿到自己种的珊瑚编号，后续可在小程序里追踪生长'
      ] },
    { id: 4, title: 'AI水下监测年报：累计识别珊瑚20万+株，效率提升50倍', date: '2026-06-05', tag: '技术报告',
      img: IMG.wxSurvey, url: 'https://github.com/starhaohanwuyin/blue-coral-guardian/tree/main/ai-service',
      urlName: '项目开源仓库 · AI 服务（监测技术）',
      paragraphs: [
        '多模态 AI 水下识别监测系统完成年度统计：累计识别珊瑚 20 万株以上，监测效率较人工提升 30–50 倍。',
        '【指标口径】',
        '• 珊瑚属识别准确率 88%–96%',
        '• 覆盖率量化准确率 85%–92%',
        '• 白化识别灵敏度 ≥90%',
        '• 百平米监测报告生成时间 ＜ 5 分钟',
        '【为什么强调白化灵敏度】',
        '• 白化比例是判断「气候韧性」的直接观测量：同一片礁连续监测，才能看出恢复力强弱'
      ] },
    { id: 5, title: '珊瑚的「气候韧性」到底指什么', date: '2026-07-02', tag: '气候韧性',
      img: IMG.wxReef, url: 'https://reefresilience.org/',
      urlName: 'Reef Resilience Network（珊瑚气候韧性）',
      paragraphs: [
        '「气候韧性」不是「不会白化」，而是一片珊瑚礁在经历海洋热浪之后，仍能存活、恢复并维持造礁能力的程度。',
        '【韧性由三样东西决定】',
        '• 共生藻：虫黄藻（Symbiodinium）有多个系群，耐热系群占比越高，白化阈值越高',
        '• 遗传多样性：同属不同个体的耐热能力可以差几摄氏度，有性繁殖能产生新的耐热组合',
        '• 局部环境：上升流、冷水团、浑浊遮光的水域，是热浪里的「天然空调房」',
        '【怎么观测】',
        '• 连续监测白化比例与覆盖率变化，比单次拍照更能反映韧性强弱',
        '• 本项目把 NOAA 热压力档案与图像评估放进同一份报告，让「韧性」有数据可依'
      ] },
    { id: 6, title: '海水热压力怎么读：DHW 与白化预警', date: '2026-06-26', tag: '气候韧性',
      img: IMG.wxSst, url: 'https://coralreefwatch.noaa.gov/product/5km/index.php',
      urlName: 'NOAA CRW · 5km 白化预警产品',
      paragraphs: [
        '珊瑚白化最常见的触发器是海水升温：海水比夏季最高月均温高出 1℃ 并持续数周，就足以让珊瑚开始白化。',
        '【三个常被搞混的指标】',
        '• HotSpot（SST 异常）：当下海温比该地同期气候态高多少℃——瞬时指标',
        '• DHW（周热压力累积）：把超出 1℃ 的部分按周累加、滚动 12 周求和——累积指标',
        '• BAA（Bleaching Alert Area）：NOAA 官方结论等级，回答「是否达到白化警戒 / 严重风险」',
        '【为什么看累积】',
        '• 共生藻流失是渐进过程，同样是 32℃，来两天和来二十天后果完全不同',
        '【三个使用边界】',
        '• 空间：5km 格点只能给「哪片海」，不能给「哪个礁」',
        '• 时间：DHW 是 12 周滚动量，峰值会滞后于热浪',
        '• 用途：热压力只是选点选时的其中一个维度'
      ] },
    { id: 7, title: '白化 ≠ 死亡：三级判断与恢复窗口', date: '2026-06-18', tag: '白化科普',
      img: IMG.wxBleach, url: 'https://zh.wikipedia.org/wiki/%E7%8F%8A%E7%91%9A%E7%99%BD%E5%8C%96',
      urlName: '维基百科 · 珊瑚白化（中文）',
      paragraphs: [
        '成片发白的珊瑚常被当成「死光了」，其实白化只是珊瑚排出了体内的虫黄藻，珊瑚虫本身常常还活着。',
        '【三个阶段】',
        '• 部分白化：颜色变浅、出现斑块，仍有虫黄藻残留，最容易恢复',
        '• 全白化：几乎纯白，但组织完整、珊瑚杯轮廓清晰，仍可能数周内恢复',
        '• 死亡：表面覆上灰绿色藻膜或泥沙，珊瑚杯结构塌陷模糊',
        '【现场怎么判断】',
        '• 看轮廓：活珊瑚的珊瑚杯清晰锐利，死亡后变模糊',
        '• 看覆膜：长出绒毛状藻膜、轻碰就散的多半已死亡',
        '• 水温回落后，珊瑚可在数周到数月内重新获得虫黄藻、恢复颜色'
      ] },
    { id: 8, title: '白化是怎么发生的：虫黄藻、热应激与酸化', date: '2026-06-11', tag: '白化科普',
      img: IMG.wxBleach2, url: 'https://oceanservice.noaa.gov/facts/coral_bleach.html',
      urlName: 'NOAA Ocean Service · 什么是珊瑚白化',
      paragraphs: [
        '珊瑚的颜色来自住在它组织里的虫黄藻：虫黄藻光合作用供给珊瑚约 80%–90% 的能量，珊瑚则提供栖息空间与营养。',
        '【热应激的连锁反应】',
        '• 光合作用的光反应对温度极敏感，升温会让它过度运转、产生大量活性氧（ROS）',
        '• 珊瑚为自保把虫黄藻「请出去」——颜色消失，白化发生',
        '• 高温若持续，失去主要能量来源的珊瑚会进一步死亡',
        '【叠加的压力】',
        '• 海洋酸化：CO₂ 升高使 pH 下降，珊瑚钙化速率降低、礁体变脆',
        '• 紫外线增强：与高温协同加速白化，浅水区尤其明显',
        '• 富营养化与赤潮：藻类争夺空间和光照，让恢复更慢'
      ] },
    { id: 9, title: '全球珊瑚礁在退：GCRMN 的评估怎么看', date: '2026-09-20', tag: '气候韧性',
      img: IMG.wxTransect, url: 'https://gcrmn.net/',
      urlName: 'GCRMN 全球珊瑚礁监测网络',
      paragraphs: [
        'GCRMN（全球珊瑚礁监测网络）汇总各国长期监测数据，是判断「全球珊瑚礁在变好还是变差」最常被引用的来源。',
        '【报告怎么看】',
        '• 先看覆盖：口径是「有多少礁区被监测到」，不是全球所有礁区',
        '• 再看指标：活珊瑚覆盖率是主指标，白化比例、藻类覆盖、鱼类生物量是配套指标',
        '• 最后看趋势：单年波动大，要连续多年对比才有意义',
        '【结论怎么用】',
        '• 全球尺度的结论不能直接搬到某一个礁点——本地点位仍要靠自己的连续监测',
        '• 这也是本项目坚持「图像评估 + 热压力档案」两条腿走路的原因'
      ] },
    { id: 10, title: '升温 1.5℃ 还是 2℃：珊瑚礁的临界点在哪', date: '2026-09-06', tag: '气候韧性',
      img: IMG.wxReefColor, url: 'https://global-tipping-points.org/',
      urlName: '《全球临界点报告》官网',
      paragraphs: [
        '珊瑚礁是全球气候临界点里最敏感的系统之一：升温幅度每多 0.5℃，白化的频率和强度都会明显上一个台阶。',
        '【为什么说它是「临界点」】',
        '• 升温 1.5℃ 情景下，热带珊瑚礁大面积消失的风险显著上升；到 2℃ 风险进一步加大',
        '• 临界点的含义是「过了这个点，恢复会变得非常困难」，而不是「刚好那一天」',
        '• 白化事件之间的间隔越短，珊瑚来不及恢复，礁体就会从「白化」走向「死亡」',
        '【对修复工作的直接含义】',
        '• 修复能争取时间窗口，但改变不了升温趋势本身；减碳与修复是并行关系',
        '• 因此本项目把「避开发白化高风险月份」写进投放建议'
      ] },
    { id: 11, title: '海洋变暖与酸化：IPCC 海洋特别报告怎么说', date: '2026-08-22', tag: '气候韧性',
      img: IMG.wxOcean, url: 'https://www.ipcc.ch/srocc/',
      urlName: 'IPCC · 海洋与冰冻圈特别报告（SROCC）',
      paragraphs: [
        'IPCC 的《海洋与冰冻圈特别报告》（SROCC）是讨论「海洋变暖 / 酸化对珊瑚礁意味着什么」时最权威的依据之一。',
        '【与珊瑚礁相关的三条结论】',
        '• 海洋吸收了气候系统中绝大部分多余热量，海表热浪事件的频率与强度都在上升',
        '• 海洋持续吸收 CO₂ 导致酸化，珊瑚钙化速率下降、礁体结构变脆',
        '• 珊瑚礁对升温最敏感，是受影响最早、最直接的生态系统之一',
        '【读报告的实用建议】',
        '• 关注「情景 × 时段」两个坐标，不要只看结论句',
        '• 区域性结论要与本地数据（如 NOAA CRW 的 5km 格点）结合，才能落到具体礁点'
      ] },
    { id: 12, title: '海洋珊瑚礁保护：官方通报在哪里看', date: '2026-08-08', tag: '白化科普',
      img: IMG.wxCoast, url: 'http://scs.mnr.gov.cn/',
      urlName: '自然资源部南海局（官方）',
      paragraphs: [
        '做海洋（含广东、广西、海南沿海）的珊瑚礁工作，官方口径与通报一般来自自然资源部南海局。',
        '【在这里通常能找到】',
        '• 珊瑚礁生态监测通报、保护区管理动态',
        '• 海洋生态修复项目的公开信息',
        '• 与地方联合发布的科普与执法信息',
        '【为什么建议引用官方来源】',
        '• 官方通报是可核验的权威口径，比自媒体转载更稳',
        '• 竞赛 / 答辩场景下，来源清晰的官方数据更可信'
      ] },
    { id: 13, title: '大堡礁白化实录：一场热浪之后礁区发生了什么', date: '2026-07-26', tag: '白化科普',
      img: IMG.wxGbr, url: 'https://www.barrierreef.org/',
      urlName: '大堡礁基金会（Great Barrier Reef Foundation）',
      paragraphs: [
        '大堡礁是全球被监测最久的珊瑚礁系统之一，它的白化记录是理解「热浪—白化—恢复」过程最完整的样本。',
        '【一次热浪之后通常发生什么】',
        '• 第 1–2 周：颜色变浅，出现斑块状白化，此时珊瑚仍可恢复',
        '• 第 3–6 周：若高温持续，白化比例上升，部分个体开始死亡',
        '• 热浪过后：水温回落，存活个体重新获得虫黄藻，但生长与繁殖会滞后 1–2 年',
        '【为什么反复白化最致命】',
        '• 白化—恢复—再白化的间隔太短时，珊瑚的储备被耗尽，死亡率会显著上升',
        '• 这也是「气候韧性」的核心：不只是扛过一次，而是扛过之后还能回来'
      ] },
    { id: 14, title: '海表温度记录是怎么来的：卫星与浮标怎么测海温', date: '2026-07-12', tag: '气候韧性',
      img: IMG.wxBuoy, url: 'https://climate.copernicus.eu/',
      urlName: 'Copernicus 气候服务（SST 数据集）',
      paragraphs: [
        '「海水变暖了多少」这句话背后，是一套卫星遥感 + 海上浮标 + 船舶观测的长期记录体系。',
        '【数据怎么来的】',
        '• 卫星辐射计测海表「皮温」，浮标（如 Argo/TAO）测水下温度，两者互相校准',
        '• 不同机构用同一批观测做再分析，产出网格化 SST 与异常值（Anomaly）',
        '• 本项目用的 NOAA CRW 5km 产品，就是在这类 SST 基础上算 HotSpot 与 DHW',
        '【读 SST 数据要注意的事】',
        '• 「气候态」是多年平均，换基准期会让异常值变化，比较时要注意口径',
        '• 5km 格点 ≈ 一片海，不代表你脚下那个礁点：需要本地实测配合'
      ] }
  ],
  news: [
    { id: 1, title: '仙本那核心礁区珊瑚监测最新动态', date: '2026-07-10', tag: '生态监测', img: IMG.field,
      paragraphs: [
        '仙本那核心礁区（4.4°N, 118.8°E）最新一轮 AI 水下识别显示：活珊瑚覆盖率 39.71%，与 Reef Check Malaysia 2024 实地调查的区域平均（39.56%）仅差 0.15 个百分点。',
        '同期 NOAA 5km 热压力档案显示：2024 年 DHW 峰值 5.42，官方白化预警等级为「警报一级」，属于近 41 年里 3 个达到白化警戒的年份之一。',
        '【后续安排】',
        '• 继续按季度做 AI 水下识别监测，跟踪覆盖率与白化比例的长期趋势',
        '• 把 NOAA 热压力档案纳入投放窗口决策，优先选择热压力更低的月份作业'
      ] },
    { id: 2, title: '珊瑚2号杂交品系进入海区规模培育测试', date: '2026-06-28', tag: '技术突破', img: IMG.coralNo2,
      paragraphs: [
        '珊瑚2号（LT 品系）杂交子代完成陆基培育阶段，进入海区规模培育测试。',
        '该品系在实验室高温（+1℃）与酸化（pH↓1.18）胁迫下成活率达 98%，海区表现是本轮测试重点。',
        '【观测指标】',
        '• 成活率与生长速率；白化发生时间与程度（对比本地亲本）；附着基上的固着稳定性'
      ] },
    { id: 3, title: '青少年珊瑚夏令营第43期圆满结束', date: '2026-06-15', tag: '科普活动', img: IMG.camp,
      paragraphs: [
        '第 43 期青少年珊瑚夏令营结束，营员完成了珊瑚种植、水下观察与水质检测三门实践课。',
        '夏令营累计覆盖 8 个城市、参与学生 1473 人。',
        '【每期都会讲的一句话】',
        '• 「珊瑚白化不等于死亡」：理解机制，才知道为什么要减碳与修复同时做'
      ] },
    { id: 4, title: '仙本那海水热压力速览：41 年档案与 2024 年峰值', date: '2026-07-05', tag: '气候韧性', img: IMG.tech4,
      paragraphs: [
        '仙本那点位（4.4°N, 118.8°E）的 NOAA CRW 5km 档案覆盖 1985–2025 共 41 年，逐年记录 HotSpot、DHW 与官方白化预警等级（BAA）。',
        '2024 年 DHW 峰值 5.42，全年有 58 天达到 DHW≥4，是该点位 41 年里最热的 3 年之一，官方等级为「白化警报一级」。',
        '【怎么读这些数字】',
        '• HotSpot 是瞬时海温异常（当下比常年高多少℃），DHW 是 12 周滚动累积，BAA 是官方结论等级',
        '• 触发白化的门槛是「比夏季最高月均温高 1℃ 并持续数周」，所以看累积量比只看单日峰值更有意义',
        '• 5km 格点只回答「哪片海」，回答不了「哪个礁」——礁级判断仍要靠水下识别'
      ] },
    { id: 5, title: '仙本那的季风窗口：热压力什么时候回落', date: '2026-06-30', tag: '修复决策', img: IMG.field,
      paragraphs: [
        '仙本那属热带季风气候，11–2 月东北季风期的海况与热压力通常相对缓和，是投放种苗的优先窗口。',
        '把 NOAA 逐日 DHW 档案与投放计划对齐后，本项目的做法是：优先在热压力回落窗口投放，避开 DHW 爬升期。',
        '【为什么重要】',
        '• 种苗最脆弱的是投放后 4–8 周，这段时间撞上热浪，成活率会明显下降',
        '• 耐热品系（珊瑚2号 LT 品系）能抬高阈值，但改变不了「投放时点撞上热浪」带来的损失'
      ] }
  ]
}

/* ================= 科普 ================= */
const knowledgeCategories = [
  { key: 'all', name: '全部' },
  { key: 'species', name: '珊瑚种类' },
  { key: 'ecosystem', name: '生态系统' },
  { key: 'bleaching', name: '白化危机' },
  { key: 'climate', name: '气候韧性' },
  { key: 'tech', name: '修复技术' },
  { key: 'camp', name: '珊瑚夏令营' }
]

const knowledgeItems = [
  {
    id: 0, category: 'species', title: '柔枝鹿角珊瑚', img: IMG.coral1,
    summary: '海洋最常见的造礁珊瑚之一，分支状生长，是珊瑚礁生态系统的基石物种',
    paragraphs: [
      '柔枝鹿角珊瑚（Acropora valida）是海洋最常见的造礁珊瑚之一，属于鹿角珊瑚科鹿角珊瑚属。',
      '它是一种分枝状珊瑚，分支细长且密集，形态优美。柔枝鹿角珊瑚是珊瑚礁生态系统的基石物种，为大量海洋生物提供栖息地和庇护所。',
      '蓝珊科技将柔枝鹿角珊瑚作为珊瑚2号有性杂交抗逆选育技术的重要亲本之一，通过种间定向杂交，成功培育出具有更强环境抗逆性的珊瑚子代。',
      '【关键数据】',
      '• 种间杂交受精率 ＞ 95%',
      '• 两年生长长度超 20 厘米',
      '• 实验室胁迫环境下成活率达 98%'
    ]
  },
  {
    id: 1, category: 'bleaching', title: '珊瑚白化现象', img: IMG.tech1,
    summary: '全球超过80%的珊瑚礁已出现严重白化，了解白化的成因与危害',
    paragraphs: [
      '珊瑚白化是指珊瑚在环境压力下失去共生虫黄藻，导致颜色变白的现象。2025年发布的第二份《全球临界点报告》指出，全球超过80%的珊瑚礁已出现严重白化现象。',
      '【白化的主要原因】',
      '• 海水温度升高（+1℃即可触发）',
      '• 海洋酸化（pH值下降）',
      '• 赤潮等极端环境事件',
      '• 紫外线辐射增强',
      '蓝珊科技的珊瑚2号杂交品系可耐受+1℃高温、pH↓1.18的酸化环境，为应对白化危机提供了技术解决方案。'
    ]
  },
  {
    id: 2, category: 'ecosystem', title: '珊瑚礁生态系统', img: IMG.tech2,
    summary: '珊瑚礁被称为"海洋中的热带雨林"，养育着25%的海洋物种',
    paragraphs: [
      '珊瑚礁被称为"海洋中的热带雨林"，虽然仅覆盖不到0.1%的海底面积，却养育着约25%的海洋物种。',
      '全球约有5亿人直接依赖珊瑚礁生态系统获取食物、生计和海岸保护。珊瑚礁作为天然防波堤，可吸收70%-90%的海浪冲击力。',
      '【蓝珊科技的修复成果】',
      '• 深圳大澳湾活珊瑚覆盖率从30.84%提升至50.12%',
      '• 修复区鱼类物种数从23种增至57种',
      '• 每年固定约225吨碳酸钙，相当于封存约100吨CO₂',
      '• 台风"山竹"期间修复区后方沙滩侵蚀量减少62%'
    ]
  },
  {
    id: 3, category: 'tech', title: 'AI智能监测技术', img: IMG.tech4,
    summary: 'YOLOv9+SAM3赋能水下珊瑚识别，监测效率提升30-50倍',
    paragraphs: [
      '蓝珊科技打造的多模态AI水下智能识别监测系统，是珊瑚管护技术的核心突破。',
      '【技术架构】',
      '• 硬件层：自主研发防抖光学成像模块 + 低照度补光系统，IP68级水下防护，可抗3级海流',
      '• 算法层：YOLOv9目标检测 + SAM3图像分割 + 大模型分析',
      '• 数据层：海洋珊瑚种质资源库，覆盖20种以上常见石珊瑚',
      '【核心指标】',
      '• 识别准确率：88%-96%',
      '• 珊瑚覆盖率量化准确率：85%-92%',
      '• 白化识别灵敏度：≥90%',
      '• 百平米监测报告生成时间：＜5分钟',
      '• 监测效率提升：30-50倍'
    ]
  },
  {
    id: 4, category: 'tech', title: '珊瑚礁修复实践', img: IMG.field,
    summary: '从种苗繁育到野外定植，蓝珊科技的全链条修复之路',
    paragraphs: [
      '蓝珊科技团队成立于2024年4月，拟于2026年12月正式注册成立广东蓝珊科技有限公司，深耕珊瑚礁生态修复领域。',
      '【全链条修复技术体系】',
      '1. 种质选育 → 珊瑚2号有性杂交抗逆选育',
      '2. 育苗载体 → 贝壳基免烧结3D打印导流式底托',
      '3. 野外修复 → 模块化仿生导流式珊瑚生长装置',
      '4. 智能管护 → 多模态AI水下智能识别监测',
      '5. 科普赋能 → "珊小小"IP + 数字化互动科普平台',
      '【修复成效】',
      '• 深圳大鹏湾修复区珊瑚覆盖率达50%以上',
      '• 广东徐闻退化礁区覆盖率从不足5%恢复至22%',
      '• 野外成活率稳定在80%以上'
    ]
  },
  {
    id: 5, category: 'camp', title: '珊瑚夏令营', img: IMG.camp,
    summary: '已开展43个班次，覆盖8个城市，1473名青少年参与',
    paragraphs: [
      '蓝珊科技已开展青少年珊瑚夏令营43个班次，覆盖深圳、湛江、茂名、惠州、珠海、江门、钦州、三亚8个城市，参与学生1473人。',
      '【科普成果】',
      '• 累计开展珊瑚科普讲座368场',
      '• 小学156场、渔村83场、镇文化中心81场',
      '• 直接受益人数达25,682人',
      '• 世界海洋日及珊瑚保护日主题宣讲17次',
      '• 覆盖广东、广西、海南3省18市，影响超10万人',
      '夏令营通过亲手种植珊瑚、水下观察、科普实验等沉浸式体验，让青少年深入了解海洋生态与珊瑚保护的重要性。'
    ]
  },
  {
    id: 6, category: 'species', title: '短小鹿角珊瑚', img: IMG.coral2,
    summary: '蓝珊科技珊瑚2号杂交亲本之一，耐高温品种，可耐受+1℃高温',
    paragraphs: [
      '短小鹿角珊瑚（Acropora humilis）是蓝珊科技珊瑚2号有性杂交抗逆选育技术的重要亲本之一。',
      '短小鹿角珊瑚是海洋本土优势品种，具有较好的耐高温特性。蓝珊科技通过将其与柔枝鹿角珊瑚进行种间定向杂交，成功选育出LT（柔枝×短小）等优势杂交品系。',
      '【杂交品系优势】',
      '• 可耐受+1℃高温环境',
      '• 可耐受pH↓1.18酸化环境',
      '• 胁迫环境下成活率与正常环境无显著差异',
      '• 两年生长长度超20厘米'
    ]
  },
  {
    id: 7, category: 'tech', title: '3D打印珊瑚底托', img: IMG.basePrint,
    summary: '贝壳基免烧结3D打印工艺，仿生纹理结构提升附着成功率',
    paragraphs: [
      '贝壳基免烧结3D打印导流式底托是蓝珊科技自主研发的核心修复装备之一。',
      '以海洋固废贝壳粉为核心原料，采用免烧结DIW 3D打印工艺制备，兼具绿色低碳属性与功能优化双重优势。',
      '【技术特点】',
      '• 仿生纹理表面结构，提升珊瑚虫附着成功率',
      '• 双层导流孔道，形成上升流与微型涡流',
      '• 持续冲刷沉积物、输送营养物质',
      '• 支持岩礁打孔、钢钉固定、珊瑚胶泥三种定植方式',
      '• 适配海洋多样海底底质环境',
      '该底托是珊瑚种苗从陆基到海区定植的核心载体，有效提升了珊瑚修复的成活率与稳定性。'
    ]
  },
  {
    id: 8, category: 'climate', title: '珊瑚的气候韧性从哪里来', img: IMG.tech4,
    link: 'https://reefresilience.org/', linkName: 'Reef Resilience Network（珊瑚气候韧性）',
    summary: '气候韧性不是「不白化」，而是白化后还能恢复——它由共生藻、遗传多样性与局部环境共同决定',
    paragraphs: [
      '「气候韧性」指的是一片珊瑚礁在经历海洋热浪之后，仍能存活、恢复并维持造礁能力的程度。说得直白一点：韧性不是「不白化」，而是「白化之后还回得来」。',
      '【韧性的三个来源】',
      '• 共生藻多样性：虫黄藻（Symbiodinium）有多个系群，耐热系群占比越高的珊瑚，白化阈值越高',
      '• 遗传多样性：同一属内不同个体的耐热能力可以相差数摄氏度，有性繁殖能不断产生新的耐热组合',
      '• 局部环境避难所：上升流、冷水团、浑浊遮光的水域，是热浪中的「天然空调房」',
      '【怎么量化】',
      '• DHW（周热压力累积量）：把 12 周内超出常年均值的海温异常累加起来，是 NOAA 判定白化风险的核心指标',
      '• 白化预警等级：DHW≥4 进入白化警戒，DHW≥8 进入严重白化风险（对应 NOAA Bleaching Alert Level 1 / 2）',
      '【蓝珊的做法】',
      '• 选育：筛选耐高温亲本、做种间定向杂交，实验室高温酸化胁迫下成活率达 98%',
      '• 选址选时：把 NOAA 热压力档案纳入投放决策，避开风险月份（本项目仙本那点位建议避开 4—7 月）',
      '• 监测：用 AI 水下识别持续跟踪白化比例，让「韧性」可以被观测，而不是凭感觉判断'
    ]
  },
  {
    id: 9, category: 'climate', title: '读懂海水热压力：DHW 与白化预警', img: IMG.tech5,
    link: 'https://coralreefwatch.noaa.gov/product/5km/index.php',
    linkName: 'NOAA CRW · 5km 白化预警产品',
    summary: '海水只高 1℃ 就可能触发白化；SST 异常、DHW、BAA 三个指标分别在看什么',
    paragraphs: [
      '珊瑚白化最常见的触发器是海水升温。研究普遍认为，海水温度比夏季最高月均温高出 1℃ 并持续数周，就足以让珊瑚开始白化。',
      '【三个常被搞混的指标】',
      '• SST 异常（HotSpot）：当下海温比该地同期气候态高多少℃，是「瞬时」指标',
      '• DHW（周热压力累积）：把超出 1℃ 的部分按周累加、滚动 12 周求和，是「累积」指标——热浪再猛，只热三天也不算高',
      '• BAA（Bleaching Alert Area）：NOAA 官方给出的结论等级，直接回答「有没有达到白化警戒 / 严重风险」',
      '【为什么看累积，而不是看峰值】',
      '• 共生藻的流失是一个渐进过程，累积热压力比某一天的瞬时高温更能预测白化与死亡',
      '• 同样是 32℃，来两天和来二十天，后果完全不同',
      '【读数的三个边界】',
      '• 空间：本项目用的是 5km 网格（NOAA CRW v3.1），只能告诉你「哪片海」，不能给「哪个礁」',
      '• 时间：DHW 是 12 周滚动量，峰值出现时间会滞后于热浪本身',
      '• 用途：热压力只是选点选时的其中一个维度，还要叠加底质、水深、水流、藻类与人力条件'
    ]
  },
  {
    id: 10, category: 'climate', title: '珊瑚礁也是气候防线', img: IMG.tech2,
    link: 'https://icriforum.org/about-coral-reefs/', linkName: 'ICRI · 珊瑚礁与气候',
    summary: '占不到 0.1% 海底面积的珊瑚礁，养育着 25% 的海洋物种，还能削掉 70%—90% 的浪能',
    paragraphs: [
      '珊瑚礁常被称作「海洋中的热带雨林」，但它同时还是海岸线的一道防线——这让它和气候议题有了两层关系。',
      '【第一层：珊瑚礁帮我们缓冲气候影响】',
      '• 天然防波堤：健康的礁体可吸收 70%—90% 的波浪能量，直接削弱风暴潮对海岸的冲击',
      '• 台风「山竹」期间，修复区后方沙滩侵蚀量减少约 62%',
      '• 碳循环：珊瑚礁每年固定约 225 吨碳酸钙，本项目修复区估算相当于封存约 100 吨 CO₂',
      '• 生计：全球约有 5 亿人直接依赖珊瑚礁获取食物、收入与海岸保护',
      '【第二层：气候反过来威胁珊瑚礁】',
      '• 海洋热浪频率上升，白化事件更频繁，珊瑚的恢复窗口被压缩',
      '• 海洋酸化让钙化速率下降，礁体结构变脆',
      '• 于是「提升气候韧性」成了修复工作的核心目标，而不是附加题',
      '【对修复的启示】',
      '• 只种不管不够：要把耐热选育、投放时间窗、长期监测串成一条线',
      '• 生态系统的韧性不等于单个物种的韧性：鱼类、藻类、草食动物的平衡同样重要'
    ]
  },
  {
    id: 11, category: 'bleaching', title: '白化 ≠ 死亡：三级判断与恢复窗口', img: IMG.coral3,
    link: 'https://zh.wikipedia.org/wiki/%E7%8F%8A%E7%91%9A%E7%99%BD%E5%8C%96',
    linkName: '维基百科 · 珊瑚白化（中文）',
    summary: '白化的珊瑚往往还活着——分清部分白化 / 全白化 / 死亡，才不会误判一片礁',
    paragraphs: [
      '很多人第一次看到成片发白的珊瑚，会直接以为「死光了」。其实白化只是珊瑚排出了体内的虫黄藻，珊瑚虫本身常常还活着。',
      '【白化的三个阶段】',
      '• 部分白化（Pale / Partially bleached）：颜色变浅、出现斑块，仍有虫黄藻残留，最容易恢复',
      '• 全白化（Fully bleached）：几乎纯白，但组织完整、珊瑚杯轮廓清晰，仍可能在数周内恢复',
      '• 死亡（Dead）：表面覆上灰绿色藻膜或泥沙，珊瑚杯结构塌陷模糊，光合与钙化停止',
      '【现场怎么判断】',
      '• 看轮廓：活珊瑚的珊瑚杯（corallite）清晰锐利，死亡后结构会变模糊',
      '• 看覆膜：长出绒毛状藻膜、轻碰就散的多半已经死亡',
      '• 看荧光：部分珊瑚在白化前会先出现荧光色（天然防晒蛋白），这是「还在挣扎」的信号',
      '【恢复窗口】',
      '• 水温回落后，珊瑚可在数周到数月内重新获得虫黄藻、恢复颜色',
      '• 恢复能力取决于热浪持续时长与累积热压力（DHW）；反复白化会耗尽储备',
      '• 这也是为什么监测要「连续」而不是「一次性拍照」——AI 的价值正在于能持续给出白化比例'
    ]
  },
  {
    id: 12, category: 'bleaching', title: '白化是怎么发生的：虫黄藻、热应激与酸化', img: IMG.tech1,
    link: 'https://oceanservice.noaa.gov/facts/coral_bleach.html',
    linkName: 'NOAA · 什么是珊瑚白化',
    summary: '温度、酸化、紫外线三条压力线，如何一步步逼走珊瑚的「房客」',
    paragraphs: [
      '珊瑚的颜色其实来自住在它组织里的虫黄藻。理解白化的机制，才能理解为什么「降温」是最关键的救援。',
      '【共生关系】',
      '• 虫黄藻进行光合作用，把产物交给珊瑚，供给珊瑚约 80%—90% 的能量',
      '• 珊瑚则提供安全的栖息空间与氮磷等营养，双方互利共生',
      '【热应激的连锁反应】',
      '• 光合作用的光反应阶段对温度极为敏感，升温会让它过度运转并产生大量活性氧（ROS）',
      '• 珊瑚为自保，会主动把虫黄藻「请出去」——颜色随之消失，白化发生',
      '• 若高温持续，失去主要能量来源的珊瑚会进一步死亡',
      '【叠加的压力】',
      '• 海洋酸化：海水中 CO₂ 升高使 pH 下降，珊瑚钙化速率随之降低',
      '• 紫外线增强：与高温协同加速白化，浅水区尤其明显',
      '• 富营养化与赤潮：藻类争夺空间和光照，让白化后的恢复更慢',
      '【AI 眼中的白化】',
      '• 分割模型先取出珊瑚像元，再由白化分类模型给出 healthy / bleached / dead 三类概率',
      '• 本项目实测白化识别灵敏度 ≥90%，并用双模型「共识」标出分歧样本，提示人工复核'
    ]
  },
  {
    id: 13, category: 'bleaching', title: '白化之后：一片礁还能救回来吗', img: IMG.tech3,
    link: 'https://gcrmn.net/', linkName: 'GCRMN 全球珊瑚礁监测网络',
    summary: '从耐热选育到投放时间窗，修复工作的六个抓手',
    paragraphs: [
      '白化不是终点。珊瑚礁的恢复力比想象中强，但需要人帮它把「恢复窗口」争取出来。',
      '【六个抓手】',
      '1. 耐热种源：筛选耐高温亲本、做种间杂交，保留韧性更高的基因组合',
      '2. 苗圃培育：先在受控环境里把幼苗养壮，再定植到野外',
      '3. 底质与结构：用 3D 打印仿生底托等载体改善附着条件，提高成活率',
      '4. 选点选时：避开热压力高风险月份投放（本项目仙本那点位建议避开 4—7 月）',
      '5. 减少本地压力：控制沉积物、营养盐与藻类竞争，给珊瑚留出生长空间',
      '6. 连续监测：用 AI 水下识别跟踪白化比例与覆盖率变化，评估干预是否有效',
      '【一句提醒】',
      '• 修复能「加速」恢复，但改变不了升温趋势本身；减碳与修复是并行关系，不是替代关系',
      '• 所以本项目把气候数据（NOAA CRW）与图像评估放进同一份报告，让决策同时看到两个维度'
    ]
  }
]

const species = [
  { name: '鹿角珊瑚', latin: 'Acropora spp.', desc: '分枝状造礁珊瑚，海洋最常见的珊瑚属，分支如鹿角般伸展', dist: 'Indo-Pacific、海洋', img: IMG.coral1 },
  { name: '脑珊瑚', latin: 'Diploria spp.', desc: '球形或块状，表面沟回纹路如大脑，生长缓慢但寿命极长', dist: '全球热带海域', img: IMG.tech2 },
  { name: '蘑菇珊瑚', latin: 'Fungia spp.', desc: '单体型珊瑚，形如蘑菇，可自由移动，是少数能移动珊瑚', dist: '印度-太平洋', img: IMG.coral3 },
  { name: '软珊瑚', latin: 'Alcyonacea', desc: '无石灰质骨骼，柔软随水流摆动，色彩丰富形态优美', dist: '全球热带亚热带', img: IMG.coral2 },
  { name: '柳珊瑚', latin: 'Gorgonia spp.', desc: '扇形分枝如柳条，常见于海流较强区域，是海洋生物栖息地', dist: '海洋、加勒比海', img: IMG.tech4 },
  { name: '笙珊瑚', latin: 'Tubipora musica', desc: '管状骨骼并联如笙管，鲜红或绿色，极具观赏价值', dist: '印度-太平洋', img: IMG.tech5 }
]

const allSpecies = species.concat([
  { name: '火珊瑚', latin: 'Millepora spp.', desc: '触手含刺细胞，触碰如火烧，是造礁珊瑚中唯一的水螅珊瑚', dist: '全球热带海域', img: IMG.coral1 },
  { name: '桌珊瑚', latin: 'Acropora hyacinthus', desc: '平板状展开如水中圆桌，是鹿角珊瑚属中形态最独特的品种', dist: '印度-太平洋', img: IMG.tech2 },
  { name: '玫瑰珊瑚', latin: 'Euphyllia spp.', desc: '花瓣状触手排列如玫瑰，色彩艳丽，是水族馆最受欢迎的品种', dist: '印度-太平洋', img: IMG.coral3 },
  { name: '柱珊瑚', latin: 'Porites spp.', desc: '圆柱形直立生长，生长极缓慢但寿命可达数百年，是礁石骨架主要构建者', dist: '全球热带海域', img: IMG.tech1 },
  { name: '气泡珊瑚', latin: 'Plerogyra sinuosa', desc: '表面布满气泡状共生藻，白天膨胀如葡萄串，是珊瑚礁中最独特的景观', dist: '印度-太平洋', img: IMG.tech5 },
  { name: '短小鹿角珊瑚', latin: 'Acropora humilis', desc: '蓝珊科技珊瑚2号杂交亲本之一，耐高温品种，可耐受+1℃高温', dist: '海洋', img: IMG.coral2 }
])

/* ================= AI ================= */
const aiHistory = [
  { id: 1, title: '柔枝鹿角珊瑚 · 健康', time: '2026-07-15 14:30', confidence: 94.2, img: IMG.coral1 },
  { id: 2, title: '块状牡丹珊瑚 · 轻度白化', time: '2026-07-14 09:15', confidence: 89.7, img: IMG.tech2 },
  { id: 3, title: '短小鹿角珊瑚 · 健康', time: '2026-07-12 16:42', confidence: 91.5, img: IMG.coral2 }
]

const aiResultSpecies = {
  icon: '🪸', title: '柔枝鹿角珊瑚', sub: 'Acropora valida · 鹿角珊瑚科', confidence: 94.2,
  details: [
    { label: '学名', value: 'Acropora valida' },
    { label: '科属', value: '鹿角珊瑚科 · 鹿角珊瑚属' },
    { label: '分布区域', value: '海洋、印度洋-太平洋' },
    { label: '生长形态', value: '分枝状造礁珊瑚' },
    { label: '保护等级', value: '国家二级保护动物' },
    { label: '抗逆评级', value: '★★★★☆' },
    { label: '珊瑚2号亲本', value: '是（主要亲本）' }
  ],
  tags: [
    { text: '造礁珊瑚', type: '' },
    { text: '海洋常见种', type: '' },
    { text: '珊瑚2号亲本', type: '' },
    { text: '置信度高', type: 'green' }
  ]
}

const aiResultGrowth = {
  icon: '📊', title: '健康状态评估报告', sub: '综合分析完成 · 整体状态良好', confidence: 87.3,
  details: [
    { label: '白化程度', value: '无白化 ✅' },
    { label: '活体覆盖率', value: '87.3%' },
    { label: '生长速率', value: '2.3 cm/月' },
    { label: '珊瑚骨架密度', value: '1.42 g/cm³' },
    { label: '虫黄藻密度', value: '正常 (2.1×10⁶/cm²)' },
    { label: '环境风险评估', value: '低风险' },
    { label: '水温', value: '26.8℃ (适宜)' },
    { label: '建议', value: '保持当前环境参数，定期监测' }
  ],
  tags: [
    { text: '健康', type: 'green' },
    { text: '生长稳定', type: 'green' },
    { text: '无需干预', type: '' },
    { text: '建议30天后复测', type: 'coral' }
  ]
}

/* ================= 实体认养 ================= */
const entityProducts = [
  {
    id: 'agent', icon: '🪸', title: '珊瑚代种', subtitle: '远程认养 · 专业养护 · 实时追踪',
    desc: '购买一株珊瑚，蓝珊专业团队在海洋修复区帮您种植和养护。通过AI监测系统远程查看珊瑚生长状态，定期收到成长报告。',
    features: ['专属编号命名', 'AI实时监测', '月度成长报告', '电子认养证书'],
    price: 299, priceUnit: '/株起', button: '立即认养'
  },
  {
    id: 'dive', icon: '🤿', title: '潜水种植体验', subtitle: '亲自下水 · 海底种珊瑚 · 深度体验',
    desc: '购买珊瑚+潜水套餐，在专业教练带领下亲自下水，体验海底种植珊瑚的乐趣。包含潜水装备、专业指导、水下摄影及认养证书。',
    features: ['PADI认证教练', '全套潜水装备', '水下摄影跟拍', '珊瑚+潜水套餐'],
    price: 1280, priceUnit: '/人起', button: '预约体验'
  }
]

const myCorals = [
  { id: 1, name: '蓝珊-001号', species: '柔枝鹿角珊瑚', code: 'LS20260315', growth: 65, carbon: 82.3, img: IMG.coral1 },
  { id: 2, name: '蓝珊-002号', species: '短小鹿角珊瑚', code: 'LS20260422', growth: 42, carbon: 58.7, img: IMG.coral2 },
  { id: 3, name: '蓝珊-003号', species: '陀螺珊瑚', code: 'LS20260510', growth: 28, carbon: 45.5, img: IMG.coral3 }
]

const coralDetail = {
  id: 1, name: '蓝珊-001号', species: '柔枝鹿角珊瑚', growth: 65, img: IMG.coral1,
  remain: 350, area: '深圳大鹏湾',
  timeline: [
    { time: '2026-07-10', desc: 'AI监测：珊瑚生长良好，覆盖面积增长12%' },
    { time: '2026-06-15', desc: '季度巡检完成，珊瑚状态健康，白化风险低' },
    { time: '2026-04-20', desc: '完成模块化仿生导流式生长装置定植' },
    { time: '2026-03-15', desc: '珊瑚2号种苗培育完成，开始认养' }
  ]
}

const cameraData = {
  img: IMG.tech4,
  live: true,
  metrics: [
    { icon: '🌡', label: '水温 26.8°C' },
    { icon: '💧', label: 'pH 8.12' },
    { icon: '🔆', label: '透明度 12m' }
  ],
  location: '深圳大鹏湾 · 珊瑚修复区A3',
  coord: "N22°33' E114°37'"
}

/* ================= 虚拟认养（养成玩法） ================= */
const feeds = [
  { key: 'basic', name: '基础浮游生物', icon: '🦠', price: 10, growth: 3, desc: '珊瑚日常营养补充' },
  { key: 'calcium', name: '钙质营养液', icon: '🧪', price: 20, growth: 5, desc: '促进珊瑚骨骼生长' },
  { key: 'algae', name: '海藻精华', icon: '🌿', price: 30, growth: 8, desc: '富含共生藻营养' },
  { key: 'mineral', name: '深海矿物质', icon: '💎', price: 50, growth: 12, desc: '稀有深海矿物精华' },
  { key: 'polyp', name: '珊瑚虫粮食', icon: '🪸', price: 80, growth: 18, desc: '高浓度珊瑚虫专用粮' },
  { key: 'moonlight', name: '月光珊瑚素', icon: '🌙', price: 120, growth: 25, desc: '传说中的月光精华' }
]

const cultureItems = [
  { id: 'badge', name: '珊瑚保护徽章', icon: '🏅', price: 100, desc: '限量版珊瑚保护者徽章' },
  { id: 'bag', name: '蓝珊帆布袋', icon: '👜', price: 200, desc: '环保帆布袋，印有珊瑚图案' },
  { id: 'phonecase', name: '珊瑚主题手机壳', icon: '📱', price: 300, desc: '定制珊瑚图案手机壳' },
  { id: 'postcard', name: '海洋生态明信片套装', icon: '📮', price: 150, desc: '12张海洋珊瑚实景明信片' },
  { id: 'frame', name: '珊瑚标本相框', icon: '🖼️', price: 500, desc: '真实珊瑚标本装裱相框' },
  { id: 'tshirt', name: '蓝珊联名T恤', icon: '👕', price: 400, desc: '珊瑚保护主题联名T恤' }
]

const coralNames = ['鹿角珊珊', '蘑菇小珊', '柳枝珊瑚', '笙管珊瑚', '火珊瑚宝宝', '气泡小珊', '桌珊瑚苗', '玫瑰珊瑚', '柱珊瑚宝宝', '脑纹珊瑚']

const tasks = [
  { id: 'checkin', icon: '📅', iconBg: 'rgba(255,193,7,0.12)', name: '每日签到', desc: '每日登录即可领取', points: 10, action: 'claim' },
  { id: 'share', icon: '📤', iconBg: 'rgba(30,136,229,0.12)', name: '分享好友', desc: '分享给1位好友', points: 20, action: 'share' },
  { id: 'learn', icon: '📚', iconBg: 'rgba(0,188,212,0.12)', name: '科普学习', desc: '阅读1篇科普文章', points: 15, action: 'learn' },
  { id: 'donate', icon: '💚', iconBg: 'rgba(76,175,80,0.12)', name: '公益捐赠', desc: '参与珊瑚保护公益', points: 50, action: 'donate' },
  { id: 'quiz', icon: '🧠', iconBg: 'rgba(171,71,188,0.12)', name: '知识问答', desc: '完成珊瑚知识答题', points: 15, action: 'quiz' },
  { id: 'steps', icon: '👟', iconBg: 'rgba(255,112,67,0.12)', name: '步数达标', desc: '今日步行满5000步', points: 15, action: 'steps' },
  { id: 'welfare', icon: '🏖️', iconBg: 'rgba(0,150,136,0.12)', name: '珊瑚公益活动', desc: '参与净滩行动/珊瑚种植等', points: 30, action: 'welfare' }
]

const welfareActivities = [
  { icon: '🏖️', name: '净滩行动', desc: '参与海滩清洁，保护海洋生态环境' },
  { icon: '🪸', name: '珊瑚种植日', desc: '亲手种植珊瑚幼苗，修复珊瑚礁生态' },
  { icon: '🐠', name: '海洋生态调查', desc: '参与珊瑚礁鱼类和生物多样性调查' }
]

/* ================= 问答 ================= */
const quizQuestions = [
  { q: '珊瑚礁被称为"海洋中的什么"？', options: ['海洋中的沙漠', '海洋中的热带雨林', '海洋中的草原', '海洋中的森林'], answer: 1 },
  { q: '蓝珊科技珊瑚2号有性杂交的受精率是多少？', options: ['＞80%', '＞90%', '＞95%', '100%'], answer: 2 },
  { q: '珊瑚白化的主要原因是什么？', options: ['海水盐度增加', '海水温度升高', '海洋噪声污染', '月光照射增强'], answer: 1 },
  { q: 'AI监测系统识别珊瑚的准确率范围是？', options: ['70%-80%', '88%-96%', '95%-99%', '60%-75%'], answer: 1 },
  { q: '15公顷珊瑚礁每年大约固定多少碳酸钙？', options: ['50吨', '100吨', '225吨', '500吨'], answer: 2 }
]

/* ================= 夏令营 ================= */
const campData = {
  img: IMG.camp,
  stats: [
    { num: '43', label: '班次' },
    { num: '8', label: '城市' },
    { num: '1473', label: '名学生' },
    { num: '368', label: '场讲座' }
  ],
  desc: '蓝珊科技已开展青少年珊瑚夏令营43个班次，覆盖深圳、湛江、茂名、惠州、珠海、江门、钦州、三亚8个城市，参与学生1473人。累计开展科普讲座368场，直接受益人数达25,682人。',
  cities: ['深圳', '湛江', '茂名', '惠州', '珠海', '江门', '钦州', '三亚'],
  camps: [
    {
      icon: '🌱', name: '成长营', price: '¥2,160/人', color: 'primary',
      target: '面向12-18岁中学生 · 3天2夜',
      content: '系统课程 + 出海科考模拟 + 探访育苗车间 + 浮潜观测 + 海底种植直播',
      note: '结营颁发"青年珊瑚大使"证书',
      tags: ['寒暑假各3期', '每期25人']
    },
    {
      icon: '🤿', name: '专业营', price: '¥3,680/人', color: 'accent',
      target: '面向持OW及以上潜水证成年人 · 5天4夜',
      content: '专家授课 + 潜水普查实操(2次) + 海底修复实战 + 数据研习 + 认证颁证',
      note: '普查数据计入年度报告，认证志愿服务时长',
      tags: ['寒暑假各1期', '每期12人']
    },
    {
      icon: '👑', name: '领袖营', price: '¥6,980/人', color: 'coral',
      target: '面向持AOW及以上潜水证高阶人士/企业管理者 · 6天5夜',
      content: '专家闭门交流 + 大规模海底种植(每人20株+) + 专利技术研习 + 独立普查 + 珊瑚礁认养(专属命名权)',
      note: '数据录入中国珊瑚礁监测网络年度报告',
      tags: ['每年1期', '限额10人', '需审核']
    }
  ]
}

/* ================= 水族箱 ================= */
const aquariumData = {
  metrics: [
    { val: '26.8°C', lbl: '水温' },
    { val: '8.12', lbl: 'pH值' },
    { val: '3株', lbl: '珊瑚数量' },
    { val: '5条', lbl: '鱼类数量' }
  ],
  diagnosis: [
    { status: '健康', level: 'good', name: '001号珊瑚' },
    { status: '健康', level: 'good', name: '002号珊瑚' },
    { status: '注意', level: 'warn', name: '003号珊瑚' }
  ]
}

/* ================= 勋章 ================= */
const badges = [
  { icon: '🌊', name: '海洋守护者', desc: '认养首株珊瑚', achieved: true, progress: 100 },
  { icon: '🪸', name: '珊瑚园丁', desc: '累计认养3株', achieved: true, progress: 100 },
  { icon: '🌿', name: '碳汇先锋', desc: '碳汇超100g CO₂', achieved: true, progress: 100 },
  { icon: '📚', name: '科普达人', desc: '完成10个科普学习', achieved: true, progress: 100 },
  { icon: '🐠', name: '水族箱大师', desc: '查看水族箱10次', achieved: true, progress: 100 },
  { icon: '🏆', name: '珊瑚大使', desc: '邀请5位好友认养', achieved: false, progress: 40, progressText: '2/5' }
]

const badgeLevels = [
  { stars: '★', name: '入门守护者', desc: '获得1-2枚勋章 · 已达成 ✓', color: 'gold' },
  { stars: '★★', name: '珊瑚守护者', desc: '获得3-4枚勋章 · 已达成 ✨', color: 'blue' },
  { stars: '★★★', name: '海洋大使', desc: '获得全部6枚勋章 · 进度 5/6', color: 'purple' },
  { stars: '👑', name: '蓝珊传奇', desc: '海洋大使 + 邀请5位好友 · 未解锁', color: 'coral' }
]

/* ================= 成长档案 ================= */
const growthData = {
  chart: [
    { val: '5cm', height: 34, label: '3月' },
    { val: '7cm', height: 48, label: '4月' },
    { val: '9.5cm', height: 65, label: '5月' },
    { val: '12cm', height: 82, label: '6月' },
    { val: '14.5cm', height: 100, label: '7月' }
  ],
  metrics: [
    { val: '14.5 cm', lbl: '累计生长', green: false },
    { val: '2.3 cm', lbl: '月均增长', green: false },
    { val: '28次', lbl: 'AI监测次数', green: false },
    { val: '95分', lbl: '健康评分', green: true }
  ],
  timeline: [
    { time: '2026-07-10', desc: 'AI监测：珊瑚高度达14.5cm，较上月增长2.5cm' },
    { time: '2026-06-15', desc: '季度巡检完成，珊瑚状态健康，新增2个分支' },
    { time: '2026-05-20', desc: '珊瑚出现新色彩变化，虫黄藻密度正常' },
    { time: '2026-04-10', desc: '完成春季养护，珊瑚生长态势良好' }
  ]
}

/* ================= 社区评论 ================= */
const defaultComments = [
  { id: 1, avatar: '🌊', name: '海洋之心', time: '2小时前', text: '今天去大鹏湾看到了蓝珊团队修复的珊瑚礁，真的太美了！覆盖率比三年前高了好多，鱼也多了起来。', mine: false },
  { id: 2, avatar: '🐠', name: '潜水爱好者', time: '5小时前', text: '参加了珊瑚夏令营，第一次亲手种了珊瑚，那种感觉太奇妙了。孩子们也学到了很多海洋知识！', mine: false },
  { id: 3, avatar: '🪸', name: '蓝珊小助手', time: '昨天', text: '珊瑚2号LT品系最新监测数据：胁迫环境下成活率98%，两年生长长度超过20厘米！为科研团队点赞👍', mine: false },
  { id: 4, avatar: '🐡', name: '生态守护者', time: '2天前', text: '认养了第5株珊瑚啦～看着成长值一天天增加，就像看自己的孩子长大一样。保护珊瑚人人有责！', mine: false }
]

/* ================= 证书 ================= */
const certEntity = {
  type: 'entity',
  topLabel: 'CORAL ADOPTION CERTIFICATE',
  title: '珊瑚认养证书',
  subTitle: '蓝珊科技 · 海洋珊瑚礁保护计划',
  img: IMG.coral1,
  fields: [
    { label: '认养者', value: '蓝珊守护者' },
    { label: '珊瑚品种', value: '柔枝鹿角珊瑚' },
    { label: '珊瑚编号', value: 'LS-2026-0315-001' },
    { label: '认养日期', value: '2026年3月15日' },
    { label: 'GPS坐标', value: "N22°33' E114°37'" },
    { label: '修复海域', value: '深圳大鹏湾' }
  ],
  org: '广东蓝珊科技有限公司',
  issueDate: '签发日期：2026年3月15日'
}

const certVirtual = {
  type: 'virtual',
  topLabel: 'VIRTUAL CORAL ADOPTION',
  title: '虚拟珊瑚认养证书',
  subTitle: '蓝珊科技 · 数字珊瑚礁保护计划',
  fields: [
    { label: '认养者', value: '蓝珊守护者' },
    { label: '虚拟珊瑚', value: '鹿角珊珊' },
    { label: '成长状态', value: '🌱 成长中' },
    { label: '实物珊瑚', value: '成长100%可领取' }
  ],
  org: '广东蓝珊科技有限公司'
}

/* ================= 关于 ================= */
const aboutInfo = {
  intro: '蓝珊科技致力于海洋珊瑚礁生态保护与修复，通过"良种培育+智能监测+生态恢复+公众参与"四位一体模式，守护海洋珊瑚礁生态系统。',
  rows: [
    { label: '依托单位', value: '广东海洋大学深圳研究院' },
    { label: '核心技术', value: '石珊瑚有性育种和无性育种繁育体系' },
    { label: '修复面积', value: '15公顷珊瑚礁' },
    { label: '科普覆盖', value: '368场讲座 · 25682人' },
    { label: '联系邮箱', value: 'service@bluecoral.cn' }
  ]
}

/* ================= Mock 状态管理 ================= */
const MKEY = 'mock_'

function mGet(key, def) {
  const v = wx.getStorageSync(MKEY + key)
  return v === '' || v === undefined || v === null ? def : v
}
function mSet(key, val) {
  wx.setStorageSync(MKEY + key, val)
}

function delay(data, ms) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(typeof data === 'function' ? data() : data), ms || 300)
  })
}

function getMockUser() {
  return mGet('user', null)
}
function setMockUser(u) {
  mSet('user', u)
}
function clearMockUser() {
  wx.removeStorageSync(MKEY + 'user')
}

// 虚拟养成状态
function getVirtualState() {
  let points = mGet('points', null)
  if (points === null) { points = 320; mSet('points', points) }
  let shop = mGet('shop', null)
  if (!shop) { shop = { basic: 2, calcium: 1, algae: 0, mineral: 0, polyp: 0, moonlight: 0 }; mSet('shop', shop) }
  let corals = mGet('corals', null)
  if (!corals) { corals = [{ name: coralNames[0], growth: 0, points: 0 }]; mSet('corals', corals) }
  let culture = mGet('culture', {})
  const done = mGet('tasks_done', {})
  return { points, shop, corals, culture, tasksDone: done }
}

function saveVirtualState(state) {
  mSet('points', state.points)
  mSet('shop', state.shop)
  mSet('corals', state.corals)
  mSet('culture', state.culture)
  mSet('tasks_done', state.tasksDone)
}

function getComments() {
  return mGet('comments', defaultComments.slice())
}
function saveComments(list) {
  mSet('comments', list)
}

// 订单（mock 模式记录到本地，供演示）
function getOrders() { return mGet('orders', []) }
function saveOrders(list) { mSet('orders', list) }

/* 公众号链接开关：WX_LINKS 里填了哪条，就用公众号原文覆盖那条的外链 */
/* ================= 英文文案（首页中英切换用） =================
 * 英文全部集中在这一块，改文案只改这里；页面按 id / 数组顺序取值，
 * 哪条没写英文就自动回落成中文，不会出现空白。
 */
const EN = {
  brand: 'LanShan',
  slogan: 'Guard the ocean corals · tracking marine heat stress',
  /* 顺序与 homeData.stats 一致 */
  // 每个标签拆成两行（\n）：英文比中文长，单行会把数字挤变形
  stats: ['Corals\nadopted', 'Reef cover\nrestored', 'Recognisable\ngenera', 'Years of\nclimate data'],
  carbon: 'Reefs fix about 225 t of calcium carbonate a year — roughly 100 t of CO₂ locked away.',
  climate: {
    title: 'Climate & corals',
    sub: 'Heat stress factored into restoration decisions',
    tag: 'Resilience',
    metrics: ['2024 DHW peak', 'Bleaching alert level', 'Heat-stress record'],
    desc: 'Corals bleach when the water stays about 1 °C above the summer maximum for weeks. ' +
      'At our Semporna site, 3 of the past 41 years reached bleaching alert level — so we pair ' +
      'heat-tolerant breeding with a low-risk deployment window.'
  },
  /* 顺序与 homeData.corals 一致 */
  corals: [
    { name: 'LanShan-001', species: 'Acropora valida' },
    { name: 'LanShan-002', species: 'Acropora humilis' },
    { name: 'LanShan-003', species: 'Turbinaria sp.' }
  ],
  /* 顺序与 homeData.tech 一致 */
  tech: [
    {
      label: 'Breeding',
      title: 'Coral No.2: sexual hybridisation for stress tolerance',
      desc: 'Heat- and acidification-tolerant native parent colonies from the ocean are crossed ' +
        'to produce offspring with >95% fertilisation and 98% survival under lab heat / acid stress ' +
        '(+1 °C, pH −1.18).',
      tags: ['Sexual hybridisation', 'Stress-tolerant breeding', 'Fertilisation >95%']
    },
    {
      label: 'AI monitoring',
      title: 'Multi-modal AI underwater monitoring system',
      desc: 'YOLOv9 detection plus SAM3 segmentation over an ocean coral germplasm library: ' +
        '20+ common scleractinian taxa recognised at 88–96% accuracy, 30–50× faster than manual survey.',
      tags: ['YOLOv9', 'SAM3', 'AI recognition', 'Real-time']
    },
    {
      label: 'Restoration gear',
      title: 'Shell-based sinter-free 3D-printed flow-guide base',
      desc: 'Printed in one piece from recycled marine shell powder, with biomimetic surface texture and ' +
        'dual-layer flow channels that improve polyp settlement and seedling growth.',
      tags: ['3D printing', 'Shell-based material', 'Low carbon']
    }
  ],
  videoCaption: 'LanShan · Restoring reefs in the ocean',
  videoUrl: '/video/team.mp4',
  /* 推文：key = 文章 id（对应 homeData.articles[].id） */
  articles: {
    1: ['Reef restoration milestone: live coral cover up from 30% to 50%', 'Project'],
    2: ['Coral No.2 released: fertilisation >95%, survival 98%', 'Technology'],
    3: ['2026 summer coral camps: 43 sessions across 8 cities', 'Recruiting'],
    4: ['AI survey annual report: 200,000+ corals identified, 50× faster', 'Report'],
    5: ['What does coral “climate resilience” actually mean?', 'Resilience'],
    6: ['Reading marine heat stress: DHW and bleaching alerts', 'Resilience'],
    7: ['Bleached ≠ dead: three stages and the recovery window', 'Bleaching'],
    8: ['How bleaching happens: zooxanthellae, heat stress and acidification', 'Bleaching'],
    9: ['Global reefs in decline: how to read the GCRMN assessment', 'Resilience'],
    10: ['1.5 °C or 2 °C: where is the reef tipping point?', 'Resilience'],
    11: ['Ocean warming and acidification: what the IPCC ocean report says', 'Resilience'],
    12: ['Ocean reef protection: where official notices are published', 'Bleaching'],
    13: ['Great Barrier Reef bleaching: what a heatwave leaves behind', 'Bleaching'],
    14: ['Where sea-surface temperature records come from: satellites and buoys', 'Resilience']
  },
  /* 动态：key = 动态 id（对应 homeData.news[].id） */
  news: {
    1: ['Semporna core reef: latest coral monitoring', 'Monitoring'],
    2: ['Coral No.2 hybrid enters large-scale sea-nursery trials', 'Technology'],
    3: ['43rd youth coral camp wraps up', 'Education'],
    4: ['Semporna heat stress at a glance: a 41-year record and the 2024 peak', 'Resilience'],
    5: ['Semporna seasonal window: when heat stress eases', 'Restoration planning']
  }
  ,
  /* ---- 科普页：分类名（key = 分类 key） ---- */
  knowledgeCategories: {
    all: 'All',
    species: 'Coral species',
    ecosystem: 'Ecosystem',
    bleaching: 'Bleaching crisis',
    climate: 'Climate resilience',
    tech: 'Restoration tech',
    camp: 'Summer camp'
  },
  /* ---- 科普文章：key = 文章 id → [标题, 摘要] ---- */
  knowledge: {
    0: ['Staghorn coral (Acropora valida)',
        'One of the most common reef-building corals in the ocean; its branching growth makes it a keystone reef species'],
    1: ['Coral bleaching explained',
        'Over 80% of the world\u2019s reefs have suffered severe bleaching — causes, mechanism and consequences'],
    2: ['The coral reef ecosystem',
        'Reefs cover less than 0.1% of the sea floor yet support about 25% of all marine species'],
    3: ['AI underwater monitoring',
        'YOLOv9 + SAM3 recognition: 88–96% accuracy and 30–50× faster than manual survey'],
    4: ['Coral reef restoration in practice',
        'From nursery rearing to out-planting: LanShan\u2019s full-chain restoration workflow'],
    5: ['Coral summer camps',
        '43 sessions, 8 cities, 1,473 students — marine science education in the field'],
    6: ['Short staghorn coral (Acropora humilis)',
        'A parent colony of Coral No.2: a heat-tolerant variety that withstands +1 °C'],
    7: ['3D-printed coral substrate',
        'Sinter-free printing from recycled shell powder; biomimetic texture improves settlement'],
    8: ['Where coral climate resilience comes from',
        'Resilience is not \u201cnever bleaching\u201d — it is how well a reef comes back afterwards'],
    9: ['Reading marine heat stress: DHW and bleaching alerts',
        'What SST anomaly, DHW and BAA each tell you — and what they cannot'],
    10: ['Reefs are a climate defence line too',
        'Under 0.1% of the sea floor, 25% of marine species, 70–90% of wave energy absorbed'],
    11: ['Bleached \u2260 dead: three stages and the recovery window',
        'How to tell partial bleaching, full bleaching and dead coral apart in the field'],
    12: ['How bleaching happens: zooxanthellae, heat stress and acidification',
        'The chain reaction that drives a coral\u2019s algal partners out — and why cooling matters most'],
    13: ['After bleaching: can a reef recover?',
        'Six levers of restoration, from heat-tolerant stock to the deployment window']
  }
  ,
  /* ---- 图鉴（珊瑚种类）：按「固定取值 / 形态码 / 条目 id」对应，不做模糊匹配 ---- */
  catalogGroups: {
    '造礁石珊瑚': 'Reef-building scleractinian',
    '非造礁石珊瑚': 'Non-reef-building scleractinian',
    '软珊瑚': 'Soft coral',
    '水螅珊瑚': 'Hydrocoral',
    '柳珊瑚': 'Gorgonian / sea fan'
  },
  catalogDist: {
    'Indo-Pacific、海洋': 'Indo-Pacific, ocean',
    '全球热带海域': 'Pantropical',
    '印度-太平洋': 'Indo-Pacific',
    '全球热带亚热带': 'Tropical and subtropical seas',
    '海洋、加勒比海': 'ocean, Caribbean'
  },
  catalogProtection: {
    'CITES 附录 II；中国《国家重点保护野生动物名录》（2021）列为国家二级':
      'CITES Appendix II; Class II protected wildlife in China (2021 national list)',
    '未列入 CITES 附录 I；国内重点名录多数未收录（以官方名录为准）':
      'Not listed in CITES Appendix I; mostly absent from China\u2019s key protected list (check official lists)'
  },
  catalogProtectionNote: 'Class-level default — check the CITES appendices and the national protected-wildlife list for the exact species',
  catalogRisk: { '高': 'High', '中': 'Medium', '低': 'Low' },
  catalogTempSal: '23–29 °C optimum (short-term 18–32 °C); salinity 34–36 \u2030 (optimum 35 \u2030)',
  /* 形态码 → 详情页「形态 / 习性 / 威胁」通性（与中文 FORM_ATTR 一一对应） */
  catalogForms: {
    B: {
      form: 'Branching',
      size: 'Colony 20–60 cm across, branches 10–40 cm',
      depth: '1–20 m (mostly 2–10 m)',
      growth: 'Fast: branches extend about 3–10 cm per year',
      symb: 'Strongly symbiotic with zooxanthellae; about 80–90% of its energy comes from their photosynthesis',
      mates: 'Reef fish, shrimps and crabs, brittle stars, boring sponges and worms',
      threat: 'Bleaching in marine heatwaves; storm breakage; sediment and nutrient loading; collection for the aquarium trade',
      feed: 'Mainly powered by its zooxanthellae (about 80–90% of its energy); tentacles also catch plankton and organic particles, most actively after dark',
      pop: 'Widespread and often dominant on reefs, but numbers swing with heatwaves and storms; most species lack global assessments and local declines follow collection and habitat loss'
    },
    M: {
      form: 'Massive / boulder',
      size: 'Colony 30–100 cm across, some over 2 m',
      depth: '0–30 m (deeper in turbid water)',
      growth: 'Slow: about 0.5–2 cm per year, colonies may live for centuries',
      symb: 'Stable zooxanthellae symbiosis; slow calcification but the biggest contributor to reef framework',
      mates: 'Boring sponges and polychaetes, reef fish, shrimps and crabs, epiphytic algae',
      threat: 'Slow recovery after bleaching; acidification slows calcification; anchor and trampling damage; sediment burial',
      feed: 'Zooxanthellae supply most of its energy; at night it extends tentacles and mucus to capture plankton and organic detritus',
      pop: 'Long-lived and massive, so recovery after damage is very slow; local declines near shore from sediment and pollution, and it is highly sensitive to ocean warming'
    },
    P: {
      form: 'Plate / table',
      size: 'Plates 20–80 cm across, often stacked in layers',
      depth: '2–25 m, often on slightly turbid reef slopes and lagoons',
      growth: 'Moderate: edges extend about 1–4 cm per year',
      symb: 'Zooxanthellae symbiosis; the single-sided plate improves light use',
      mates: 'Reef fish, crustaceans and gastropods; the shaded underside shelters juvenile fish',
      threat: 'Bleaching in heatwaves; sediment covering the lit surface; physical damage from waves and currents',
      feed: 'Mostly zooxanthellae-powered; tentacles on the upper surface and plate edge catch plankton, while shaded undersides rely more on heterotrophy',
      pop: 'Common on lit reef slopes, but plates are fragile in storms and sediment and bleaching can strip whole plates, so numbers track heatwave events'
    },
    F: {
      form: 'Foliose / thin plate',
      size: 'Blades 15–50 cm across, a few millimetres to 1 cm thick',
      depth: '1–30 m, also on dim slopes and cave mouths',
      growth: 'Moderate: about 1–5 cm per year',
      symb: 'Zooxanthellae symbiosis; the thin blade suits light capture in dim habitats',
      mates: 'Reef-slope fish, shrimps and crabs, and cryptic invertebrates',
      threat: 'The most sensitive to bleaching and sediment; acidification makes blades brittle; easy to snap on contact',
      feed: 'Mainly zooxanthellae-driven; the thin blade improves light capture in dim habitats and also traps plankton and suspended particles',
      pop: 'Restricted to dim reef slopes and cave mouths; the most sensitive to bleaching and sediment, with clear local declines'
    },
    U: {
      form: 'Solitary / free-living',
      size: 'Single polyp 5–30 cm across (mostly 10–20 cm)',
      depth: '1–25 m, often on sand and reef flats',
      growth: 'Slow: about 0.5–2 cm per year',
      symb: 'Symbiotic with zooxanthellae; adults are free-living and can right themselves after being flipped',
      mates: 'Sand-dwelling invertebrates, commensal crabs and snails; juveniles settle on rock',
      threat: 'Bleaching; burial by sediment; collection and trampling; free-living individuals can be overturned by waves',
      feed: 'Inflates by day to feed its zooxanthellae; at night it extends tentacles to take plankton and settling organic particles',
      pop: 'Numerous on reef flats and sand, but easily overturned by waves and collected; the family Fungiidae is listed in CITES Appendix II'
    },
    S: {
      form: 'Soft / fleshy',
      size: 'Colony 10–60 cm tall, caps up to 30 cm across',
      depth: '2–30 m, moderate current and lower light',
      growth: 'Fairly fast: 10–60 mm per year (flow and nutrients matter)',
      symb: 'Mostly symbiotic with zooxanthellae; some groups (e.g. Dendronephthya) have none and feed on plankton',
      mates: 'Small fish, shrimps and crabs, anemonefish and commensal crustaceans',
      threat: 'Heat and turbidity stress; collection pressure; physical tearing',
      feed: 'Mostly zooxanthellae-powered, with extended polyps filtering plankton and dissolved organics; species without symbionts are fully heterotrophic',
      pop: 'Grows fast and can cover large areas, but needs stable water quality; turbidity and nutrients shrink colonies and popular species are heavily collected'
    },
    G: {
      form: 'Fan / whip',
      size: 'Colony 20–100 cm tall, fans 20–80 cm wide',
      depth: '3–40 m, strong current and lower light',
      growth: 'Moderate: about 1–5 cm per year (flow and food supply)',
      symb: 'Mostly heterotrophic filter feeding, not dependent on zooxanthellae; a few species are symbiotic',
      mates: 'Nursery habitat and perches for fish, brittle stars and commensal shrimps',
      threat: 'Breakage by trawls and anchor chains; sediment clogging; harvest for curios',
      feed: 'Mostly heterotrophic filter feeding: eight-tentacled polyps intercept plankton and organic particles; many species do not rely on zooxanthellae',
      pop: 'Common in strong currents, but slow-growing and slow to recover once broken; some species are assessed as vulnerable'
    },
    H: {
      form: 'Hydrocoral',
      size: 'Colony 10–60 cm tall, branching or blade-like',
      depth: '0–20 m',
      growth: 'Fairly fast: blades extend about 2–10 cm per year',
      symb: 'Symbiotic with zooxanthellae inside the hydroid — the main reef-building hydrozoan',
      mates: 'Reef fish, shrimps and crabs; its nematocysts sting divers',
      threat: 'Bleaches in heatwaves too; storm breakage; sediment; damage caused by sting reactions',
      feed: 'Hydroid tentacles capture plankton while zooxanthellae inside the tissue also supply energy; nematocysts serve both feeding and defence',
      pop: 'Widespread with high local cover, and it bleaches in heatwaves too; its brittle skeleton means clear losses after storms'
    }
  },
  catalogColors: {
    B: 'Polyp tissue: pale yellow to cream. With zooxanthellae: olive-yellow, tan to brown, branch tips paler in strong light. Bleached: bone white overall, tips first',
    M: 'Polyp tissue: cream to pale brown. With zooxanthellae: tan to brown-orange, darker deep in the grooves. Bleached: grooves fade first, then the whole colony turns white and the pattern stands out',
    P: 'Polyp tissue: pale yellow. With zooxanthellae: tan, plate edges paler and undersides darker. Bleached: whitens from the edge inwards to a translucent bone colour',
    F: 'Polyp tissue: translucent cream. With zooxanthellae: tan to pale brown. Bleached: the thin blade turns white, leaving bare skeleton',
    U: 'Polyp tissue: cream. With zooxanthellae: bright yellow to cream, darker in the furrows. Bleached: white overall, furrow outlines still visible',
    S: 'Polyp tissue: milky white. With zooxanthellae and its own pigments: pink-purple, cream, flesh tones, soft and translucent. Bleached: dull grey-white and limp',
    G: 'Polyp tissue: scarlet to orange-yellow (colour mostly from its own pigments, little from zooxanthellae). Bleached: pigment lost, grey-white with the netted skeleton exposed',
    H: 'Polyp tissue: cream. With zooxanthellae: yellowish brown to pale tan with pale growth tips. Bleached: turns bone white'
  },
  /* 每条：英文名 + 英文描述（描述同时用作「群落形态」与「辨识特征」） */
  catalogSpecies: {
    'species-acropora-spp': { name: 'Staghorn coral', desc: 'Branching reef-building coral; the most common genus in the ocean, with branches spreading like antlers' },
    'species-diploria-spp': { name: 'Brain coral', desc: 'Round or boulder-shaped, with maze-like grooves that resemble a brain; slow growing but very long-lived' },
    'species-fungia-spp': { name: 'Mushroom coral', desc: 'Solitary free-living coral shaped like a mushroom — one of the few corals that can move' },
    'species-alcyonacea': { name: 'Soft corals', desc: 'No limestone skeleton: soft colonies that sway with the current, in many colours and shapes' },
    'species-gorgonia-spp': { name: 'Sea fans', desc: 'Fan-shaped, willow-like branches common in strong currents; important habitat for reef life' },
    'species-tubipora-musica': { name: 'Organ-pipe coral', desc: 'Parallel tube-like skeleton resembling organ pipes; brilliant red or green and much sought after' },
    'species-millepora-spp': { name: 'Fire coral', desc: 'Stings on contact; the only common reef-building hydrozoan among reef corals' },
    'species-acropora-hyacinthus': { name: 'Table coral', desc: 'Spreads into flat plates like a round table — the most distinctive growth form in the genus Acropora' },
    'species-euphyllia-spp': { name: 'Hammer / anchor coral', desc: 'Petal-like tentacles arranged like a rose; brightly coloured and very popular in aquaria' },
    'species-porites-spp': { name: 'Porites / finger coral', desc: 'Grows as upright columns; extremely slow but can live for centuries, a main builder of reef framework' },
    'species-plerogyra-sinuosa': { name: 'Bubble coral', desc: 'Surface covered in bubble-like tissue over its zooxanthellae; inflates like a bunch of grapes by day' },
    'species-acropora-humilis': { name: 'Short staghorn coral', desc: 'One of the parent colonies of LanShan Coral No.2; a heat-tolerant variety that withstands +1 °C' }
  }
}
homeData.en = EN

homeData.articles.forEach((a) => {
  const wx = WX_LINKS[a.id]
  if (wx) {
    a.url = wx
    a.urlName = '微信公众号原文'
  }
})

module.exports = {
  IMG,
  EN,
  homeData,
  knowledgeCategories,
  knowledgeItems,
  species,
  allSpecies,
  aiHistory,
  aiResultSpecies,
  aiResultGrowth,
  entityProducts,
  myCorals,
  coralDetail,
  cameraData,
  feeds,
  cultureItems,
  coralNames,
  tasks,
  welfareActivities,
  quizQuestions,
  campData,
  aquariumData,
  badges,
  badgeLevels,
  growthData,
  defaultComments,
  certEntity,
  certVirtual,
  aboutInfo,
  delay,
  getMockUser,
  setMockUser,
  clearMockUser,
  getVirtualState,
  saveVirtualState,
  getComments,
  saveComments,
  getOrders,
  saveOrders
}
