/* ============================================================================
 * 小程序运行时（浏览器版）—— 让小程序页面 JS/WXML 直接跑在网页里
 * ----------------------------------------------------------------------------
 * 组成：
 *   ① CommonJS 加载器（复用小程序 utils/*.js 原样代码）
 *   ② wx.* shim（约 30 个 API：导航/存储/弹窗/请求/上传/定位/画布…）
 *   ③ App()/Page() shim（data + setData + 生命周期 + 事件派发）
 *   ④ WXML 模板树渲染器（{{表达式}} 用 new Function 求值）
 *   ⑤ 哈希路由 + tabBar + 返回 + 弹层
 * 说明：小程序页面源码**零改动**，差异全部由本文件吸收。
 * ==========================================================================*/
(function () {
  'use strict';

  /* 版本参数（缓存穿透）-------------------------------------------------------
   * 为什么需要：运行时代码/模板/样式以前用裸 URL 抓取（/mp/pages/x/x.js），
   * 浏览器（Edge/Chrome 的启发式缓存）会长期缓存旧文件且不回头校验 → 出现
   * 「代码改了、页面却还是旧的」（详情页打不开、文案不更新都栽在这里）。
   * 现在从自己的 <script src="…/mp.js?v=xxx"> 上取版本号，拼到所有运行时请求上：
   * index.html 里 v 一变，整套 /mp/** 立刻全部重新抓取，普通刷新即可（不用清缓存）。
   * v 的值由 tools/build_web_pages.py 每次构建自动更新。 */
  const VER = (function () {
    try {
      const s = document.currentScript;
      const m = s && s.src && s.src.match(/[?&]v=([^&]+)/);
      return m ? m[1] : '';
    } catch (e) { return ''; }
  })();
  const VQ = VER ? ('?v=' + encodeURIComponent(VER)) : '';

  const MP = '/mp/';                       // 运行时代码根（由 serve_fusion 静态托管）
  const SRC = Object.create(null);         // 路径 -> 源码文本（先抓取，再同步 require）
  const CACHE = Object.create(null);       // 路径 -> module.exports
  let curDir = MP;                         // require 的相对基准
  const EXPR_CACHE = Object.create(null);  // 表达式 -> 编译后的函数
  // 诊断计数（仅当 URL 带 mpdebug=1 时写入 DOM，便于 headless 排查）
  const DBG = /(?:^|[?&])mpdebug=1/.test(location.search);
  const CNT = { setData: 0, paint: 0, page: '', info: '', html: 0 };
  function dbg() {
    if (!DBG) return;
    document.documentElement.setAttribute('data-dbg',
      `setData=${CNT.setData} paint=${CNT.paint} page=${CNT.page} html=${CNT.html} info=${CNT.info}`);
  }

  /* ---------------------------------------------------------------- 1. 加载器 */
  function normalize(p) {
    // 以 / 开头 = 站点绝对路径（运行时内部用的都是这种，如 /mp/pages/index/index.js）
    // 否则按 require 的相对语义，基于当前模块目录解析（小程序源码里的 '../../utils/x.js'）
    const raw = p.charAt(0) === '/' ? p.slice(1) : (curDir.replace(/^\//, '') + p);
    const parts = raw.split('/');
    const out = [];
    for (const seg of parts) {
      if (!seg || seg === '.') continue;
      if (seg === '..') out.pop();
      else out.push(seg);
    }
    return '/' + out.join('/');
  }
  function require(p) {
    const path = normalize(p);
    if (CACHE[path]) return CACHE[path].exports;
    const text = SRC[path];
    if (text == null) throw new Error('require 失败（未预加载）: ' + path);
    const mod = { exports: {} };
    CACHE[path] = mod;
    const prev = curDir;
    curDir = path.slice(0, path.lastIndexOf('/') + 1);
    try {
      const fn = new Function('module', 'exports', 'require', 'wx', 'getApp', 'App', 'Page',
                              'Component', 'console', text + '\n//# sourceURL=' + path);
      fn(mod, mod.exports, require, wx, getApp, App, Page, Component, console);
    } finally {
      curDir = prev;
    }
    return mod.exports;
  }
  async function preload(paths) {
    await Promise.all(paths.map(async (p) => {
      if (SRC[p] != null) return;
      const r = await fetch(p + VQ);
      if (!r.ok) throw new Error('抓取失败 ' + p + ' HTTP ' + r.status);
      SRC[p] = await r.text();
    }));
  }

  /* ------------------------------------------------------- 2. 表达式与插值 */
  function compile(expr) {
    let f = EXPR_CACHE[expr];
    if (!f) {
      // with($s) 让 WXML 里 {{a.b}}、{{item.x}} 直接可用（非严格模式）
      f = new Function('$s', 'with($s){return (' + expr + ')}');
      EXPR_CACHE[expr] = f;
    }
    return f;
  }
  function evalExpr(expr, scope) {
    try {
      // ⚠️ 控制属性（wx:if / wx:elif / wx:for）在模板里存的是原样的 "{{expr}}"，
      //    必须先剥掉花括号再当 JS 求值，否则会因语法错误恒为假（曾导致所有
      //    wx:if / wx:for 静默失效——排查了很久，别再改回去）。
      let e = String(expr == null ? '' : expr).trim();
      const m = e.match(/^\{\{([\s\S]*)\}\}$/);
      if (m) e = m[1];
      return compile(e)(scope);
    } catch (err) {
      return '';
    }
  }
  function interp(str, scope) {
    if (str == null) return '';
    return String(str).replace(/\{\{([\s\S]*?)\}\}/g, (_, e) => {
      const v = evalExpr(e, scope);
      return v == null ? '' : String(v);
    });
  }

  /* ------------------------------------------------------------- 3. wx shim */
  const LS_PREFIX = 'coralweb:';
  const listeners = [];
  function emit(evt, payload) {
    listeners.forEach((f) => f(evt, payload));
    try { window.dispatchEvent(new CustomEvent('mp:' + evt, { detail: payload })); } catch (e) {}
  }

  const wx = {
    /* 存储 */
    setStorageSync(k, v) { try { localStorage.setItem(LS_PREFIX + k, JSON.stringify(v)); } catch (e) {} },
    getStorageSync(k) {
      try { const s = localStorage.getItem(LS_PREFIX + k); return s == null ? '' : JSON.parse(s); }
      catch (e) { return ''; }
    },
    removeStorageSync(k) { localStorage.removeItem(LS_PREFIX + k); },
    clearStorageSync() { Object.keys(localStorage).filter((k) => k.startsWith(LS_PREFIX)).forEach((k) => localStorage.removeItem(k)); },
    getStorageInfoSync() {
      const keys = Object.keys(localStorage).filter((k) => k.startsWith(LS_PREFIX));
      return { keys, currentSize: 0, limitSize: 10240 };
    },
    /* 系统信息 */
    getSystemInfoSync: () => ({
      platform: 'web', system: navigator.platform || 'web', brand: 'browser', model: 'browser',
      windowWidth: Math.min(window.innerWidth, 480), windowHeight: window.innerHeight,
      screenWidth: window.innerWidth, screenHeight: window.innerHeight,
      pixelRatio: window.devicePixelRatio || 1, statusBarHeight: 0, safeArea: {},
      language: 'zh_CN', version: '8.0.0', SDKVersion: '3.0.0',
    }),
    getWindowInfo: () => ({
      windowWidth: Math.min(window.innerWidth, 480), windowHeight: window.innerHeight,
      screenWidth: window.innerWidth, screenHeight: window.innerHeight,
      pixelRatio: window.devicePixelRatio || 1, statusBarHeight: 0,
    }),
    getDeviceInfo: () => ({ platform: 'web', system: navigator.platform || 'web', model: 'browser' }),
    getAppBaseInfo: () => ({ version: '3.0.0', SDKVersion: '3.0.0', language: 'zh_CN', theme: 'light' }),
    /* 导航（交给路由） */
    navigateTo(o) { router.push(o.url, o.query); o.success && o.success({}); o.complete && o.complete({}); },
    redirectTo(o) { router.replace(o.url, o.query); o.success && o.success({}); },
    switchTab(o) { router.switchTab(o.url); o.success && o.success({}); },
    reLaunch(o) { router.replace(o.url, o.query); o.success && o.success({}); },
    navigateBack(o) { router.back(o && o.delta); o.success && o.success({}); },
    /* 界面 */
    showToast(o) { toast(o.title || '', o.icon !== 'none'); o.success && o.success({}); },
    hideToast() { hideToast(); },
    showLoading(o) { loading(o.title || '加载中'); },
    hideLoading() { loading(null); },
    showModal(o) {
      modal({
        title: o.title || '提示', content: o.content || '',
        confirmText: o.confirmText || '确定', cancelText: o.cancelText || '取消',
        showCancel: o.showCancel !== false,
      }).then((ok) => { if (ok) o.success && o.success({ confirm: true, cancel: false }); else o.fail && o.fail({ errMsg: 'cancel' }); });
    },
    setNavigationBarTitle(o) { emit('title', o.title || ''); },
    setNavigationBarColor() {},
    pageScrollTo(o) { window.scrollTo({ top: o.scrollTop || 0, behavior: 'smooth' }); },
    stopPullDownRefresh() {},
    startPullDownRefresh() {},
    /* 交互 */
    setClipboardData(o) {
      (navigator.clipboard ? navigator.clipboard.writeText(o.data) : Promise.reject())
        .then(() => o.success && o.success({})).catch(() => toast('复制失败，请手动选择', false));
    },
    vibrateShort() {}, vibrateLong() {},
    openSetting(o) { o.success && o.success({ authSetting: {} }); },
    requirePrivacyAuthorize(o) { o.success && o.success({}); },
    getSetting(o) { o.success && o.success({ authSetting: {} }); },
    authorize(o) { o.success && o.success({}); },
    /* 登录（网页端没有微信登录：给一个本地标识，后端不校验） */
    login(o) {
      let code = localStorage.getItem(LS_PREFIX + 'wcode');
      if (!code) { code = 'web-' + Math.random().toString(36).slice(2, 12); localStorage.setItem(LS_PREFIX + 'wcode', code); }
      o.success && o.success({ code, errMsg: 'login:ok' });
    },
    checkSession(o) { o.success && o.success({}); },
    getUserProfile(o) { o.fail && o.fail({ errMsg: '网页版不支持 getUserProfile' }); },
    getUserInfo(o) { o.fail && o.fail({ errMsg: '网页版不支持 getUserInfo' }); },
    /* 支付（网页端无法调起微信支付——如实失败，不假装成功） */
    requestPayment(o) {
      modal({ title: '网页版不支持微信支付', content: '认养/捐赠的支付需要在微信小程序内完成。\n你可以继续浏览与体验其它功能。', showCancel: false })
        .then(() => o.fail && o.fail({ errMsg: 'requestPayment:fail 网页端不支持' }));
    },
    /* 网络 */
    request(o) {
      const url = /^https?:/.test(o.url) ? o.url : o.url;
      fetch(url, { method: o.method || 'GET', headers: o.header || {}, body: o.data && o.method === 'POST' ? JSON.stringify(o.data) : undefined })
        .then(async (r) => {
          const txt = await r.text();
          let data = txt;
          try { data = JSON.parse(txt); } catch (e) {}
          if (r.ok) o.success && o.success({ statusCode: r.status, data, header: {} });
          else o.fail && o.fail({ statusCode: r.status, data });
        })
        .catch((e) => o.fail && o.fail({ errMsg: String(e) }))
        .finally(() => o.complete && o.complete({}));
      return { abort() {} };
    },
    uploadFile(o) {
      const form = o.formData || {};
      const fd = new FormData();
      Object.keys(form).forEach((k) => fd.append(k, form[k]));
      if (o.filePath) {
        fetch(o.filePath).then((r) => r.blob()).then((b) => {
          fd.append(o.name || 'file', b, 'upload.jpg');
          return fetch(o.url, { method: 'POST', body: fd });
        }).then(async (r) => {
          // ⚠️ 微信的 wx.uploadFile 里 res.data 是**字符串**（不是对象）：
          //    小程序侧普遍写 JSON.parse(res.data)。这里必须同样返回文本，
          //    否则 JSON.parse(对象) 会抛 SyntaxError → 页面降级成"演示数据"（踩过）。
          const text = await r.text();
          o.success && o.success({ statusCode: r.status, data: text });
        }).catch((e) => o.fail && o.fail({ errMsg: String(e) }))
          .finally(() => o.complete && o.complete({}));
      }
      return { abort() {} };
    },
    downloadFile(o) { fetch(o.url).then((r) => r.blob()).then((b) => o.success && o.success({ tempFilePath: URL.createObjectURL(b) })).catch((e) => o.fail && o.fail({ errMsg: String(e) })); },
    /* 媒体 */
    chooseMedia(o) { pickImage(o.count || 1).then((paths) => o.success && o.success({ tempFiles: paths.map((p) => ({ tempFilePath: p })) })).catch(() => o.fail && o.fail({ errMsg: 'cancel' })); },
    chooseImage(o) { pickImage(o.count || 1).then((paths) => o.success && o.success({ tempFilePaths: paths })).catch(() => o.fail && o.fail({ errMsg: 'cancel' })); },
    previewImage(o) { modal({ title: '图片预览', content: o.current || (o.urls || [])[0] || '', showCancel: false }); },
    saveImageToPhotosAlbum(o) {
      const a = document.createElement('a');
      a.href = o.filePath; a.download = 'coral.jpg'; a.click();
      o.success && o.success({});
    },
    /* 位置 */
    getLocation(o) {
      if (!navigator.geolocation) return o.fail && o.fail({ errMsg: '浏览器不支持定位' });
      navigator.geolocation.getCurrentPosition(
        (p) => o.success && o.success({ latitude: p.coords.latitude, longitude: p.coords.longitude, speed: 0, accuracy: p.coords.accuracy }),
        (e) => o.fail && o.fail({ errMsg: e.message || '定位失败（HTTP 下手机浏览器会禁用定位）' }),
        { timeout: 8000 });
    },
    chooseLocation(o) { o.fail && o.fail({ errMsg: '网页版不支持选择位置' }); },
    openLocation(o) { window.open('https://uri.amap.com/marker?position=' + o.longitude + ',' + o.latitude, '_blank'); },
    /* 画布/文件（认养证书等功能用） */
    canvasToTempFilePath(o) {
      const cv = document.querySelector('canvas');
      if (!cv) return o.fail && o.fail({ errMsg: '找不到 canvas' });
      o.success && o.success({ tempFilePath: cv.toDataURL('image/png') });
    },
    createCanvasContext() { return canvasCtxStub(); },
    createSelectorQuery() { return selectorQuery(); },
    getFileSystemManager() {
      return {
        saveFile(o) { o.success && o.success({ savedFilePath: o.tempFilePath }); },
        readFile(o) { o.fail && o.fail({ errMsg: 'web 不支持 readFile' }); },
        writeFile(o) { o.success && o.success({}); },
        getFileInfo(o) { o.success && o.success({ size: 0 }); },
      };
    },
    getUpdateManager: () => ({ onCheckForUpdate() {}, onUpdateReady() {}, applyUpdate() {} }),
    onAppShow() {}, offAppShow() {}, onError() {}, offError() {},
    nextTick: (f) => setTimeout(f, 0),
    canIUse: () => true,
    getMenuButtonBoundingClientRect: () => ({ top: 0, bottom: 0, left: 0, right: 0, width: 0, height: 0 }),
    setKeepScreenOn(o) { o.success && o.success({}); },
    setScreenBrightness(o) { o.success && o.success({}); },
  };

  /* 统一补默认参数。
     微信允许 `wx.navigateBack()` / `wx.showToast()` 这类**不传参**调用，而我们的实现里
     大多直接读 `o.success`，不传就抛 TypeError —— 实测 coral-species 页调 wx.navigateBack()
     时报 "Cannot read properties of undefined (reading 'success')"，整页绑死。
     这里把所有「收对象参数」的 API 统一包装成 `o = {}`。 */
  const CALLBACK_APIS = [
    'navigateTo', 'redirectTo', 'switchTab', 'reLaunch', 'navigateBack',
    'showToast', 'showLoading', 'showModal', 'setNavigationBarTitle', 'pageScrollTo',
    'setClipboardData', 'openSetting', 'getSetting', 'requirePrivacyAuthorize', 'authorize',
    'login', 'checkSession', 'getUserProfile', 'getUserInfo', 'requestPayment',
    'request', 'downloadFile', 'uploadFile', 'chooseMedia', 'chooseImage', 'previewImage',
    'saveImageToPhotosAlbum', 'getLocation', 'openLocation', 'setKeepScreenOn',
    'setScreenBrightness', 'showShareMenu', 'hideShareMenu', 'showActionSheet',
  ];
  CALLBACK_APIS.forEach((k) => {
    const fn = wx[k];
    if (typeof fn !== 'function') return;
    wx[k] = function (o, ...rest) { return fn.call(wx, o || {}, ...rest); };
  });

  window.wx = wx;

  function canvasCtxStub() {
    const noop = () => {};
    return new Proxy({}, { get: (t, k) => (k in t ? t[k] : noop) });
  }
  function selectorQuery() {
    return {
      select() { return this; }, selectAll() { return this; }, selectViewport() { return this; },
      boundingClientRect(cb) { this._cb = cb; return this; },
      scrollOffset(cb) { this._cb = cb; return this; },
      fields(o, cb) { this._cb = cb; return this; },
      exec(cb) {
        const el = document.querySelector('.coral-page');
        const r = el ? el.getBoundingClientRect() : { top: 0, left: 0, width: 0, height: 0, bottom: 0, right: 0 };
        const res = [{ top: r.top, left: r.left, width: r.width, height: r.height, bottom: r.bottom, right: r.right, scrollTop: window.scrollY, dataset: {} }];
        if (this._cb) this._cb(res[0]);
        cb && cb(res);
      },
    };
  }
  function pickImage(count) {
    return new Promise((resolve, reject) => {
      const inp = document.createElement('input');
      inp.type = 'file'; inp.accept = 'image/*'; inp.multiple = count > 1;
      inp.style.display = 'none';
      document.body.appendChild(inp);
      inp.onchange = () => {
        const fs = Array.from(inp.files || []);
        inp.remove();
        if (!fs.length) return reject(new Error('cancel'));
        resolve(fs.map((f) => URL.createObjectURL(f)));
      };
      inp.click();
    });
  }

  /* ----------------------------------------------------------- 4. App/Page */
  let appInstance = null;
  function App(def) { appInstance = Object.assign({}, def); return appInstance; }
  function getApp() { return appInstance || {}; }
  function Component(def) { Page(def); }   // 本项目没有自定义组件，兜底

  const pages = Object.create(null);       // name -> def
  function Page(def) { if (currentDef) { Object.assign(currentDef, def); pages[currentDef.__name] = currentDef; } }

  /* ------------------------------------------------------------ 5. 渲染器 */
  const EVT_ATTRS = {
    bindtap: 'tap', catchtap: 'tap', 'bind:tap': 'tap',
    bindlongpress: 'longpress', catchlongpress: 'longpress',
    bindinput: 'input', bindchange: 'change', bindconfirm: 'confirm',
    bindsubmit: 'submit', bindscroll: 'scroll', bindscrolltolower: 'scrolltolower',
    bindload: 'load', binderror: 'error', bindblur: 'blur', bindfocus: 'focus',
    bindanimationfinish: 'animfinish', bindplay: 'play', bindpause: 'pause',
    bindended: 'ended', bindtouchstart: 'touchstart', bindtouchmove: 'touchmove',
    bindtouchend: 'touchend',
  };

  function renderNode(node, scope, inst, out) {
    if (node.x !== undefined) { out.push(esc(interp(node.x, scope))); return; }
    if (node.f !== undefined) {
      let arr = evalExpr(node.f, scope);
      if (arr == null) arr = [];
      if (typeof arr === 'number') arr = Array.from({ length: arr });
      if (!Array.isArray(arr)) arr = Object.keys(arr).map((k) => arr[k]);
      const itemName = node.fi || 'item', idxName = node.fx || 'index';
      arr.forEach((item, index) => {
        const s = Object.create(scope);
        s[itemName] = item; s[idxName] = index;
        renderSelf(node, s, inst, out);
      });
      return;
    }
    renderSelf(node, scope, inst, out);
  }

  function renderSelf(node, scope, inst, out) {
    if (node.i !== undefined && !truthy(evalExpr(node.i, scope))) return;
    if (node.e !== undefined && !truthy(evalExpr(node.e, scope))) return;
    if (node.l !== undefined && node.l !== '') { /* wx:else 恒真，由同级 if 控制 */ }

    const tag = node.t;
    if (tag === 'block') { renderChildren(node, scope, inst, out); return; }
    const html = TAGMAP[tag] || tag;
    const attrs = [];
    const a = node.a || {};
    // scroll-view / swiper 没有对应的 HTML 标签，转成 div 时必须补上滚动能力，
    // 否则横向内容会把整页撑宽（踩过：首页横向卡片把 480px 页面撑到 859px）
    let extraCls = '';
    if (tag === 'scroll-view') {
      const sx = interp(a['scroll-x'] || '', scope), sy = interp(a['scroll-y'] || '', scope);
      const horiz = truthy(sx) || sx === 'true';
      const vert = truthy(sy) || sy === 'true';
      extraCls = ' mp-scroll' + (vert && !horiz ? ' mp-scroll-y' : ' mp-scroll-x');
    } else if (tag === 'swiper') {
      extraCls = ' mp-swiper';
    } else if (tag === 'swiper-item') {
      extraCls = ' mp-swiper-item';
    }
    let styleVal = '';        // 合并成单个 style 属性，避免重复属性相互覆盖
    let imgModeStyle = '';    // 小程序的 <image mode> 必须映射成 object-fit，否则图片会拉伸变形
    for (const k of Object.keys(a)) {
      if (k.startsWith('wx:')) continue;
      const v = interp(a[k], scope);
      if (k === 'mode' && tag === 'image') {
        const m = String(v).toLowerCase();
        if (m === 'aspectfill') imgModeStyle = 'object-fit:cover;';
        else if (m === 'aspectfit') imgModeStyle = 'object-fit:contain;';
        else if (m === 'widthfix') imgModeStyle = 'height:auto;object-fit:contain;';
        else if (m === 'scaletofill') imgModeStyle = 'object-fit:fill;';
        continue;
      }
      if (EVT_ATTRS[k]) { attrs.push(`data-evt="${EVT_ATTRS[k]}:${v}"`); continue; }
      if (k === 'class') { attrs.push(`class="${esc(v)}${extraCls}"`); extraCls = ''; continue; }
      if (k === 'style') { styleVal = v; continue; }
      if (k === 'hidden') { if (truthy(v)) styleVal += ';display:none'; continue; }
      if (k === 'disabled') { if (truthy(v)) attrs.push('disabled'); continue; }
      if (k.startsWith('data-')) { attrs.push(`${k}="${esc(v)}"`); continue; }
      if (k === 'src') { attrs.push(`src="${esc(v)}"`); continue; }
      // <video> / <audio>：小程序的 poster / controls / playsinline 等要原样透出，
      // 否则网页版拿不到封面和播放控件（object-fit 在 HTML 里得走 CSS）
      if (tag === 'video' || tag === 'audio') {
        if (k === 'object-fit') { if (v) styleVal += ';object-fit:' + v; continue; }
        if (k === 'show-center-play-btn' || k === 'enable-progress-gesture' ||
            k === 'show-fullscreen-btn' || k === 'show-play-btn') { continue; }
        if (k === 'controls' || k === 'autoplay' || k === 'loop' || k === 'muted' ||
            k === 'playsinline' || k === 'show-mute-btn') {
          attrs.push(k);                       // 布尔属性
          continue;
        }
        if (k === 'poster' || k === 'preload' || k === 'duration' || k === 'initial-time') {
          attrs.push(`${k === 'initial-time' ? 'data-initial-time' : k}="${esc(v)}"`);
          continue;
        }
      }
      if (k === 'value' && tag === 'input') { attrs.push(`value="${esc(v)}"`); continue; }
      if (k === 'value' && tag === 'textarea') { continue; }
      if (k === 'placeholder' || k === 'maxlength' || k === 'type' || k === 'name' ||
          k === 'confirm-type' || k === 'password' || k === 'id' || k === 'scroll-y' ||
          k === 'scroll-x' || k === 'show-scrollbar' || k === 'open-type' || k === 'lang') {
        const kk = k === 'open-type' ? 'data-opentype' : k;
        attrs.push(`${kk}="${esc(v)}"`);
        continue;
      }
      if (k === 'url' || k === 'hover-class' || k === 'target' || k === 'app-id' ||
          k === 'path' || k === 'version' || k === 'extra-data') { continue; }
      attrs.push(`data-${k}="${esc(v)}"`);
    }
    const styleAll = [styleVal.replace(/^;/, ''), imgModeStyle].filter(Boolean).join(';');
    if (styleAll) attrs.push(`style="${esc(styleAll)}"`);
    const voidTag = tag === 'image' || tag === 'input' || tag === 'br';
    if (extraCls) attrs.push(`class="${extraCls.trim()}"`);   // 没有 class 属性的 scroll-view/swiper
    if (voidTag) { out.push(`<${html} ${attrs.join(' ')}>`); return; }
    out.push(`<${html} ${attrs.join(' ')}>`);
    renderChildren(node, scope, inst, out);
    out.push(`</${html}>`);
  }

  function renderChildren(node, scope, inst, out) {
    const kids = node.c || [];
    let i = 0;
    const stack = [];   // [{active:boolean}] 记录 if/elif/else 链
    for (const kid of kids) {
      if (kid && kid.i !== undefined) {
        const ok = truthy(evalExpr(kid.i, scope));
        stack.push(ok);
        if (ok) renderNode(kid, scope, inst, out);
        continue;
      }
      if (kid && kid.e !== undefined) {
        const prev = stack.length ? stack[stack.length - 1] : false;
        const ok = !prev && truthy(evalExpr(kid.e, scope));
        stack[stack.length - 1] = prev || ok;
        if (ok) renderNode(kid, scope, inst, out);
        continue;
      }
      if (kid && kid.l !== undefined) {
        const prev = stack.length ? stack.pop() : false;
        if (!prev) renderNode(kid, scope, inst, out);
        continue;
      }
      if (kid && (kid.i === undefined && kid.e === undefined && kid.l === undefined)) stack.length = 0;
      renderNode(kid, scope, inst, out);
    }
  }

  const TAGMAP = {
    view: 'div', text: 'span', image: 'img', 'scroll-view': 'div', swiper: 'div',
    'swiper-item': 'div', navigator: 'a', block: 'block', button: 'button',
    input: 'input', textarea: 'textarea', progress: 'progress', 'rich-text': 'div',
    'cover-view': 'div', 'cover-image': 'img', 'movable-area': 'div', 'movable-view': 'div',
    video: 'video', canvas: 'canvas', picker: 'div', switch: 'div', checkbox: 'div',
    radio: 'div', label: 'label', form: 'form', icon: 'span', slot: 'div', camera: 'div',
  };
  const truthy = (v) => !(v === false || v === 0 || v === '' || v == null || v === 'false');
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  /* --------------------------------------------------------- 6. 页面实例 */
  function deepClone(o) { return o == null ? o : JSON.parse(JSON.stringify(o)); }
  function setByPath(obj, path, val) {
    const segs = String(path).replace(/\[(\d+)\]/g, '.$1').split('.');
    let cur = obj;
    for (let i = 0; i < segs.length - 1; i++) {
      const k = segs[i];
      if (cur[k] == null) cur[k] = /^\d+$/.test(segs[i + 1]) ? [] : {};
      cur = cur[k];
    }
    cur[segs[segs.length - 1]] = val;
  }
  function makeInstance(def, name, query) {
    const inst = Object.create(def);
    inst.__name = name;
    inst.__query = query || {};
    // ⚠️ 微信里 `this.route` 是页面路径（如 pages/index/index），page-i18n 靠它：
    //    ① 取「页面作用域词条」——否则 index.brand 与 knowledge.brand 拍平后互相覆盖，
    //       首页会显示科普页的品牌名「📚 珊瑚科普」（实测踩过）；
    //    ② 切语言时设置导航栏标题。之前没设 route，这两个功能都是静默失效的。
    try {
      const meta = ((state.manifest && state.manifest.pages) || []).find((p) => p.name === name);
      inst.route = (meta && meta.route) || name;
    } catch (e) { inst.route = name; }
    inst.data = deepClone(def.data) || {};
    inst.__pending = false;
    inst.setData = function (patch, cb) {
      CNT.setData++; dbg();
      Object.keys(patch || {}).forEach((k) => {
        if (k.indexOf('.') >= 0 || k.indexOf('[') >= 0) setByPath(inst.data, k, patch[k]);
        else inst.data[k] = patch[k];
      });
      if (!inst.__pending) {
        inst.__pending = true;
        Promise.resolve().then(() => { inst.__pending = false; paint(inst); });
      }
      cb && cb();
    };
    inst.selectComponent = () => null;
    inst.selectAllComponents = () => [];
    inst.createSelectorQuery = () => selectorQuery();
    inst.animate = () => ({ step() {}, export() {} });
    return inst;
  }

  /* ------------------------------------------------------------- 7. 路由 */
  const state = { stack: [], manifest: null, booted: false };

// 微信 API：getCurrentPages() → 页面实例数组（栈底在前，栈顶在最后）。
// 页面代码（如 page-i18n 取页面作用域词条）会用它兜底拿 route，缺了就会静默走错分支。
wx.getCurrentPages = function () { return state.stack.map((f) => f.inst); };
  // 需要 id 的详情页 → 深链/刷新时的默认值（与 mock 数据的第一条对应）
  const DETAIL_PAGES = { 'coral-detail': '1', article: '1', 'knowledge-detail': '1', growth: '1' };
  const TABS = () => (state.manifest.tabBar.list || []).map((i) => i.pagePath.split('/')[1]);

  const router = {
    async push(url, query) { await go(url, query, 'push'); },
    async replace(url, query) { await go(url, query, 'replace'); },
    async switchTab(url) { await go(url, null, 'tab'); },
    back(delta) {
      const d = delta || 1;
      for (let i = 0; i < d; i++) {
        const cur = state.stack.pop();
        if (cur && cur.inst.onUnload) cur.inst.onUnload();
      }
      const top = state.stack[state.stack.length - 1];
      if (top) { if (top.inst.onShow) top.inst.onShow(); paint(top.inst); }
      syncHash();
    },
  };

  function parseUrl(url) {
    const clean = String(url || '').replace(/^\//, '').replace(/\?.*$/, '');
    const name = clean.split('/').filter(Boolean)[1] || clean;
    return name;
  }
  function queryOf(url) {
    const q = {};
    const s = String(url || '').split('?')[1];
    if (s) s.split('&').forEach((kv) => { const [k, v] = kv.split('='); if (k) q[decodeURIComponent(k)] = decodeURIComponent(v || ''); });
    return q;
  }
  function safe(inst, method, arg) {
    // 页面生命周期/方法出错不能让整个应用白屏：捕获、记录、继续渲染
    try {
      if (typeof inst[method] === 'function') return inst[method](arg);
    } catch (e) {
      logErr(inst.__name + '.' + method + ': ' + (e && e.message));
      console.error('[mp] ' + inst.__name + '.' + method, e);
    }
  }

  async function go(url, query, mode) {
    const name = parseUrl(url);
    const q = Object.assign(queryOf(url), query || {});
    if (!name) return;
    // 详情类页面在小程序里总是被带参跳转；网页端支持刷新/直达，
    // 没有参数时给一个默认 id（否则页面自身的 mock 查找会读到 undefined）。
    if (DETAIL_PAGES[name] && q.id == null) q.id = DETAIL_PAGES[name];
    if (mode === 'tab') {
      state.stack.forEach((f) => safe(f.inst, 'onUnload'));
      state.stack = [];
    } else if (mode === 'replace') {
      const cur = state.stack.pop();
      if (cur) safe(cur.inst, 'onUnload');
    } else {
      const cur = state.stack[state.stack.length - 1];
      if (cur) safe(cur.inst, 'onHide');
    }
    await ensurePage(name);
    const def = pages[name];
    const inst = makeInstance(def, name, q);
    state.stack.push({ name, inst });
    const meta = (state.manifest.pages || []).find((p) => p.name === name);
    // 标题也跟随语言：manifest 里带了构建期生成的英文标题（titleEn）
    let pageTitle = (meta && meta.title) || '蓝珊 · 珊瑚卫士';
    if (meta && meta.titleEn) {
      let lg = 'zh';
      try {
        const raw = localStorage.getItem(LS_PREFIX + 'ls_lang');
        if (raw != null) lg = String(JSON.parse(raw)).replace(/"/g, '') || 'zh';
      } catch (e) {}
      if (lg === 'en') pageTitle = meta.titleEn;
    }
    emit('title', pageTitle);
    safe(inst, 'onLoad', q);
    paint(inst);
    setTimeout(() => safe(inst, 'onReady'), 0);
    safe(inst, 'onShow');
    syncHash(name);
    window.scrollTo({ top: 0 });
  }
  function syncHash(name) {
    const top = name || (state.stack[state.stack.length - 1] || {}).name;
    if (top) {
      const cur = location.hash || '';
      // 保留查询串（如 #/coral-detail?id=2），深链/刷新才能复原同一页面
      if (!cur.startsWith('#/' + top)) history.replaceState(null, '', '#/' + top);
    }
  }
  function paint(inst) {
    const host = document.getElementById('page-host');
    if (!host) return;                       // 容器不存在（如探针页）时不要抛错
    CNT.paint++; CNT.page = inst.__name; dbg();
    const tpl = TEMPLATES[inst.__name];
    if (!tpl) { host.innerHTML = `<div class="mp-error">模板缺失：${inst.__name}</div>`; return; }
    try {
      const out = [];
      // 顶层：tpl 是 {t:'block',c:[...]}
      renderChildren({ c: tpl.c || [] }, inst.data, inst, out);
      CNT.html = out.join('').length;
      CNT.info = 'd=' + (inst.data.d ? 'T' : 'F') + ',keys=' + Object.keys(inst.data).length;
      host.innerHTML = `<div class="coral-page ${inst.__name}-page">${out.join('')}</div>`;
      dbg();
    } catch (e) {
      logErr('渲染 ' + inst.__name + ': ' + (e && e.message));
      console.error('[mp] 渲染失败', inst.__name, e);
      return;
    }
    ensurePageStyle(inst.__name);
    bindEvents(host, inst);
    fixImages(host);
    updateTabBar(inst.__name);
    emit('painted', inst);
  }

  /* 图片兜底：mock 数据里的配图放在外部 CDN（s.coze.cn / images.unsplash.com），
     断网或没有代理时会裂成"破图"图标。这里统一替换成占位块，保证离线也好看。
     （若已用 tools/localize_images.py 把图片下载到本地，则不会触发） */
  function fixImages(host) {
    host.querySelectorAll('img').forEach((im) => {
      if (im.dataset.fallbackBound) return;
      im.dataset.fallbackBound = '1';
      im.addEventListener('error', () => {
        if (im.dataset.replaced) return;
        im.dataset.replaced = '1';
        const ph = document.createElement('div');
        ph.className = 'mp-img-ph';
        ph.textContent = '🪸';
        ph.style.cssText = 'display:flex;align-items:center;justify-content:center;' +
          'background:linear-gradient(135deg,#e3f2fd,#b2dfdb);color:#00796b;font-size:20px;' +
          'width:' + (im.clientWidth || im.getAttribute('width') || 100) + 'px;' +
          'height:' + (im.clientHeight || im.getAttribute('height') || 80) + 'px;' +
          'border-radius:8px;';
        im.replaceWith(ph);
      });
      // 已经加载失败的（error 在绑定前就触发过）也补上
      if (im.complete && im.naturalWidth === 0) im.dispatchEvent(new Event('error'));
    });
  }
  const loadedStyle = Object.create(null);
  function ensurePageStyle(name) {
    if (loadedStyle[name]) return;
    loadedStyle[name] = true;
    const l = document.createElement('link');
    l.rel = 'stylesheet'; l.href = MP + 'styles/' + name + '.css' + VQ;
    document.head.appendChild(l);
  }

  function bindEvents(host, inst) {
    host.querySelectorAll('[data-evt]').forEach((el) => {
      const [evt, fn] = el.getAttribute('data-evt').split(':');
      if (!fn) return;
      const handler = (domEvt) => {
        const dataset = {};
        Object.keys(el.dataset).forEach((k) => { if (k !== 'evt') dataset[k] = el.dataset[k]; });
        const e = {
          type: evt, target: { dataset, id: el.id, value: el.value },
          currentTarget: { dataset, id: el.id, value: el.value },
          detail: { value: el.value },
        };
        if (evt === 'input' || evt === 'change' || evt === 'blur' || evt === 'focus' || evt === 'confirm') {
          e.detail.value = el.value;
          if (el.tagName === 'SELECT') e.detail.value = el.value;
        }
        try {
          const f = inst[fn];
          if (typeof f === 'function') f.call(inst, e);
          else console.warn('[mp] 页面没有方法 ' + fn + '（' + inst.__name + '）');
        } catch (err) { console.error('[mp] 事件 ' + fn + ' 出错:', err); }
      };
      const domEvt = { tap: 'click', longpress: 'contextmenu', scrolltolower: 'scroll' }[evt] || evt;
      el.addEventListener(domEvt, handler);
      if (evt === 'tap') el.style.cursor = 'pointer';
    });
    // input / textarea 的值回写到 el.value（受控）
    host.querySelectorAll('input,textarea').forEach((el) => {
      const dv = el.getAttribute('value');
      if (dv != null && el.value !== dv) el.value = dv;
    });
  }

  /* ------------------------------------------------------- 8. UI 外壳 */
  function updateTabBar(activeName) {
    const bar = document.getElementById('mp-tabbar');
    if (!bar) return;                        // 外壳缺 tabBar 容器时不抛错
    const list = (state.manifest.tabBar.list || []);
    const tabs = TABS();
    // 中英切换：语言由页面写进 storage（key: ls_lang，值形如 "en"；
    // wx.setStorageSync 会加上 LS_PREFIX 前缀并 JSON 序列化，这里要按同样规则读）
    let lang = 'zh';
    try {
      const raw = localStorage.getItem(LS_PREFIX + 'ls_lang');
      if (raw != null) lang = String(JSON.parse(raw)).replace(/"/g, '') || 'zh';
    } catch (e) {}
    const TAB_EN = { '首页': 'Home', '认养': 'Adopt', '科普': 'Learn', 'AI识别': 'AI scan', '我的': 'Me' };
    bar.innerHTML = list.map((it, i) => {
      const nm = it.pagePath.split('/')[1];
      const icon = ({ home: 'home', adopt: 'adopt', knowledge: 'book', ai: 'ai', profile: 'user' })[nm] || 'home';
      const on = nm === activeName;
      const label = lang === 'en' ? (TAB_EN[it.text] || it.text) : it.text;
      return `<div class="tab-item ${on ? 'active' : ''}" data-tab="${nm}">
                <div class="tab-icon icon-${icon} ${on ? 'active' : ''}"></div>
                <span class="tab-label">${esc(label)}</span>
              </div>`;
    }).join('');
    bar.querySelectorAll('[data-tab]').forEach((el) => {
      el.onclick = () => router.switchTab('/pages/' + el.getAttribute('data-tab') + '/' + el.getAttribute('data-tab'));
    });
    bar.style.display = tabs.length ? 'flex' : 'none';
  }

  let toastTimer = null;
  function toast(text, withIcon) {
    let el = document.getElementById('mp-toast');
    if (!el) { console.log('[mp] toast:', text); return; }
    el.innerHTML = (withIcon ? '' : '') + esc(text);
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), 1800);
  }
  function hideToast() { const e = document.getElementById('mp-toast'); if (e) e.classList.remove('show'); }
  function loading(text) {
    const el = document.getElementById('mp-loading');
    if (!el) return;
    if (!text) { el.classList.remove('show'); return; }
    el.querySelector('.txt').textContent = text;
    el.classList.add('show');
  }
  function modal(o) {
    return new Promise((resolve) => {
      const wrap = document.getElementById('mp-modal');
      if (!wrap) { console.log('[mp] modal:', o.title, o.content); return resolve(true); }
      wrap.querySelector('.m-title').textContent = o.title;
      wrap.querySelector('.m-content').textContent = o.content;
      const okBtn = wrap.querySelector('.m-ok'), noBtn = wrap.querySelector('.m-no');
      okBtn.textContent = o.confirmText; noBtn.textContent = o.cancelText;
      noBtn.style.display = o.showCancel === false ? 'none' : '';
      wrap.classList.add('show');
      okBtn.onclick = () => { wrap.classList.remove('show'); resolve(true); };
      noBtn.onclick = () => { wrap.classList.remove('show'); resolve(false); };
    });
  }

  /* ---------------------------------------------------------- 9. 启动 */
  const TEMPLATES = Object.create(null);
  let currentDef = null;

  async function ensurePage(name) {
    if (pages[name]) return;
    const p = MP + 'pages/' + name + '/' + name + '.js';
    await preload([p]);
    if (!TEMPLATES[name]) {
      const t = await fetch(MP + 'templates/' + name + '.json' + VQ).then((r) => r.json());
      TEMPLATES[name] = t;
    }
    currentDef = { __name: name };
    try {
      require(p);
    } finally {
      currentDef = null;
    }
    if (!pages[name]) throw new Error('页面未注册: ' + name);
  }

  function parseHash() {
    const h = (location.hash || '').replace(/^#\/?/, '');
    const [nm, qs] = h.split('?');
    const q = {};
    (qs || '').split('&').forEach((kv) => {
      const i = kv.indexOf('=');
      if (i > 0) q[decodeURIComponent(kv.slice(0, i))] = decodeURIComponent(kv.slice(i + 1));
    });
    return { name: nm || 'index', q };
  }

  async function boot() {
    state.manifest = await fetch(MP + 'manifest.json' + VQ).then((r) => r.json());
    // 预加载 app.js + 全部 utils（页面里 require 是同步的，必须先有源码）
    const appJs = MP + 'app.js';
    const utils = state.manifest.utils.map((f) => MP + 'utils/' + f);
    await preload([appJs].concat(utils));
    // 页面 JS 里可能 require key 不存在的 utils，逐个 try
    require(appJs);
    if (appInstance && appInstance.onLaunch) appInstance.onLaunch({ path: 'pages/index/index' });
    if (appInstance && appInstance.onShow) appInstance.onShow({});
    // 预抓所有页面模板（体积很小）
    await Promise.all(state.manifest.pages.map(async (p) => {
      const t = await fetch(MP + 'templates/' + p.name + '.json' + VQ).then((r) => r.json());
      TEMPLATES[p.name] = t;
    }));
    // 首次路由（支持 #/xxx?id=1 直达与刷新）
    const first = parseHash();
    const inTabs = TABS().includes(first.name);
    await go('/pages/' + first.name + '/' + first.name, first.q, inTabs ? 'tab' : 'replace');
    state.booted = true;
    window.addEventListener('hashchange', async () => {
      const h = parseHash();
      const top = (state.stack[state.stack.length - 1] || {}).name;
      const sameQ = JSON.stringify(h.q) === JSON.stringify((state.stack[state.stack.length - 1] || {}).inst && (state.stack[state.stack.length - 1].inst.__query) || {});
      if (h.name && (h.name !== top || !sameQ)) {
        await go('/pages/' + h.name + '/' + h.name, h.q, TABS().includes(h.name) ? 'tab' : 'replace');
      }
    });
    const bootEl = document.getElementById('mp-boot');
    if (bootEl) bootEl.style.display = 'none';
  }

  window.MP_RUNTIME = { router, wx, boot, state, getApp, require, SRC, CACHE, pages, updateTabBar };
  /* 错误汇总到隐藏元素：headless 验证脚本靠它发现页面里的 JS 报错 */
  function logErr(msg) {
    let d = document.getElementById('mp-errlog');
    if (!d) {
      d = document.createElement('div');
      d.id = 'mp-errlog';
      d.style.display = 'none';
      document.body.appendChild(d);
    }
    d.textContent += ' | ' + msg;
  }
  window.addEventListener('error', (e) => logErr((e.message || 'error') + ' @' + (e.filename || '').split('/').pop() + ':' + e.lineno));
  window.addEventListener('unhandledrejection', (e) => logErr('promise: ' + ((e.reason && e.reason.message) || e.reason)));
  document.addEventListener('DOMContentLoaded', () => {
    boot().catch((e) => {
      console.error(e);
      document.getElementById('mp-boot').innerHTML =
        '<div class="mp-error">运行时启动失败：' + esc(e.message) + '<br>请确认服务已启动并刷新页面。</div>';
    });
  });
})();
