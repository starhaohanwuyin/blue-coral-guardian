/**
 * 认养页
 * - 虚拟认养：养成玩法（喂养/任务/积分/商城/新珊瑚）
 * - 实体认养：产品下单（JSAPI 支付）+ 碳汇 + 我的珊瑚
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')
const mock = require('../../utils/mock.js')
const app = getApp()

/* 任务按钮文案映射 */
const TASK_BTN = {
  checkin: '领取',
  share: '去完成',
  learn: '去学习',
  donate: '去捐赠',
  quiz: '去答题',
  steps: '去记录',
  welfare: '去参加'
}

Page({
  data: {
    statusBarHeight: 20,
    type: 0, // 0虚拟 1实体

    /* 虚拟养成 */
    points: 0,
    growth: 0,
    corals: [],
    shop: {},
    tasks: [],
    feedingAnim: false,

    /* 实体认养 */
    products: [],
    myCorals: [],
    carbon: { value: 0, unit: 'g CO₂' },
    carbonDeg: 0,

    /* 喂养弹窗 */
    feedModal: false,
    feeds: [],

    /* 公益活动弹窗 */
    welfareModal: false,
    welfareActivities: []
  },

  onLoad() {
    this.setData({
      statusBarHeight: (app.globalData && app.globalData.statusBarHeight) || 20,
      feeds: mock.feeds,
      welfareActivities: mock.welfareActivities
    })
    this.loadAll()
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 1 })
    }
    // 从商城/捐赠/答题等页面返回时刷新任务与状态
    if (this._loaded) this.refreshVirtual()
  },

  loadAll() {
    this.refreshVirtual()
    api.getEntityProducts().then((list) => this.setData({ products: list || [] })).catch(() => {})
    api.getMyCorals().then((list) => this.setData({ myCorals: list || [] })).catch(() => {})
    api.getCarbon().then((c) => {
      // 环形进度：以 300g 为满环
      const deg = Math.min(Math.round(((c.value || 0) / 300) * 360), 360)
      this.setData({ carbon: c, carbonDeg: deg })
    }).catch(() => {})
    this._loaded = true
  },

  /* 刷新虚拟养成状态 + 任务列表 */
  refreshVirtual() {
    api.getVirtualState().then((s) => {
      this.setData({
        points: s.points,
        growth: s.growth || 0,
        corals: s.corals || [],
        shop: s.shop || {}
      })
    }).catch(() => {})
    api.getTasks().then((d) => {
      const list = (d.list || []).map((t) => Object.assign({}, t, { btnText: TASK_BTN[t.id] || '去完成' }))
      this.setData({ tasks: list })
    }).catch(() => {})
  },

  switchType(e) {
    this.setData({ type: Number(e.currentTarget.dataset.type) })
  },

  /* ================= 虚拟养成 ================= */

  /* 喂养珊瑚：无养料提示去商城，有养料打开喂养弹窗 */
  onFeed() {
    if (this.data.growth >= 100) {
      util.toast('珊瑚已成熟！可认养新珊瑚')
      return
    }
    const shop = this.data.shop
    const has = mock.feeds.some((f) => (shop[f.key] || 0) > 0)
    if (!has) {
      util.toast('没有养料了！去积分商城购买吧')
      return
    }
    this.setData({ feedModal: true })
  },

  closeFeed() {
    this.setData({ feedModal: false })
  },

  /* 使用养料 */
  onUseFeed(e) {
    const key = e.currentTarget.dataset.key
    api.useFeed(key).then((s) => {
      this.applyState(s)
      this.setData({ feedModal: false, feedingAnim: true })
      const feed = mock.feeds.filter((f) => f.key === key)[0]
      util.toast('喂养成功！成长 +' + feed.growth + '%')
      setTimeout(() => this.setData({ feedingAnim: false }), 700)
    }).catch((err) => util.toast(err.message))
  },

  /* 直接购买养料 */
  onBuyFeed(e) {
    const key = e.currentTarget.dataset.key
    api.buyFeed(key).then((s) => {
      this.applyState(s)
      const feed = mock.feeds.filter((f) => f.key === key)[0]
      util.toast('购买成功！获得 ' + feed.icon + ' ' + feed.name)
    }).catch((err) => util.toast(err.message))
  },

  applyState(s) {
    this.setData({
      points: s.points,
      growth: s.growth || 0,
      corals: s.corals || [],
      shop: s.shop || {}
    })
  },

  goShop() {
    wx.navigateTo({ url: '/pages/shop/shop' })
  },

  goVirtualCert() {
    wx.navigateTo({ url: '/pages/cert/cert?type=virtual' })
  },

  /* 认养新虚拟珊瑚 */
  onAdoptNew() {
    api.adoptNewCoral().then((s) => {
      this.applyState(s)
      util.toast('🎉 恭喜！新珊瑚加入你的海底花园')
    }).catch((err) => util.toast(err.message))
  },

  /* 任务点击 */
  onTaskTap(e) {
    const id = e.currentTarget.dataset.id
    const action = e.currentTarget.dataset.action
    switch (action) {
      case 'claim':
      case 'steps':
        this.claimTask(id)
        break
      case 'learn':
        wx.switchTab({ url: '/pages/knowledge/knowledge' })
        break
      case 'donate':
        wx.navigateTo({ url: '/pages/donate/donate' })
        break
      case 'quiz':
        wx.navigateTo({ url: '/pages/quiz/quiz' })
        break
      case 'welfare':
        this.setData({ welfareModal: true })
        break
    }
  },

  claimTask(id) {
    api.claimTask(id).then((res) => {
      util.toast('完成！积分 +' + res.reward)
      this.refreshVirtual()
    }).catch((err) => util.toast(err.message))
  },

  /* 分享任务：分享即完成 */
  onShareAppMessage() {
    const shareTask = this.data.tasks.filter((t) => t.id === 'share' && !t.done)[0]
    if (shareTask) {
      api.claimTask('share').then(() => {
        util.toast('分享成功！积分 +' + shareTask.points)
        this.refreshVirtual()
      }).catch(() => {})
    }
    return {
      title: '我在蓝珊认养了一株珊瑚，一起来守护南海吧！',
      path: '/pages/index/index'
    }
  },

  /* 公益活动 */
  closeWelfare() {
    this.setData({ welfareModal: false })
  },

  onWelfareJoin() {
    this.setData({ welfareModal: false })
    this.claimTask('welfare')
  },

  /* ================= 实体认养 ================= */

  /**
   * 实体认养下单
   * Mock：直接成功；真实后端：返回 payParams 时调起 wx.requestPayment（JSAPI）
   */
  onBuy(e) {
    const id = e.currentTarget.dataset.id
    const product = this.data.products.filter((p) => p.id === id)[0]
    if (!product) return

    if (!util.ensureLogin('请先登录后认养')) return

    wx.showModal({
      title: '确认认养',
      content: product.title + ' · ¥' + product.price + product.priceUnit + '，确认下单？',
      confirmColor: '#1E88E5',
      success: (res) => {
        if (!res.confirm) return
        wx.showLoading({ title: '下单中...', mask: true })
        api.createOrder(product).then((data) => {
          wx.hideLoading()
          if (data && data.payParams) {
            // 真实支付：后端返回 JSAPI 支付参数
            wx.requestPayment({
              timeStamp: data.payParams.timeStamp,
              nonceStr: data.payParams.nonceStr,
              package: data.payParams.package,
              signType: data.payParams.signType || 'RSA',
              paySign: data.payParams.paySign,
              success: () => {
                util.toast('🎉 支付成功，认养完成！')
                this.loadAll()
              },
              fail: () => util.toast('支付已取消')
            })
          } else {
            util.toast('🎉 认养成功！可在我的珊瑚中查看')
            this.loadAll()
          }
        }).catch((err) => {
          wx.hideLoading()
          util.toast(err.message || '下单失败')
        })
      }
    })
  },

  goCamera() {
    wx.navigateTo({ url: '/pages/camera/camera' })
  },

  goCert() {
    wx.navigateTo({ url: '/pages/cert/cert?type=entity' })
  },

  goMyAdopt() {
    wx.navigateTo({ url: '/pages/my-adopt/my-adopt' })
  },

  goCoralDetail(e) {
    wx.navigateTo({ url: '/pages/coral-detail/coral-detail?id=' + e.currentTarget.dataset.id })
  }
})
