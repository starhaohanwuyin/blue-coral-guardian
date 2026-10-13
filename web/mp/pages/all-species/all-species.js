/**
 * 全部珊瑚种类页
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')

Page({
  data: {
    hot: [],
    all: []
  },

  onLoad() {
    api.getAllSpecies().then((d) => {
      this.setData({
        hot: d.hot || [],
        all: d.all || []
      })
    }).catch((e) => util.toast(e.message || '加载失败'))
  },

  onShareAppMessage() {
    return {
      title: '南海珊瑚图鉴 · 20+品种一次看全',
      path: '/pages/all-species/all-species'
    }
  }
})
