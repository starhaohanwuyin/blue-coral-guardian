/**
 * 登录页（账号体系核心）
 * ------------------------------------------------------------------
 * 与官网共用同一套账号：
 *  1. 账号密码登录 —— 直接调用官网登录接口，同一 token
 *  2. 微信一键登录 —— wx.login code 换 openid：
 *     · 已绑定官网账号 → 直接返回 token，数据天然同步
 *     · 未绑定 → 引导输入官网账号密码完成绑定（wxBind）
 * ------------------------------------------------------------------
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')
const config = require('../../utils/config.js')
const app = getApp()

Page({
  data: {
    mode: 'account', // account | wechat
    bindMode: false, // 微信未绑定，展示绑定表单
    username: '',
    password: '',
    agreed: false
  },

  onLoad(options) {
    if (options && options.mode === 'wechat') {
      this.setData({ mode: 'wechat' })
    }
  },

  switchMode(e) {
    this.setData({ mode: e.currentTarget.dataset.mode, bindMode: false })
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ [field]: e.detail.value })
  },

  toggleAgree() {
    this.setData({ agreed: !this.data.agreed })
  },

  /* 查看协议：type=agreement(用户协议) | privacy(隐私政策) */
  viewAgreement(e) {
    const type = e.currentTarget.dataset.type || 'agreement'
    wx.navigateTo({ url: '/pages/agreement/agreement?type=' + type })
  },

  checkAgree() {
    if (!this.data.agreed) {
      util.toast('请先阅读并同意用户协议与隐私政策')
      return false
    }
    return true
  },

  /* ============ 账号密码登录 ============ */
  onAccountLogin() {
    if (!this.checkAgree()) return
    const { username, password } = this.data
    if (!username || !password) {
      util.toast('请输入账号和密码')
      return
    }
    wx.showLoading({ title: '登录中...', mask: true })
    api.login({ username, password }).then((data) => {
      wx.hideLoading()
      this.loginSuccess(data)
    }).catch((e) => {
      wx.hideLoading()
      util.toast(e.message || '登录失败，请检查账号密码')
    })
  },

  /* ============ 微信一键登录 ============ */
  onWxLogin() {
    if (!this.checkAgree()) return
    wx.login({
      success: (res) => {
        if (!res.code) {
          util.toast('微信登录失败，请重试')
          return
        }
        this._wxCode = res.code
        wx.showLoading({ title: '验证中...', mask: true })
        api.wxLogin(res.code).then((data) => {
          wx.hideLoading()
          if (data && data.bound) {
            // 已绑定官网账号：直接登录
            this.loginSuccess(data)
          } else {
            // 未绑定：进入绑定流程
            this.setData({ bindMode: true, mode: 'wechat' })
            util.toast('请绑定官网账号以同步数据')
          }
        }).catch((e) => {
          wx.hideLoading()
          util.toast(e.message || '微信登录失败')
        })
      },
      fail: () => util.toast('微信登录失败，请重试')
    })
  },

  /* ============ 绑定官网账号 ============ */
  onBindSubmit() {
    const { username, password } = this.data
    if (!username || !password) {
      util.toast('请输入官网账号和密码')
      return
    }
    wx.showLoading({ title: '绑定中...', mask: true })
    api.wxBind({
      username,
      password,
      code: this._wxCode // 后端可用于复核 openid
    }).then((data) => {
      wx.hideLoading()
      this.loginSuccess(data)
    }).catch((e) => {
      wx.hideLoading()
      util.toast(e.message || '绑定失败，请检查账号密码')
    })
  },

  cancelBind() {
    this.setData({ bindMode: false })
  },

  /* ============ 登录成功：统一落地（mock / 真实后端一致） ============ */
  loginSuccess(data) {
    if (data && data.token) {
      wx.setStorageSync(config.TOKEN_KEY, data.token)
    }
    if (data && data.user) {
      wx.setStorageSync(config.USER_KEY, data.user)
      app.globalData.userInfo = data.user
    }
    util.toast('登录成功，数据已同步', 'success')
    setTimeout(() => {
      // 返回来源页；无来源页则进入首页
      const pages = getCurrentPages()
      if (pages.length > 1) {
        wx.navigateBack()
      } else {
        wx.switchTab({ url: '/pages/index/index' })
      }
    }, 800)
  }
})
