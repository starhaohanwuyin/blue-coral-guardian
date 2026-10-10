/**
 * 绀佸尯鏅鸿兘璇勪及椤?
 * ------------------------------------------------------------------
 * 涓€娆′笂浼狅紝涓夌被缁撴灉锛?
 *   1. 绀佸尯瑕嗙洊璇勪及锛堣涔夊垎鍓诧級锛氭椿鐝婄憵 / 鐧藉寲 / 姝讳骸 / 钘荤被 / 娌欑牼 鐧惧垎姣?
 *   2. 涓昏鐝婄憵灞炶瘑鍒紙鍦ㄥ垎鍓插嚭鐨勭強鐟氬尯鍩熶笂鍋氬睘绾у垎绫伙級
 *   3. 涓昏搴曟爾绫诲埆鏄庣粏
 *
 * 鏁版嵁鏉ヨ嚜铻嶅悎鎺ㄧ悊鏈嶅姟锛坈oral_ml/scripts/serve_fusion.py锛夛細
 *   config.USE_REAL_AI = true  鈫?璋冪敤鐪熷疄鏈嶅姟
 *   config.USE_REAL_AI = false 鈫?浣跨敤鏈湴婕旂ず鏁版嵁锛堢粨鏋勪竴鑷达紝渚夸簬鏃犳湇鍔℃紨绀猴級
 *
 * 瀹夊叏浣跨敤杈圭晫锛堝凡瀹炴祴閲忓寲锛夛細
 *   路 鎷嶆憚娣卞害 鈮?m 鏃惰鐩栫巼浼拌璇樊 鈮?.2%锛?5m 浠ヤ笂娴戞祳姘村煙鏄捐憲澶辨晥
 *   路 椤甸潰鍥哄畾灞曠ず浣跨敤杈圭晫涓庡厤璐ｅ０鏄?
 *   路 鏄熷湴楠岃瘉锛氭ā鍨嬩及璁?39.71% vs RCM 瀹炲湴 39.56%
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')
// 鈿狅笍 蹇呴』鏄惧紡 require锛氭澶勬浘婕忔帀锛屽鑷?startAnalysis 閲?`config.DEFAULT_SITE` 鎶?
//    ReferenceError锛堝悓姝ユ姏鍑恒€乸romise 鏈缓绔嬶級锛岄〉闈㈡案杩滃仠鍦?loading 涓斾笉鍙戣姹傘€?
const config = require('../../utils/config.js')
const app = getApp()

/**
 * 鍘嗗彶璁板綍瀛樺偍閿?
 * 鈿狅笍 甯︾増鏈彿锛氱粨鏋滅粨鏋勪粠銆岀绫?鐧藉寲銆嶆敼涓恒€岃鐩栫巼+鐝婄憵灞炪€嶅悗锛?
 *    鏃ц褰曠己灏?alivePct/coralTotal 绛夊瓧娈碉紝浼氭覆鏌撴垚绌虹櫧銆?
 *    鎻愬崌鐗堟湰鍙峰彲璁╂棫璁板綍鑷姩澶辨晥锛岄伩鍏嶈剰鏁版嵁銆?
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
    view: {},              // 棰勮绠楀ソ鐨勫睍绀哄瓧娈碉紙WXML 涓嶄究鍋氳繍绠楋級
    errorMsg: '',
    history: []
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
    // 鍏煎鍏跺畠椤甸潰鐨勮法 Tab 璺宠浆鍙傛暟锛堟湰椤典笉鍐嶅尯鍒嗘ā寮忥級
    if (app.globalData && app.globalData.pendingAiTab !== undefined) {
      delete app.globalData.pendingAiTab
    }
  },

  /* ==================== 閫夊浘 ==================== */
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
        // 鐢ㄦ埛涓诲姩鍙栨秷涓嶆彁绀?
        if (err && (err.errMsg || '').indexOf('cancel') === -1) {
          util.toast('閫夋嫨鍥剧墖澶辫触锛岃妫€鏌ョ浉鍐?鐩告満鏉冮檺')
        }
      }
    })
  },

  resetUpload() {
    this.setData({ state: 'upload', imgPath: '', savedImgPath: '', result: null, errorMsg: '' })
  },

  /* 鎶婃帴鍙ｇ粨鏋滆浆鎴愯鍥惧瓧娈碉紙鐧惧垎姣旂瓑锛?*/
  /* 鐜鏁版嵁瑙嗗浘锛圢OAA 娴疯〃鐑帇鍔涳級 */
  buildClimateView(cl) {
    if (!cl || !cl.ok) return null
    const lvl = cl.baa >= 3 ? 'danger' : cl.baa === 2 ? 'warn' : 'ok'
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
      anomalyNote: cl.anomalyNote || '',
      verdict: cl.verdict || '',
      peakDate: cl.peakDate || '',
      source: cl.source || ''
    }
  },

  /* 缁煎悎鐮斿垽瑙嗗浘锛堜慨澶嶄紭鍏堢骇 + 鑻楁姇鏀惧缓璁級 */
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

    // 鍔熻兘缇ゅ崰姣旀潯锛堟寜淇濊偛鍏虫敞搴︽帓搴忥級
    const GROUPS = [
      { key: 'alivePct', name: '娲荤強鐟?, cls: 'alive' },
      { key: 'bleachedPct', name: '鐧藉寲鐝婄憵', cls: 'bleached' },
      { key: 'deadPct', name: '姝讳骸鐝婄憵', cls: 'dead' },
      { key: 'algaePct', name: '钘荤被瑕嗙洊', cls: 'algae' },
      { key: 'substratePct', name: '娌欑牼搴曡川', cls: 'substrate' }
    ]
    const groupBars = GROUPS.map((g) => ({
      key: g.key,
      name: g.name,
      cls: g.cls,
      pct: toPct(c[g.key]),
      raw: Number(c[g.key]) || 0
    }))

    // 鐝婄憵灞炶瘑鍒紙鏉ヨ嚜鍒嗗壊鎺╄啘瑁佸壀鍖哄煙锛?
    const genusTop = (cr.top || []).map((t) => ({
      genus: t.genus,
      pct: toPct(t.confidence)
    }))

    const bleachingShare = toPct(c.bleachingShareOfCoral)
    const coralTotal = toPct(c.coralTotalPct)

    // 鎷嶆憚鏉′欢鑷锛氳秴鍑洪€傜敤杈圭晫鏃讹紝瑕嗙洊鐜囨暟瀛椾笉鍙俊锛岄〉闈㈠繀椤绘樉钁楁彁绀?
    const q = res.captureQuality || {}
    const quality = {
      level: q.level || 'unknown',
      usable: q.usable !== false,
      contrast: q.contrast != null ? Math.round(q.contrast * 10000) / 10000 : null,
      message: q.message || '',
      // 闃堝€肩敱鏈嶅姟绔笅鍙戯紙閬垮厤鍓嶇鍐欐鍚庝笌瀹為檯鏍囧畾鍊煎け閰嶏級
      goodContrast: (q.thresholds && q.thresholds.goodContrast) != null
        ? q.thresholds.goodContrast : 0.0306
    }

    // 鐧藉寲鐘舵€侊細鏉ヨ嚜**鍒嗙被妯″瀷**锛堜笉鏄垎鍓叉ā鍨嬬殑 bleachedPct 鈥斺€?鍚庤€呯粡瀹炴祴璺ㄥ煙鏃犳晥锛?
    const bl = res.bleaching || null
    const bleachView = bl ? {
      label: bl.label || '',
      labelCn: bl.labelCn || '',
      pct: Math.round((Number(bl.confidence) || 0) * 1000) / 10,
      reliable: bl.reliable !== false,
      model: bl.model || '',
      probs: Object.keys(bl.probabilities || {}).map((k) => ({
        key: k,
        name: ({ bleached: '鐧藉寲', healthy: '鍋ュ悍', dead: '姝讳骸' })[k.toLowerCase()] || k,
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
      genusNote: (cr && cr.note) || '',
      quality,
      qualityWarn: quality.level === 'warn',
      qualityPoor: quality.level === 'poor',
      // 鏈嶅姟涓嶅彲鐢ㄦ椂鐨勯檷绾ф爣璁帮紙涓嶅啋鍏呯湡瀹炵粨鏋滐級
      isDemo: !!res.isDemo,
      demoReason: res.demoReason || '',
      topClasses: (res.topClasses || []).slice(0, 5).map((t) => ({
        name: t.name, pct: toPct(t.pct)
      })),
      // 鐧藉寲鍗犳瘮 > 10% 鏃剁粰鍑烘彁绀猴紙闃堝€煎彲鎸夐」鐩彛寰勮皟鏁达級
      bleachAlert: Number(c.bleachingShareOfCoral || 0) > 0.10,
      inferenceMs: res.inferenceMs || 0,
        // 鐜鏁版嵁锛圢OAA 娴疯〃鐑帇鍔涳級
        climate: this.buildClimateView(res.climate),
        // 缁煎悎鐮斿垽锛堜慨澶嶄紭鍏堢骇 + 鑻楁姇鏀惧缓璁?+ 淇濊偛鎶ュ憡锛?
        restoration: this.buildRestorationView(res.restoration)
    }
  },

  /* ==================== 璇嗗埆 ==================== */
  startAnalysis() {
    if (!this.data.imgPath) return
    this.setData({ state: 'loading', errorMsg: '' })

    // 鈿狅笍 鏁存鍖?try/catch锛氬弬鏁版眰鍊奸樁娈电殑**鍚屾寮傚父**锛堝鍙橀噺鏈畾涔夛級涓嶄細杩涘叆 .catch锛?
    //    浼氭妸椤甸潰姘镐箙鐣欏湪 loading锛堟浘鍥?config 鏈?require 鐪熷疄韪╁埌锛夈€傝繖閲屽厹搴曟垚 error 鎬併€?
    try {
      const p = api.recognize(this.data.imgPath, config.DEFAULT_SITE, config.DEFAULT_YEAR)
      if (!p || typeof p.then !== 'function') {
        this.setData({ state: 'error', errorMsg: '璇嗗埆鎺ュ彛杩斿洖寮傚父锛堟湭杩斿洖 Promise锛? })
        return
      }
      p.then((res) => {
        this.setData({
          state: 'result',
          result: res,
          view: this.buildView(res)
        })
        this.persistAndRecord(res)
      }).catch((e) => {
        this.setData({
          state: 'error',
          errorMsg: (e && e.message) || '璇勪及澶辫触锛岃閲嶈瘯'
        })
      })
    } catch (e) {
      this.setData({ state: 'error', errorMsg: (e && e.message) || '璇嗗埆鍚姩澶辫触锛岃閲嶈瘯' })
    }
  },

  onRetry() {
    if (this.data.imgPath) this.startAnalysis()
    else this.resetUpload()
  },

  /* ==================== 鍘嗗彶璁板綍锛堟湰鍦版寔涔呭寲锛?==================== */
  persistAndRecord(res) {
    const c = res.cover || {}
    const cr = res.coralRegion || {}
    const topGenus = (cr.top && cr.top[0] && cr.top[0].genus) || ''
    // 鍥剧墖杞瓨鍒版湰鍦扮敤鎴风洰褰曪紝閬垮厤涓存椂鏂囦欢澶辨晥
    const finish = (savedPath) => {
      const list = this.data.history.slice()
      list.unshift({
        // 鈿狅笍 涓嶈兘鍙敤 Date.now()锛氳繛缁袱娆″垎鏋愯惤鍦ㄥ悓涓€姣浼?ID 鍐茬獊锛?
        //    瀵艰嚧 onHistoryTap 鍙栧埌閿欒璁板綍銆傚姞闅忔満鍚庣紑淇濊瘉鍞竴銆?
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
      this.setData({ history: trimmed, savedImgPath: savedPath || '' })
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
      util.toast('璇ヨ褰曠己灏戝畬鏁存暟鎹?)
      return
    }
    this.setData({
      state: 'result',
      result: item.result,
      view: this.buildView(item.result),
      imgPath: item.img || ''
    })
    wx.pageScrollTo({ scrollTop: 0, duration: 200 })
  },

  clearHistory() {
    if (!this.data.history.length) return
    wx.showModal({
      title: '娓呯┖璇嗗埆鍘嗗彶',
      content: '灏嗗垹闄ゆ湰鏈轰繚瀛樼殑 ' + this.data.history.length + ' 鏉¤瘑鍒褰曪紝纭畾鍚楋紵',
      confirmColor: '#FF7043',
      success: (r) => {
        if (!r.confirm) return
        wx.removeStorageSync(HKEY)
        this.setData({ history: [] })
        util.toast('宸叉竻绌?)
      }
    })
  },

  /* 鏈嶅姟鐘舵€佽嚜妫€锛氳瘎浼板け璐ユ椂甯敤鎴峰畾浣嶉棶棰?*/
  checkService() {
    util.toast('姝ｅ湪妫€鏌ヨ瘎浼版湇鍔?..')
    wx.request({
      url: require('../../utils/config.js').CORAL_API + '/health',
      timeout: 8000,
      success: (r) => {
        if (r.statusCode === 200 && r.data && r.data.status === 'ok') {
          const d = r.data
          const seg = d.segmentation === 'loaded' ? '鍒嗗壊宸插姞杞? : '鍒嗗壊缂哄け'
          const sp = d.species === 'loaded' ? '灞炲垎绫诲凡鍔犺浇' : '灞炲垎绫绘湭璁粌'
          util.toast('鏈嶅姟姝ｅ父 路 ' + seg + ' 路 ' + sp, 'success')
        } else {
          util.toast('鏈嶅姟杩斿洖寮傚父锛岃妫€鏌?serve_fusion.py')
        }
      },
      fail: () => util.toast('鏈嶅姟鏈惎鍔細璇疯繍琛?python serve_fusion.py')
    })
  },

  formatTime(d) {
    const p = (n) => (n < 10 ? '0' + n : '' + n)
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) +
      ' ' + p(d.getHours()) + ':' + p(d.getMinutes())
  },

  /* ==================== 鍒嗕韩 ==================== */
  onShareAppMessage() {
    const v = this.data.view || {}
    const title = v.coralTotal != null
      ? '杩欑墖绀佸尯鐝婄憵瑕嗙洊 ' + v.coralTotal + '%锛屼竴璧锋潵瀹堟姢鐝婄憵绀?
      : '钃濈強AI 路 鎷嶇収璇勪及绀佸尯瑕嗙洊鐜囦笌鐝婄憵灞?
    return { title, path: '/pages/ai/ai' }
  }
})
