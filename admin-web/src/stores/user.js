/**
 * 管理端登录态（Pinia + localStorage 持久化）
 * token 由 simplejwt 签发（/admin/api/auth/login → data.access/refresh）
 */
import { defineStore } from 'pinia'
import { loginApi, refreshTokenApi } from '../api/auth'

export const useUserStore = defineStore('admin-user', {
  state: () => ({
    access: localStorage.getItem('admin_access') || '',
    refresh: localStorage.getItem('admin_refresh') || '',
    userInfo: JSON.parse(localStorage.getItem('admin_user') || 'null')
  }),
  getters: {
    isLoggedIn: (s) => Boolean(s.access)
  },
  actions: {
    async login(username, password) {
      const data = await loginApi(username, password)
      this.access = data.access
      this.refresh = data.refresh
      this.userInfo = { username, name: username }
      localStorage.setItem('admin_access', data.access)
      localStorage.setItem('admin_refresh', data.refresh)
      localStorage.setItem('admin_user', JSON.stringify(this.userInfo))
    },
    async tryRefresh() {
      if (!this.refresh) return false
      try {
        const data = await refreshTokenApi(this.refresh)
        this.access = data.access
        localStorage.setItem('admin_access', data.access)
        return true
      } catch (e) {
        this.logout()
        return false
      }
    },
    logout() {
      this.access = ''
      this.refresh = ''
      this.userInfo = null
      localStorage.removeItem('admin_access')
      localStorage.removeItem('admin_refresh')
      localStorage.removeItem('admin_user')
    }
  }
})
