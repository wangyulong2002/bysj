/**
 * 微信授权登录/绑定/解绑（T1-4，设计报告 3.4）
 *
 * 流程：
 *   1. wechatLogin()            uni.login 取 code → POST /api/auth/wechat/login
 *        - openid 已绑定   → resolve({ token, user, needBind: false })
 *        - openid 未绑定   → reject({ needBind: true, code })  页面引导账号密码绑定
 *   2. bindWechat(code, username, password)  → 绑定 openid 到账号并登录
 *   3. unbindWechat()        登录态解绑（换绑前调用）
 *
 * 平台说明：uni.login 仅微信小程序可用；H5/PC 端微信授权入口给出提示引导。
 */
import { post, del } from './request'
import { STORAGE_KEYS } from './config'

/** 平台是否支持微信登录（仅小程序） */
export function isWechatSupported() {
  // #ifdef MP-WEIXIN
  return true
  // #endif
  // #ifndef MP-WEIXIN
  return false
  // #endif
}

/** 获取微信登录 code（小程序专用） */
function getWechatCode() {
  return new Promise((resolve, reject) => {
    // #ifdef MP-WEIXIN
    uni.login({
      provider: 'weixin',
      success(res) {
        if (res.code) {
          resolve(res.code)
        } else {
          reject(new Error('微信授权失败：未获取到 code'))
        }
      },
      fail(err) {
        reject(new Error(err.errMsg || '微信授权失败'))
      }
    })
    // #endif
    // #ifndef MP-WEIXIN
    reject(new Error('当前平台不支持微信登录，请使用账号密码登录'))
    // #endif
  })
}

/**
 * 微信授权登录
 * - openid 已绑定   → resolve({ needBind: false, token, user })，会话已保存
 * - openid 未绑定   → resolve({ needBind: true, code })，页面引导账号密码绑定
 * - 接口/平台错误   → reject(Error)
 * @returns {Promise<{needBind: boolean, token?: string, user?: object, code?: string}>}
 */
export async function wechatLoginCheckBind() {
  const code = await getWechatCode()
  const data = await post('/api/auth/wechat/login', { code })
  if (data && data.need_bind) {
    return { needBind: true, code }
  }
  saveSession(data)
  return { needBind: false, token: data.token, user: data.user, code }
}

/**
 * 绑定微信到指定账号（openid 未绑定时引导用户输入账号密码完成绑定）
 * @param {string} code     微信登录 code（来自 wechatLoginCheckBind）
 * @param {string} username 账号（学号/工号）
 * @param {string} password 密码
 * @returns {Promise<{token, user}>}
 */
export async function bindWechat(code, username, password) {
  const data = await post('/api/auth/wechat/login', { code, username, password })
  saveSession(data)
  return { token: data.token, user: data.user }
}

/**
 * 解绑微信（需登录态）
 * @returns {Promise}
 */
export function unbindWechat() {
  return del('/api/auth/wechat/unbind')
}

/** 保存登录会话到本地（token 持久化） */
export function saveSession(data) {
  if (data && data.token) {
    uni.setStorageSync(STORAGE_KEYS.token, data.token)
  }
  if (data && data.user) {
    uni.setStorageSync(STORAGE_KEYS.userInfo, data.user)
  }
}

/** 清除本地会话（退出登录 / 401 时） */
export function clearSession() {
  uni.removeStorageSync(STORAGE_KEYS.token)
  uni.removeStorageSync(STORAGE_KEYS.userInfo)
}
