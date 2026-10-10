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

  // 评估年份（NOAA 数据可用：2023 / 2024 / 2025）
  DEFAULT_YEAR: 2024,

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

  VERSION: '2.0.0',

  // 客服邮箱
  SERVICE_EMAIL: 'service@bluecoral.cn'
}
