/**
 * 统一 API 层（小程序端与官网共用同一套后端接口）
 * ------------------------------------------------------------------
 * 接入真实后端步骤：
 *   1. utils/config.js 中将 BASE_URL 改为官网 API 域名，USE_MOCK 改为 false
 *   2. 按下方 URL 常量与官网实际接口路径逐一对齐（只改这一处，页面无需变动）
 *   3. 后端需为小程序补充的接口（计划 Task 2）：
 *      - POST /api/auth/wx-login   小程序 code 换 openid 并返回绑定信息
 *      - POST /api/auth/wx-bind    微信绑定已有账号（账号打通核心）
 *      - POST /api/order/create    小程序 JSAPI 支付下单（返回 wx.requestPayment 参数）
 *   4. 其余登录/认养/积分/科普/评论等接口直接复用官网现有接口
 * ------------------------------------------------------------------
 */
const config = require('./config.js')
const req = require('./request.js')
const mock = require('./mock.js')

/* 当前进行中的上传任务：硬超时触发时用它 abort，避免请求悬着不放 */
let pendingUploadTask = null

/* 后端接口路径（按官网实际接口调整这里） */
const URL = {
  authLogin: '/api/auth/login',
  authWxLogin: '/api/auth/wx-login',
  authWxBind: '/api/auth/wx-bind',
  authLogout: '/api/auth/logout',
  userProfile: '/api/user/profile',
  homeData: '/api/home',
  entityProducts: '/api/adopt/products',
  myCorals: '/api/adopt/my-corals',
  coralDetail: '/api/adopt/coral/',
  carbon: '/api/adopt/carbon',
  cert: '/api/adopt/certificate',
  virtualState: '/api/virtual/state',
  feeds: '/api/virtual/feeds',
  buyFeed: '/api/virtual/feed/buy',
  useFeed: '/api/virtual/feed/use',
  adoptNewCoral: '/api/virtual/coral/new',
  cultureItems: '/api/virtual/culture',
  exchangeCulture: '/api/virtual/culture/exchange',
  tasks: '/api/virtual/tasks',
  claimTask: '/api/virtual/tasks/claim',
  knowledgeList: '/api/knowledge/list',
  knowledgeDetail: '/api/knowledge/detail/',
  allSpecies: '/api/knowledge/species',
  aiRecognize: '/api/ai/recognize',
  aiHistory: '/api/ai/history',
  comments: '/api/community/comments',
  quizQuestions: '/api/quiz/questions',
  quizSubmit: '/api/quiz/submit',
  donateCreate: '/api/donate/create',
  orderCreate: '/api/order/create',
  campInfo: '/api/camp/info',
  aquariumInfo: '/api/aquarium/info',
  badges: '/api/user/badges',
  growth: '/api/user/growth',
  about: '/api/about'
}

const api = {}

/* ================= 登录鉴权（与官网同一账号体系） ================= */

/**
 * 账号密码登录（与官网完全同源：同一接口、同一 token）
 */
api.login = function (data) {
  if (config.USE_MOCK) {
    if (!data.username || !data.password) {
      return Promise.reject(new Error('请输入账号和密码'))
    }
    const user = {
      nickname: data.username,
      id: 'LS20260315',
      level: '珊瑚守护者 · Lv.2',
      stats: { corals: 3, growth: 128, badges: 5, learnHours: 12 }
    }
    mock.setMockUser(user)
    return mock.delay({ token: 'mock-token-' + Date.now(), user })
  }
  return req.post(URL.authLogin, data).then((data2) => {
    if (data2 && data2.token) req.setToken(data2.token)
    if (data2 && data2.user) wx.setStorageSync(config.USER_KEY, data2.user)
    return data2
  })
}

/**
 * 微信一键登录：
 * wx.login 获取 code → 后端 code2Session 换 openid →
 *  - 已绑定官网账号：直接返回 token（同一账号，数据天然同步）
 *  - 未绑定：返回 { bound: false }，由前端引导绑定/注册
 */
api.wxLogin = function (code) {
  if (config.USE_MOCK) {
    return mock.delay({ bound: false }) // mock：始终走「绑定」流程演示
  }
  return req.post(URL.authWxLogin, { code })
}

/**
 * 微信绑定已有官网账号（或以新账号注册并绑定）
 */
api.wxBind = function (data) {
  if (config.USE_MOCK) {
    if (!data.username || !data.password) {
      return Promise.reject(new Error('请输入账号和密码'))
    }
    const user = {
      nickname: data.username,
      id: 'LS20260315',
      level: '珊瑚守护者 · Lv.2',
      stats: { corals: 3, growth: 128, badges: 5, learnHours: 12 }
    }
    mock.setMockUser(user)
    return mock.delay({ token: 'mock-token-' + Date.now(), user })
  }
  return req.post(URL.authWxBind, data).then((data2) => {
    if (data2 && data2.token) req.setToken(data2.token)
    if (data2 && data2.user) wx.setStorageSync(config.USER_KEY, data2.user)
    return data2
  })
}

