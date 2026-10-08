/**
 * Mock 数据层
 * 完整提取自官网「蓝珊APP.html」的全部业务数据。
 * - USE_MOCK=true 时作为数据源（可独立演示，状态存于本机 storage）
 * - 接入真实后端后本文件不再被调用（仅作为字段结构参考/字段契约）
 */

const IMG = {
  coral1: 'https://s.coze.cn/image/fAxnZEmbNRA/',
  coral2: 'https://s.coze.cn/image/hYssppc_-Qg/',
  coral3: 'https://s.coze.cn/image/DuIWc5CXDwg/',
  tech1: 'https://s.coze.cn/image/nQxFroDmA3o/',
  tech2: 'https://s.coze.cn/image/qnp7mQdS-TI/',
  tech3: 'https://s.coze.cn/image/Ozu5AlLQeaM/',
  tech4: 'https://s.coze.cn/image/sk2faUzel3o/',
  tech5: 'https://s.coze.cn/image/Iv_WEll27NE/',
  camp: 'https://s.coze.cn/image/tuqN1lUToF8/'
}

/* ================= 首页 ================= */
const homeData = {
  stats: [
    { num: '12,847', label: '累计认养(株)' },
    { num: '50.12%', label: '修复区覆盖率' },
    { num: '20+', label: '可识别品种' }
  ],
  energy: { cur: 650, max: 1000 },
  carbon: {
    value: 186.5,
    unit: 'g CO₂',
    desc: '珊瑚礁每年可固定约225吨碳酸钙 ≈ 封存约100吨CO₂'
  },
  corals: [
    { id: 1, name: '蓝珊-001号', species: '柔枝鹿角珊瑚', date: '2026.03.15', growth: 65, img: IMG.coral1 },
    { id: 2, name: '蓝珊-002号', species: '短小鹿角珊瑚', date: '2026.04.22', growth: 42, img: IMG.coral2 },
    { id: 3, name: '蓝珊-003号', species: '陀螺珊瑚', date: '2026.05.10', growth: 28, img: IMG.coral3 }
  ],
  tech: [
    {
      img: IMG.tech1, label: '核心育种技术', title: '珊瑚2号有性杂交抗逆选育技术',
      desc: '筛选耐高温、耐酸化的南海本土珊瑚亲本，通过种间定向杂交培育高抗逆珊瑚子代，种间杂交受精率＞95%，实验室高温酸化环境下成活率达98%，可耐受+1℃高温、pH↓1.18酸化环境。',
      tags: ['有性杂交', '抗逆选育', '受精率＞95%']
    },
    {
      img: IMG.tech2, label: '智能监测技术', title: '多模态AI水下智能识别监测系统',
      desc: '融合YOLOv9目标检测与SAM3图像分割模型，依托南海珊瑚种质资源库，可自动识别20种以上南海常见石珊瑚，识别准确率88%-96%，监测效率较人工提升30-50倍。',
      tags: ['YOLOv9', 'SAM3', 'AI识别', '实时监测']
    },
    {
      img: IMG.tech3, label: '修复装备技术', title: '贝壳基免烧结3D打印导流式底托',
      desc: '以海洋固废贝壳粉为原料，采用免烧结精细化3D打印工艺制备，可定制仿生纹理结构与双层导流孔道，有效提升珊瑚虫附着成功率与幼苗生长速率。',
      tags: ['3D打印', '贝壳基材料', '绿色低碳']
    }
  ],
  teamIntro: '蓝珊科技汇聚了海洋生物、生态修复、AI技术等多领域专家，扎根南海十余年，致力于珊瑚礁生态保护与修复。',
  team: [
    { name: '张教授', role: '首席科学家', desc: '珊瑚遗传育种方向，30年海洋生物研究经验', avatar: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=120&h=120&fit=crop&crop=face' },
    { name: '李博士', role: 'AI技术总监', desc: '计算机视觉专家，主导AI水下监测系统开发', avatar: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=120&h=120&fit=crop&crop=face' },
    { name: '王工程师', role: '生态修复主管', desc: '负责南海珊瑚礁修复基地的运维与管理', avatar: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=120&h=120&fit=crop&crop=face' },
    { name: '陈老师', role: '科普教育总监', desc: '策划执行368场科普讲座，受益25682人', avatar: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=120&h=120&fit=crop&crop=face' },
    { name: '刘经理', role: '项目经理', desc: '统筹夏令营及珊瑚认养项目运营', avatar: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=120&h=120&fit=crop&crop=face' }
  ],
  teamDetail: [
    { name: '张教授', role: '首席科学家', desc: '珊瑚遗传育种方向，30年海洋生物研究经验。主持国家自然科学基金重点项目5项，发表SCI论文60余篇，培育出珊瑚2号等4个高抗逆品系。' },
    { name: '李博士', role: 'AI技术总监', desc: '计算机视觉与深度学习专家，主导开发基于YOLOv9+SAM3的水下珊瑚智能监测系统，识别准确率达88%-96%。' },
    { name: '王工程师', role: '生态修复主管', desc: '10年海洋生态修复经验，负责南海珊瑚礁修复基地日常运维，主导完成15公顷珊瑚礁修复工程。' },
    { name: '陈老师', role: '科普教育总监', desc: '环境教育专业背景，累计策划执行科普讲座368场，受益人数25682人，设计"三阶九级"珊瑚礁科普课程体系。' },
    { name: '刘经理', role: '项目经理', desc: '统筹管理夏令营（累计43班次、1473名学生）和珊瑚认养项目运营，确保项目高质量交付。' }
  ],
  videoCaption: '蓝珊科技 · 南海珊瑚礁修复纪录',
  articles: [
    { id: 1, title: '南海珊瑚礁修复取得阶段性成果：覆盖率从30%提升至50%', date: '2026-07-15', tag: '项目进展', img: IMG.coral1, url: 'https://mp.weixin.qq.com/s/example1' },
    { id: 2, title: '珊瑚2号新品系发布：受精率＞95%，成活率98%', date: '2026-07-08', tag: '技术突破', img: IMG.coral3, url: 'https://mp.weixin.qq.com/s/example2' },
    { id: 3, title: '2026年暑期夏令营招募启动！8城43班次等你来', date: '2026-06-20', tag: '活动招募', img: IMG.tech4, url: 'https://mp.weixin.qq.com/s/example3' },
    { id: 4, title: 'AI水下监测年报：累计识别珊瑚20万+株，效率提升50倍', date: '2026-06-05', tag: '技术报告', img: IMG.tech5, url: 'https://mp.weixin.qq.com/s/example4' }
  ],
  news: [
    { id: 1, title: '深圳大鹏湾修复区珊瑚覆盖率达50%以上', date: '2026-07-10', tag: '生态修复', img: IMG.coral1 },
    { id: 2, title: '珊瑚2号杂交品系进入海区规模培育测试', date: '2026-06-28', tag: '技术突破', img: IMG.tech5 },
    { id: 3, title: '青少年珊瑚夏令营第43期圆满结束', date: '2026-06-15', tag: '科普活动', img: IMG.tech3 }
  ]
}

/* ================= 科普 ================= */
const knowledgeCategories = [
  { key: 'all', name: '全部' },
  { key: 'species', name: '珊瑚种类' },
  { key: 'ecosystem', name: '生态系统' },
  { key: 'bleaching', name: '白化危机' },
  { key: 'tech', name: '修复技术' },
  { key: 'camp', name: '珊瑚夏令营' }
]

const knowledgeItems = [
  {
    id: 0, category: 'species', title: '柔枝鹿角珊瑚', img: IMG.coral1,
    summary: '南海最常见的造礁珊瑚之一，分支状生长，是珊瑚礁生态系统的基石物种',
    paragraphs: [
      '柔枝鹿角珊瑚（Acropora valida）是南海最常见的造礁珊瑚之一，属于鹿角珊瑚科鹿角珊瑚属。',
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
      '• 数据层：南海珊瑚种质资源库，覆盖20种以上常见石珊瑚',
      '【核心指标】',
      '• 识别准确率：88%-96%',
      '• 珊瑚覆盖率量化准确率：85%-92%',
      '• 白化识别灵敏度：≥90%',
      '• 百平米监测报告生成时间：＜5分钟',
      '• 监测效率提升：30-50倍'
    ]
  },
  {
    id: 4, category: 'tech', title: '珊瑚礁修复实践', img: IMG.tech5,
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
      '短小鹿角珊瑚是南海本土优势品种，具有较好的耐高温特性。蓝珊科技通过将其与柔枝鹿角珊瑚进行种间定向杂交，成功选育出LT（柔枝×短小）等优势杂交品系。',
      '【杂交品系优势】',
      '• 可耐受+1℃高温环境',
      '• 可耐受pH↓1.18酸化环境',
      '• 胁迫环境下成活率与正常环境无显著差异',
      '• 两年生长长度超20厘米'
    ]
  },
  {
    id: 7, category: 'tech', title: '3D打印珊瑚底托', img: IMG.coral3,
    summary: '贝壳基免烧结3D打印工艺，仿生纹理结构提升附着成功率',
    paragraphs: [
      '贝壳基免烧结3D打印导流式底托是蓝珊科技自主研发的核心修复装备之一。',
      '以海洋固废贝壳粉为核心原料，采用免烧结DIW 3D打印工艺制备，兼具绿色低碳属性与功能优化双重优势。',
      '【技术特点】',
      '• 仿生纹理表面结构，提升珊瑚虫附着成功率',
      '• 双层导流孔道，形成上升流与微型涡流',
      '• 持续冲刷沉积物、输送营养物质',
      '• 支持岩礁打孔、钢钉固定、珊瑚胶泥三种定植方式',
      '• 适配南海多样海底底质环境',
      '该底托是珊瑚种苗从陆基到海区定植的核心载体，有效提升了珊瑚修复的成活率与稳定性。'
    ]
  }
]

const species = [
  { name: '鹿角珊瑚', latin: 'Acropora spp.', desc: '分枝状造礁珊瑚，南海最常见的珊瑚属，分支如鹿角般伸展', dist: 'Indo-Pacific、南海', img: IMG.coral1 },
  { name: '脑珊瑚', latin: 'Diploria spp.', desc: '球形或块状，表面沟回纹路如大脑，生长缓慢但寿命极长', dist: '全球热带海域', img: IMG.tech2 },
  { name: '蘑菇珊瑚', latin: 'Fungia spp.', desc: '单体型珊瑚，形如蘑菇，可自由移动，是少数能移动珊瑚', dist: '印度-太平洋', img: IMG.coral3 },
  { name: '软珊瑚', latin: 'Alcyonacea', desc: '无石灰质骨骼，柔软随水流摆动，色彩丰富形态优美', dist: '全球热带亚热带', img: IMG.coral2 },
  { name: '柳珊瑚', latin: 'Gorgonia spp.', desc: '扇形分枝如柳条，常见于海流较强区域，是海洋生物栖息地', dist: '南海、加勒比海', img: IMG.tech4 },
  { name: '笙珊瑚', latin: 'Tubipora musica', desc: '管状骨骼并联如笙管，鲜红或绿色，极具观赏价值', dist: '印度-太平洋', img: IMG.tech5 }
]

const allSpecies = species.concat([
  { name: '火珊瑚', latin: 'Millepora spp.', desc: '触手含刺细胞，触碰如火烧，是造礁珊瑚中唯一的水螅珊瑚', dist: '全球热带海域', img: IMG.coral1 },
  { name: '桌珊瑚', latin: 'Acropora hyacinthus', desc: '平板状展开如水中圆桌，是鹿角珊瑚属中形态最独特的品种', dist: '印度-太平洋', img: IMG.tech2 },
  { name: '玫瑰珊瑚', latin: 'Euphyllia spp.', desc: '花瓣状触手排列如玫瑰，色彩艳丽，是水族馆最受欢迎的品种', dist: '印度-太平洋', img: IMG.coral3 },
  { name: '柱珊瑚', latin: 'Porites spp.', desc: '圆柱形直立生长，生长极缓慢但寿命可达数百年，是礁石骨架主要构建者', dist: '全球热带海域', img: IMG.tech1 },
  { name: '气泡珊瑚', latin: 'Plerogyra sinuosa', desc: '表面布满气泡状共生藻，白天膨胀如葡萄串，是珊瑚礁中最独特的景观', dist: '印度-太平洋', img: IMG.tech5 },
  { name: '短小鹿角珊瑚', latin: 'Acropora humilis', desc: '蓝珊科技珊瑚2号杂交亲本之一，耐高温品种，可耐受+1℃高温', dist: '南海', img: IMG.coral2 }
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
    { label: '分布区域', value: '南海、印度洋-太平洋' },
    { label: '生长形态', value: '分枝状造礁珊瑚' },
    { label: '保护等级', value: '国家二级保护动物' },
    { label: '抗逆评级', value: '★★★★☆' },
    { label: '珊瑚2号亲本', value: '是（主要亲本）' }
  ],
  tags: [
    { text: '造礁珊瑚', type: '' },
    { text: '南海常见种', type: '' },
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
    desc: '购买一株珊瑚，蓝珊专业团队在南海修复区帮您种植和养护。通过AI监测系统远程查看珊瑚生长状态，定期收到成长报告。',
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
  { id: 'postcard', name: '海洋生态明信片套装', icon: '📮', price: 150, desc: '12张南海珊瑚实景明信片' },
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
      icon: '🌱', name: '成长营', price: '¥1,280/人', color: 'primary',
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
  subTitle: '蓝珊科技 · 南海珊瑚礁保护计划',
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
  intro: '蓝珊科技致力于南海珊瑚礁生态保护与修复，通过"良种培育+智能监测+生态恢复+公众参与"四位一体模式，守护南海珊瑚礁生态系统。',
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

module.exports = {
  IMG,
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
