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

const pageI18n = require('../../utils/page-i18n.js')

Page(pageI18n.wrap({
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
    videoCaption: '',
    videoCover: '/assets/video/team-cover.jpg',
    videoPoster: '',
    videoUrl: '',
    videoError: false,
    videoStarted: false,
    articles: [],
    news: [],
    actions: ACTIONS
  },

  onLoad() {
    this.setData({ statusBarHeight: (app.globalData && app.globalData.statusBarHeight) || 20 })
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
      videoCaption: en ? (e.videoCaption || d.videoCaption) : d.videoCaption,
      videoCover: d.videoCover || (d.tech && d.tech[2] && d.tech[2].img) || '',
      articles: (d.articles || []).map((a) => {
        const x = en ? ((e.articles || {})[a.id] || []) : []
        return Object.assign({}, a, { title: x[0] || a.title, tag: x[1] || a.tag })
      }),
      news: (d.news || []).map((a) => {
        const x = en ? ((e.news || {})[a.id] || []) : []
        return Object.assign({}, a, { title: x[0] || a.title, tag: x[1] || a.tag })
      })
    })
    this.resolveVideo(d.videoUrl, d.videoCover)
  },

  /* 团队视频：网页版由同源静态目录提供，小程序端改走服务绝对地址。
   * 12MB 原片不适合塞进 2MB 主包，因此不再依赖包内 /assets/video/team.mp4。 */
  resolveVideo(path, coverPath) {
    this._videoFallbackTried = false
    if (!path) {
      this.setData({ videoUrl: '', videoError: true })
      return
    }
    const cover = coverPath || this.data.videoCover || ''
    Promise.all([
      api.resolveMediaUrl(path),
      cover ? api.resolveMediaUrl(cover) : Promise.resolve('')
    ]).then((pair) => {
      const url = pair[0] || ''
      const poster = pair[1] || ''
      this.setData({ videoUrl: url, videoPoster: poster, videoError: !url })
    }).catch(() => {
      this.setData({ videoUrl: '', videoError: true })
    })
  },

  onVideoError() {
    // 少数开发者工具/基础库对 http 流媒体的处理不稳定：
    // 先尝试把视频下载成临时文件再交给 <video> 播放，仍失败才显示降级提示。
    if (this._videoFallbackTried || !this.data.videoUrl) {
      this.setData({ videoError: true })
      return
    }
    this._videoFallbackTried = true
    util.toast('视频直连失败，正在改用本地缓存播放…')
    wx.downloadFile({
      url: this.data.videoUrl,
      success: (res) => {
        if (res.statusCode === 200 && res.tempFilePath) {
          this.setData({ videoUrl: res.tempFilePath, videoError: false })
        } else {
          this.setData({ videoError: true })
        }
      },
      fail: () => this.setData({ videoError: true })
    })
  },

  onVideoReady() {
    if (this.data.videoError) this.setData({ videoError: false })
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
    // 先显示与网页版一致的封面；用户点击后再切到原生视频并自动播放。
    // 这样不会被 <video> 的黑色初始画面盖住，也不依赖 poster 对包内图片的兼容性。
    if (this.data.videoUrl && !this.data.videoError) {
      this.setData({ videoStarted: true })
      return
    }
    if (!this.data.videoError) {
      util.toast('视频正在加载，请稍候')
      return
    }
    wx.showModal({
      title: '视频服务暂不可用',
      content: '团队视频和 AI 识别共用同一个后端服务。真机上 127.0.0.1 指向手机自己，'
        + '不能访问电脑上的服务。\n\n调试可填电脑局域网地址；正式体验需使用公网 HTTPS 域名。',
      confirmText: '设置地址',
      cancelText: '稍后再试',
      success: (res) => {
        if (!res.confirm) return
        util.configureApiBase((r) => {
          if (r && r.ok) this.resolveVideo(this._raw && this._raw.videoUrl)
        })
      }
    })
  },

  onShareAppMessage() {
    return {
      title: i18n.pick('蓝珊 · 认养一株珊瑚，守护海洋',
                       'LanShan · Adopt a coral, guard the ocean'),
      path: '/pages/index/index'
    }
  }
}))

