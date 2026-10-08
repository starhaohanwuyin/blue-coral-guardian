/**
 * 科普详情页
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')

Page({
  data: {
    item: null
  },

  onLoad(options) {
    api.getKnowledgeDetail(options.id).then((item) => {
      if (!item) {
        util.toast('内容不存在')
        setTimeout(() => wx.navigateBack(), 800)
        return
      }
      this.setData({ item })
      wx.setNavigationBarTitle({ title: item.title })
    }).catch((e) => util.toast(e.message || '加载失败'))
  },

  goQuiz() {
    wx.navigateTo({ url: '/pages/quiz/quiz' })
  },

  onShareAppMessage() {
    const item = this.data.item || {}
    return {
      title: '蓝珊科普 | ' + (item.title || '探索珊瑚世界'),
      path: '/pages/knowledge/knowledge'
    }
  }
})
