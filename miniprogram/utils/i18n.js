/**
 * 中英文切换（轻量 i18n）
 * ------------------------------------------------------------------
 * · 语言存在本地（key: ls_lang，取值 zh / en），切换后在其它页面 onShow 时也会读到；
 * · 首页右上角是切换按钮，点一下在中文 / English 之间切；
 * · 文案都放在下面这个 DICT 里（zh / en 成对），后续要给其它页面做英文，往这里加 key 即可。
 */
const PH = require('./i18n-phrases.js')      // 中文 → 英文（整串精确匹配，构建器生成）
const LANG_KEY = 'ls_lang'

const DICT = {
  /* 顶部与首页各区块标题 */
  'index.brand': { zh: '蓝珊', en: 'LanShan' },
  'index.slogan': {
    zh: '守护海洋珊瑚 · 追踪海洋热压力',
    en: 'Guard the ocean corals · tracking marine heat stress'
  },
  'index.langBtn': { zh: 'EN', en: '中文' },   // 按钮上显示「点了会切到哪种语言」
  'index.heroTitle': { zh: '🌊 认养一株珊瑚', en: '🌊 Adopt a coral' },
  'index.heroDesc': {
    zh: '你认养的珊瑚正在海洋深处成长，通过AI智能监测系统实时追踪它的生长状态；我们同时跟踪海水热压力（DHW），为它挑选更安全的生长窗口。',
    en: 'Your coral is growing in the ocean. AI monitoring tracks its growth, and we follow marine heat stress (DHW) to pick a safer window for it.'
  },
  'index.heroBtn': { zh: '查看我的珊瑚 →', en: 'View my corals →' },
  'index.growth': { zh: '成长值', en: 'Growth' },
  'index.carbonTitle': { zh: '你的碳汇贡献：', en: 'Your carbon sink: ' },
  'index.quick': { zh: '快捷功能', en: 'Quick actions' },
  'index.mine': { zh: '我的珊瑚', en: 'My corals' },
  'index.mineMore': { zh: '查看全部', en: 'View all' },
  'index.tech': { zh: '核心技术', en: 'Core technologies' },
  'index.video': { zh: '团队视频', en: 'Team video' },
  'index.videoHint': { zh: '点击播放：珊瑚卫士', en: 'Tap to play: Coral Guardian' },
  'index.articles': { zh: '推文&资讯', en: 'Articles & news' },
  'index.news': { zh: '最新动态', en: "What's new" },
  'index.adoptedAt': { zh: '认养于', en: 'Adopted' },
  'index.growthPct': { zh: '成长', en: 'growth' },
  'index.videoSoon': { zh: '团队视频即将上线，敬请期待', en: 'Team video coming soon' },
  'index.videoMpOnly': {
    zh: '团队视频请在网页版打开（小程序端需先把视频放进包内或用网络地址）',
    en: 'Open the web version to watch the team video'
  },
  'index.loadFail': { zh: '加载失败', en: 'Failed to load' },
  'index.toastEn': { zh: 'Switched to English', en: 'Switched to English' },
  'index.toastZh': { zh: '已切换为中文', en: 'Switched to Chinese' },

  /* 科普页（knowledge） */
  'knowledge.brand': { zh: '📚 珊瑚科普', en: '📚 Coral guide' },
  'knowledge.sub': { zh: '探索珊瑚的奇妙世界', en: 'Exploring the world of corals' },
  'knowledge.heroSub': {
    zh: '认识海洋珊瑚 · 读懂白化与气候韧性',
    en: 'Ocean corals · bleaching & climate resilience'
  },
  'knowledge.speciesTitle': { zh: '珊瑚种类', en: 'Coral species' },
  'knowledge.viewAll': { zh: '查看全部', en: 'View all' },
  'knowledge.empty': { zh: '该分类暂无内容', en: 'No articles in this category yet' },

  /* 全部种类页（all-species） */
  'guide.intro': {
    zh: '海洋常见珊瑚图鉴 · AI可识别多种品种',
    en: 'Coral field guide · multiple taxa recognised by AI'
  },
  'guide.hot': { zh: '🔥 热门种类', en: '🔥 Featured species' },
  'guide.all': { zh: '📖 全部种类', en: '📖 All species' },

  /* 珊瑚种类详情页（coral-species） */
  'detail.basic': { zh: '✅ 基础档案', en: '✅ Basic profile' },
  'detail.morph': { zh: '✅ 形态识别', en: '✅ Morphology & ID' },
  'detail.habit': { zh: '✅ 生物习性', en: '✅ Biology & habits' },
  'detail.threat': { zh: '✅ 生存威胁', en: '✅ Threats' },
  'detail.back': { zh: '← 回到图鉴', en: '← Back to the guide' },
  'detail.quiz': { zh: '了解更多 · 知识问答', en: 'Learn more · knowledge quiz' },
  'detail.featured': { zh: '精选', en: 'Featured' },
  'detail.aiGenus': { zh: 'AI 可识别属', en: 'Recognised by AI' },
  'detail.levelGenus': { zh: '属级条目', en: 'Genus-level entry' },
  'detail.levelSpecies': { zh: '物种条目', en: 'Species entry' },
  'detail.bleachScale': {
    zh: '（判据：DHW≥4 进入白化警戒，≥8 为严重白化风险）',
    en: '(DHW≥4 = bleaching alert, ≥8 = severe risk)'
  },
  'detail.loading': { zh: '加载中…', en: 'Loading…' },
  'detail.missingId': { zh: '缺少种类 id', en: 'Missing species id' },
  'detail.notFound': { zh: '没有这个种类', en: 'Species not found' },
  'detail.loadFail': { zh: '加载失败', en: 'Failed to load' },

  /* 详情页字段名（在 coral-species.js 里用 t() 取，故键名可以带点） */
  'f.name': { zh: '中文名', en: 'Chinese name' },
  'f.alias': { zh: '别名', en: 'Common name' },
  'f.latin': { zh: '拉丁学名', en: 'Scientific name' },
  'f.taxonomy': { zh: '生物分类', en: 'Taxonomy' },
  'f.protection': { zh: '保护等级', en: 'Protection status' },
  'f.protectionNote': { zh: '保护等级说明', en: 'Note on protection' },
  'f.dist': { zh: '分布海域', en: 'Distribution' },
  'f.group': { zh: '类群', en: 'Group' },
  'f.genus': { zh: '属', en: 'Genus' },
  'f.colonyForm': { zh: '群落形态', en: 'Colony form' },
  'f.size': { zh: '成体尺寸', en: 'Adult size' },
  'f.color': { zh: '外观颜色', en: 'Colour' },
  'f.idFeature': { zh: '简易辨识特征', en: 'Key ID features' },
  'f.depth': { zh: '栖息水深', en: 'Depth range' },
  'f.tempSal': { zh: '适宜水温 / 盐度', en: 'Temperature / salinity' },
  'f.growth': { zh: '生长速度', en: 'Growth rate' },
  'f.symbiosis': { zh: '与虫黄藻共生特点', en: 'Zooxanthellae symbiosis' },
  'f.companions': { zh: '伴生生物', en: 'Associated organisms' },
  'f.feeding': { zh: '捕食方式', en: 'Feeding' },
  'f.bleaching': { zh: '白化敏感程度', en: 'Bleaching sensitivity' },
  'f.threats': { zh: '主要致危因素', en: 'Main threats' },
  'f.population': { zh: '野外种群现状', en: 'Wild population status' },

  /* 底部 tabBar（小程序用 custom-tab-bar；网页版在 web/mp.js 里按同一个表翻译） */
  'tab.home': { zh: '首页', en: 'Home' },
  'tab.adopt': { zh: '认养', en: 'Adopt' },
  'tab.knowledge': { zh: '科普', en: 'Learn' },
  'tab.ai': { zh: 'AI识别', en: 'AI scan' },
  'tab.profile': { zh: '我的', en: 'Me' }
}

