/**
 * 礁区智能评估页
 * ------------------------------------------------------------------
 * 一次上传，三类结果：
 *   1. 礁区覆盖评估（语义分割）：活珊瑚 / 白化 / 死亡 / 藻类 / 沙砾 百分比
 *   2. 主要珊瑚属识别（在分割出的珊瑚区域上做属级分类）
 *   3. 主要底栖类别明细
 *
 * 数据来自融合推理服务（coral_ml/scripts/serve_fusion.py）：
 *   config.USE_REAL_AI = true  → 调用真实服务
 *   config.USE_REAL_AI = false → 使用本地演示数据（结构一致，便于无服务演示）
 *
 * 安全使用边界（已实测量化）：
 *   · 拍摄深度 ≤8m 时覆盖率估计误差 ≤2.2%；15m 以上浑浊水域显著失效
 *   · 页面固定展示使用边界与免责声明
 *   · 星地验证：模型估计 39.71% vs RCM 实地 39.56%
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')
// ⚠️ 必须显式 require：此处曾漏掉，导致 startAnalysis 里 `config.DEFAULT_SITE` 抛
//    ReferenceError（同步抛出、promise 未建立），页面永远停在 loading 且不发请求。
//    回归闸门：node tools/check-modules.js
const config = require('../../utils/config.js')
const app = getApp()

/**
 * 历史记录存储键
 * ⚠️ 带版本号：结果结构从「种类+白化」改为「覆盖率+珊瑚属」后，
 *    旧记录缺少 alivePct/coralTotal 等字段，会渲染成空白。
 *    提升版本号可让旧记录自动失效，避免脏数据。
 */
const HKEY = 'coral_history_v2'
const HMAX = 20

