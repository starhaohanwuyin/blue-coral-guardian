/**
 * 首页
 * 数据源：api.getHomeData()（Mock / 真实后端自动切换）
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')
const i18n = require('../../utils/i18n.js')
const app = getApp()

/* 快捷功能：中英各一份，切换语言时只换 name */
const ACTIONS = [
  { icon: '📷', name: 'AI识别', nameEn: 'AI scan', bg: 'rgba(30,136,229,0.1)', action: 'ai' },
  { icon: '🔬', name: '健康检测', nameEn: 'Health check', bg: 'rgba(0,188,212,0.1)', action: 'ai-health' },
  { icon: '📚', name: '珊瑚科普', nameEn: 'Learn', bg: 'rgba(255,112,67,0.1)', action: 'knowledge' },
  { icon: '🐠', name: '珊瑚认养', nameEn: 'Adopt', bg: 'rgba(171,71,188,0.1)', action: 'adopt' },
  { icon: '🏕', name: '夏令营', nameEn: 'Camp', bg: 'rgba(255,193,7,0.1)', action: 'camp' },
  { icon: '🐡', name: '水族箱', nameEn: 'Aquarium', bg: 'rgba(0,188,212,0.1)', action: 'aquarium' },
  { icon: '🏅', name: '我的勋章', nameEn: 'Badges', bg: 'rgba(255,112,67,0.1)', action: 'badges' },
  { icon: '📈', name: '成长档案', nameEn: 'Growth log', bg: 'rgba(76,175,80,0.1)', action: 'growth' }
]

/* 本页用到的文案 key（i18n.dict 会去掉 index. 前缀，wxml 里写 {{t.quick}}） */
const T_KEYS = [
  'index.brand', 'index.slogan', 'index.langBtn', 'index.heroTitle', 'index.heroDesc',
  'index.heroBtn', 'index.growth', 'index.carbonTitle', 'index.quick', 'index.mine',
  'index.mineMore', 'index.tech', 'index.video', 'index.videoHint', 'index.articles',
  'index.news', 'index.adoptedAt', 'index.growthPct'
]

