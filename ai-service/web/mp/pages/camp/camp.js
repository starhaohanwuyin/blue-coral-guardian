/**
 * 珊瑚夏令营页
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')

const pageI18n = require('../../utils/page-i18n.js')

Page(pageI18n.wrap({
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
    // Demo：不留报名表单，直接给联系电话
    wx.showModal({
      title: '报名下期夏令营',
      content: '请拨打号码 18936361581 与工作人员进行联系',
      showCancel: false,
      confirmText: '知道了',
      confirmColor: '#1E88E5'
    })
  },

  onShareAppMessage() {
    return {
      title: '珊瑚夏令营 · 和孩子一起亲手种珊瑚 🏕',
      path: '/pages/index/index'
    }
  }
}))
