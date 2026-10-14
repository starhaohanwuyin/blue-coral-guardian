/**
 * 实时海景页
 * Mock：静态监测图；真实后端：可替换为 live-img 接口或视频流封面轮询
 */
const util = require('../../utils/util.js')
const mock = require('../../utils/mock.js')

const pageI18n = require('../../utils/page-i18n.js')

Page(pageI18n.wrap({
  data: {
    d: null
  },

  onLoad() {
    this.setData({ d: mock.cameraData })
  },

  onRefresh() {
    wx.showLoading({ title: '刷新中...', mask: true })
    setTimeout(() => {
      wx.hideLoading()
      util.toast('画面已刷新')
    }, 800)
  },

  onShareAppMessage() {
    return {
      title: '蓝珊 · 海洋修复区实时海景',
      path: '/pages/index/index'
    }
  }
}))
