/**
 * 科普页
 * 种类横滑 + 分类筛选 + 科普文章网格
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')
const app = getApp()

Page({
  data: {
    statusBarHeight: 20,
    species: [],
    categories: [],
    filter: 'all',
    filteredItems: []
  },

  onLoad() {
    this.setData({ statusBarHeight: (app.globalData && app.globalData.statusBarHeight) || 20 })
    api.getKnowledgeList().then((d) => {
      this._items = d.items || []
      this.setData({
        categories: d.categories || [],
        filteredItems: this._items
      })
    }).catch((e) => util.toast((e && e.message) || '加载失败'))
    api.getAllSpecies().then((d) => this.setData({ species: d.hot || [] })).catch(() => {})
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 2 })
    }
    // 消费首页「健康检测」等入口传入的 Tab 状态
    const pending = app.globalData && app.globalData.pendingKnowledge
    if (pending !== undefined) delete app.globalData.pendingKnowledge
  },

  onFilter(e) {
    const key = e.currentTarget.dataset.key
    const filtered = key === 'all' ? this._items : (this._items || []).filter((it) => it.category === key)
    this.setData({ filter: key, filteredItems: filtered })
  },

  goAllSpecies() {
    wx.navigateTo({ url: '/pages/all-species/all-species' })
  },

  goDetail(e) {
    wx.navigateTo({ url: '/pages/knowledge-detail/knowledge-detail?id=' + e.currentTarget.dataset.id })
  },

  onShareAppMessage() {
    return {
      title: '蓝珊科普 · 探索珊瑚的奇妙世界',
      path: '/pages/knowledge/knowledge'
    }
  }
})
