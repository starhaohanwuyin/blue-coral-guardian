/**
 * 公益捐赠页
 * Mock：直接成功；真实后端：可返回支付参数走 wx.requestPayment
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')

Page({
  data: {
    amounts: [10, 50, 100],
    amount: 50,
    customAmount: '',
    customMode: false
  },

  onSelectAmount(e) {
    this.setData({
      amount: Number(e.currentTarget.dataset.amount),
      customMode: false,
      customAmount: ''
    })
  },

  onCustomInput(e) {
    this.setData({
      customAmount: e.detail.value,
      customMode: !!(e.detail.value && Number(e.detail.value) > 0)
    })
  },

  onDonate() {
    const amount = this.data.customMode ? Number(this.data.customAmount) : this.data.amount
    if (!amount || amount <= 0) {
      util.toast('请选择或输入捐赠金额')
      return
    }

    wx.showModal({
      title: '确认捐赠',
      content: '将为珊瑚保护公益捐赠 ¥' + amount + '，感谢您的善举！',
      confirmColor: '#4CAF50',
      success: (res) => {
        if (!res.confirm) return
        wx.showLoading({ title: '处理中...', mask: true })
        api.createDonation(amount).then((data) => {
          wx.hideLoading()
          if (data && data.payParams) {
            // 真实后端：捐赠需要真实支付时返回 JSAPI 参数
            wx.requestPayment({
              timeStamp: data.payParams.timeStamp,
              nonceStr: data.payParams.nonceStr,
              package: data.payParams.package,
              signType: data.payParams.signType || 'RSA',
              paySign: data.payParams.paySign,
              success: () => util.toast('捐赠成功，感谢您的善举！💚'),
              fail: () => util.toast('支付已取消')
            })
          } else {
            util.toast('捐赠成功，感谢您的善举！💚')
          }
        }).catch((e) => {
          wx.hideLoading()
          util.toast(e.message || '捐赠失败')
        })
      }
    })
  }
})
