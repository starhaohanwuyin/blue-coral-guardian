/**
 * 页面级中英文（让"每个页面都能切语言"只写一行）
 *
 * 用法（页面 JS）：
 *     const pageI18n = require('../../utils/page-i18n.js')
 *     Page(pageI18n.wrap({
 *       data: { ... },
 *       onLoad() { ... },
 *     }))
 *
 * 它会做四件事，页面自己不用再写：
 *   ① 注入 t：整本词条（i18n.all()）→ WXML 里 {{t.xxx}} 直接用，不用维护 T_KEYS
 *   ② 翻译数据：英文时把 setData 里的中文按短语表换成英文
 *      （所以文章正文、题目、商品名这类"内容"也能跟着切，不用逐个写 map 函数）
 *   ③ 翻译提示：wx.showToast / wx.showModal 的 title/content 走同一张短语表
 *   ④ 语言切换后重渲染：onShow 时发现语言变了，就用**原始数据**重算一遍
 *
 * 说明：只做"整串精确匹配"，匹配不到就原样保留（所以不会误伤 id、数字、用户输入）。
 */
const i18n = require('./i18n.js')
let TITLES = {}
try { TITLES = require('./i18n-titles.js') } catch (e) { TITLES = {} }

const CJK = /[\u4e00-\u9fff]/

function translateValue(v) {
  if (!i18n.isEn() || !v) return v
  if (typeof v === 'string') {
    const hit = i18n.tr(v)
    return hit
  }
  if (Array.isArray(v)) return v.map(translateValue)
  if (v && typeof v === 'object') {
    const out = {}
    Object.keys(v).forEach((k) => { out[k] = translateValue(v[k]) })
    return out
  }
  return v
}

/** 翻译一整个 setData 载荷（英文时才翻译） */
function translatePayload(payload) {
  if (!i18n.isEn() || !payload) return payload
  return translateValue(payload)
}

/** 当前页面的词条前缀：pages/index/index → index。
 *  拿不到路由时返回空串（等于只用整本拍平表，行为与修复前一致，不会报错）。 */
function pagePrefixOf(inst) {
  let route = (inst && (inst.route || inst.__route)) || ''
  if (!route && typeof getCurrentPages === 'function') {
    try {
      const stack = getCurrentPages() || []
      const last = stack[stack.length - 1]
      route = (last && (last.route || last.__route)) || ''
    } catch (e) { route = '' }
  }
  const seg = String(route).split('/').filter(Boolean)
  return seg.length ? seg[seg.length - 1] : ''
}

function wrap(cfg) {
  const page = cfg || {}
  const rawOnLoad = page.onLoad
  const rawOnShow = page.onShow
  const rawOnUnload = page.onUnload
  hookDialogs()

  const applyLang = function () {
    const changed = this.data.lang !== undefined && this.data.lang !== i18n.getLang()
    // ⚠️ t 必须**按页面作用域**：整本拍平表里 `index.brand` 与 `knowledge.brand` 都叫 `brand`，
    //    后遍历到的会覆盖前面的 → 首页曾显示科普页的品牌名「📚 珊瑚科普」。
    //    这里用「本页前缀的词条」覆盖全局拍平表，各页各取自己的值。
    const prefix = pagePrefixOf(this)
    const next = {
      t: Object.assign({}, i18n.all(), i18n.pageFlat ? i18n.pageFlat(prefix) : {}),
      lang: i18n.getLang(),
    }
    // 语言变了 → 用原始数据重算，避免"翻了两遍"
    if (changed && this.__rawData) {
      const raw = Object.assign({}, this.__rawData)
      delete raw.t
      delete raw.lang
      Object.assign(next, translatePayload(raw))
    }
    this.setData(next)
    // 导航栏标题也要跟着切（页面 json 里写死的是中文）
    try {
      const route = this.route || this.__route || ''
      const zh = TITLES[route] || TITLES['/' + route]
      if (zh && typeof wx !== 'undefined' && wx.setNavigationBarTitle) {
        wx.setNavigationBarTitle({ title: i18n.tr(zh) })
      }
    } catch (e) { /* 标题设置失败不影响页面 */ }
  }

  page.onLoad = function (query) {
    const self = this
    // 记录 setData 进来的原始（中文）数据，供切换语言时重算；
    // 只把「含中文的字符串」当原始值，避免页面把已翻译的英文回写进来后覆盖掉中文
    this.__rawData = {}
    Object.keys(this.data || {}).forEach((k) => {
      if (typeof this.data[k] === 'string' && CJK.test(this.data[k])) this.__rawData[k] = this.data[k]
    })
    const rawSetData = this.setData.bind(this)
    this.setData = function (obj, cb) {
      if (obj && typeof obj === 'object') {
        Object.keys(obj).forEach((k) => {
          const v = obj[k]
          if (typeof v === 'string') {
            if (CJK.test(v)) self.__rawData[k] = v
          } else if (!(k in self.__rawData)) {
            self.__rawData[k] = v
          }
        })
      }
      // 已翻译过的数据再次 setData 时不会被重复翻译（表里查不到英文）
      return rawSetData(translatePayload(Object.assign({}, obj)), cb)
    }
    applyLang.call(this)
    if (rawOnLoad) rawOnLoad.call(this, query)
  }

  page.onShow = function () {
    if (rawOnShow) rawOnShow.call(this)
    applyLang.call(this)
  }

  page.onUnload = function () {
    if (rawOnUnload) rawOnUnload.call(this, ...arguments)
  }

  return page
}

/* 把 wx.showToast / showModal 的文案也接上短语表（只挂一次） */
let dialogsHooked = false
function hookDialogs() {
  if (dialogsHooked || typeof wx === 'undefined') return
  dialogsHooked = true
  const rawToast = wx.showToast
  const rawModal = wx.showModal
  if (typeof rawToast === 'function') {
    wx.showToast = function (o) {
      const n = Object.assign({}, o)
      if (n.title && typeof n.title === 'string') n.title = i18n.tr(n.title)
      return rawToast.call(wx, n)
    }
  }
  if (typeof rawModal === 'function') {
    wx.showModal = function (o) {
      const n = Object.assign({}, o)
      if (n.title) n.title = i18n.tr(n.title)
      if (n.content) n.content = i18n.tr(n.content)
      return rawModal.call(wx, n)
    }
  }
}

module.exports = { wrap: wrap, translateValue: translateValue, translatePayload: translatePayload,
                   hookDialogs: hookDialogs }
