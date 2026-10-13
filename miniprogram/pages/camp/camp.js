/**
 * 珊瑚夏令营页
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')

Page({
  data: {
    data: null
  },

  onLoad() {
    api.getCampInfo().then((data) => {
      this.setData({ data })
    }).catch(() => {
      util.toast('加载失败，请重试')
    })
  },

  onApply() {
    util.toast('已收到报名意向，工作人员将与您联系')
  },

  onShareAppMessage() {
    return {
      title: '珊瑚夏令营 · 和孩子一起亲手种珊瑚 🏕',
      path: '/pages/index/index'
    }
  }
})
