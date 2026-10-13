/**
 * 推文/资讯详情页
 * 参数：id=推文id（homeData.articles）；news=1&id=动态id（homeData.news）
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')

Page({
  data: {
    a: null
  },

  onLoad(options) {
    const id = Number(options.id || 0)
    const isNews = options.news === '1'
    api.getHomeData().then((d) => {
      const list = isNews ? (d.news || []) : (d.articles || [])
      const a = list.filter((x) => x.id === id)[0]
      if (!a) {
        util.toast('内容不存在')
        setTimeout(() => wx.navigateBack(), 800)
        return
      }
      this.setData({ a })
      wx.setNavigationBarTitle({ title: a.tag || '资讯详情' })
    }).catch((e) => util.toast(e.message || '加载失败'))
  },

  onCopyLink() {
    util.copyText(this.data.a.url, '原文链接已复制')
  },

  onShareAppMessage() {
    const a = this.data.a || {}
    return {
      title: a.title || '蓝珊资讯',
      path: '/pages/index/index'
    }
  }
})
