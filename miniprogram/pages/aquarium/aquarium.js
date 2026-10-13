/**
 * 珊瑚水族箱页
 * - CSS 动画还原官网水族箱场景
 * - AI 健康诊断 + 跳转 AI 检测 / 实时相机
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')
const app = getApp()

Page({
  data: {
    data: null
  },

  onLoad() {
    api.getAquariumInfo().then((data) => {
      this.setData({ data })
    }).catch(() => {
      util.toast('加载失败，请重试')
    })
  },

  /* 前往 AI 检测（跨 Tab 传参，定位到健康监测 tab） */
  goAiDetect() {
    app.globalData.pendingAiTab = 1
    wx.switchTab({ url: '/pages/ai/ai' })
  },

  /* 实时相机 */
  goCamera() {
    wx.navigateTo({ url: '/pages/camera/camera' })
  },

  onChangeBg() {
    util.toast('水族箱背景更换功能即将上线')
  },

  onShareAppMessage() {
    return {
      title: '我的珊瑚水族箱 🐠 快来看看我的珊瑚',
      path: '/pages/index/index'
    }
  }
})