api.logout = function () {
  if (config.USE_MOCK) {
    // 退出登录 = 只清登录状态（真实产品语义：退出 ≠ 删数据）。
    // 想清空本机演示数据，个人页另有「清除演示数据」入口（mock.clearDemoData）。
    mock.clearMockUser()
    return Promise.resolve()
  }
  return req.post(URL.authLogout, {}).catch(() => {})
}

/* ================= 用户 ================= */

api.getUserProfile = function () {
  if (config.USE_MOCK) {
    const u = mock.getMockUser()
    if (u) return mock.delay(u)
    return mock.delay({
      nickname: '蓝珊守护者',
      id: 'LS20260315',
      level: '珊瑚守护者 · Lv.2',
      stats: { corals: 3, growth: 128, badges: 5, learnHours: 12 }
    })
  }
  return req.get(URL.userProfile)
}

/* ================= 首页 ================= */

api.getHomeData = function () {
  if (config.USE_MOCK) return mock.delay(mock.homeData)
  return req.get(URL.homeData)
}

/* ================= 实体认养 ================= */

api.getEntityProducts = function () {
  if (config.USE_MOCK) return mock.delay(mock.entityProducts)
  return req.get(URL.entityProducts)
}

api.getMyCorals = function () {
  if (config.USE_MOCK) return mock.delay(mock.myCorals)
  return req.get(URL.myCorals)
}

/* 「我的认养珊瑚」详情（含成长值/刻度环）。
 * ⚠️ 必须和「珊瑚种类详情」区分开：物种详情也叫 getCoralDetail（见下方，查图鉴库 /corals/{id}）。
 *    本文件里曾出现**两个 api.getCoralDetail 定义**，后定义的会覆盖前一个
 *    → 认养详情页取不到数据、一直停在「加载中…」（网页版与小程序都会中招）。
 *    故这里改名为 getAdoptCoralDetail，调用方 pages/coral-detail。 */
api.getAdoptCoralDetail = function (id) {
  if (config.USE_MOCK) {
    const d = Object.assign({}, mock.coralDetail)
    d.id = id
    // ⚠️ 页面传进来的是 data-id（DOM dataset 里是**字符串**），而 myCorals 的 id 是数字，
    //    以前用 `x.id === id` 严格比较永远为 false → 点哪一株都只显示默认的「蓝珊-001号」。
    const c = (mock.myCorals || []).filter((x) => String(x.id) === String(id))[0]
    if (c) {
      d.name = c.name
      d.species = c.species
      d.growth = c.growth
      d.img = c.img
      d.code = c.code || d.code
      d.carbon = c.carbon != null ? c.carbon : d.carbon
      d.remain = Math.round((100 - c.growth) * 5.4)
    }
    return mock.delay(d)
  }
  return req.get(URL.coralDetail + id)
}

api.getCarbon = function () {
  if (config.USE_MOCK) return mock.delay(mock.homeData.carbon)
  return req.get(URL.carbon)
}

/**
 * 实体认养下单
 * 真实后端：创建订单并返回 JSAPI 支付参数，前端调 wx.requestPayment
 */
api.createOrder = function (product) {
  if (config.USE_MOCK) {
    const orders = mock.getOrders()
    orders.unshift({
      id: 'MO' + Date.now(),
      product: product.title,
      amount: product.price,
      time: new Date().toLocaleString(),
      status: '已支付(演示)'
    })
    mock.saveOrders(orders)
    return mock.delay({ success: true, payParams: null }, 600)
  }
  return req.post(URL.orderCreate, { productId: product.id })
}

/* ================= 虚拟养成 ================= */

api.getVirtualState = function () {
  if (config.USE_MOCK) {
    const s = mock.getVirtualState()
    const growth = s.corals.length ? s.corals[s.corals.length - 1].growth : 0
    // 与网页版一致：第一株珊瑚未成熟前成长值取第一株
    const g = s.corals[0] ? s.corals[0].growth : 0
    return mock.delay({
      points: s.points,
      growth: s.corals.length > 1 && s.corals[0].growth >= 100 ? g : (s.corals[0] ? s.corals[0].growth : 0),
      shop: s.shop,
      corals: s.corals,
      culture: s.culture,
      tasksDone: s.tasksDone
    })
  }
  return req.get(URL.virtualState)
}

api.getFeeds = function () {
  if (config.USE_MOCK) return mock.delay(mock.feeds)
  return req.get(URL.feeds)
}

api.getCultureItems = function () {
  if (config.USE_MOCK) return mock.delay(mock.cultureItems)
  return req.get(URL.cultureItems)
}

function mockStateResult(state) {
  const g = state.corals[0] ? state.corals[0].growth : 0
  return {
    points: state.points,
    growth: g,
    shop: state.shop,
    corals: state.corals,
    culture: state.culture,
    tasksDone: state.tasksDone
  }
}

