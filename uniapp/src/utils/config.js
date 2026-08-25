/**
 * 应用配置（T1-4）
 * - API 基础地址：统一在 ./dev.js 集中配置（修改一处，H5/小程序/真机多端复用）
 * - 小程序真机调试：只需改 utils/dev.js 的 DEV_IP 为局域网地址
 */
import { API_BASE_URL } from './dev'

export { API_BASE_URL }

export const STORAGE_KEYS = {
  token: 'campus_token',
  userInfo: 'campus_user_info'
}
