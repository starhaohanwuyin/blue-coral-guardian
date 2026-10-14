/**
 * 自定义 tabBar：文案跟随中英切换（语言存本地 ls_lang）
 * 首页点「EN / 中文」后会调用本组件的 build() 立即刷新。
 */
const i18n = require('../utils/i18n.js')

Component({
  data: {
    selected: 0,
    list: []
  },
  lifetimes: {
    attached() { this.build() }
  },
  pageLifetimes: {
    show() { this.build() }          // 切页面回来时同步一次（语言可能在别处改了）
  },
  methods: {
    /* 按当前语言生成 tabBar 文案 */
    build() {
      this.setData({
        list: [
          { pagePath: 'pages/index/index', text: i18n.t('tab.home'), icon: 'home' },
          { pagePath: 'pages/adopt/adopt', text: i18n.t('tab.adopt'), icon: 'adopt' },
          { pagePath: 'pages/knowledge/knowledge', text: i18n.t('tab.knowledge'), icon: 'book' },
          { pagePath: 'pages/ai/ai', text: i18n.t('tab.ai'), icon: 'ai' },
          { pagePath: 'pages/profile/profile', text: i18n.t('tab.profile'), icon: 'user' }
        ]
      })
    },
    switchTab(e) {
      const path = e.currentTarget.dataset.path
      wx.switchTab({ url: '/' + path })
    }
  }
})
