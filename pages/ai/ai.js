/**
 * AI识别页
 * 上传图片 → 识别（种类/生长）→ 结果展示 → 历史
 * 真实后端：api.recognize 内部走 wx.uploadFile 上传至 /api/ai/recognize
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')
const app = getApp()

Page({
  data: {
    statusBarHeight: 20,
    mode: 0, // 0种类识别 1生长检测
    state: 'upload', // upload | preview | loading | result
    imgPath: '',
    progress: 0,
    result: null,
    history: [],
    techList: [
      { icon: '🎯', bg: 'rgba(30,136,229,0.1)', title: 'YOLOv9 目标检测', desc: '实时检测画面中的珊瑚区域，精准定位每一株珊瑚的边界框' },
      { icon: '🧩', bg: 'rgba(0,188,212,0.1)', title: 'SAM3 图像分割', desc: '像素级分割珊瑚轮廓，精确量化活珊瑚覆盖面积与白化比例' },
      { icon: '🧠', bg: 'rgba(255,112,67,0.1)', title: '大模型分析', desc: '依托南海珊瑚种质资源库训练，关联唯一编号生成生长曲线' }
    ]
  },

  onLoad() {
    this.setData({ statusBarHeight: (app.globalData && app.globalData.statusBarHeight) || 20 })
    this.loadHistory()
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 3 })
    }
    // 消费首页「健康检测」入口：切换到生长检测标签
    if (app.globalData && app.globalData.pendingAiTab !== undefined) {
      this.setData({ mode: Number(app.globalData.pendingAiTab) })
      delete app.globalData.pendingAiTab
    }
  },

  loadHistory() {
    api.getAiHistory().then((list) => this.setData({ history: list || [] })).catch(() => {})
  },

  switchMode(e) {
    const mode = Number(e.currentTarget.dataset.mode)
    if (mode === this.data.mode) return
    // 切换模式时重置流程
    this.setData({ mode, state: 'upload', imgPath: '', result: null, progress: 0 })
  },

  /* 选择图片（wx.chooseMedia 替代网页 file input） */
  chooseImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      sizeType: ['compressed'],
      success: (res) => {
        this.setData({ state: 'preview', imgPath: res.tempFiles[0].tempFilePath })
      }
    })
  },

  resetUpload() {
    this.setData({ state: 'upload', imgPath: '', result: null, progress: 0 })
  },

  /* 开始识别 */
  startAnalysis() {
    this.setData({ state: 'loading', progress: 0 })
    // 进度条模拟动画
    this._timer = setInterval(() => {
      const p = Math.min(this.data.progress + Math.random() * 18, 92)
      this.setData({ progress: Math.round(p) })
    }, 320)

    api.recognize(this.data.imgPath, this.data.mode).then((result) => {
      clearInterval(this._timer)
      this.setData({ state: 'result', result, progress: 100 })
      this.loadHistory()
    }).catch((e) => {
      clearInterval(this._timer)
      this.setData({ state: 'preview' })
      util.toast((e && e.message) || '识别失败，请重试')
    })
  },

  onHide() {
    if (this._timer) clearInterval(this._timer)
  },

  onUnload() {
    if (this._timer) clearInterval(this._timer)
  },

  onHistoryTap() {
    util.toast('历史记录详情开发中')
  },

  onShareAppMessage() {
    return {
      title: '蓝珊AI · 拍照识别珊瑚种类',
      path: '/pages/ai/ai'
    }
  }
})
