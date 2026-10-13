/**
 * 网络请求封装
 * - 自动携带官网同一套 token（Authorization: Bearer xxx）
 * - 401 统一清凭证并跳转登录页
 * - 小程序端与网页端共用同一后端、同一鉴权方式
 */
const config = require('./config.js')

function getToken() {
  return wx.getStorageSync(config.TOKEN_KEY) || ''
}

function setToken(token) {
  wx.setStorageSync(config.TOKEN_KEY, token)
}

function clearToken() {
  wx.removeStorageSync(config.TOKEN_KEY)
  wx.removeStorageSync(config.USER_KEY)
}

let redirecting = false
function redirectToLogin() {
  if (redirecting) return
  redirecting = true
  wx.showModal({
    title: '请先登录',
    content: '登录状态已失效，请重新登录',
    showCancel: false,
    success() {
      redirecting = false
      wx.navigateTo({ url: '/pages/login/login' })
    },
    fail() { redirecting = false }
  })
}

function request(options) {
  return new Promise((resolve, reject) => {
    const header = Object.assign(
      { 'content-type': 'application/json' },
      options.header || {}
    )
    const token = getToken()
    if (token) header['Authorization'] = 'Bearer ' + token

    wx.request({
      url: config.BASE_URL + options.url,
      method: options.method || 'GET',
      data: options.data || {},
      timeout: options.timeout || 15000,
      header,
      success(res) {
        if (res.statusCode === 401) {
          clearToken()
          redirectToLogin()
          reject(new Error('未登录或登录已过期'))
          return
        }
        // 约定后端返回 { code, message, data }；也可按实际后端调整此处
        const body = res.data
        if (res.statusCode >= 200 && res.statusCode < 300) {
          if (body && typeof body === 'object' && 'code' in body) {
            if (body.code === 0 || body.code === 200) {
              resolve(body.data)
            } else {
              wx.showToast({ title: body.msg || body.message || '请求失败', icon: 'none' })
              reject(new Error(body.msg || body.message || '请求失败'))
            }
          } else {
            resolve(body)
          }
        } else {
          wx.showToast({ title: '服务异常(' + res.statusCode + ')', icon: 'none' })
          reject(new Error('HTTP ' + res.statusCode))
        }
      },
      fail(err) {
        wx.showToast({ title: '网络连接失败，请检查网络', icon: 'none' })
        reject(err)
      }
    })
  })
}

function get(url, data) {
  return request({ url, method: 'GET', data })
}

function post(url, data) {
  return request({ url, method: 'POST', data })
}

/**
 * 文件上传（AI识别图片等）
 * @param url    后端上传接口路径
 * @param filePath 本地临时文件路径
 * @param name   文件字段名，默认 file
 */
function upload(url, filePath, name, formData) {
  return new Promise((resolve, reject) => {
    const header = {}
    const token = getToken()
    if (token) header['Authorization'] = 'Bearer ' + token
    wx.uploadFile({
      url: config.BASE_URL + url,
      filePath,
      name: name || 'file',
      formData: formData || {},
      header,
      success(res) {
        if (res.statusCode === 401) {
          clearToken()
          redirectToLogin()
          reject(new Error('未登录'))
          return
        }
        try {
          const body = JSON.parse(res.data)
          if (body && (body.code === 0 || body.code === 200)) resolve(body.data)
          else {
            wx.showToast({ title: (body && (body.msg || body.message)) || '上传失败', icon: 'none' })
            reject(new Error('上传失败'))
          }
        } catch (e) {
          reject(e)
        }
      },
      fail: reject
    })
  })
}

module.exports = {
  request,
  get,
  post,
  upload,
  getToken,
  setToken,
  clearToken
}