function getLang() {
  try {
    return wx.getStorageSync(LANG_KEY) === 'en' ? 'en' : 'zh'
  } catch (e) {
    return 'zh'
  }
}

function setLang(lang) {
  const l = lang === 'en' ? 'en' : 'zh'
  try { wx.setStorageSync(LANG_KEY, l) } catch (e) {}
  return l
}

function isEn() { return getLang() === 'en' }

/** 中↔英切换，返回切换后的语言 */
function toggle() { return setLang(isEn() ? 'zh' : 'en') }

function t(key) {
  const d = DICT[key]
  if (!d) return key
  return isEn() ? d.en : d.zh
}

/** 一次取一批 key：dict(['index.quick','guide.hot']) → { quick: '…', hot: '…' }（去掉第一段前缀） */
function dict(keys) {
  const o = {}
  ;(keys || []).forEach((k) => { o[k.replace(/^[^.]+\./, '')] = t(k) })
  return o
}

/** 二选一：pick('中文', 'English') */
function pick(zh, en) { return isEn() ? (en || zh) : zh }

/** 单串翻译：英文时按短语表整串替换；查不到原样返回（所以 id / 数字 / 用户输入不会被误伤） */
function tr(s) {
  if (!isEn() || !s) return s
  const v = PH[s]
  return v === undefined ? s : v
}

