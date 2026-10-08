Component({
  data: {
    selected: 0,
    list: [
      { pagePath: 'pages/index/index', text: '首页', icon: 'home' },
      { pagePath: 'pages/adopt/adopt', text: '认养', icon: 'adopt' },
      { pagePath: 'pages/knowledge/knowledge', text: '科普', icon: 'book' },
      { pagePath: 'pages/ai/ai', text: 'AI识别', icon: 'ai' },
      { pagePath: 'pages/profile/profile', text: '我的', icon: 'user' }
    ]
  },
  methods: {
    switchTab(e) {
      const path = e.currentTarget.dataset.path
      wx.switchTab({ url: '/' + path })
    }
  }
})
