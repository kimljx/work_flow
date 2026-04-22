import { defineStore } from 'pinia'
import http from '../api/http'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: '',
    refreshToken: '',
    profile: null,
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.accessToken && state.profile),
    isAdmin: (state) => state.profile?.role === 'admin',
    isMember: (state) => state.profile?.role === 'member',
  },
  actions: {
    hydrate() {
      if (this.accessToken) {
        return
      }
      this.accessToken = localStorage.getItem('access_token') || ''
      this.refreshToken = localStorage.getItem('refresh_token') || ''
      const profile = localStorage.getItem('profile')
      this.profile = profile ? JSON.parse(profile) : null
    },
    persist() {
      localStorage.setItem('access_token', this.accessToken || '')
      localStorage.setItem('refresh_token', this.refreshToken || '')
      localStorage.setItem('profile', JSON.stringify(this.profile || null))
    },
    async login(payload) {
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
      const { data } = await http.get('/auth/me')
      this.profile = data
      this.persist()
    },
    logout() {
      this.accessToken = ''
      this.refreshToken = ''
      this.profile = null
      this.persist()
    },
  },
})
