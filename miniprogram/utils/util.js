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

function isWebRuntime() {
  return typeof window !== 'undefined' && !!window.MP_RUNTIME
}

/**
 * 是否是桌面端（开发者工具或 Windows / macOS 微信）。
 * 桌面端没有手机相册，wx.saveImageToPhotosAlbum 容易直接失败，
 * 证书保存要改走「写入小程序文件目录 + 页面预览」。
 */
function isDesktop() {
  try {
    const s = wx.getSystemInfoSync ? wx.getSystemInfoSync() : {}
    const p = String(s.platform || '').toLowerCase()
    if (p === 'devtools' || p === 'windows' || p === 'mac') return true
    if (wx.getDeviceInfo) {
      const d = wx.getDeviceInfo() || {}
      const dp = String(d.platform || '').toLowerCase()
      if (dp === 'windows' || dp === 'mac') return true
    }
  } catch (e) {}
  return false
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

/**
 * 真机调试/临时演示时手动指定评估服务地址。
 * 正式发布请改 config.js 的 PUBLIC_API_BASE，不要依赖用户手填。
 * @param done 可选回调 ({ok, url})
 */
function configureApiBase(done) {
  const api = require('./api.js')
  const current = (function () {
    try { return wx.getStorageSync('coral_api_base') || config.CORAL_API || '' } catch (e) { return '' }
  })()
  wx.showModal({
    title: '评估服务地址',
    content: '真机调试填电脑局域网地址；正式体验填公网 HTTPS 域名。留空并确认可恢复自动探测。',
    editable: true,
    placeholderText: current || 'https://api.example.com',
    confirmText: '保存并测试',
    cancelText: '取消',
    success(res) {
      if (!res.confirm) return
      let raw = String(res.content || '').trim()
      if (!raw) {
        api.clearApiBase()
        toast('已恢复自动探测')
        done && done({ ok: true, url: '' })
        return
      }
      // 局域网调试常直接输 192.168.x.x:8000，自动补 http://
      if (!/^https?:\/\//i.test(raw) &&
          /^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(raw)) {
        raw = 'http://' + raw
      }
      const set = api.setApiBase(raw)
      if (!set.ok) {
        toast(set.message)
        return
      }
      toast('正在测试连接...')
      wx.request({
        url: set.url + '/health',
        timeout: 8000,
        success(h) {
          const d = h && h.data
          if (h.statusCode === 200 && d && d.status === 'ok') {
            toast('服务连接成功', 'success')
            done && done({ ok: true, url: set.url })
          } else {
            wx.showModal({
              title: '连接失败',
              content: '地址已保存，但健康检查返回异常（HTTP ' + (h.statusCode || '?') + '）。请确认地址和端口正确。',
              showCancel: false
            })
            done && done({ ok: false, url: set.url })
          }
        },
        fail() {
          wx.showModal({
            title: '连接失败',
            content: '地址已保存，但手机无法访问该服务。请确认：\n'
              + '① 服务已监听 0.0.0.0:8000；\n'
              + '② 手机与电脑在同一 Wi-Fi（局域网调试）；\n'
              + '③ 电脑防火墙已放行 8000；\n'
              + '④ 正式体验必须使用 HTTPS 公网域名。',
            showCancel: false
          })
          done && done({ ok: false, url: set.url })
        }
      })
    }
  })
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
    const attempt = () => {
      wx.saveImageToPhotosAlbum({
        filePath,
        fileName,                      // 浏览器端直接下载时用它命名文件（小程序端忽略）
        success: resolve,
        fail(err) {
          if (err && (err.errMsg || '').indexOf('auth') !== -1) {
            wx.showModal({
              title: '需要相册权限',
              content: '请在设置中允许保存到相册，授权后会自动重试',
              confirmText: '去设置',
              success(res) {
                if (!res.confirm) { reject(err); return }
                wx.openSetting({
                  success(setting) {
                    if (setting && setting.authSetting &&
                        setting.authSetting['scope.writePhotosAlbum']) {
                      attempt()
                    } else {
                      reject(err)
                    }
                  },
                  fail() { reject(err) }
                })
              }
            })
          } else {
            reject(err)
          }
        }
      })
    }
    attempt()
  })
}

/* 桌面端兜底：把临时图片复制到小程序文件目录，返回可在页面里预览的路径 */
function saveImageToUserData(filePath, fileName) {
  return new Promise((resolve, reject) => {
    try {
      const fs = wx.getFileSystemManager()
      if (!fs || typeof fs.saveFile !== 'function') {
        reject(new Error('当前环境不支持文件保存'))
        return
      }
      const safeName = String(fileName || 'blue-coral-certificate.png').replace(/[\\/:*?"<>|]/g, '-')
      // 只用最基础的 saveFile(tempFilePath)。部分开发者工具版本不接受自定义
      // filePath，传了会直接 fail，导致桌面端“保存不了”。
      fs.saveFile({
        tempFilePath: filePath,
        success(r) {
          const saved = (r && r.savedFilePath) || filePath
          // 直接把文件读成 base64 给页面预览：开发者工具里 wxfile:// 路径
          // 有时不能直接塞进 <image>，有 data URL 就不会出现“保存成功但预览空白”。
          try {
            fs.readFile({
              filePath: saved,
              encoding: 'base64',
              success(read) {
                resolve({
                  mode: 'file',
                  path: saved,
                  dataUrl: read && read.data ? ('data:image/png;base64,' + read.data) : '',
                  fileName: safeName
                })
              },
              fail() {
                resolve({ mode: 'file', path: saved, fileName: safeName })
              }
            })
          } catch (e) {
            resolve({ mode: 'file', path: saved, fileName: safeName })
          }
        },
        fail(err) { reject(err) }
      })
    } catch (e) {
      reject(e)
    }
  })
}

/**
 * 保存证书图片：
 * - 网页版：直接触发浏览器下载
 * - 桌面开发者工具 / PC 微信：写入文件目录，返回路径供页面预览、右键另存
 * - 手机：保存到相册；相册权限失败再退回文件目录
 * @returns Promise<{mode:'download'|'file'|'album', path?:string, fileName?:string}>
 */
function saveCertificateImage(filePath, fileName) {
  if (isWebRuntime()) {
    return saveImageToAlbum(filePath, fileName).then(() => ({ mode: 'download' }))
  }
  const fromFile = () => saveImageToUserData(filePath, fileName)
  if (isDesktop()) {
    return fromFile().catch(() => saveImageToAlbum(filePath, fileName).then(() => ({ mode: 'album' })))
  }
  return saveImageToAlbum(filePath, fileName)
    .then(() => ({ mode: 'album' }))
    .catch((err) => {
      // 用户明确拒绝相册权限时不要偷偷换保存位置，先引导授权
      const msg = (err && err.errMsg) || ''
      if (msg.indexOf('auth') !== -1) throw err
      return fromFile()
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
  isWebRuntime,
  isDesktop,
  openLink,
  configureApiBase,
  formatPrice,
  drawRing,
  saveImageToAlbum,
  saveCertificateImage,
  ensureLogin,
  VERSION: config.VERSION,
  SERVICE_EMAIL: config.SERVICE_EMAIL
}
