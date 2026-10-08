/**
 * 珊瑚成长档案页
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')

Page({
  data: {
    data: null
  },

  onLoad() {
    api.getGrowth().then((data) => {
      this.setData({ data })
    }).catch(() => {
      util.toast('加载失败，请重试')
    })
  },

  onShareAppMessage() {
    return {
      title: '我的珊瑚已长到14.5cm啦 📈 一起来见证成长',
      path: '/pages/index/index'
    }
  }
})
