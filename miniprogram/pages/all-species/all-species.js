/**
 * 全部珊瑚种类页
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')
const i18n = require('../../utils/i18n.js')

const T_KEYS = ['guide.intro', 'guide.hot', 'guide.all']

const pageI18n = require('../../utils/page-i18n.js')

Page(pageI18n.wrap({
  data: {
    lang: 'zh',
    t: {},
    hot: [],
    all: [],
    fromDb: true,
    total: 0,
    fullTotal: 225,
    loading: false
  },

  onLoad() {
    this.applyLang()
    this.load()
  },

  load() {
    if (this.data.loading) return
    this.setData({ loading: true })
    api.getAllSpecies().then((d) => {
      this._raw = d
      this.setData({ fromDb: !!d.fromDb, total: d.total || (d.all || []).length })
      this.render()
    }).catch((e) => {
      this.setData({ fromDb: false })
      util.toast(e.message || i18n.pick('加载失败', 'Failed to load'))
    }).then(() => this.setData({ loading: false }))
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

  onRetry() {
    this.load()
  },

  /* 网络实拍图加载失败时收掉 <image>，露出底下的珊瑚占位块，避免整张破图 */
  onImgError(e) {
    const id = e.currentTarget.dataset.id
    const clear = (arr) => (arr || []).map((x) => String(x.id) === String(id)
      ? Object.assign({}, x, { img: '' }) : x)
    this.setData({ hot: clear(this.data.hot), all: clear(this.data.all) })
  },

  /* 点条目 → 珊瑚种类详情页 */
  onSpecies(e) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.navigateTo({ url: '/pages/coral-species/coral-species?id=' + encodeURIComponent(id) })
  },

  onShareAppMessage() {
    return {
      title: i18n.pick('海洋珊瑚图鉴 · 多种品种一次看全',
                       'Ocean coral field guide · multiple taxa'),
      path: '/pages/all-species/all-species'
    }
  }
}))
