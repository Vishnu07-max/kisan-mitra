import api, { tokenStore } from './api'

export async function register(data) {
  const res = await api.post('/auth/register/', data)
  tokenStore.set(res.data.tokens)
  return res.data
}

export async function login(username, password) {
  const res = await api.post('/auth/login/', { username, password })
  tokenStore.set(res.data)
}

export async function logout() {
  const refresh = tokenStore.refresh
  try {
    if (refresh) await api.post('/auth/logout/', { refresh })
  } catch {
    // Even if the server call fails, we still log out locally
  }
  tokenStore.clear()
}

export const getProfile = () => api.get('/profile/').then((res) => res.data)
export const updateProfile = (data) => api.patch('/profile/', data).then((res) => res.data)