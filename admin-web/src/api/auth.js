/**
 * 管理端认证接口（P1-9：/admin/api/auth/*，simplejwt）
 * 登录响应经 ApiJSONRenderer 包装：data = { access, refresh }
 */
import request from '../utils/request'

/** 管理员登录 */
export function loginApi(username, password) {
  return request.post('/auth/login', { username, password })
}

/** 刷新 access token */
export function refreshTokenApi(refresh) {
  return request.post('/auth/refresh', { refresh })
}
