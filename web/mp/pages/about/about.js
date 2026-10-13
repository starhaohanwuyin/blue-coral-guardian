/**
 * 关于我们页
 * 公司简介 / 核心团队 / 联系方式
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')

Page({
  data: {
    info: { intro: '', rows: [] },
    team: [],
    teamIntro: '',
    email: util.SERVICE_EMAIL,
    version: util.VERSION
  },

  onLoad() {
    api.getAbout().then((data) => {
      this.setData({
        info: data.info || { intro: '', rows: [] },
        team: data.team || [],
        teamIntro: data.intro || ''
      })
    }).catch(() => {
      util.toast('加载失败，请重试')
    })
  },

  onCopyEmail() {
    util.copyText(this.data.email, '邮箱已复制')
  },

  onShareAppMessage() {
    return {
      title: '蓝珊科技 · 守护南海珊瑚 🪸',
      path: '/pages/index/index'
    }
  }
})