/** 短语表的词条名：FNV-1a(UTF-16 码元) → base36，与 tools/i18n_build.py 的 key_for() 一致。
 *  WXML 里写 {{t.p<hash>}} 取的就是它（哈希命名 → 短语表增删不会让已有引用错位）。 */
function phKey(s) {
  let h = 0x811c9dc5
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return 'p' + h.toString(36)
}

let AUTO = {}
let AUTO_LANG = ''
function autoDict() {
  const lang = getLang()
  if (AUTO_LANG === lang) return AUTO
  const o = {}
  const en = lang === 'en'
  Object.keys(PH).forEach((zh) => { o[phKey(zh)] = en ? PH[zh] : zh })
  AUTO = o
  AUTO_LANG = lang
  return o
}

/** 某个页面作用域的词条：取 DICT 里以 `prefix.` 开头的键，去掉前缀。
 *
 * 为什么需要：all() 把 DICT 拍平成"尾段 key"，于是 `index.brand` 与 `knowledge.brand`
 * 都变成 `brand`，**后遍历到的覆盖前面的** —— 首页顶部曾因此显示科普页的品牌名「📚 珊瑚科普」。
 * 页面级 t 用本函数的结果覆盖 all()，就能各页各取自己的值。 */
function pageFlat(prefix) {
  if (!prefix) return {}
  const out = {}
  Object.keys(DICT).forEach((k) => {
    const dot = k.indexOf('.')
    if (dot > 0 && k.slice(0, dot) === prefix) out[k.slice(dot + 1)] = t(k)
  })
  return out
}

/** 整本词条（DICT 的尾段 key + 短语表词条）：页面 data.t 直接用它，不用维护 T_KEYS */
function all() {
  const lang = getLang()
  if (ALL_LANG === lang && ALL_CACHE) return ALL_CACHE
  const o = {}
  Object.keys(DICT).forEach((k) => { o[k.replace(/^[^.]+\./, '')] = t(k) })
  Object.assign(o, autoDict())
  ALL_CACHE = o
  ALL_LANG = lang
  return o
}
let ALL_CACHE = null
let ALL_LANG = ''

/* ================= 内容映射：图鉴条目 / 科普文章 =================
 * 英文文案在 mock.js 的 EN 块里（按 固定取值 / 形态码 / 条目 id 对应，不做模糊匹配）；
 * 任何一条缺英文就自动回落成中文，不会出现空白。
 */
function enBlock() {
  try { return require('./mock.js').EN || {} } catch (e) { return {} }
}

/** 图鉴条目 → 当前语言（英文缺项回落中文） */
function mapSpecies(it) {
  const src = it || {}
  if (!isEn()) return src
  const e = enBlock()
  const sp = (e.catalogSpecies || {})[src.id] || {}
  return Object.assign({}, src, {
    name: sp.name || src.name,
    desc: sp.desc || src.desc,
    dist: (e.catalogDist || {})[src.dist] || src.dist,
    group: (e.catalogGroups || {})[src.group] || src.group,
    levelCn: t(src.level === 'genus' ? 'detail.levelGenus' : 'detail.levelSpecies')
  })
}

function mapSpeciesList(list) { return (list || []).map(mapSpecies) }

/** 科普文章 → 当前语言 */
function mapKnowledgeItem(it) {
  const src = it || {}
  if (!isEn()) return src
  const x = ((enBlock().knowledge || {})[src.id] || [])
  return Object.assign({}, src, { title: x[0] || src.title, summary: x[1] || src.summary })
}