Page({
  data: {
    statusBarHeight: 20,
    lang: 'zh',          // 当前语言（zh / en）
    langBtn: 'EN',       // 右上角按钮：显示「点了会切到哪种语言」
    t: {},               // 文案词典
    stats: [],
    energy: { cur: 0, max: 1000 },
    energyPercent: 0,
    carbon: {},
    corals: [],
    tech: [],
    climate: {},
    videoCaption: '',
    videoCover: '',
    videoUrl: '',
    canPlayVideo: false,      // 网页版可内嵌播放；小程序端显示封面 + 提示
    articles: [],
    news: [],
    actions: ACTIONS
  },

  onLoad() {
    this.setData({ statusBarHeight: (app.globalData && app.globalData.statusBarHeight) || 20 })
    // 只有网页版（web/mp.js 运行时挂了 window.MP_RUNTIME）才能内嵌播放本地视频
    this.setData({ canPlayVideo: typeof window !== 'undefined' && !!window.MP_RUNTIME })
    this.applyLang()
    this.load()
  },

  onShow() {
    // 从别的页面回来时语言可能变了（比如在设置里切的）→ 刷新本页文案
    if (i18n.getLang() !== this.data.lang) this.applyLang()
    if (this._raw) this.render()
    // 更新自定义 TabBar 选中态
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 0 })
      if (typeof this.getTabBar().build === 'function') this.getTabBar().build()
    }
  },

  /* ============ 中英切换 ============ */
  toggleLang() {
    const lang = i18n.toggle()
    this.applyLang()
    if (this._raw) this.render()
    // 小程序：刷新自定义 tabBar 文案
    if (typeof this.getTabBar === 'function' && this.getTabBar() &&
        typeof this.getTabBar().build === 'function') {
      this.getTabBar().build()
    }
    // 网页版：让运行时重画底部 tabBar
    if (typeof window !== 'undefined' && window.MP_RUNTIME &&
        typeof window.MP_RUNTIME.updateTabBar === 'function') {
      window.MP_RUNTIME.updateTabBar('index')
    }
    util.toast(lang === 'en' ? i18n.t('index.toastEn') : i18n.t('index.toastZh'))
  },

  /* 把词典灌进 data：t.quick / t.tech … 供 wxml 直接用 */
  applyLang() {
    const en = i18n.isEn()
    this.setData({
      lang: i18n.getLang(),
      langBtn: i18n.t('index.langBtn'),
      t: i18n.dict(T_KEYS),
      actions: ACTIONS.map((a) => Object.assign({}, a, {
        name: en ? (a.nameEn || a.name) : a.name
      }))
    })
  },

  onPullDownRefresh() {
    this.load(() => wx.stopPullDownRefresh())
  },

  load(cb) {
    api.getHomeData().then((d) => {
      this._raw = d
      this.render()
      cb && cb()
    }).catch((e) => {
      util.toast((e && e.message) || i18n.t('index.loadFail'))
      cb && cb()
    })
  },

  /* 按当前语言把原始数据映射成视图数据（英文缺项自动回落中文） */
  render() {
    const d = this._raw || {}
    const en = i18n.isEn()
    const e = d.en || {}
    const energy = d.energy || { cur: 0, max: 1000 }
    this.setData({
      stats: (d.stats || []).map((s, i) => ({
        num: s.num, label: en ? ((e.stats || [])[i] || s.label) : s.label
      })),
      energy,
      energyPercent: energy.max ? Math.round((energy.cur / energy.max) * 100) : 0,
      carbon: Object.assign({}, d.carbon || {}, {
        desc: en ? (e.carbon || (d.carbon || {}).desc) : (d.carbon || {}).desc
      }),
      corals: (d.corals || []).map((c, i) => {
        const x = en ? ((e.corals || [])[i] || {}) : {}
        return Object.assign({}, c, { name: x.name || c.name, species: x.species || c.species })
      }),
      tech: (d.tech || []).map((x, i) => {
        const y = en ? ((e.tech || [])[i] || {}) : {}
        return { img: x.img, label: y.label || x.label, title: y.title || x.title,
                 desc: y.desc || x.desc, tags: y.tags || x.tags }
      }),
      climate: mapClimate(d.climate, e.climate, en),
      videoCaption: en ? (e.videoCaption || d.videoCaption) : d.videoCaption,
      videoCover: d.videoCover || (d.tech && d.tech[2] && d.tech[2].img) || '',
      videoUrl: d.videoUrl || '',
      articles: (d.articles || []).map((a) => {
        const x = en ? ((e.articles || {})[a.id] || []) : []
        return Object.assign({}, a, { title: x[0] || a.title, tag: x[1] || a.tag })
      }),
      news: (d.news || []).map((a) => {
        const x = en ? ((e.news || {})[a.id] || []) : []
        return Object.assign({}, a, { title: x[0] || a.title, tag: x[1] || a.tag })
      })
    })
  },

  /* 快捷功能分发 */
  onAction(e) {
    const action = e.currentTarget.dataset.action
    switch (action) {
      case 'ai':
        wx.switchTab({ url: '/pages/ai/ai' })
        break
      case 'ai-health':
        // 健康检测 = AI页第二个标签，通过全局变量传递后由 ai 页 onShow 消费
        app.globalData.pendingAiTab = 1
        wx.switchTab({ url: '/pages/ai/ai' })
        break
      case 'knowledge':
        wx.switchTab({ url: '/pages/knowledge/knowledge' })
        break
      case 'adopt':
        wx.switchTab({ url: '/pages/adopt/adopt' })
        break
      case 'camp':
        wx.navigateTo({ url: '/pages/camp/camp' })
        break
      case 'aquarium':
        wx.navigateTo({ url: '/pages/aquarium/aquarium' })
        break
      case 'badges':
        wx.navigateTo({ url: '/pages/badges/badges' })
        break
      case 'growth':
        wx.navigateTo({ url: '/pages/growth/growth' })
        break
    }
  },

  /* 查看我的珊瑚（默认进入第一株详情） */
  goMyCoral() {
    const first = this.data.corals[0]
    wx.navigateTo({ url: '/pages/coral-detail/coral-detail?id=' + (first ? first.id : 1) })
  },

  goMyAdopt() {
    wx.navigateTo({ url: '/pages/my-adopt/my-adopt' })
  },

  goCoralDetail(e) {
    wx.navigateTo({ url: '/pages/coral-detail/coral-detail?id=' + e.currentTarget.dataset.id })
  },

  goArticle(e) {
    wx.navigateTo({ url: '/pages/article/article?id=' + e.currentTarget.dataset.id })
  },

  /* 最新动态（无外链的资讯，进入文章页展示） */
  goNews(e) {
    wx.navigateTo({ url: '/pages/article/article?news=1&id=' + e.currentTarget.dataset.id })
  },

  onVideoTap() {
    util.toast(i18n.t('index.videoMpOnly'))
  },

  onShareAppMessage() {
    return {
      title: i18n.pick('蓝珊 · 认养一株珊瑚，守护海洋',
                       'LanShan · Adopt a coral, guard the ocean'),
      path: '/pages/index/index'
    }
  }
})

/** 气候卡：英文时用 enData 的标题/副标题/标签/指标/说明，缺项自动回落中文 */
function mapClimate(zh, enData, en) {
  const c = zh || {}
  const e = enData || {}
  if (!en) {
    return Object.assign({}, c, {
      metrics: (c.metrics || []).map((m) => ({ value: m.value, label: m.label }))
    })
  }
  return {
    title: e.title || c.title,
    sub: e.sub || c.sub,
    tag: e.tag || c.tag,
    desc: e.desc || c.desc,
    metrics: (c.metrics || []).map((m, i) => ({
      value: m.value, label: (e.metrics || [])[i] || m.label
    }))
  }
}
