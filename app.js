// 蓝珊小程序 - 应用入口
const config = require('./utils/config.js')
const mock = require('./utils/mock.js')

App({
  globalData: {
    statusBarHeight: 20,
    userInfo: null,      // 当前登录用户（与官网同一账号体系）
    systemInfo: null
  },

  onLaunch() {
    // 获取系统信息（自定义导航栏需要状态栏高度）
    try {
      const win = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync()
      this.globalData.statusBarHeight = win.statusBarHeight || 20
    } catch (e) {
      this.globalData.statusBarHeight = 20
    }

    // 恢复登录态：
    // - 联调真实后端时：本地存有 token 即视为已登录（如需校验可在此调用 api.user.getProfile()）
    // - Mock 模式：恢复本地 mock 用户
    const token = wx.getStorageSync(config.TOKEN_KEY)
    if (token) {
      this.globalData.userInfo = wx.getStorageSync(config.USER_KEY) || null
    } else if (config.USE_MOCK) {
      const u = mock.getMockUser()
      if (u) this.globalData.userInfo = u
    }
  },

  // 全局：判断是否已登录（未登录时业务接口调用会被引导去登录页）
  isLoggedIn() {
    return !!(this.globalData.userInfo || wx.getStorageSync(config.TOKEN_KEY))
  },

  // 统一登出（小程序与网站共用同一 token 体系，登出仅清除本地凭证）
  logout() {
    wx.removeStorageSync(config.TOKEN_KEY)
    wx.removeStorageSync(config.USER_KEY)
    this.globalData.userInfo = null
    if (config.USE_MOCK) mock.clearMockUser()
  }
})