api.buyFeed = function (key) {
  if (config.USE_MOCK) {
    const state = mock.getVirtualState()
    const feed = mock.feeds.filter((f) => f.key === key)[0]
    if (!feed) return Promise.reject(new Error('养料不存在'))
    if (state.points < feed.price) return Promise.reject(new Error('积分不足！完成任务获取更多积分'))
    state.points -= feed.price
    state.shop[key] = (state.shop[key] || 0) + 1
    mock.saveVirtualState(state)
    return mock.delay(mockStateResult(state))
  }
  return req.post(URL.buyFeed, { key })
}

api.useFeed = function (key) {
  if (config.USE_MOCK) {
    const state = mock.getVirtualState()
    const feed = mock.feeds.filter((f) => f.key === key)[0]
    if (!feed || (state.shop[key] || 0) <= 0) return Promise.reject(new Error('该养料已用完'))
    const coral = state.corals[0]
    if (!coral || coral.growth >= 100) return Promise.reject(new Error('珊瑚已成熟'))
    state.shop[key]--
    coral.growth = Math.min(coral.growth + feed.growth, 100)
    coral.points += feed.price
    mock.saveVirtualState(state)
    return mock.delay(mockStateResult(state))
  }
  return req.post(URL.useFeed, { key })
}

api.adoptNewCoral = function () {
  if (config.USE_MOCK) {
    const state = mock.getVirtualState()
    const last = state.corals[state.corals.length - 1]
    if (last && last.growth < 100) {
      return Promise.reject(new Error('还有珊瑚未成长到100%，请继续培育~'))
    }
    const used = {}
    state.corals.forEach((c) => { used[c.name] = true })
    let newName = mock.coralNames[0]
    for (let i = 0; i < mock.coralNames.length; i++) {
      if (!used[mock.coralNames[i]]) { newName = mock.coralNames[i]; break }
    }
    state.corals.push({ name: newName, growth: 0, points: 0 })
    mock.saveVirtualState(state)
    return mock.delay(mockStateResult(state))
  }
  return req.post(URL.adoptNewCoral, {})
}

api.exchangeCulture = function (id) {
  if (config.USE_MOCK) {
    const state = mock.getVirtualState()
    const item = mock.cultureItems.filter((c) => c.id === id)[0]
    if (!item) return Promise.reject(new Error('商品不存在'))
    if (state.points < item.price) return Promise.reject(new Error('积分不足！完成任务获取更多积分'))
    state.points -= item.price
    state.culture[id] = (state.culture[id] || 0) + 1
    mock.saveVirtualState(state)
    return mock.delay(mockStateResult(state))
  }
  return req.post(URL.exchangeCulture, { id })
}

api.getTasks = function () {
  if (config.USE_MOCK) {
    const state = mock.getVirtualState()
    return mock.delay({
      list: mock.tasks.map((t) => Object.assign({}, t, { done: !!state.tasksDone[t.id] }))
    })
  }
  return req.get(URL.tasks)
}

/**
 * 领取任务奖励（每日任务在服务端按天重置；mock 模式存本地）
 */
api.claimTask = function (taskId) {
  if (config.USE_MOCK) {
    const state = mock.getVirtualState()
    if (state.tasksDone[taskId]) return Promise.reject(new Error('今日已完成该任务'))
    const task = mock.tasks.filter((t) => t.id === taskId)[0]
    if (!task) return Promise.reject(new Error('任务不存在'))
    state.tasksDone[taskId] = true
    state.points += task.points
    mock.saveVirtualState(state)
    return mock.delay({ points: state.points, reward: task.points })
  }
  return req.post(URL.claimTask, { taskId })
}

/* ================= 科普 ================= */

api.getKnowledgeList = function () {
  if (config.USE_MOCK) return mock.delay({ categories: mock.knowledgeCategories, items: mock.knowledgeItems })
  return req.get(URL.knowledgeList)
}

api.getKnowledgeDetail = function (id) {
  if (config.USE_MOCK) {
    const item = mock.knowledgeItems.filter((k) => k.id === Number(id))[0]
    return mock.delay(item)
  }
  return req.get(URL.knowledgeDetail + id)
}

api.getAllSpecies = function () {
  // 兼容旧调用：热门（精选）+ 第一页全部
  return api.getHotSpecies().then((hot) =>
    // limit 要大于图鉴条目总数，否则「全部珊瑚种类」会被人为截断（曾只有 60 条）
    api.getCoralCatalog({ limit: 500 }).then((page) => ({
      hot,
      all: page.items,
      total: page.total,
      fromDb: page.fromDb
    })))
}

/* ================= 珊瑚图鉴（SQLite 数据库） =================
 * 数据源：ai-service/scripts/coral_catalog.py（corals.db），后台页面 /admin.html
 * 页面读 GET /corals（搜索 + 属筛选 + 分页）、GET /corals/stats
 * 连不上服务时自动退回 utils/mock.js 的静态数组（24 条），页面不会空。
 */

let DB_BASE = ''          // 图鉴服务地址（拿到后把相对图片路径补成绝对地址）