Page({
  data: {
    statusBarHeight: 20,
    state: 'upload',       // upload | preview | loading | result | error
    imgPath: '',
    savedImgPath: '',
    result: null,
    view: {},              // 预计算好的展示字段（WXML 不便做运算）
    errorMsg: '',
    imgFailed: false,     // 图片路径失效（临时文件被移动/清理）时的兜底标记
    history: [],
    // 点位选择（环境背景随点位变化；此前是写死仙本那核心区）
    sites: config.SITES,
    siteIndex: 0,
    siteName: config.SITES[0].name,
    locating: false,
    version: config.VERSION,
    // 年份选择（环境卡片的"年度等级"随年份变化）
    years: config.YEARS,          // 快捷芯片
    allYears: config.ALL_YEARS,   // 「其他年份」选择器的完整列表（1985–2025）
    yearIndex: 0,
    year: config.YEARS[0],
    yearIsQuick: true,            // 当前年份是否在快捷芯片里（WXML 不能调 indexOf，先在 JS 算好）
  },

  /* 统一设置年份：同步 yearIsQuick（决定"其他年份"那个芯片显示什么） */
  setYear(y) {
    const yy = Number(y)
    if (!yy) return
    this.setData({ year: yy, yearIsQuick: config.YEARS.indexOf(yy) !== -1 })
  },

  /* 把服务端返回的 availableYears 并入下拉列表（以实际数据为准；上次已选年份保留） */
  mergeAvailableYears(list) {
    if (!Array.isArray(list) || !list.length) return
    const ys = list.map(Number).filter((v) => v > 1900).sort((a, b) => b - a)
    if (!ys.length) return
    const same = ys.length === this.data.allYears.length &&
      ys.every((v, i) => v === this.data.allYears[i])
    if (!same) this.setData({ allYears: ys })
  },

  /* 当前使用的点位：定位点优先，否则用预设点 */
  currentSite() {
    return this.data.customSite || this.data.sites[this.data.siteIndex] || config.DEFAULT_SITE
  },

  /** 切换预设点位；已有结果时自动按新点位重跑，避免"卡片还是旧点位"的误解 */
  onSiteTap(e) {
    const idx = Number(e.currentTarget.dataset.index)
    const site = this.data.sites[idx]
    if (!site || idx === this.data.siteIndex) return
    this.setData({ siteIndex: idx, siteName: site.name, customSite: null })
    if (this.data.state === 'result' && this.data.imgPath) {
      this.startAnalysis()
    }
  },

  /** 点快捷年份芯片；已有结果时自动重跑，让"年度等级"立刻反映所选年份。
   *  用**年份值**判断选中（而不是下标），这样「其他年份」选择器选了 1998 时，
   *  快捷芯片里没有 1998 也不会误高亮。 */
  onYearTap(e) {
    const y = Number(e.currentTarget.dataset.year)
    if (!y || y === this.data.year) return
    this.setYear(y)
    if (this.data.state === 'result' && this.data.imgPath) {
      this.startAnalysis()
    }
  },

  /** 「其他年份」选择器：可从 1985–2025 全部 41 年里选 */
  onYearPick(e) {
    const y = Number(this.data.allYears[Number(e.detail.value)])
    if (!y || y === this.data.year) return
    this.setYear(y)
    if (this.data.state === 'result' && this.data.imgPath) {
      this.startAnalysis()
    }
  },

  /** 用定位作为点位；超出 NOAA 网格则提示（网格外后端会返回"无数据"） */
  useMyLocation() {
    const bb = config.GRID_BBOX
    if (this.data.locating) return
    this.setData({ locating: true })

    // ⚠️ 真机上 `wx.getLocation` 需满足两个前提，否则直接 fail：
    //   ① app.json 声明 `permission.scope.userLocation` 与 `requiredPrivateInfos: ["getLocation"]`（已声明）
    //   ② 用户已同意隐私授权 —— 新基础库需先调 `wx.requirePrivacyAuthorize`
    const locate = () => {
      wx.getLocation({
        type: 'gcj02',
        success: (res) => {
          const lat = Number(res.latitude)
          const lon = Number(res.longitude)
          const inside = lat >= bb.latMin && lat <= bb.latMax && lon >= bb.lonMin && lon <= bb.lonMax
          if (!inside) {
            this.setData({ locating: false })
            util.toast('当前位置不在 NOAA 覆盖网格内（仙本那及周边），请选预设点位')
            return
          }
          const site = { lat: lat, lon: lon, name: `我的位置 ${lat.toFixed(2)}N ${lon.toFixed(2)}E` }
          this.setData({ customSite: site, siteName: site.name, locating: false })
          if (this.data.state === 'result' && this.data.imgPath) this.startAnalysis()
        },
        fail: () => {
          this.setData({ locating: false })
          util.toast('定位不可用（未授权或未开启），已保留当前点位')
        },
      })
    }

    if (typeof wx.requirePrivacyAuthorize === 'function') {
      wx.requirePrivacyAuthorize({
        success: locate,
        fail: () => {
          this.setData({ locating: false })
          util.toast('需先同意隐私授权（含定位用途说明）才能使用「我的位置」')
        },
      })
    } else {
      locate()
    }
  },

  onLoad() {
    this.setData({
      statusBarHeight: (app.globalData && app.globalData.statusBarHeight) || 20
    })
    this.loadHistory()
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 3 })
    }
    // 兼容其它页面的跨 Tab 跳转参数（本页不再区分模式）
    if (app.globalData && app.globalData.pendingAiTab !== undefined) {
      delete app.globalData.pendingAiTab
    }
  },

  /* ==================== 选图 ==================== */
  chooseImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      sizeType: ['compressed'],
      success: (res) => {
        const f = res.tempFiles && res.tempFiles[0]
        if (!f) return
        this.setData({ state: 'preview', imgPath: f.tempFilePath, result: null, errorMsg: '' })
      },
      fail: (err) => {
        // 用户主动取消不提示
        if (err && (err.errMsg || '').indexOf('cancel') === -1) {
          util.toast('选择图片失败，请检查相册/相机权限')
        }
      }
    })
  },

  resetUpload() {
    this.setData({ state: 'upload', imgPath: '', savedImgPath: '', result: null, errorMsg: '', imgFailed: false })
  },

  /** 图片路径失效时的兜底（历史记录里可能存着上个会话的临时路径）：
   *  DevTools 的临时目录端口每次会话都会变，旧路径必然 404 —— 显示占位而不是裂图。 */
  onImgError() {
    if (!this.data.imgFailed) this.setData({ imgFailed: true })
  },

  onHistoryImgError(e) {
    const id = e.currentTarget.dataset.id
    this.setData({
      history: this.data.history.map((h) => (h.id === id ? Object.assign({}, h, { img: '' }) : h)),
    })
  },

  /* 把接口结果转成视图字段（百分比等） */
  /* 环境数据视图（NOAA 海表热压力）
   * dep = 后端同一次返回里的 deployment（41 年历史热压力档案），无需额外请求。
   * ⚠️ 卡片展示的是**年度等级**（该年 DHW 峰值对应的 BAA），不是实时状态，
   *    因此补一行"该点位历史"与"建议避开月份"，避免把单年等级误读为常态。 */
  buildClimateView(cl, dep) {
    if (!cl || !cl.ok) return null
    const lvl = cl.baa >= 3 ? 'danger' : cl.baa === 2 ? 'warn' : 'ok'
    const d = dep && dep.ok ? dep : null
    const alertYears = (d && d.alertYears) || []
    const severeYears = (d && d.severeYears) || []
    const avoid = (d && d.avoidMonths) || []
    const monthTxt = (arr) => arr.map((m) => m + ' 月').join('、')
    return {
      year: cl.year,
      gridLat: cl.gridCell && cl.gridCell.lat,
      gridLon: cl.gridCell && cl.gridCell.lon,
      dhwMax: cl.dhwMax,
      baa: cl.baa,
      baaLabel: cl.baaLabel,
      level: lvl,
      daysGe4: cl.daysDhwGe4,
      daysGe8: cl.daysDhwGe8,
      // —— 年度等级口径提示 + 41 年历史（来自同一响应的 deployment）——
      hasHistory: !!d,
      siteName: this.data.siteName || config.DEFAULT_SITE.name,
      historyYears: d ? d.nYears : 0,
      historyText: d ? `${(d.alertYears || []).length} 年达警戒`
        + (alertYears.length ? `（${alertYears.join('、')}）` : '') : '',
      severeText: severeYears.length ? `${severeYears.length} 年达严重档（${severeYears.join('、')}）` : '',
      avoidText: avoid.length ? monthTxt(avoid) : '',
      avoidNote: d && d.riskLevel === 'high' ? '该点位历史上反复发生白化，不建议投放' : '',
      anomalyNote: cl.anomalyNote || '',
      verdict: cl.verdict || '',
      peakDate: cl.peakDate || '',
      source: cl.source || ''
    }
  },

  /* 综合研判视图（修复优先级 + 苗投放建议） */
  buildRestorationView(r) {
    if (!r || !r.ok) return null
    return {
      priority: Math.round(Number(r.priority || 0)),
      gradeLabel: r.gradeLabel || '',
      grade: r.grade || 'medium',
      seedling: Math.round(Number(r.seedlingSuitability || 0)),
      recovery: Math.round(Number((r.recovery && r.recovery.score) || 0)),
      urgency: Math.round(Number((r.urgency && r.urgency.score) || 0)),
      actions: (r.actions || []).map((a) => String(a).replace(/\*\*/g, '')),
      report: r.report || '',
      reasoning: r.reasoning || '',
      disclaimer: r.disclaimer || '',
      hasReport: !!(r.report && r.report.length > 40)
    }
  },

  buildView(res) {
    const c = res.cover || {}
    const cr = res.coralRegion || {}
    const toPct = (v) => Math.round((Number(v) || 0) * 1000) / 10

    // 功能群占比条（按保育关注度排序）
    const GROUPS = [
      { key: 'alivePct', name: '活珊瑚', cls: 'alive' },
      { key: 'bleachedPct', name: '白化珊瑚', cls: 'bleached' },
      { key: 'deadPct', name: '死亡珊瑚', cls: 'dead' },
      { key: 'algaePct', name: '藻类覆盖', cls: 'algae' },
      { key: 'substratePct', name: '沙砾底质', cls: 'substrate' }
    ]
    const groupBars = GROUPS.map((g) => ({
      key: g.key,
      name: g.name,
      cls: g.cls,
      pct: toPct(c[g.key]),
      raw: Number(c[g.key]) || 0
    }))

    // 珊瑚属识别（来自分割掩膜裁剪区域）
    const genusTop = (cr.top || []).map((t) => ({
      genus: t.genus,
      pct: toPct(t.confidence)
    }))

    const bleachingShare = toPct(c.bleachingShareOfCoral)
    const coralTotal = toPct(c.coralTotalPct)

    // 拍摄条件自检：超出适用边界时，覆盖率数字不可信，页面必须显著提示
    const q = res.captureQuality || {}
    const quality = {
      level: q.level || 'unknown',
      usable: q.usable !== false,
      contrast: q.contrast != null ? Math.round(q.contrast * 10000) / 10000 : null,
      message: q.message || '',
      // 阈值由服务端下发（避免前端写死后与实际标定值失配）
      goodContrast: (q.thresholds && q.thresholds.goodContrast) != null
        ? q.thresholds.goodContrast : 0.0306
    }

    // 白化状态：来自**分类模型**（不是分割模型的 bleachedPct —— 后者经实测跨域无效）
    const bl = res.bleaching || null
    const bleachView = bl ? {
      label: bl.label || '',
      labelCn: bl.labelCn || '',
      pct: Math.round((Number(bl.confidence) || 0) * 1000) / 10,
      reliable: bl.reliable !== false,
      model: bl.model || '',
      probs: Object.keys(bl.probabilities || {}).map((k) => ({
        key: k,
        name: ({ bleached: '白化', healthy: '健康', dead: '死亡' })[k.toLowerCase()] || k,
        pct: Math.round((Number(bl.probabilities[k]) || 0) * 1000) / 10
      })).sort((a, b) => b.pct - a.pct)
    } : null

    return {
      groupBars,
      coralTotal,
      bleachingShare,
      bleachView,
      hasBleach: !!bleachView,
      genusTop,
      hasGenus: genusTop.length > 0,
      genusUnreliable: !!(cr && cr.reliable === false),
      // 本次识别用的点位与前端版本（便于确认"跑的是哪版代码/哪个点位"）
      siteName: this.data.siteName || config.DEFAULT_SITE.name,
      version: config.VERSION,
      quality,
      qualityWarn: quality.level === 'warn',
      qualityPoor: quality.level === 'poor',
      // 服务不可用时的降级标记（不冒充真实结果）
      isDemo: !!res.isDemo,
      demoReason: res.demoReason || '',
      topClasses: (res.topClasses || []).slice(0, 5).map((t) => ({
        name: t.name, pct: toPct(t.pct)
      })),
      // 白化占比 > 10% 时给出提示（阈值可按项目口径调整）
      bleachAlert: Number(c.bleachingShareOfCoral || 0) > 0.10,
      inferenceMs: res.inferenceMs || 0,
        // 环境数据（NOAA 海表热压力）
        climate: this.buildClimateView(res.climate, res.deployment),
        // 综合研判（修复优先级 + 苗投放建议 + 保育报告）
        restoration: this.buildRestorationView(res.restoration)
    }
  },

  /* ==================== 识别 ==================== */
  startAnalysis() {
    if (!this.data.imgPath) return
    this.setData({ state: 'loading', errorMsg: '' })

    // ⚠️ 整段包 try/catch：参数求值阶段的**同步异常**（如变量未定义）不会进入 .catch，
    //    会把页面永久留在 loading（曾因 config 未 require 真实踩到）。这里兜底成 error 态。
    try {
      const p = api.recognize(this.data.imgPath, this.currentSite(), this.data.year)
      if (!p || typeof p.then !== 'function') {
        this.setData({ state: 'error', errorMsg: '识别接口返回异常（未返回 Promise）' })
        return
      }
      p.then((res) => {
        this.setData({
          state: 'result',
          result: res,
          view: this.buildView(res)
        })
        // 用服务端返回的 availableYears 校准年份下拉（以实际数据为准，防止列表与后端不一致）
        if (res && res.climate && res.climate.availableYears) {
          this.mergeAvailableYears(res.climate.availableYears)
        }
        this.persistAndRecord(res)
      }).catch((e) => {
        this.setData({
          state: 'error',
          errorMsg: (e && e.message) || '评估失败，请重试'
        })
      })
    } catch (e) {
      this.setData({ state: 'error', errorMsg: (e && e.message) || '识别启动失败，请重试' })
    }
  },

  onRetry() {
    if (this.data.imgPath) this.startAnalysis()
    else this.resetUpload()
  },

  /* ==================== 历史记录（本地持久化） ==================== */
  persistAndRecord(res) {
    const c = res.cover || {}
    const cr = res.coralRegion || {}
    const topGenus = (cr.top && cr.top[0] && cr.top[0].genus) || ''
    // 图片转存到本地用户目录，避免临时文件失效
    const finish = (savedPath) => {
      const list = this.data.history.slice()
      list.unshift({
        // ⚠️ 不能只用 Date.now()：连续两次分析落在同一毫秒会 ID 冲突，
        //    导致 onHistoryTap 取到错误记录。加随机后缀保证唯一。
        id: Date.now() + '-' + Math.random().toString(36).slice(2, 8),
        time: this.formatTime(new Date()),
        img: savedPath || this.data.imgPath,
        alivePct: Number(c.alivePct) || 0,
        bleachedPct: Number(c.bleachedPct) || 0,
        deadPct: Number(c.deadPct) || 0,
        coralTotalPct: Number(c.coralTotalPct) || 0,
        bleachingShare: Number(c.bleachingShareOfCoral) || 0,
        topGenus: topGenus,
        result: res
      })
      const trimmed = list.slice(0, HMAX)
      wx.setStorageSync(HKEY, trimmed)
      // ⚠️ `FileSystemManager.saveFile` 会**移动**临时文件：调用成功后 `tempFilePath` 就不可用了。
      //    所以保存成功后必须把 imgPath 也换成持久路径，否则预览图/结果图会加载失败
      //    （DevTools 控制台报 `Failed to load image .../__tmp__/xxx.jpg`，真机上同样会白图）。
      const shown = savedPath || this.data.imgPath
      this.setData({ history: trimmed, savedImgPath: savedPath || '', imgPath: shown, imgFailed: false })
    }

    try {
      wx.getFileSystemManager().saveFile({
        tempFilePath: this.data.imgPath,
        success: (r) => finish(r.savedFilePath),
        fail: () => finish('')
      })
    } catch (e) {
      finish('')
    }
  },

  loadHistory() {
    const list = wx.getStorageSync(HKEY)
    this.setData({ history: Array.isArray(list) ? list : [] })
  },

  onHistoryTap(e) {
    const id = e.currentTarget.dataset.id
    const item = this.data.history.filter((h) => h.id === id)[0]
    if (!item || !item.result) {
      util.toast('该记录缺少完整数据')
      return
    }
    this.setData({
      state: 'result',
      result: item.result,
      view: this.buildView(item.result),
      imgPath: item.img || '',
      imgFailed: false,      // 新记录重新尝试加载；若路径已失效由 onImgError 兜底
    })
    wx.pageScrollTo({ scrollTop: 0, duration: 200 })
  },

  clearHistory() {
    if (!this.data.history.length) return
    wx.showModal({
      title: '清空识别历史',
      content: '将删除本机保存的 ' + this.data.history.length + ' 条识别记录，确定吗？',
      confirmColor: '#FF7043',
      success: (r) => {
        if (!r.confirm) return
        wx.removeStorageSync(HKEY)
        this.setData({ history: [] })
        util.toast('已清空')
      }
    })
  },

  /* 服务状态自检：评估失败时帮用户定位问题 */
  checkService() {
    util.toast('正在检查评估服务...')
    wx.request({
      url: require('../../utils/config.js').CORAL_API + '/health',
      timeout: 8000,
      success: (r) => {
        if (r.statusCode === 200 && r.data && r.data.status === 'ok') {
          const d = r.data
          const seg = d.segmentation === 'loaded' ? '分割已加载' : '分割缺失'
          const sp = d.species === 'loaded' ? '属分类已加载' : '属分类未训练'
          util.toast('服务正常 · ' + seg + ' · ' + sp, 'success')
        } else {
          util.toast('服务返回异常，请检查 serve_fusion.py')
        }
      },
      fail: () => util.toast('服务未启动：请运行 python serve_fusion.py')
    })
  },

  formatTime(d) {
    const p = (n) => (n < 10 ? '0' + n : '' + n)
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) +
      ' ' + p(d.getHours()) + ':' + p(d.getMinutes())
  },

  /* ==================== 分享 ==================== */
  onShareAppMessage() {
    const v = this.data.view || {}
    const title = v.coralTotal != null
      ? '这片礁区珊瑚覆盖 ' + v.coralTotal + '%，一起来守护珊瑚礁'
      : '蓝珊AI · 拍照评估礁区覆盖率与珊瑚属'
    return { title, path: '/pages/ai/ai' }
  }
})
