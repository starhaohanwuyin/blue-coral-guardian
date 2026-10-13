/**
 * 我的认养页
 * 认养列表（进度/碳汇）+ AI 养护建议
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')

Page({
  data: {
    corals: [],
    loaded: false
  },

  onLoad() {
    this.fetchData()
  },

  onPullDownRefresh() {
    this.fetchData(() => {
      wx.stopPullDownRefresh()
    })
  },

  fetchData(cb) {
    api.getMyCorals().then((corals) => {
      this.setData({ corals: corals || [], loaded: true })
      if (typeof cb === 'function') cb()
    }).catch(() => {
      this.setData({ loaded: true })
      if (typeof cb === 'function') cb()
      util.toast('加载失败，请重试')
    })
  },

  /* 珊瑚详情 */
  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: '/pages/coral-detail/coral-detail?id=' + id })
  },

  /* 前往 AI 检测 */
  goAi() {
    wx.switchTab({ url: '/pages/ai/ai' })
  },

  onShareAppMessage() {
    return {
      title: '我在蓝珊认养了珊瑚，一起来守护南海珊瑚礁 🪸',
      path: '/pages/index/index'
    }
  }
})
