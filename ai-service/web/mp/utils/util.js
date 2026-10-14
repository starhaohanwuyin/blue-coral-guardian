/**
 * 通用工具函数
 */
const config = require('./config.js')

function toast(msg, icon) {
  wx.showToast({ title: msg, icon: icon || 'none', duration: 2000 })
}

function copyText(text, tip) {
  wx.setClipboardData({
    data: text,
    success() { toast(tip || '已复制') }
  })
}

/**
 * 网页版（H5）里能直接打开外链；小程序不允许打开外部网页，只能复制。
 * 判定依据是 web/mp.js 运行时挂在 window 上的 MP_RUNTIME（小程序里没有 window）。
 */
function canOpenExternal() {
  return typeof window !== 'undefined' && !!window.MP_RUNTIME &&
    typeof window.open === 'function'
}

/**
 * 打开一个外链：网页版新开标签页；小程序退回复制到剪贴板并提示。
 * @param url 链接
 * @param tip 小程序里复制成功后的提示文案
 */
function openLink(url, tip) {
  if (!url) return
  if (canOpenExternal()) {
    window.open(url, '_blank')
    return
  }
  copyText(url, tip || '链接已复制，可粘贴到微信或浏览器打开')
}

function formatPrice(n) {
  return '¥' + (Number(n) || 0).toLocaleString()
}

/**
 * 环形进度绘制（canvas 2d）
 * @param canvas  canvas 节点
 * @param ctx     2d 上下文
 * @param percent 0-100
 * @param opts    {size, lineWidth, colors:[c1,c2], trackColor}
 */
function drawRing(canvas, ctx, percent, opts) {
  const o = opts || {}
  const size = o.size || canvas.width
  const lw = o.lineWidth || Math.max(8, size * 0.07)
  const r = (size - lw) / 2 - 1
  const cx = size / 2
  const cy = size / 2

  ctx.clearRect(0, 0, size, size)
  // 背景环
  ctx.beginPath()
  ctx.arc(cx, cy, r, 0, Math.PI * 2)
  ctx.strokeStyle = o.trackColor || '#E8EDF5'
  ctx.lineWidth = lw
  ctx.lineCap = 'round'
  ctx.stroke()

  // 前景渐变环
  const grd = ctx.createLinearGradient(0, 0, size, size)
  const colors = o.colors || ['#1E88E5', '#00BCD4']
  grd.addColorStop(0, colors[0])
  grd.addColorStop(1, colors[1])
  const start = -Math.PI / 2
  const end = start + Math.PI * 2 * Math.min(percent, 100) / 100
  ctx.beginPath()
  ctx.arc(cx, cy, r, start, end)
  ctx.strokeStyle = grd
  ctx.lineWidth = lw
  ctx.lineCap = 'round'
  ctx.stroke()
}

/**
 * 保存图片到相册（含权限引导）
 */
function saveImageToAlbum(filePath, fileName) {
  return new Promise((resolve, reject) => {
    wx.saveImageToPhotosAlbum({
      filePath,
      fileName,                      // 浏览器端直接下载时用它命名文件（小程序端忽略）
      success: resolve,
      fail(err) {
        if (err && (err.errMsg || '').indexOf('auth') !== -1) {
          wx.showModal({
            title: '需要相册权限',
            content: '请在设置中允许保存到相册',
            confirmText: '去设置',
            success(res) {
              if (res.confirm) wx.openSetting()
              reject(err)
            }
          })
        } else {
          reject(err)
        }
      }
    })
  })
}

/**
 * 统一的登录检查：未登录弹窗引导
 */
function ensureLogin() {
  const app = getApp()
  if (app.isLoggedIn()) return true
  wx.showModal({
    title: '请先登录',
    content: '登录蓝珊账号后即可同步您的认养与积分数据',
    confirmText: '去登录',
    success(res) {
      if (res.confirm) wx.navigateTo({ url: '/pages/login/login' })
    }
  })
  return false
}

module.exports = {
  toast,
  copyText,
  canOpenExternal,
  openLink,
  formatPrice,
  drawRing,
  saveImageToAlbum,
  ensureLogin,
  VERSION: config.VERSION,
  SERVICE_EMAIL: config.SERVICE_EMAIL
}
