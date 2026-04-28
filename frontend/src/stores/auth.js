import { defineStore } from 'pinia'
import http from '../api/http'

export const useAuthStore = defineStore('auth', {
  // 鉴权状态统一保存在 Pinia，并同步落盘到 localStorage。
  state: () => ({
    accessToken: '',
    refreshToken: '',
    profile: null,
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.accessToken && state.profile),
    isSystemAdmin: (state) => state.profile?.role === 'system_admin',
    isAdmin: (state) => ['system_admin', 'admin'].includes(state.profile?.role),
    isMember: (state) => state.profile?.role === 'member',
  },
  actions: {
    hydrate() {
      // 页面刷新后恢复登录上下文，避免出现“接口已登录、页面未登录”的状态割裂。
      if (this.accessToken) {
        return
      }
      this.accessToken = localStorage.getItem('access_token') || ''
      this.refreshToken = localStorage.getItem('refresh_token') || ''
      const profile = localStorage.getItem('profile')
      this.profile = profile ? JSON.parse(profile) : null
    },
    persist() {
      // 统一持久化入口，减少不同动作分别操作 localStorage 时的遗漏风险。
      localStorage.setItem('access_token', this.accessToken || '')
      localStorage.setItem('refresh_token', this.refreshToken || '')
      localStorage.setItem('profile', JSON.stringify(this.profile || null))
    },
    async login(payload) {
      // 登录后立即拉取当前用户资料，保证页面可以立刻按角色渲染。
      const { data } = await http.post('/auth/login', payload)
      this.accessToken = data.access_token
      this.refreshToken = data.refresh_token
      await this.fetchMe()
      this.persist()
    },
    async refresh() {
      try {
        const { data } = await http.post('/auth/refresh', { refresh_token: this.refreshToken })
        this.accessToken = data.access_token
        this.refreshToken = data.refresh_token
        await this.fetchMe()
        this.persist()
        return true
      } catch (error) {
        return false
      }
    },
    async fetchMe() {
      // 当前用户资料是路由鉴权、菜单展示与页面权限判断的统一来源。
      const { data } = await http.get('/auth/me')
      this.profile = data
      this.persist()
    },
    logout() {
      // 退出时清空内存和本地缓存，避免脏状态影响下次登录。
      this.accessToken = ''
      this.refreshToken = ''
      this.profile = null
      this.persist()
    },
  },
})
