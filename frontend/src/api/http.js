import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const http = axios.create({
  baseURL: '/api/v1',
})

let refreshInFlight = null

function isRefreshRequest(config) {
  return (config?.url || '').includes('/auth/refresh')
}

function redirectToLogin() {
  if (window.location.pathname !== '/auth/login') {
    window.location.replace('/auth/login')
  }
}

http.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const auth = useAuthStore()
    const originalRequest = error.config

    if (error.response?.status !== 401 || !originalRequest) {
      return Promise.reject(error)
    }

    if (isRefreshRequest(originalRequest) || originalRequest._skipAuthRefresh || originalRequest._retry || !auth.refreshToken) {
      auth.logout()
      redirectToLogin()
      return Promise.reject(error)
    }

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
