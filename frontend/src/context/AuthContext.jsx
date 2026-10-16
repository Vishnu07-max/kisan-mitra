import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { tokenStore } from '../services/api'
import * as authApi from '../services/auth'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const { i18n } = useTranslation()
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(Boolean(tokenStore.access))

  const loadProfile = useCallback(async () => {
    try {
      const data = await authApi.getProfile()
      setProfile(data)
      return data
    } catch (err) {
      if (err.response?.status === 401) tokenStore.clear()
      setProfile(null)
      return null
    }
  }, [])

  // On page load: if we have a token, fetch the profile
  useEffect(() => {
    if (tokenStore.access) {
      loadProfile().finally(() => setLoading(false))
    }
  }, [loadProfile])

  // The API layer tells us when the session is dead
  useEffect(() => {
    const onLogout = () => setProfile(null)
    window.addEventListener('auth:logout', onLogout)
    return () => window.removeEventListener('auth:logout', onLogout)
  }, [])

  const login = async (username, password) => {
    await authApi.login(username, password)
    const data = await loadProfile()
    if (data?.preferred_language) i18n.changeLanguage(data.preferred_language)
  }

  const register = async (formData) => {
    await authApi.register(formData)
    await loadProfile()
  }

  const logout = async () => {
    await authApi.logout()
    setProfile(null)
  }

  const value = {
    profile,
    setProfile,
    loading,
    isAuthenticated: Boolean(profile),
    login,
    register,
    logout,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)