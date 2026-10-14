/**
 * 全部珊瑚种类页
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')
const i18n = require('../../utils/i18n.js')

const T_KEYS = ['guide.intro', 'guide.hot', 'guide.all']

Page({
  data: {
    lang: 'zh',
    t: {},
    hot: [],
    all: []
  },

  onLoad() {
    this.applyLang()
    api.getAllSpecies().then((d) => {
      this._raw = d
      this.render()
    }).catch((e) => util.toast(e.message || i18n.pick('加载失败', 'Failed to load')))
  },

  onShow() {
    // 语言可能在首页被切过 → 回到本页时刷新
    if (i18n.getLang() !== this.data.lang) { this.applyLang(); this.render() }
  },

  /* ============ 中英切换 ============ */
  applyLang() {
    this.setData({ lang: i18n.getLang(), t: i18n.dict(T_KEYS) })
  },

  render() {
    const d = this._raw || {}
    this.setData({
      hot: i18n.mapSpeciesList(d.hot || []),
      all: i18n.mapSpeciesList(d.all || [])
    })
  },

  /* 点条目 → 珊瑚种类详情页 */
  onSpecies(e) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.navigateTo({ url: '/pages/coral-species/coral-species?id=' + encodeURIComponent(id) })
  },

  onShareAppMessage() {
    return {
      title: i18n.pick('海洋珊瑚图鉴 · 20+ 品种一次看全',
                       'Ocean coral field guide · 20+ taxa'),
      path: '/pages/all-species/all-species'
    }
  }
})
