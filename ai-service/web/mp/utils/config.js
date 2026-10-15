/**
 * 全局配置
 * ------------------------------------------------------------------
 * 接入真实后端时只需改两处：
 *   1. BASE_URL  → 官网后端的 API 域名（须 HTTPS + 已备案，并加入小程序
 *                  后台「request 合法域名」，文件上传需加入「uploadFile 合法域名」）
 *   2. USE_MOCK  → false
 * 然后按 utils/api.js 顶部说明对齐接口路径即可，页面代码无需改动。
 * ------------------------------------------------------------------
 */
module.exports = {
  // TODO: 替换为官网现有后端 API 地址（同一域名同一端口，网页端/小程序端共用）
  BASE_URL: 'http://127.0.0.1:3000',

  // true = 本地演示模式（无需后端即可完整体验，数据存于本机 storage）
  // false = 调用真实后端
  USE_MOCK: true,

  /* ============ 礁区评估推理服务（AI 模块专用） ============
   * 由 Python FastAPI 提供：ai-service/scripts/serve_fusion.py
   * 启动：cd ai-service/scripts && python serve_fusion.py --host 0.0.0.0 --port 8000
   * 一次请求返回「礁区覆盖率 + 主要珊瑚属 + 底栖类别明细」。
   * 开发期指向本机即可（开发者工具 urlCheck 已关闭）；
   * 真机/发布需换成 HTTPS 已备案域名。
   */
  /* 评估服务地址候选表（按顺序探测，第一个 /health 通的就是它）
   *
   * 为什么不再靠 platform 判断：新版微信开发者工具里 `wx.getDeviceInfo().platform`
   * 返回的是 'windows'/'mac'（不再是 'devtools'），旧判断会把开发者工具误当成真机，
   * 于是用了写死的局域网 IP → 连不上 → 页面降级成"演示数据"。
   * 现在改为**运行时探测**：同源（网页版）→ 127.0.0.1（开发者工具）→ 局域网候选（真机）。
   * 换网络/换电脑后不用改代码：真机若都探测失败，可在小程序里覆盖（见 API_BASE_KEY）。
   */
  CORAL_API_CANDIDATES: (function buildCandidates() {
    var list = []
    // ① 用户手动覆盖（存 storage，优先级最高）
    try {
      var saved = wx.getStorageSync && wx.getStorageSync('coral_api_base')
      if (saved) list.push(String(saved).replace(/\/+$/, ''))
    } catch (e) {}
    // ② 网页版：与页面同源（服务同时托管网页与接口，永远正确）
    try {
      if (typeof location !== 'undefined' && location.origin &&
          location.origin.indexOf('http') === 0) {
        list.push(location.origin)
      }
    } catch (e) {}
    // ③ 开发者工具 / 本机浏览器
    list.push('http://127.0.0.1:8000')
    // ④ 真机：电脑局域网 IP 候选（换网络后把新 IP 加到这里，或在小程序里覆盖）
    //    ⚠️ 校园网/热点下的 IP 会变（本机已从 10.0.124.43 → 10.48.96.44 → 10.0.167.199 变过三次），
    //       所以这里保留多个候选，运行时逐个探测，第一个 /health 通的即为服务地址。
    //       真机若都探测失败：wx.setStorageSync('coral_api_base', 'http://新IP:8000') 覆盖即可。
    list.push('http://10.0.167.199:8000')  // 2026-10-15 本机 WLAN IP
    list.push('http://10.48.96.44:8000')   // 2026-10-14 本机 WLAN IP
    list.push('http://10.0.124.43:8000')   // 2026-10-13 本机 WLAN IP
    list.push('http://10.0.250.15:8000')   // 旧 IP（保留兼容）
    // 去重
    var out = []
    for (var i = 0; i < list.length; i++) if (list[i] && out.indexOf(list[i]) < 0) out.push(list[i])
    return out
  })(),

  /* 兼容旧代码：给出"最可能正确"的那个（网页版=同源 / 开发者工具=127.0.0.1）。
   * 真正的调用请走 utils/api.js 的 resolveApiBase()（会按候选表探测并缓存）。 */
  CORAL_API: (function pickCoralApi() {
    var c = module.exports.CORAL_API_CANDIDATES || []
    return c[0] || 'http://127.0.0.1:8000'
  })(),

  // true  = 调用真实评估服务（需要 serve_fusion.py 在运行）
  // false = 直接使用本地演示数据
  USE_REAL_AI: true,

  /* 珊瑚图鉴数据库（科普页「珊瑚种类」的数据源）
   * true  = 从评估服务的 /corals 读 SQLite 图鉴库（可上传/自行维护，见 /admin.html）
   * false = 用 utils/mock.js 里的静态数组（24 条，离线兜底）
   * 连不上服务时会自动退回 mock（受 FALLBACK_TO_MOCK 控制），页面不会空。
   */
  USE_CORAL_DB: true,

  /* 真实服务不可用时是否自动降级到演示数据
   * true  = 连不上服务时显示演示结果（带「演示数据」标记），页面不会卡在报错
   * false = 连不上就直接报错，并提示如何启动服务
   * 建议：开发者本地用 true（方便演示），正式联调用 false（暴露问题）
   */
  FALLBACK_TO_MOCK: true,

  /* 默认评估点位（用于查询环境数据 + 修复优先级研判）
   * NOAA CRW 5km 数据覆盖范围：4.0–5.0°N, 118.0–119.5°E（仙本那及周边）
   * 真机使用时可由定位获取，此处给仙本那核心区的默认值
   */
  DEFAULT_SITE: { lat: 4.4, lon: 118.8, name: '仙本那 · 核心礁区' },

  /* 可选点位（全部落在 NOAA 网格内）。环境背景会随所选点位变化 ——
   * 此前只有一个写死的点位，导致"每次识别的热压力结论都一样"。
   * 西侧点位历史风险高、东侧外海热压力友好，可用于演示对比。 */
  SITES: [
    { lat: 4.4, lon: 118.8, name: '仙本那 · 核心礁区' },
    { lat: 4.2, lon: 118.1, name: '西侧近岸（历史高危）' },
    { lat: 4.9, lon: 119.0, name: '东侧外海（热压力友好）' },
    { lat: 4.8, lon: 118.5, name: '北侧礁区' },
  ],

  /* NOAA CRW 网格覆盖范围（与后端 `coverageBBox` 一致）：用于"用我的位置"时的
   * 前置校验；网格外后端会返回 ok=false，这里提前给出提示更友好。 */
  GRID_BBOX: { latMin: 4.025, latMax: 5.025, lonMin: 118.025, lonMax: 119.525 },

  /* 评估年份（NOAA 数据可用：2023 / 2024 / 2025）
   * ⚠️ 设为 null = **不指定年份**，由服务端自动取**最新可用年份**（当前 2025）。
   *    原因：此前写死 2024，而 2024 是该点位 41 年里最热的 3 年之一
   *    （DHW 峰值 5.42，58 天 ≥4），导致"每次识别都是白化警报一级"、
   *    看起来像结论永远不变。改为最新年后同一格点为「白化警告」，
   *    且以后有新年份数据时会自动前进，无需改代码。
   *    若要固定某年做对比，把它改成具体年份（如 2024）即可。 */
  DEFAULT_YEAR: null,

  /* 快捷年份芯片 = **近五年**（最新在前）。
   * 更早的年份（含实地报告记载的白化事件年 2020 / 2016 / 2010，以及 1985 起的全部 41 年）
   * 走「其他年份 ▾」选择器。
   * 数组第一项为默认；`DEFAULT_YEAR: null` 表示"跟着服务端最新年份走"。 */
  YEARS: [2025, 2024, 2023, 2022, 2021],

  /* 全部可选年份（1985–2025，共 41 年，最新在前）—— 供「其他年份」选择器使用。
   * 后端档案覆盖 41 年（DHW / HotSpot / 官方 BAA 全部逐日），接口支持任意年份；
   * 首次识别后会再用服务端返回的 availableYears 覆盖这个列表（以实际数据为准）。
   * 注：1985 是产品首个不完整年（官方数据自 1985-03-31 起，当年 HotSpot 峰值 <1 → DHW 全年为 0）。 */
  ALL_YEARS: (function () {
    const a = []
    for (let y = 2025; y >= 1985; y--) a.push(y)
    return a
  })(),

  // 是否请求「环境数据 + 修复优先级」研判（需要服务端支持）
  USE_RESTORATION: true,

  // 识别超时（毫秒）。首次推理含模型预热，给宽松一些
  AI_TIMEOUT: 30000,

  /* 硬超时兜底（毫秒）：wx.uploadFile 的 timeout 在部分基础库/工具版本**不生效**，
   * 请求被域名校验拦下或网络黑洞时既不 success 也不 fail → 页面会永远停在「正在分析…」。
   * 到点强制给页面一个结果（超时错误；FALLBACK_TO_MOCK 为 true 时降级为演示数据并标注原因）。 */
  AI_HARD_TIMEOUT: 45000,

  // 本地存储键（token 与官网登录接口共用同一套账号体系）
  TOKEN_KEY: 'ls_token',
  USER_KEY: 'ls_user',

  VERSION: '2.2.5',

  // 客服邮箱
  SERVICE_EMAIL: 'service@bluecoral.cn',

  /* 客服电话（demo 里所有"联系客服/报名/下单咨询"统一走这里）
   * ⚠️ 正式版应改为后端下发，不要写死在客户端（公开仓库会被爬虫收集） */
  SERVICE_PHONE: '18936361581'
}
