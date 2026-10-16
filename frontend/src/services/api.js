import axios from 'axios'

const baseURL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1'

// Simple helper for the two login tokens
export const tokenStore = {
  get access() {
    return localStorage.getItem('access')
  },
  get refresh() {
    return localStorage.getItem('refresh')
  },
  set(tokens) {
    if (tokens.access) localStorage.setItem('access', tokens.access)
    if (tokens.refresh) localStorage.setItem('refresh', tokens.refresh)
  },
  clear() {
    localStorage.removeItem('access')
    localStorage.removeItem('refresh')
  },
}

const api = axios.create({ baseURL, timeout: 10000 })

// Attach the access token to every request
api.interceptors.request.use((config) => {
  const token = tokenStore.access
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// If several requests fail at once, refresh only one time
let refreshPromise = null

function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = axios
      .post(`${baseURL}/auth/refresh/`, { refresh: tokenStore.refresh }, { timeout: 10000 })
      .then((res) => {
        tokenStore.set({ access: res.data.access, refresh: res.data.refresh })
        return res.data.access
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

// On 401 (expired access token): refresh once, then retry the request
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    const isAuthCall = original?.url?.includes('/auth/')

    if (
      error.response?.status === 401 &&
      !original._retry &&
      !isAuthCall &&
      tokenStore.refresh
    ) {
      original._retry = true
      try {
        const access = await refreshAccessToken()
        original.headers.Authorization = `Bearer ${access}`
        return api(original)
      } catch {
        tokenStore.clear()
        window.dispatchEvent(new Event('auth:logout'))
      }
    }
    return Promise.reject(error)
  },
)

export default api