/**
 * 我的页
 * 登录态展示 + 服务菜单 + 珊瑚社区评论
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')
const app = getApp()

Page({
  data: {
    statusBarHeight: 20,
    user: null,
    commentText: '',
    comments: [],
    menuGroups: [
      {
        title: '我的服务',
        items: [
          { icon: '🪸', bg: 'linear-gradient(135deg,rgba(30,136,229,0.12),rgba(0,188,212,0.08))', label: '我的认养', desc: '查看珊瑚生长状态与养护建议', badge: '3', url: '/pages/my-adopt/my-adopt' },
          { icon: '🐠', bg: 'linear-gradient(135deg,rgba(0,188,212,0.12),rgba(30,136,229,0.08))', label: '珊瑚水族箱', desc: 'AI拍照识别 · 虚拟水族箱', url: '/pages/aquarium/aquarium' },
          { icon: '🏕', bg: 'linear-gradient(135deg,rgba(255,112,67,0.12),rgba(255,152,0,0.08))', label: '珊瑚夏令营', desc: '成长营 · 专业营 · 领袖营', badge: '热', badgeCls: 'green', url: '/pages/camp/camp' }
        ]
      },
      {
        title: '学习成长',
        items: [
          { icon: '📈', bg: 'linear-gradient(135deg,rgba(76,175,80,0.12),rgba(139,195,74,0.08))', label: '珊瑚成长档案', desc: '记录珊瑚成长轨迹与数据', url: '/pages/growth/growth' },
          { icon: '🏅', bg: 'linear-gradient(135deg,rgba(255,193,7,0.12),rgba(255,152,0,0.08))', label: '我的勋章', desc: '已收集 5/12 枚勋章', url: '/pages/badges/badges' },
          { icon: '📚', bg: 'linear-gradient(135deg,rgba(33,150,243,0.12),rgba(3,169,244,0.08))', label: '科普课堂', desc: '已学习 12 课时 · 继续学习', url: 'switchTab:/pages/knowledge/knowledge' }
        ]
      },
      {
        title: '更多',
        items: [
          { icon: '💬', bg: 'linear-gradient(135deg,rgba(156,39,176,0.12),rgba(186,104,200,0.08))', label: '联系客服', desc: '在线咨询 · 工作日 9:00-18:00', contact: true },
          { icon: 'ℹ️', bg: 'linear-gradient(135deg,rgba(96,125,139,0.12),rgba(120,144,156,0.08))', label: '关于我们', desc: '蓝珊科技 · 守护南海珊瑚', url: '/pages/about/about' }
        ]
      }
    ]
  },

  onLoad() {
    this.setData({ statusBarHeight: (app.globalData && app.globalData.statusBarHeight) || 20 })
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 4 })
    }
    this.refreshUser()
    this.loadComments()
  },

  refreshUser() {
    api.getUserProfile().then((u) => {
      this.setData({ user: u })
      app.globalData.userInfo = u
    }).catch(() => {})
  },

  loadComments() {
    api.getComments().then((list) => this.setData({ comments: list || [] })).catch(() => {})
  },

  onUserTap() {
    if (!app.isLoggedIn()) {
      wx.navigateTo({ url: '/pages/login/login' })
    } else {
      util.toast('头像编辑功能开发中')
    }
  },

  onSetting() {
    util.toast('设置功能开发中')
  },

  onMessage() {
    util.toast('消息中心开发中')
  },

  /* 菜单跳转（switchTab: 前缀表示 Tab 页） */
  onMenuTap(e) {
    const url = e.currentTarget.dataset.url
    if (!url) return
    if (url.indexOf('switchTab:') === 0) {
      wx.switchTab({ url: url.replace('switchTab:', '') })
    } else {
      wx.navigateTo({ url })
    }
  },

  /* 退出登录（与官网同一账号体系，token 同步清除） */
  onLogout() {
    wx.showModal({
      title: '退出登录',
      content: '退出后将无法同步您的认养与积分数据',
      confirmColor: '#FF7043',
      success: (res) => {
        if (!res.confirm) return
        api.logout().then(() => {
          app.logout()
          this.setData({ user: null })
          util.toast('已退出登录')
        })
      }
    })
  },

  /* ================= 社区评论 ================= */

  onCommentInput(e) {
    this.setData({ commentText: e.detail.value })
  },

  addComment() {
    const text = (this.data.commentText || '').trim()
    if (!text) {
      util.toast('请输入评论内容')
      return
    }
    api.addComment(text).then((list) => {
      this.setData({ comments: list || [], commentText: '' })
      util.toast('发布成功')
    }).catch((e) => util.toast(e.message || '发布失败'))
  },

  onDeleteComment(e) {
    const id = e.currentTarget.dataset.id
    wx.showModal({
      title: '删除评论',
      content: '确定删除这条评论吗？',
      confirmColor: '#FF7043',
      success: (res) => {
        if (!res.confirm) return
        api.deleteComment(id).then((list) => {
          this.setData({ comments: list || [] })
          util.toast('已删除')
        })
      }
    })
  },

  onShareAppMessage() {
    return {
      title: '蓝珊 · 认养一株珊瑚，守护南海',
      path: '/pages/index/index'
    }
  }
})
