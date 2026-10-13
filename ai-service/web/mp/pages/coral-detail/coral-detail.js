/**
 * 珊瑚详情页
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')

Page({
  data: {
    d: null,
    deg: 0
  },

  onLoad(options) {
    const id = options.id || 1
    api.getCoralDetail(id).then((d) => {
      this.setData({
        d,
        deg: Math.round((d.growth / 100) * 360)
      })
      wx.setNavigationBarTitle({ title: d.name || '珊瑚详情' })
    }).catch((e) => util.toast(e.message || '加载失败'))
  },

  goCamera() {
    wx.navigateTo({ url: '/pages/camera/camera' })
  },

  goCert() {
    wx.navigateTo({ url: '/pages/cert/cert?type=entity' })
  },

  onShareAppMessage() {
    const d = this.data.d || {}
    return {
      title: '我的珊瑚 ' + (d.name || '') + ' 正在南海成长中',
      path: '/pages/index/index'
    }
  }
})
