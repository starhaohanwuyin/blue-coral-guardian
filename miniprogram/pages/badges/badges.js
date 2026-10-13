/**
 * 我的勋章页
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')

Page({
  data: {
    badges: [],
    levels: []
  },

  onLoad() {
    api.getBadges().then((data) => {
      this.setData({
        badges: data.badges || [],
        levels: data.levels || []
      })
    }).catch(() => {
      util.toast('加载失败，请重试')
    })
  },

  onShareAppMessage() {
    return {
      title: '我在蓝珊获得了勋章，一起来守护珊瑚礁吧 🏅',
      path: '/pages/index/index'
    }
  }
})
