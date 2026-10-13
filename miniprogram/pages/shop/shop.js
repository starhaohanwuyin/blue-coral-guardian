/**
 * 积分商城页
 * 养料区（喂养虚拟珊瑚）+ 文创区（积分兑换周边）
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')

Page({
  data: {
    points: 0,
    shop: {},
    culture: {},
    tab: 'feed',
    feeds: [],
    cultureItems: []
  },

  onLoad() {
    // 商品列表走统一接口（Mock / 真实后端自动切换）
    api.getFeeds().then((feeds) => this.setData({ feeds: feeds || [] })).catch(() => {})
    api.getCultureItems().then((items) => this.setData({ cultureItems: items || [] })).catch(() => {})
  },

  onShow() {
    this.refresh()
  },

  refresh() {
    api.getVirtualState().then((s) => {
      this.setData({
        points: s.points,
        shop: s.shop || {},
        culture: s.culture || {}
      })
    }).catch(() => {})
  },

  switchTab(e) {
    this.setData({ tab: e.currentTarget.dataset.tab })
  },

  /* 购买养料 */
  onBuyFeed(e) {
    const key = e.currentTarget.dataset.key
    api.buyFeed(key).then((s) => {
      const feed = this.data.feeds.filter((f) => f.key === key)[0] || {}
      this.setData({ points: s.points, shop: s.shop || {} })
      util.toast('购买成功！获得 ' + (feed.icon || '') + ' ' + (feed.name || ''))
    }).catch((err) => util.toast(err.message))
  },

  /* 兑换文创 */
  onExchange(e) {
    const id = e.currentTarget.dataset.id
    api.exchangeCulture(id).then((s) => {
      const item = this.data.cultureItems.filter((c) => c.id === id)[0] || {}
      this.setData({ points: s.points, culture: s.culture || {} })
      util.toast('兑换成功！' + (item.icon || '') + ' ' + (item.name || ''))
    }).catch((err) => util.toast(err.message))
  }
})
