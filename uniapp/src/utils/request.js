/**
 * 统一请求封装（T1-4 基础；T1-7 完成 401 拦截与 token 持久化）
 * - 自动携带 Authorization: Bearer <token>
 * - 统一解包 { code, message, data }（设计报告 6.1）
 * - 401/4011 未登录：清理 token 并跳转登录页（登录态保持）
 * - 非 code=0 抛错并返回 message，供调用方 toast
 */
import { API_BASE_URL, STORAGE_KEYS } from './config'

/** 从本地存储读取 token（无则返回空串） */
function getToken() {
  return uni.getStorageSync(STORAGE_KEYS.token) || ''
}

/** 清理会话并跳转登录页（401/4011 统一入口，T1-7） */
function handleUnauthorized() {
  uni.removeStorageSync(STORAGE_KEYS.token)
  uni.removeStorageSync(STORAGE_KEYS.userInfo)
  const pages = getCurrentPages()
  const current = pages.length ? pages[pages.length - 1].route : ''
  if (current !== 'pages/login/login') {
    uni.reLaunch({ url: '/pages/login/login' })
  }
}

/**
 * 清理 GET 查询参数：剔除 undefined/null/空串。
 * uni.request 会把值为 undefined 的属性序列化成字符串 "undefined"（如
 * `ann_type=undefined`），导致后端参数校验失败（422）或过滤错误（T3-2 修复）。
 */
function cleanQuery(data = {}) {
  const out = {}
  Object.keys(data).forEach((key) => {
    const v = data[key]
    if (v === undefined || v === null || v === '') return
    out[key] = v
  })
  return out
}

/**
 * 发起请求
 * @param {string} method  GET/POST/DELETE/PUT
 * @param {string} path    API 路径（如 /api/auth/wechat/login）
 * @param {object} data    请求体（GET 时拼接 query）
 * @param {object} options  { loading: true } 显示 loading
 * @returns {Promise}       resolve(data)，业务失败 reject({code,message})
 */
export function request(method, path, data = {}, options = {}) {
  return new Promise((resolve, reject) => {
    if (options.loading) {
      uni.showLoading({ title: '加载中', mask: true })
    }
    const token = getToken()
    uni.request({
      url: `${API_BASE_URL}${path}`,
      method,
      data: method === 'GET' ? cleanQuery(data) : data,
      header: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      success(res) {
        // HTTP 401（防御兜底，本项目统一 HTTP 200 + code）
        if (res.statusCode === 401) {
          handleUnauthorized()
          reject({ code: 4011, message: '登录已过期，请重新登录' })
          return
        }
        const body = res.data || {}
        if (body.code === 0) {
          resolve(body.data)
          return
        }
        // 4011 未登录：清理 token 并跳登录页（T1-7）
        if (body.code === 4011) {
          handleUnauthorized()
        }
        reject({ code: body.code, message: body.message || '请求失败' })
      },
      fail(err) {
        reject({ code: -1, message: err.errMsg || '网络异常，请检查网络' })
      },
      complete() {
        if (options.loading) {
          uni.hideLoading()
        }
      }
    })
  })
}

export const get = (path, params = {}, options = {}) => request('GET', path, params, options)
export const post = (path, data = {}, options = {}) => request('POST', path, data, options)
export const put = (path, data = {}, options = {}) => request('PUT', path, data, options)
export const del = (path, data = {}, options = {}) => request('DELETE', path, data, options)