function absImageUrl(u) {
  if (!u) return ''
  if (/^(https?:)?\/\//.test(u) || String(u).indexOf('data:') === 0) return u
  return (DB_BASE || '') + u
}

/** 把数据库条目转成页面用的字段（含配图解析 + 详情页四大板块字段） */
function mapSpecies(it) {
  return {
    id: it.id,
    name: it.name,
    latin: it.latin || '',
    desc: it.desc || '',
    dist: it.dist || '',
    /* 配图优先级：条目自带照片(imgUrl) > 原来的实物图(imgKey 映射到 mock.IMG) > 空（页面显示占位块）
       ⚠️ 这里不再回落到「生成的示意图」——图鉴配图只用实物图。 */
    img: it.imgUrl ? absImageUrl(it.imgUrl)
      : ((it.imgKey && mock.IMG && mock.IMG[it.imgKey]) || ''),
    imageUrl: it.imgUrl ? absImageUrl(it.imgUrl)
      : ((it.imgKey && mock.IMG && mock.IMG[it.imgKey]) || ''),
    imageNote: it.imageNote || '',
    genus: it.genus || '',
    genusCn: it.genusCn || '',
    family: it.family || '',
    level: it.level || 'species',
    levelCn: it.level === 'genus' ? '属级条目' : '物种条目',
    group: it.group || '',
    bleachingRisk: it.bleachingRisk || '',
    reefBuilding: !!it.reefBuilding,
    aiGenus: !!it.aiGenus,
    featured: !!it.featured,
    tags: it.tags || [],
    seq: it.seq || 0,          // 种子/上传顺序（页面按它排序，保持原来的展示顺序）
    // ---- 详情页四大板块 ----
    alias: it.alias || '',
    taxonomy: it.taxonomy || '',
    protection: it.protection || '',
    protectionNote: it.protectionNote || '',
    colonyForm: it.colonyForm || '',
    sizeCm: it.sizeCm || '',
    colorDesc: it.colorDesc || '',
    idFeature: it.idFeature || '',
    depthM: it.depthM || '',
    tempSal: it.tempSal || '',
    growthRate: it.growthRate || '',
    symbiosis: it.symbiosis || '',
    companions: it.companions || '',
    feeding: it.feeding || '',
    threats: it.threats || '',
    population: it.population || '',
    form: it.form || '',
    formCn: it.formCn || ''
  }
}

/** 本地兜底：把 mock 静态数组伪装成同口径的图鉴条目 */
function mockCatalog(q, genus) {
  const kw = String(q || '').trim().toLowerCase()
  let list = (mock.allSpecies || []).map((s, i) => mapSpecies({
    id: 'mock-' + i, name: s.name, latin: s.latin, desc: s.desc, dist: s.dist,
    imgKey: '', genus: String(s.latin || '').split(' ')[0], genusCn: '',
    level: 'species', group: '造礁石珊瑚', bleachingRisk: '', tags: []
  })).map((s, i) => Object.assign(s, {
    // 本地图保持原样（mock 条目自带 img）
    img: (mock.allSpecies[i] || {}).img || ''
  }))
  if (kw) {
    list = list.filter((s) => (s.name + s.latin + s.desc).toLowerCase().indexOf(kw) >= 0)
  }
  if (genus) list = list.filter((s) => s.genus === genus)
  return list
}

function catalogRequest(path, qs) {
  return api.resolveApiBase().then((base) => {
    if (!base) return Promise.reject(new Error('未发现图鉴服务'))
    DB_BASE = base
    return new Promise((resolve, reject) => {
      wx.request({
        url: base + path + (qs || ''),
        method: 'GET',
        timeout: 8000,
        header: apiTokenHeader(),
        success(res) {
          let d = res.data
          if (typeof d === 'string') { try { d = JSON.parse(d) } catch (e) { d = null } }
          // 三种返回形状都要认：列表 {items,total} / 统计 {total,...} / 单条 {item}
          // （以前少了 d.item → 详情页请求被判成失败，条件不满足时降到 mock 里也找不到该 id，
          //   结果就是「点进种类卡片看不到详情、直接被退回上一页」）
          if (res.statusCode === 200 && d &&
              (d.items || d.item || d.total !== undefined)) resolve(d)
          else reject(new Error('图鉴接口返回 ' + res.statusCode))
        },
        fail() { reject(new Error('图鉴服务不可用')) }
      })
    })
  })
}

/** 图鉴统计（总数/属数/科数/属清单） */
api.getCoralStats = function () {
  if (!config.USE_CORAL_DB) return Promise.resolve(mockCoralStats())
  return catalogRequest('/corals/stats').catch(() => {
    if (!config.FALLBACK_TO_MOCK) throw new Error('图鉴服务不可用，请先启动 serve_fusion.py')
    return mockCoralStats()
  })
}

function mockCoralStats() {
  const list = mockCatalog('', '')
  const genera = {}
  list.forEach((s) => { genera[s.genus] = (genera[s.genus] || 0) + 1 })
  return {
    total: list.length,
    genera: Object.keys(genera).length,
    families: 0,
    featured: Math.min(12, list.length),
    aiGenera: 0,
    fromDb: false,
    generaList: Object.keys(genera).map((g) => ({ genus: g, genusCn: '', count: genera[g] }))
  }
}

/** 图鉴列表：{q, genus, level, featured, limit, offset} → {items, total, fromDb} */
api.getCoralCatalog = function (opts) {
  const o = opts || {}
  const limit = o.limit || 50
  const offset = o.offset || 0
  if (!config.USE_CORAL_DB) {
    const list = mockCatalog(o.q, o.genus)
    return Promise.resolve({
      items: list.slice(offset, offset + limit), total: list.length, fromDb: false
    })
  }
  let qs = '/corals?limit=' + limit + '&offset=' + offset
  if (o.q) qs += '&q=' + encodeURIComponent(o.q)
  if (o.genus) qs += '&genus=' + encodeURIComponent(o.genus)
  if (o.level) qs += '&level=' + encodeURIComponent(o.level)
  if (o.featured) qs += '&featured=true'
  return catalogRequest(qs).then((d) => ({
    items: (d.items || []).map(mapSpecies).sort(bySeq),
    total: d.total || 0, fromDb: true
  })).catch((e) => {
    if (!config.FALLBACK_TO_MOCK) throw e
    const list = mockCatalog(o.q, o.genus)
    return { items: list.slice(offset, offset + limit), total: list.length, fromDb: false }
  })
}

/** 按 seq 排序（种子/上传顺序）；没有 seq 的排到最后，再按名称兜底 */
function bySeq(a, b) {
  // ⚠️ 不能写 (a.seq || 9999)：seq=0 会被当成假值排到最后
  const x = (a && a.seq != null) ? Number(a.seq) : 9999
  const y = (b && b.seq != null) ? Number(b.seq) : 9999
  if (x !== y) return x - y
  return String(a && a.name || '').localeCompare(String(b && b.name || ''))
}

/** 精选（科普页横滑 / 首页展示） */
api.getHotSpecies = function () {
  return api.getCoralCatalog({ featured: true, limit: 20 }).then((d) => {
    if (d.items.length) return d.items
    return api.getCoralCatalog({ limit: 12 }).then((p) => p.items)
  })
}

/** 单条详情（详情页用）：GET /corals/{id}；连不上服务时退回本地演示数据 */
api.getCoralDetail = function (id) {
  if (!id) return Promise.resolve(null)
  if (!config.USE_CORAL_DB) return Promise.resolve(mockDetail(id))
  return catalogRequest('/corals/' + encodeURIComponent(id)).then((d) => {
    if (!d || !d.item) throw new Error('没有这个种类')
    return mapSpecies(d.item)
  }).catch((e) => {
    if (!config.FALLBACK_TO_MOCK) throw e
    return mockDetail(id)
  })
}

function mockDetail(id) {
  const hit = mockCatalog('', '').filter((s) => s.id === id)[0]
  if (!hit) return null
  hit.imageNote = '离线演示数据（未连接图鉴服务，字段不完整）'
  hit.idFeature = hit.desc
  hit.protectionNote = '连接服务后可查看完整档案（protect/形态/习性/威胁）'
  return hit
}

/* ================= AI 礁区评估（覆盖率 + 珊瑚属） ================= */

/* ============ 评估服务地址探测 ============
 * 为什么不写死地址：新版微信开发者工具 `wx.getDeviceInfo().platform` 返回 'windows'/'mac'
 * （不再是 'devtools'），靠它判断环境会把开发者工具误当真机，于是用了写死的局域网 IP → 连不上。
 * 现在按 config.CORAL_API_CANDIDATES 顺序探测 /health，第一个通的即为服务地址，
 * 并缓存到 storage（换网络后自动重新探测；也可手动覆盖 coral_api_base）。
 */
let API_BASE = ''
let API_PROBE = null

/* 与服务端共享的访问令牌：服务端设了 CORAL_API_TOKEN 的部署，写接口与推理接口需要带上。
 * 取值优先级：config.CORAL_API_TOKEN > storage('coral_api_token')；都没有就不带（默认部署行为）。*/
function apiTokenHeader() {
  try {
    const t = (config.CORAL_API_TOKEN || '') ||
      ((typeof wx !== 'undefined' && wx.getStorageSync) ? wx.getStorageSync('coral_api_token') : '')
    return t ? { 'X-API-Token': String(t) } : {}
  } catch (e) { return {} }
}

function probeHealth(base, timeout) {
  return new Promise((resolve) => {
    wx.request({
      url: base + '/health',
      method: 'GET',
      timeout: timeout || 2500,
      success(res) {
        let ok = false
        try {
          const d = typeof res.data === 'string' ? JSON.parse(res.data) : res.data
          ok = !!(d && d.status === 'ok')
        } catch (e) {}
        resolve(ok ? base : '')
      },
      fail() { resolve('') },
    })
  })
}

api.resolveApiBase = function () {
  if (API_BASE) return Promise.resolve(API_BASE)
  if (API_PROBE) return API_PROBE
  const cands = (config.CORAL_API_CANDIDATES && config.CORAL_API_CANDIDATES.slice()) ||
                [config.CORAL_API]
  API_PROBE = new Promise((resolve) => {
    let i = 0
    const next = () => {
      if (i >= cands.length) { resolve(''); return }
      const base = cands[i++]
      probeHealth(base).then((good) => {
        if (good) {
          API_BASE = good
          try { wx.setStorageSync('coral_api_base', good) } catch (e) {}
          console.log('[coral] 评估服务: ' + good)
          resolve(good)
        } else {
          next()
        }
      })
    }
    next()
  }).then((r) => { API_PROBE = null; return r })
  return API_PROBE
}

/**
 * 真实评估服务调用（Python FastAPI: ai-service/scripts/serve_fusion.py）
 * POST /analyze 一次返回：
 *   cover       活珊瑚/白化/死亡/藻类/沙砾 百分比 + 珊瑚总覆盖
 *   topClasses  主要底栖类别明细
 *   coralRegion 从分割掩膜裁剪珊瑚主体后做的属分类（未训练时为空）
 */
function realAnalyze(filePath, site, year) {
  // site = {lat, lon}；给了就请求「气候背景 + 修复优先级」研判
  const fd = {}
  if (config.USE_RESTORATION && site && site.lat != null && site.lon != null) {
    fd.lat = String(site.lat)
    fd.lon = String(site.lon)
    if (year != null) fd.year = String(year)
  }
  const cands = (config.CORAL_API_CANDIDATES || [config.CORAL_API])
  return api.resolveApiBase().then((base) => {
    if (!base) {
      throw new Error('无法连接评估服务：已尝试 ' + cands.join('、')
        + '，均无响应。/health 都不通说明服务没启动，或地址不对。'
        + '请先启动：cd ai-service/scripts && python serve_fusion.py --host 0.0.0.0 --port 8000')
    }
    return new Promise((resolve, reject) => {
      // ⚠️ 记录上传任务：`wx.uploadFile` 的 timeout 在部分基础库/开发者工具版本**不生效**，
      //    当请求被域名校验拦下或网络黑洞时，success/fail 都不会回调，
      //    页面就会永远停在「正在分析珊瑚影像…」。故由外层硬超时兜底并 abort。
      pendingUploadTask = wx.uploadFile({
        url: base + '/analyze',
        filePath,
        name: 'file',
        formData: fd,
        timeout: config.AI_TIMEOUT || 30000,
        header: apiTokenHeader(),
        success(res) {
          pendingUploadTask = null
          if (res.statusCode !== 200) {
            let detail = ''
            try { detail = JSON.parse(res.data).detail || '' } catch (e) {}
            reject(new Error(detail || ('识别服务异常(' + res.statusCode + ')')))
            return
          }
          try {
            const body = JSON.parse(res.data)
            if (body && body.success) resolve(body)
            else reject(new Error((body && body.detail) || '识别失败'))
          } catch (e) {
            reject(new Error('识别结果解析失败'))
          }
        },
        fail(err) {
          pendingUploadTask = null
          const msg = (err && err.errMsg) || ''
          // 连接失败说明缓存的地址可能已失效（换了网络）→ 清掉，下次重新探测
          API_BASE = ''
          try { wx.removeStorageSync('coral_api_base') } catch (e) {}
          reject(new Error('无法连接评估服务（' + base + '，' + msg + '）。'
            + '已尝试：' + cands.join('、')
            + '。请确认服务已启动：cd ai-service/scripts && python serve_fusion.py --host 0.0.0.0 --port 8000'
            + '；开发者工具需勾选「不校验合法域名」'))
        }
      })
    })
  })
}

/* 无服务时的演示数据（结构真实接口一致） */
function mockCoralResult() {
  return {
    success: true,
    cover: {
      alivePct: 0.3966, bleachedPct: 0.0312, deadPct: 0.0205,
      algaePct: 0.1000, substratePct: 0.3983, seagrassPct: 0.0,
      coralTotalPct: 0.4483, bleachingShareOfCoral: 0.0696
    },
    topClasses: [
      { name: 'massive/meandering alive', pct: 0.2143 },
      { name: 'unknown hard substrate', pct: 0.1822 },
      { name: 'sand', pct: 0.1611 },
      { name: 'algae covered substrate', pct: 0.1000 },
      { name: 'branching alive', pct: 0.0921 }
    ],
    coralRegion: {
      regionBox: [120, 88, 420, 376],
      coralPixelRatio: 0.4483,
      reliable: true,
      top: [
        { genus: 'Acropora', confidence: 0.7821 },
        { genus: 'Pocillopora', confidence: 0.1102 },
        { genus: 'Porites', confidence: 0.0431 }
      ]
    },
    captureQuality: {
      level: 'good',
      usable: true,
      contrast: 0.2279,
      rgRatio: 0.655,
      message: '拍摄条件良好，评估结果可信'
    },
    bleaching: {
      model: 'bleaching_all',
      label: 'bleached', labelCn: '白化',
      confidence: 0.9612, reliable: true,
      probabilities: { bleached: 0.9612, dead: 0.0210, healthy: 0.0178 },
      top: [
        { label: 'bleached', labelCn: '白化', confidence: 0.9612 },
        { label: 'dead', labelCn: '死亡', confidence: 0.0210 },
        { label: 'healthy', labelCn: '健康', confidence: 0.0178 }
      ]
    },
    disclaimer: '本结果由AI模型给出，仅供保育决策参考；建议拍摄深度 ≤10m。本项目仅用于学术研究与竞赛，非商业用途。',
      inferenceMs: 812,
    // 环境数据（演示值取自仙本那核心格点 2025 年 NOAA 实况，与"默认取最新年"一致）
    climate: {
      ok: true, year: 2025,
      gridCell: { lat: 4.425, lon: 118.775, distanceDeg: 0.035 },
      dhwMax: 2.69, baa: 2, baaLabel: '白化警告', riskScore: 0.5,
      daysDhwGe4: 0, daysDhwGe8: 0, peakDate: '2025-05-27',
      verdict: '轻度热应激：需持续关注',
      typicalDhwMax: 3.55, anomalyVsOtherYears: -0.86,
      anomalyNote: '比其它年份平均高 -0.86（-24%）',
      source: 'NOAA CRW v3.1 5km via PacIOOS mirror',
    },
    // 投放时间窗档案（41 年历史；演示值取自本项目实算结果）
    deployment: {
      ok: true, nYears: 41,
      gridCell: { lat: 4.425, lon: 118.775, distanceDeg: 0.035 },
      label: '41 年中 3 年达白化警戒（7%）',
      riskLevel: 'medium',
      alertYears: ['2016', '2020', '2024'], severeYears: [],
      avoidMonths: [4, 5, 6, 7], safeMonths: [1, 2, 3, 8, 9, 10, 11, 12],
    },
    // 综合研判（演示值）
    restoration: {
      ok: true, priority: 52.3, grade: 'medium', gradeLabel: '三级 · 可观察',
      seedlingSuitability: 49.9,
      recovery: { score: 68.3, components: { coralStock: 100, structure: 100, lowAlgae: 70, diversity: 50, lowThermal: 50 } },
      urgency: { score: 32.8, components: { bleaching: 20, mortality: 10, thermal: 50 } },
      bleachRatioOfCoral: 0.0696,
      reasoning: '恢复潜力 68 分，主要由 coralStock、structure 贡献；紧迫度 33 分。',
      actions: ['**建议苗圃暂养**：热压力为「白化警告」，场地本身条件尚可，待本季热浪结束、确认无二次白化后投放'],
      disclaimer: '本结果为基于规则的决策支持参考，非经验证的预测模型，不提供准确率指标，不替代专业珊瑚礁评估。',
      report: '【礁区保育研判报告】（演示数据）\n\n本报告由规则型决策支持启发式自动生成，仅供人工决策参考。',
    },
    isDemo: true,
  }
}

/**
 * 上传水下影像并做礁区评估
 * @param filePath 本地临时文件路径
 * @returns {Promise<{cover, topClasses, coralRegion, captureQuality, disclaimer}>}
 *
 * 降级策略：USE_REAL_AI 为 true 但服务连不上时，
 * 若 FALLBACK_TO_MOCK 为 true，则返回演示数据并标记 `isDemo`，
 * 便于无服务环境下演示（页面会显示「演示数据」标记，不会冒充真实结果）。
 */
api.recognize = function (filePath, site, year) {
  if (config.USE_REAL_AI) {
    // 硬超时兜底：即便 wx.uploadFile 既不 success 也不 fail，也必须在 N 秒后给页面一个结果，
    // 否则页面会永远停在 loading（本会话实测到的现象）。
    const hard = new Promise((_, reject) => {
      setTimeout(() => {
        if (pendingUploadTask && pendingUploadTask.abort) {
          try { pendingUploadTask.abort() } catch (e) {}
          pendingUploadTask = null
        }
        reject(new Error('识别请求超时未返回（' + (API_BASE || config.CORAL_API) + '）。排查顺序：'
          + '①服务是否在跑（浏览器打开 http://127.0.0.1:8000/health）；'
          + '②开发者工具「详情→本地设置」勾选「不校验合法域名」；'
          + '③真机调试：手机与电脑连同一 Wi-Fi，地址候选见 utils/config.js 的 CANDIDATES'
          + '（也可用 wx.setStorageSync("coral_api_base", "http://电脑IP:8000") 手动指定）'))
      }, config.AI_HARD_TIMEOUT || 45000)
    })
    return Promise.race([realAnalyze(filePath, site, year), hard]).catch((e) => {
      if (!config.FALLBACK_TO_MOCK) throw e
      return mock.delay(mockCoralResult(), 700).then((r) => {
        r.isDemo = true
        r.demoReason = (e && e.message) || '评估服务不可用'
        return r
      })
    })
  }
  if (config.USE_MOCK) return mock.delay(mockCoralResult(), 1600)
  return req.upload(URL.aiRecognize, filePath, 'file', {})
}

api.getAiHistory = function () {
  if (config.USE_MOCK) return mock.delay(mock.aiHistory)
  return req.get(URL.aiHistory)
}

/* ================= 社区评论 ================= */

api.getComments = function () {
  if (config.USE_MOCK) return mock.delay(mock.getComments())
  return req.get(URL.comments)
}

api.addComment = function (text) {
  if (config.USE_MOCK) {
    const list = mock.getComments()
    const user = mock.getMockUser()
    list.unshift({
      id: Date.now(),
      avatar: '🌟',
      name: (user && user.nickname) || '我',
      time: '刚刚',
      text,
      mine: true
    })
    mock.saveComments(list)
    return mock.delay(list)
  }
  return req.post(URL.comments, { text })
}

api.deleteComment = function (id) {
  if (config.USE_MOCK) {
    const list = mock.getComments().filter((c) => c.id !== id)
    mock.saveComments(list)
    return mock.delay(list)
  }
  return req.post(URL.comments + '/delete', { id })
}

/* ================= 问答 / 捐赠 ================= */

api.getQuizQuestions = function () {
  if (config.USE_MOCK) return mock.delay(mock.quizQuestions)
  return req.get(URL.quizQuestions)
}

api.submitQuiz = function (score, total) {
  if (config.USE_MOCK) return mock.delay({ ok: true })
  return req.post(URL.quizSubmit, { score, total })
}

api.createDonation = function (amount) {
  if (config.USE_MOCK) {
    const orders = mock.getOrders()
    orders.unshift({
      id: 'DN' + Date.now(),
      product: '公益捐赠',
      amount,
      time: new Date().toLocaleString(),
      status: '已捐赠(演示)'
    })
    mock.saveOrders(orders)
    return mock.delay({ success: true }, 500)
  }
  // 真实后端：若捐赠需真实支付，可在此返回支付参数走 wx.requestPayment
  return req.post(URL.donateCreate, { amount })
}

/* ================= 证书 ================= */

api.getCert = function (type, id) {
  if (config.USE_MOCK) {
    if (type === 'virtual') {
      const cert = Object.assign({}, mock.certVirtual)
      const state = mock.getVirtualState()
      const c = state.corals[0] || { name: '鹿角珊珊', growth: 0, points: 0 }
      cert.fields[1].value = c.name
      cert.fields.splice(2, 0, { label: '成长进度', value: Math.min(c.growth, 100) + '%' })
      cert.fields.push({ label: '累计积分', value: '⭐ ' + state.points })
      return mock.delay(cert)
    }
    /* 实体证书：按 id 取「这一株」的信息（品种 / 编号 / 日期 / 照片），
       否则会出现「点 002 号证书里却写着柔枝鹿角珊瑚」这种对不上的情况 */
    const cert = JSON.parse(JSON.stringify(mock.certEntity))
    const list = mock.myCorals || []
    const c = list.filter((x) => String(x.id) === String(id))[0] || list[0]
    if (c) {
      const home = ((mock.homeData && mock.homeData.corals) || [])
        .filter((x) => x.name === c.name)[0]
      cert.img = c.img
      cert.fields = [
        { label: '认养者', value: (cert.fields[0] && cert.fields[0].value) || '蓝珊守护者' },
        { label: '珊瑚品种', value: c.species },
        { label: '珊瑚编号', value: c.code },
        { label: '认养日期', value: (home && home.date) || '' },
        // 坐标与海域跟着这一株走（写在 myCorals 数据里，不再写死在证书逻辑里）
        { label: 'GPS坐标', value: c.gps || '' },
        { label: '修复海域', value: c.site || '' }
      ].filter((f) => f.value)
    }
    return mock.delay(cert)
  }
  return req.get(URL.cert, { type, id })
}

/* ================= 其他模块 ================= */

api.getCampInfo = function () {
  if (config.USE_MOCK) return mock.delay(mock.campData)
  return req.get(URL.campInfo)
}

api.getAquariumInfo = function () {
  if (config.USE_MOCK) return mock.delay(mock.aquariumData)
  return req.get(URL.aquariumInfo)
}

api.getBadges = function () {
  if (config.USE_MOCK) return mock.delay({ badges: mock.badges, levels: mock.badgeLevels })
  return req.get(URL.badges)
}

api.getGrowth = function () {
  if (config.USE_MOCK) return mock.delay(mock.growthData)
  return req.get(URL.growth)
}

api.getAbout = function () {
  if (config.USE_MOCK) {
    return mock.delay({
      info: mock.aboutInfo,
      team: mock.homeData.teamDetail,
      intro: mock.homeData.teamIntro
    })
  }
  return req.get(URL.about)
}

module.exports = api
