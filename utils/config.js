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

  // 本地存储键（token 与官网登录接口共用同一套账号体系）
  TOKEN_KEY: 'ls_token',
  USER_KEY: 'ls_user',

  VERSION: '2.0.0',

  // 客服邮箱
  SERVICE_EMAIL: 'service@bluecoral.cn'
}
