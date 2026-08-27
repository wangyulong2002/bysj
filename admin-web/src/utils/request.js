/**
 * Axios 封装（管理端 /admin/api/**）
 *
 * - 统一携带 Bearer JWT（simplejwt，P1-9）
 * - 响应统一格式 { code, message, data }（renderers.ApiJSONRenderer，6.4）
 * - 4011/4031 → 清理会话并跳转登录页
 * - 业务错误（code != 0）→ reject Error(message)，页面 toast 展示
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

const service = axios.create({
  baseURL: '/admin/api',
  timeout: 15000
})

// 请求拦截：附加 access token
service.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_access')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let redirecting = false

// 响应拦截：统一处理 { code, message, data }
service.interceptors.response.use(
  (response) => {
    const body = response.data
    // 非标准格式（理论不出现）直接透传
    if (!body || typeof body !== 'object' || !('code' in body)) {
      return body
    }
    if (body.code === 0) {
      return body.data
    }
    // 4011/4031：会话失效 → 清理并回登录页
    if (body.code === 4011 || body.code === 4031) {
      if (!redirecting) {
        redirecting = true
        localStorage.removeItem('admin_access')
        localStorage.removeItem('admin_refresh')
        localStorage.removeItem('admin_user')
        ElMessage.error(body.message || '登录已过期，请重新登录')
        router.push('/login')
        setTimeout(() => { redirecting = false }, 1500)
      }
      return Promise.reject(new Error(body.message || '未登录'))
    }
    return Promise.reject(new Error(body.message || '请求失败'))
  },
  (error) => {
    const resp = error.response
    if (resp && resp.data && resp.data.message) {
      ElMessage.error(resp.data.message)
    } else if (error.code === 'ECONNABORTED') {
      ElMessage.error('请求超时，请重试')
    } else {
      ElMessage.error('网络异常，请检查 Django 管理端是否启动（8001）')
    }
    return Promise.reject(error)
  }
)

export default service