/** 科普分类 chip → 当前语言 */
function mapCategory(c) {
  const src = c || {}
  if (!isEn()) return src
  return Object.assign({}, src, {
    name: ((enBlock().knowledgeCategories || {})[src.key]) || src.name
  })
}

/** 白化敏感度：高/中/低 → High/Medium/Low */
function riskLabel(it) {
  const r = (it || {}).bleachingRisk || ''
  if (!r || !isEn()) return r
  return ((enBlock().catalogRisk || {})[r] || r)
}

/** 英文分类链：中文分类串里已含拉丁名，去掉中文标签再补上拉丁学名 */
function taxonomyEn(it) {
  const zh = ((it || {}).taxonomy) || ''
  const parts = zh.split('→').map((s) => s.replace(/[^\x00-\x7F]/g, '').trim()).filter(Boolean)
  const latin = (it || {}).latin || ''
  if (latin && parts.indexOf(latin) < 0) parts.push(latin)
  return parts.join(' → ')
}

/** 珊瑚种类详情页的四大板块（详情页直接用它，中文/英文都在这里生成） */
function coralDetailSections(it) {
  const src = it || {}
  const en = isEn()
  const e = enBlock()
  const s = mapSpecies(src)
  const form = (e.catalogForms || {})[src.form] || {}
  const rows = (pairs) => pairs.filter((p) => p[1]).map((p) => ({ k: p[0], v: String(p[1]) }))
  return [
    {
      icon: '✅',
      title: t('detail.basic'),
      rows: rows([
        [t('f.name'), src.name],
        [t('f.alias'), en ? (s.name + '\uff08' + (src.name || '') + '\uff09') : src.alias],
        [t('f.latin'), src.latin],
        [t('f.taxonomy'), en ? taxonomyEn(src) : src.taxonomy],
        [t('f.protection'),
          en ? ((e.catalogProtection || {})[src.protection] || src.protection) : src.protection],
        [t('f.protectionNote'),
          en ? (e.catalogProtectionNote || src.protectionNote) : src.protectionNote],
        [t('f.dist'), s.dist],
        [t('f.group'), s.group],
        [t('f.genus'), en ? src.genus : (src.genusCn ? src.genusCn + ' ' + src.genus : src.genus)]
      ])
    },
    {
      icon: '✅',
      title: t('detail.morph'),
      rows: rows([
        [t('f.colonyForm'),
          en ? ((form.form ? form.form + '; ' : '') + (s.desc || '')) : src.colonyForm],
        [t('f.size'), en ? (form.size || src.sizeCm) : src.sizeCm],
        [t('f.color'), en ? ((e.catalogColors || {})[src.form] || src.colorDesc) : src.colorDesc],
        [t('f.idFeature'), en ? (s.desc || src.idFeature) : src.idFeature]
      ])
    },
    {
      icon: '✅',
      title: t('detail.habit'),
      rows: rows([
        [t('f.depth'), en ? (form.depth || src.depthM) : src.depthM],
        [t('f.tempSal'), en ? (e.catalogTempSal || src.tempSal) : src.tempSal],
        [t('f.growth'), en ? (form.growth || src.growthRate) : src.growthRate],
        [t('f.symbiosis'), en ? (form.symb || src.symbiosis) : src.symbiosis],
        [t('f.companions'), en ? (form.mates || src.companions) : src.companions],
        [t('f.feeding'), en ? (form.feed || src.feeding) : src.feeding]
      ])
    },
    {
      icon: '✅',
      title: t('detail.threat'),
      rows: rows([
        [t('f.bleaching'),
          riskLabel(src) + (src.bleachingRisk ? (en ? ' ' : '') + t('detail.bleachScale') : '')],
        [t('f.threats'), en ? (form.threat || src.threats) : src.threats],
        [t('f.population'), en ? (form.pop || src.population) : src.population]
      ])
    }
  ]
}

module.exports = {
  LANG_KEY, DICT, getLang, setLang, isEn, toggle, t, dict, pick, tr, all, pageFlat, phKey,
  mapSpecies, mapSpeciesList, mapKnowledgeItem, mapCategory,
  riskLabel, taxonomyEn, coralDetailSections,
  /** 网页版 tabBar 用：中文标签 → 英文 */
  TAB_EN: { '首页': 'Home', '认养': 'Adopt', '科普': 'Learn', 'AI识别': 'AI scan', '我的': 'Me' }
}
