/**
 * 实时海景页
 * Mock：静态监测图；真实后端：可替换为 live-img 接口或视频流封面轮询
 */
const util = require('../../utils/util.js')
const mock = require('../../utils/mock.js')

Page({
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
      title: '蓝珊 · 南海修复区实时海景',
      path: '/pages/index/index'
    }
  }
})
