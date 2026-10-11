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
   * 由 Python FastAPI 提供：coral_ml/scripts/serve_fusion.py
   * 启动：cd coral_ml/scripts && python serve_fusion.py
   * 一次请求返回「礁区覆盖率 + 主要珊瑚属 + 底栖类别明细」。
   * 开发期指向本机即可（开发者工具 urlCheck 已关闭）；
   * 真机/发布需换成 HTTPS 已备案域名。
   */
  /* 评估服务地址（coral_ml/scripts/serve_fusion.py，监听 0.0.0.0:8000）
   * ⚠️ 真机（手机预览/调试）里 `127.0.0.1` 指的是**手机自己**，永远连不到电脑，
   *    表现就是识别页一直转圈且服务端日志里没有任何请求 —— 所以这里按运行环境自动选择。 */
  CORAL_API: (function pickCoralApi() {
    var DEVTOOLS = 'http://127.0.0.1:8000'
    var LAN = 'http://10.0.250.15:8000'   // 电脑局域网 IP；换网络后需同步修改
    try {
      var info = (typeof wx !== 'undefined' && wx.getDeviceInfo)
        ? wx.getDeviceInfo()
        : (typeof wx !== 'undefined' && wx.getSystemInfoSync ? wx.getSystemInfoSync() : null)
      // 开发者工具模拟器的 platform 为 'devtools'；真机为 'ios' / 'android'
      if (info && info.platform && info.platform !== 'devtools') return LAN
    } catch (e) {}
    return DEVTOOLS
  })(),

  // true  = 调用真实评估服务（需要 serve_fusion.py 在运行）
  // false = 直接使用本地演示数据
  USE_REAL_AI: true,

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

  /* 可选评估年份（最新在前）。
   * 后端档案现已覆盖 **1985–2025 共 41 年**（DHW / HotSpot / 官方 BAA 全部逐日），
   * 但 41 个年份全铺出来反而难选，所以给"最近 3 年 + 3 个有实地报告记载的白化事件年"：
   *   2024 = 第四次全球白化事件（沙巴热压力历史最高）
   *   2020 = 沙巴东部显著白化；2016 = 2014–2017 全球事件期内
   *   2010 = 马来西亚大规模白化事件（2024 之前的记录年）
   * 其它年份仍可通过接口查询（如 1998 / 1985）。
   * 数组第一项为默认；`DEFAULT_YEAR: null` 表示"跟着服务端最新年份走"。 */
  YEARS: [2025, 2024, 2023, 2020, 2016, 2010],

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

  VERSION: '2.2.0',

  // 客服邮箱
  SERVICE_EMAIL: 'service@bluecoral.cn'
}
