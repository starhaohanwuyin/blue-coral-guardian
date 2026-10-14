/**
 * 珊瑚详情页
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')

const pageI18n = require('../../utils/page-i18n.js')

Page(pageI18n.wrap({
  data: {
    d: null,
    deg: 0
  },

  onLoad(options) {
    const id = options.id || 1
    // ⚠️ 用 getAdoptCoralDetail（认养详情），不要用 getCoralDetail —— 后者是「珊瑚种类详情」
    //    查图鉴库 /corals/{id}，传认养编号会返回 null，页面会一直停在「加载中…」。
    api.getAdoptCoralDetail(id).then((d) => {
      if (!d) throw new Error('没有找到这株珊瑚')
      this.setData({
        d,
        deg: Math.round((d.growth / 100) * 360)
      })
      wx.setNavigationBarTitle({ title: d.name || '珊瑚详情' })
    }).catch((e) => util.toast(e.message || '加载失败'))
  },

  goCamera() {
    wx.navigateTo({ url: '/pages/camera/camera' })
  },

  goCert() {
    // 带上当前这株的 id：证书里的品种/编号/日期/照片都按它取，保证一一对应
    const id = this.data.d && this.data.d.id
    wx.navigateTo({ url: '/pages/cert/cert?type=entity' + (id ? '&id=' + id : '') })
  },

  onShareAppMessage() {
    const d = this.data.d || {}
    return {
      title: '我的珊瑚 ' + (d.name || '') + ' 正在海洋成长中',
      path: '/pages/index/index'
    }
  }
}))
