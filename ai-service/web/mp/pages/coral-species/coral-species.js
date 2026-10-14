/**
 * 珊瑚种类详情页
 * 数据源：珊瑚图鉴数据库（GET /corals/{id}）
 * 四大板块：基础档案 / 形态识别 / 生物习性 / 生存威胁
 * 配图：条目自带 imgUrl（实拍照片）优先，否则用服务端按形态生成的专属示意图。
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')
const i18n = require('../../utils/i18n.js')

const T_KEYS = ['detail.back', 'detail.quiz', 'detail.featured', 'detail.aiGenus', 'detail.loading']

Page({
  data: {
    item: null,
    sections: [],
    imgFail: false,
    lang: 'zh',
    t: {}
  },

  onLoad(options) {
    this.applyLang()
    const id = (options && options.id) || ''
    if (!id) {
      util.toast(i18n.t('detail.missingId'))
      setTimeout(() => wx.navigateBack(), 800)
      return
    }
    api.getCoralDetail(id).then((raw) => {
      if (!raw) {
        util.toast(i18n.t('detail.notFound'))
        setTimeout(() => wx.navigateBack(), 800)
        return
      }
      this._raw = raw
      this.render()
    }).catch((e) => util.toast((e && e.message) || i18n.t('detail.loadFail')))
  },

  onShow() {
    // 语言可能在首页被切过
    if (i18n.getLang() !== this.data.lang) { this.applyLang(); this.render() }
  },

  applyLang() {
    this.setData({ lang: i18n.getLang(), t: i18n.dict(T_KEYS) })
  },

  /* 按当前语言生成详情（四大板块也在这里换语言） */
  render() {
    if (!this._raw) return
    const item = i18n.mapSpecies(this._raw)
    this.setData({ item, sections: i18n.coralDetailSections(this._raw) })
    wx.setNavigationBarTitle({ title: item.name || '' })
  },

  goAll() {
    wx.navigateTo({ url: '/pages/all-species/all-species' })
  },

  /* 配图加载失败 → 用渐变底代替，避免破图 */
  onHeroError() {
    this.setData({ imgFail: true })
  },

  goQuiz() {
    wx.navigateTo({ url: '/pages/quiz/quiz' })
  },

  onShareAppMessage() {
    const it = this.data.item || {}
    return {
      title: (it.name || '') + i18n.pick(' · 蓝珊珊瑚图鉴', ' · LanShan coral guide'),
      path: '/pages/coral-species/coral-species?id=' + (it.id || '')
    }
  }
})
