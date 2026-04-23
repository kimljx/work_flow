import axios from 'axios'
import { useAuthStore } from '../stores/auth'
import { useLoadingStore } from '../stores/loading'

// 全局请求实例，统一注入接口前缀与鉴权处理。
const http = axios.create({
  baseURL: '/api/v1',
})

let refreshInFlight = null

function isRefreshRequest(config) {
  // 刷新令牌请求本身不能再次触发刷新，否则会形成递归死循环。
  return (config?.url || '').includes('/auth/refresh')
}

function redirectToLogin() {
  // 统一跳转逻辑，避免多个页面各自处理登录失效时出现行为不一致。
  if (window.location.pathname !== '/auth/login') {
    window.location.replace('/auth/login')
  }
}

function shouldUseGlobalLoading(config) {
  return !config?.skipGlobalLoading
}

http.interceptors.request.use((config) => {
  const auth = useAuthStore()
  const loading = useLoadingStore()
  if (auth.accessToken) {
    // 请求发出前自动带上最新访问令牌，减少页面层重复传参。
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  if (shouldUseGlobalLoading(config)) {
    loading.start()
  }
  return config
})

http.interceptors.response.use(
  (response) => {
    if (shouldUseGlobalLoading(response.config)) {
      useLoadingStore().finish()
    }
    return response
  },
  async (error) => {
    const auth = useAuthStore()
    const originalRequest = error.config
    if (shouldUseGlobalLoading(originalRequest)) {
      useLoadingStore().finish()
    }

    if (error.response?.status !== 401 || !originalRequest) {
      return Promise.reject(error)
    }

    if (isRefreshRequest(originalRequest) || originalRequest._skipAuthRefresh || originalRequest._retry || !auth.refreshToken) {
      auth.logout()
      redirectToLogin()
      return Promise.reject(error)
    }

    // 多个接口同时 401 时复用同一次刷新请求，避免并发刷新造成令牌覆盖。
    originalRequest._retry = true
    try {
      if (!refreshInFlight) {
        refreshInFlight = auth.refresh().finally(() => {
          refreshInFlight = null
        })
      }
      const refreshed = await refreshInFlight
      if (refreshed) {
        originalRequest.headers = originalRequest.headers || {}
        originalRequest.headers.Authorization = `Bearer ${auth.accessToken}`
        return http(originalRequest)
      }
    } catch {
      // handled below by unified logout + redirect.
    }

    auth.logout()
    redirectToLogin()
    return Promise.reject(error)
  }
)

export default http
