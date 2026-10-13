/**
 * 首页
 * 数据源：api.getHomeData()（Mock / 真实后端自动切换）
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')
const app = getApp()

Page({
  data: {
    statusBarHeight: 20,
    stats: [],
    energy: { cur: 0, max: 1000 },
    energyPercent: 0,
    carbon: {},
    corals: [],
    tech: [],
    teamIntro: '',
    team: [],
    videoCaption: '',
    videoCover: '',
    articles: [],
    news: [],
    actions: [
      { icon: '📷', name: 'AI识别', bg: 'rgba(30,136,229,0.1)', action: 'ai' },
      { icon: '🔬', name: '健康检测', bg: 'rgba(0,188,212,0.1)', action: 'ai-health' },
      { icon: '📚', name: '珊瑚科普', bg: 'rgba(255,112,67,0.1)', action: 'knowledge' },
      { icon: '🐠', name: '珊瑚认养', bg: 'rgba(171,71,188,0.1)', action: 'adopt' },
      { icon: '🏕', name: '夏令营', bg: 'rgba(255,193,7,0.1)', action: 'camp' },
      { icon: '🐡', name: '水族箱', bg: 'rgba(0,188,212,0.1)', action: 'aquarium' },
      { icon: '🏅', name: '我的勋章', bg: 'rgba(255,112,67,0.1)', action: 'badges' },
      { icon: '📈', name: '成长档案', bg: 'rgba(76,175,80,0.1)', action: 'growth' }
    ]
  },

  onLoad() {
    this.setData({ statusBarHeight: (app.globalData && app.globalData.statusBarHeight) || 20 })
    this.load()
  },

  onShow() {
    // 更新自定义 TabBar 选中态
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 0 })
    }
  },

  onPullDownRefresh() {
    this.load(() => wx.stopPullDownRefresh())
  },

  load(cb) {
    api.getHomeData().then((d) => {
      const energy = d.energy || { cur: 0, max: 1000 }
      this.setData({
        stats: d.stats || [],
        energy,
        energyPercent: energy.max ? Math.round((energy.cur / energy.max) * 100) : 0,
        carbon: d.carbon || {},
        corals: d.corals || [],
        tech: d.tech || [],
        teamIntro: d.teamIntro || '',
        team: d.team || [],
        videoCaption: d.videoCaption || '',
        videoCover: (d.tech && d.tech[2] && d.tech[2].img) || '',
        articles: d.articles || [],
        news: d.news || []
      })
      cb && cb()
    }).catch((e) => {
      util.toast((e && e.message) || '加载失败')
      cb && cb()
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

  goAbout() {
    wx.navigateTo({ url: '/pages/about/about' })
  },

  goArticle(e) {
    wx.navigateTo({ url: '/pages/article/article?id=' + e.currentTarget.dataset.id })
  },

  /* 最新动态（无外链的资讯，进入文章页展示） */
  goNews(e) {
    wx.navigateTo({ url: '/pages/article/article?news=1&id=' + e.currentTarget.dataset.id })
  },

  onVideoTap() {
    util.toast('团队视频即将上线，敬请期待')
  },

  onShareAppMessage() {
    return {
      title: '蓝珊 · 认养一株珊瑚，守护南海',
      path: '/pages/index/index'
    }
  }
})
