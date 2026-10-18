/**
 * 认养证书页
 * - 实体证书：金色 premium 版式（双层边框 + 四角装饰 + 印章）
 * - 虚拟证书：青色版式（成长进度 / 累计积分动态注入）
 * - Canvas 2D 绘制证书 → wx.canvasToTempFilePath → 保存相册
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')

const pageI18n = require('../../utils/page-i18n.js')

Page(pageI18n.wrap({
  data: {
    cert: null,
    type: 'entity',
    saving: false,
    preview: '',
    previewPath: '',
    canvasCssW: 375,
    canvasCssH: 545
  },

  onLoad(options) {
    const type = options && options.type === 'virtual' ? 'virtual' : 'entity'
    this._id = (options && options.id) || ''
    this.setData({ type })
    wx.setNavigationBarTitle({ title: type === 'virtual' ? '虚拟认养证书' : '珊瑚认养证书' })
    wx.setNavigationBarColor({
      frontColor: '#ffffff',
      backgroundColor: type === 'virtual' ? '#062E33' : '#101A2E'
    })
    api.getCert(type, this._id).then((cert) => {
      this.setData({ cert })
    }).catch(() => {
      util.toast('证书加载失败，请重试')
    })
  },

  /* ================= 保存证书 ================= */
  onSave() {
    if (!this.data.cert || this.data.saving) return
    this.setData({ saving: true })
    // 不用遮罩盖住画布：个别基础库在画布被遮挡时导出会拿到空内容
    wx.showLoading({ title: '生成中...', mask: false })

    // 画布 CSS 尺寸与 750 宽坐标系保持 1:2，避免导出时只截到左上角
    const cssH = Math.ceil(this.calcH(this.data.cert) / 2)
    const start = () => {
      this.drawCert().then((canvas) => {
        const exportOnce = (attempt) => {
          const opts = { canvas, fileType: 'png', quality: 1 }
          if (attempt === 0) {
            opts.x = 0
            opts.y = 0
            opts.width = canvas.width
            opts.height = canvas.height
            opts.destWidth = canvas.width
            opts.destHeight = canvas.height
          }
          opts.success = (res) => {
            const baseName = this.data.type === 'virtual' ? '虚拟认养证书' : '珊瑚认养证书'
            const fileName = baseName + '-' + Date.now() + '.png'
            util.saveCertificateImage(res.tempFilePath, fileName).then((result) => {
              wx.hideLoading()
              this.setData({ saving: false })
              if (result.mode === 'album' && util.isDesktop()) {
                // 桌面环境即使相册接口返回成功，也给出可右键另存的预览
                this.setData({ preview: res.tempFilePath, previewPath: res.tempFilePath })
                util.toast('证书已生成，长按或右键另存为')
              } else if (result.mode === 'album') {
                util.toast('证书已保存到相册 🎉')
              } else if (result.mode === 'download') {
                util.toast('证书已开始下载 🎉')
              } else {
                // 桌面端没有相册：直接展示生成结果，右键/长按即可另存到电脑
                const previewPath = result.path || res.tempFilePath
                this.setData({ preview: result.dataUrl || previewPath, previewPath })
                util.toast('证书已生成，长按或右键另存为')
              }
            }).catch((err) => {
              wx.hideLoading()
              this.setData({ saving: false })
              const msg = (err && err.errMsg) || ''
              if (msg.indexOf('auth') !== -1) {
                util.toast('请先在设置中允许保存图片')
              } else if (res && res.tempFilePath) {
                // 即使落盘/相册失败，只要画布已生成，就先给用户可另存的预览
                this.setData({ preview: res.tempFilePath, previewPath: res.tempFilePath })
                util.toast('已生成预览，可长按或右键另存为')
              } else {
                util.toast('保存失败，请重试')
              }
            })
          }
          opts.fail = (err) => {
            console.error('[cert] canvasToTempFilePath fail', err)
            // 刚画完的一帧在少数基础库上还没提交，稍后换一种导出参数重试
            if (attempt < 1) {
              setTimeout(() => exportOnce(attempt + 1), 220)
              return
            }
            wx.hideLoading()
            this.setData({ saving: false })
            const msg = (err && err.errMsg) || ''
            util.toast(msg ? ('导出失败：' + msg) : '生成失败，请重试')
          }
          wx.canvasToTempFilePath(opts)
        }
        exportOnce(0)
      }).catch((err) => {
        console.error('[cert] draw/export fail', err)
        wx.hideLoading()
        this.setData({ saving: false })
        const msg = (err && (err.message || err.errMsg)) || ''
        util.toast(msg ? ('生成失败：' + msg) : '生成失败，请重试')
      })
    }

    if (this.data.canvasCssH === cssH) start()
    else this.setData({ canvasCssH: cssH }, start)
  },

  closePreview() {
    this.setData({ preview: '', previewPath: '' })
  },

  copyPreviewPath() {
    if (!this.data.previewPath) return
    util.copyText(this.data.previewPath, '证书文件路径已复制')
  },

  /* 某些开发者工具版本不能直接用 wxfile:// 路径渲染 <image>；
   * 此时读成 base64 data URL 再显示，保证预览/另存这条兜底路径可用。 */
  onPreviewError() {
    const path = this.data.previewPath || this.data.preview
    if (!path || path.indexOf('data:') === 0) return
    try {
      wx.getFileSystemManager().readFile({
        filePath: path,
        encoding: 'base64',
        success: (r) => this.setData({ preview: 'data:image/png;base64,' + r.data }),
        fail: () => {}
      })
    } catch (e) {}
  },

  noop() {},

  /* ================= Canvas 绘制 ================= */
  drawCert() {
    return new Promise((resolve, reject) => {
      const guard = setTimeout(() => reject(new Error('canvas query timeout')), 10000)
      const query = wx.createSelectorQuery()
      query.select('#certCanvas').fields({ node: true, size: true }).exec((res) => {
        clearTimeout(guard)
        if (!res || !res[0] || !res[0].node) {
          reject(new Error('canvas not found'))
          return
        }
        const canvas = res[0].node
        const cert = this.data.cert
        const W = 750
        const H = this.calcH(cert)
        canvas.width = W
        canvas.height = H
        const ctx = canvas.getContext('2d')
        if (!ctx) {
          reject(new Error('canvas 2d context unavailable'))
          return
        }
        this.loadImg(canvas, cert.type === 'entity' ? cert.img : '').then((img) => {
          let painted = false
          try {
            this.paintCert(ctx, cert, W, H, img)
            painted = !this.isCanvasBlank(ctx, W, H)
          } catch (e) {
            console.error('[cert] paintCert fail, using fallback', e)
          }
          if (!painted) {
            try {
              this.paintCertFallback(ctx, cert, W, H)
            } catch (e2) {
              reject(e2)
              return
            }
          }
          // 等一帧再导出，避免“画完立刻导”拿到空白/未提交画布
          setTimeout(() => resolve(canvas), 100)
        }).catch(reject)
      })
    })
  },

  /* 画布是否完全没有像素（个别基础库会“调用成功但内容为空”） */
  isCanvasBlank(ctx, W, H) {
    try {
      const points = [[4, 4], [Math.floor(W / 2), Math.floor(H / 2)], [W - 5, H - 5]]
      for (let i = 0; i < points.length; i++) {
        const d = ctx.getImageData(points[i][0], points[i][1], 1, 1).data
        if (d && (d[3] !== 0 || d[0] !== 0 || d[1] !== 0 || d[2] !== 0)) return false
      }
      return true
    } catch (e) {
      return false
    }
  },

  /* 计算画布高度（750 宽坐标系，按内容动态） */
  calcH(cert) {
    const isE = cert.type !== 'virtual'
    let h = 84 + 52 + 40 + 56 // 顶部标签 + 主标题 + 副标题 + 间距
    h += isE ? 160 + 48 : 144 + 40 // 珊瑚圆图 + 间距
    h += (cert.fields || []).length * 56 // 字段行
    h += 28 // 印章上间距
    h += isE ? 128 + 24 + 32 + 30 : 96 + 28 // 印章 + 机构 + 日期
    h += 72 // 底部留白
    return Math.ceil(h)
  },

  /* 加载珊瑚图片，失败/超时返回 null（兜底绘制 🪸） */
  loadImg(canvas, url) {
    return new Promise((resolve) => {
      if (!url) { resolve(null); return }
      let done = false
      const timer = setTimeout(() => {
        if (!done) { done = true; resolve(null) }
      }, 6000)
      try {
        const img = canvas.createImage()
        img.onload = () => {
          if (!done) {
            done = true
            clearTimeout(timer)
            // 尺寸为 0 的图片画进圆形头像会得到 NaN，直接当加载失败处理
            resolve(img && img.width > 0 && img.height > 0 ? img : null)
          }
        }
        img.onerror = () => {
          if (!done) { done = true; clearTimeout(timer); resolve(null) }
        }
        img.src = url
      } catch (e) {
        clearTimeout(timer)
        resolve(null)
      }
    })
  },

  roundRectPath(ctx, x, y, w, h, r) {
    ctx.beginPath()
    // 统一走 arcTo：部分基础库虽然有 roundRect，但参数/实现不一致会抛异常
    ctx.moveTo(x + r, y)
    ctx.arcTo(x + w, y, x + w, y + h, r)
    ctx.arcTo(x + w, y + h, x, y + h, r)
    ctx.arcTo(x, y + h, x, y, r)
    ctx.arcTo(x, y, x + w, y, r)
    ctx.closePath()
  },

  /* 极简兜底证书：只使用最基础的 2D 指令。
   * 高级版式（渐变/圆角/图片/emoji）在个别基础库上失败时，至少还能导出一张完整证书。 */
  paintCertFallback(ctx, cert, W, H) {
    const isE = cert.type !== 'virtual'
    ctx.clearRect(0, 0, W, H)
    ctx.fillStyle = isE ? '#FFF9E6' : '#D8F5F9'
    ctx.fillRect(0, 0, W, H)
    ctx.strokeStyle = isE ? '#C8A84E' : '#00838F'
    ctx.lineWidth = 6
    ctx.strokeRect(24, 24, W - 48, H - 48)
    ctx.textAlign = 'center'
    ctx.textBaseline = 'alphabetic'
    ctx.fillStyle = isE ? '#1A2138' : '#004D40'
    ctx.font = 'bold 46px sans-serif'
    ctx.fillText(cert.title || '', W / 2, 90)
    ctx.font = '24px sans-serif'
    ctx.fillText(cert.subTitle || '', W / 2, 138)

    let y = 210
    ;(cert.fields || []).forEach((f) => {
      ctx.textAlign = 'left'
      ctx.font = '24px sans-serif'
      ctx.fillText(String(f.label || ''), 90, y)
      ctx.textAlign = 'right'
      ctx.font = 'bold 26px sans-serif'
      ctx.fillText(String(f.value == null ? '' : f.value), W - 90, y)
      ctx.beginPath()
      ctx.moveTo(90, y + 16)
      ctx.lineTo(W - 90, y + 16)
      ctx.strokeStyle = isE ? 'rgba(200,168,78,0.25)' : 'rgba(0,77,64,0.15)'
      ctx.lineWidth = 2
      ctx.stroke()
      y += 52
    })
    ctx.textAlign = 'center'
    ctx.fillStyle = isE ? '#8B7D3C' : '#00695C'
    ctx.font = '22px sans-serif'
    ctx.fillText(cert.org || '', W / 2, Math.min(H - 50, y + 70))
    ctx.fillText(cert.issueDate || '', W / 2, Math.min(H - 20, y + 108))
  },

  /* 证书主绘制（与页面版式 1:1 对应） */
  paintCert(ctx, cert, W, H, img) {
    const isE = cert.type !== 'virtual'
    const cx = W / 2

    /* 背景 */
    ctx.clearRect(0, 0, W, H)
    if (isE) {
      const g = ctx.createLinearGradient(0, 0, W, H)
      g.addColorStop(0, '#FFFEF5')
      g.addColorStop(0.5, '#FFF9E6')
      g.addColorStop(1, '#FFFEF5')
      ctx.fillStyle = g
    } else {
      const g = ctx.createLinearGradient(0, 0, W * 0.55, H)
      g.addColorStop(0, '#E0F7FA')
      g.addColorStop(0.3, '#B2EBF2')
      g.addColorStop(0.6, '#80DEEA')
      g.addColorStop(1, '#4DD0E1')
      ctx.fillStyle = g
    }
    ctx.fillRect(0, 0, W, H)

    if (isE) {
      /* 双层金边框 */
      ctx.strokeStyle = '#C8A84E'
      ctx.lineWidth = 4
      ctx.strokeRect(16, 16, W - 32, H - 32)
      ctx.strokeStyle = '#D4AF37'
      ctx.lineWidth = 2
      ctx.strokeRect(28, 28, W - 56, H - 56)
      /* 四角装饰（L 形） */
      const m = 36
      const L = 48
      ctx.strokeStyle = '#C8A84E'
      ctx.lineWidth = 4
      ctx.beginPath()
      ctx.moveTo(m, m + L); ctx.lineTo(m, m); ctx.lineTo(m + L, m)
      ctx.moveTo(W - m - L, m); ctx.lineTo(W - m, m); ctx.lineTo(W - m, m + L)
      ctx.moveTo(m, H - m - L); ctx.lineTo(m, H - m); ctx.lineTo(m + L, H - m)
      ctx.moveTo(W - m - L, H - m); ctx.lineTo(W - m, H - m); ctx.lineTo(W - m, H - m - L)
      ctx.stroke()
    } else {
      /* 白色装饰圆 */
      ctx.fillStyle = 'rgba(255,255,255,0.15)'
      ctx.beginPath(); ctx.arc(W + 40, -40, 320, 0, Math.PI * 2); ctx.fill()
      ctx.fillStyle = 'rgba(255,255,255,0.1)'
      ctx.beginPath(); ctx.arc(-60, H + 100, 360, 0, Math.PI * 2); ctx.fill()
      /* 内边框 */
      ctx.strokeStyle = 'rgba(255,255,255,0.4)'
      ctx.lineWidth = 3
      this.roundRectPath(ctx, 20, 20, W - 40, H - 40, 28)
      ctx.stroke()
    }

    /* 顶部英文标签（手动字距） */
    ctx.textAlign = 'center'
    ctx.textBaseline = 'alphabetic'
    let y = 84
    ctx.fillStyle = isE ? '#C8A84E' : 'rgba(0,77,64,0.5)'
    ctx.font = '600 22px sans-serif'
    ctx.fillText((cert.topLabel || '').split('').join(' '), cx, y)
    y += 52

    /* 主标题 */
    ctx.fillStyle = isE ? '#1A2138' : '#004D40'
    ctx.font = '700 46px Georgia, "Songti SC", serif'
    ctx.fillText(cert.title || '', cx, y)
    y += 40

    /* 副标题 */
    ctx.fillStyle = isE ? '#8B7D3C' : '#00695C'
    ctx.font = '24px sans-serif'
    ctx.fillText(cert.subTitle || '', cx, y)
    y += 56

    /* 珊瑚圆图 / 图标 */
    if (isE) {
      const R = 80
      const cyc = y + R
      ctx.save()
      ctx.beginPath()
      ctx.arc(cx, cyc, R, 0, Math.PI * 2)
      ctx.clip()
      if (img) {
        const s = Math.max(R * 2 / img.width, R * 2 / img.height)
        const dw = img.width * s
        const dh = img.height * s
        ctx.drawImage(img, cx - dw / 2, cyc - dh / 2, dw, dh)
      } else {
        ctx.fillStyle = '#FFF3D6'
        ctx.fillRect(cx - R, cyc - R, R * 2, R * 2)
        ctx.font = '76px sans-serif'
        ctx.textBaseline = 'middle'
        ctx.fillText('🪸', cx, cyc + 4)
        ctx.textBaseline = 'alphabetic'
      }
      ctx.restore()
      ctx.strokeStyle = '#D4AF37'
      ctx.lineWidth = 6
      ctx.beginPath()
      ctx.arc(cx, cyc, R, 0, Math.PI * 2)
      ctx.stroke()
      y += R * 2 + 48
    } else {
      const R = 72
      const cyc = y + R
      ctx.fillStyle = 'rgba(255,255,255,0.3)'
      ctx.beginPath()
      ctx.arc(cx, cyc, R, 0, Math.PI * 2)
      ctx.fill()
      ctx.strokeStyle = 'rgba(255,255,255,0.5)'
      ctx.lineWidth = 4
      ctx.beginPath()
      ctx.arc(cx, cyc, R, 0, Math.PI * 2)
      ctx.stroke()
      ctx.fillStyle = '#004D40'
      ctx.font = '76px sans-serif'
      ctx.textBaseline = 'middle'
      ctx.fillText('🪸', cx, cyc + 4)
      ctx.textBaseline = 'alphabetic'
      y += R * 2 + 40
    }

    /* 字段行 */
    const fx = 96
    const fx2 = W - 96
    ;(cert.fields || []).forEach((f) => {
      ctx.textAlign = 'left'
      ctx.fillStyle = isE ? '#8B7D3C' : '#00695C'
      ctx.font = '24px sans-serif'
      ctx.fillText(f.label, fx, y + 28)
      ctx.textAlign = 'right'
      ctx.fillStyle = isE ? '#1A2138' : '#004D40'
      ctx.font = '600 26px sans-serif'
      ctx.fillText(String(f.value), fx2, y + 28)
      ctx.strokeStyle = isE ? 'rgba(200,168,78,0.15)' : 'rgba(0,77,64,0.08)'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.moveTo(fx, y + 44)
      ctx.lineTo(fx2, y + 44)
      ctx.stroke()
      y += 56
    })

    /* 印章区 */
    y += 28
    ctx.textAlign = 'center'
    if (isE) {
      const scy = y + 64
      ctx.strokeStyle = '#C41E3A'
      ctx.lineWidth = 6
      ctx.beginPath()
      ctx.arc(cx, scy, 64, 0, Math.PI * 2)
      ctx.stroke()
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.arc(cx, scy, 54, 0, Math.PI * 2)
      ctx.stroke()
      ctx.fillStyle = '#C41E3A'
      ctx.font = '700 24px sans-serif'
      ctx.fillText('蓝珊', cx, scy - 8)
      ctx.fillText('认证', cx, scy + 24)
      y += 128 + 24
      ctx.fillStyle = '#5A6578'
      ctx.font = '24px sans-serif'
      ctx.fillText(cert.org || '', cx, y)
      y += 32
      ctx.fillStyle = '#8B7D3C'
      ctx.font = '22px sans-serif'
      ctx.fillText(cert.issueDate || '', cx, y)
    } else {
      ctx.font = '64px sans-serif'
      ctx.textBaseline = 'middle'
      ctx.fillText('🐚', cx, y + 40)
      ctx.textBaseline = 'alphabetic'
      y += 96
      ctx.fillStyle = '#00695C'
      ctx.font = '22px sans-serif'
      ctx.fillText(cert.org || '', cx, y)
    }
  },

  onShareAppMessage() {
    const isV = this.data.type === 'virtual'
    return {
      title: isV
        ? '我在蓝珊认养了一株虚拟珊瑚，一起来养成吧！🪸'
        : '我认养的珊瑚有了专属证书，一起来守护珊瑚礁！🪸',
      path: '/pages/index/index'
    }
  }
}))
