/**
 * 科普页
 * 种类横滑 + 分类筛选 + 科普文章网格
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')
const i18n = require('../../utils/i18n.js')
const app = getApp()

const T_KEYS = ['knowledge.brand', 'knowledge.sub', 'knowledge.heroSub',
  'knowledge.speciesTitle', 'knowledge.viewAll', 'knowledge.empty']

const pageI18n = require('../../utils/page-i18n.js')

Page(pageI18n.wrap({
  data: {
    statusBarHeight: 20,
    lang: 'zh',
    t: {},
    species: [],
    categories: [],
    filter: 'all',
    filteredItems: []
  },

  onLoad() {
    this.setData({ statusBarHeight: (app.globalData && app.globalData.statusBarHeight) || 20 })
    this.applyLang()
    api.getKnowledgeList().then((d) => {
      this._items = d.items || []
      this._cats = d.categories || []
      this.render()
    }).catch((e) => util.toast((e && e.message) || i18n.pick('加载失败', 'Failed to load')))
    api.getAllSpecies().then((d) => { this._species = d.hot || []; this.render() }).catch(() => {})
  },

  onShow() {
    // 语言可能在首页被切过 → 回到本页时刷新文案
    if (i18n.getLang() !== this.data.lang) { this.applyLang(); this.render() }
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 2 })
      if (typeof this.getTabBar().build === 'function') this.getTabBar().build()
    }
    // 消费首页「健康检测」等入口传入的 Tab 状态
    const pending = app.globalData && app.globalData.pendingKnowledge
    if (pending !== undefined) delete app.globalData.pendingKnowledge
  },

  /* ============ 中英切换 ============ */
  applyLang() {
    this.setData({ lang: i18n.getLang(), t: i18n.dict(T_KEYS) })
  },

  /* 按当前语言生成视图数据（英文缺项自动回落中文） */
  render() {
    const items = (this._items || []).map((it) => i18n.mapKnowledgeItem(it))
    const key = this.data.filter
    this.setData({
      categories: (this._cats || []).map((c) => i18n.mapCategory(c)),
      species: this._species ? i18n.mapSpeciesList(this._species) : this.data.species,
      filteredItems: key === 'all' ? items : items.filter((it) => it.category === key)
    })
  },

  onFilter(e) {
    const key = e.currentTarget.dataset.key
    this.setData({ filter: key })
    this.render()
  },

  goAllSpecies() {
    wx.navigateTo({ url: '/pages/all-species/all-species' })
  },

  /* 点种类卡 → 珊瑚种类详情页（拿不到 id 时退回全部种类页） */
  goSpecies(e) {
    const id = e.currentTarget.dataset.id
    if (!id) return this.goAllSpecies()
    wx.navigateTo({ url: '/pages/coral-species/coral-species?id=' + encodeURIComponent(id) })
  },

  goDetail(e) {
    wx.navigateTo({ url: '/pages/knowledge-detail/knowledge-detail?id=' + e.currentTarget.dataset.id })
  },

  onShareAppMessage() {
    return {
      title: i18n.t('knowledge.brand') + ' · ' + i18n.t('knowledge.sub'),
      path: '/pages/knowledge/knowledge'
    }
  }
}))
