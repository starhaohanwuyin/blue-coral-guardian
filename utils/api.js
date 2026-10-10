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

api.getCoralDetail = function (id) {
  if (config.USE_MOCK) {
    const d = Object.assign({}, mock.coralDetail)
    d.id = id
    const c = mock.myCorals.filter((x) => x.id === id)[0]
    if (c) {
      d.name = c.name
      d.species = c.species
      d.growth = c.growth
      d.img = c.img
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
  if (config.USE_MOCK) return mock.delay({ hot: mock.species, all: mock.allSpecies })
  return req.get(URL.allSpecies)
}

/* ================= AI 礁区评估（覆盖率 + 珊瑚属） ================= */

/**
 * 真实评估服务调用（Python FastAPI: coral_ml/scripts/serve_fusion.py）
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
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: config.CORAL_API + '/analyze',
      filePath,
      name: 'file',
      formData: fd,
      timeout: config.AI_TIMEOUT || 30000,
      header: {},
      success(res) {
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
      fail() {
        reject(new Error('无法连接评估服务，请确认已启动 serve_fusion.py'))
      }
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
    // 环境数据（演示值取自仙本那 2024 年 NOAA 实况）
    climate: {
      ok: true, year: 2024,
      gridCell: { lat: 4.425, lon: 118.775, distanceDeg: 0.035 },
      dhwMax: 5.42, baa: 2, baaLabel: '白化警告', riskScore: 0.5,
      daysDhwGe4: 58, daysDhwGe8: 0, peakDate: '2024-06-05',
      verdict: '中度热应激：已具备明显白化条件',
      typicalDhwMax: 2.19, anomalyVsOtherYears: 3.23,
      anomalyNote: '比其它年份平均高 +3.23（+148%）',
      source: 'NOAA CRW v3.1 5km via PacIOOS mirror',
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
    return realAnalyze(filePath, site, year).catch((e) => {
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

api.getCert = function (type) {
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
    return mock.delay(mock.certEntity)
  }
  return req.get(URL.cert, { type })
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
