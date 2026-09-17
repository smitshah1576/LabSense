import React, { createContext, useState, useEffect, useCallback } from 'react'
import { authApi } from '../api/endpoints'

export const AuthContext = createContext(null)

// Helper to decode JWT payload safely
const decodeJwt = (token) => {
  try {
    const base64Url = token.split('.')[1]
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    return JSON.parse(jsonPayload)
  } catch {
    return null
  }
}

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => localStorage.getItem('labsense_token'))
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('labsense_user')
    if (stored) {
      try {
        return JSON.parse(stored)
      } catch {
        return null
      }
    }
    const tok = localStorage.getItem('labsense_token')
    if (tok) {
      const decoded = decodeJwt(tok)
      if (decoded) {
        return {
          email: decoded.sub,
          id: decoded.user_id,
          role: decoded.role,
        }
      }
    }
    return null
  })
  const [loading, setLoading] = useState(false)

  const handleAuthSuccess = (accessToken, userProfile = null) => {
    const decoded = decodeJwt(accessToken)
    const userData = userProfile || {
      email: decoded?.sub,
      id: decoded?.user_id,
      role: decoded?.role || 'STUDENT',
    }

    setToken(accessToken)
    setUser(userData)
    localStorage.setItem('labsense_token', accessToken)
    localStorage.setItem('labsense_user', JSON.stringify(userData))
  }

  const login = async (email, password) => {
    setLoading(true)
    try {
      const res = await authApi.login(email, password)
      const accessToken = res.data.access_token
      // The login response includes the profile; keep it so the UI can show
      // the person's name rather than falling back to their email address.
      const profile = res.data.user
        ? {
            email: res.data.user.email,
            id: res.data.user.user_id,
            role: res.data.user.role,
            full_name: res.data.user.full_name,
          }
        : null
      handleAuthSuccess(accessToken, profile)
      return { success: true }
    } catch (err) {
      const message = err.response?.data?.detail || 'Invalid email or password'
      return { success: false, error: message }
    } finally {
      setLoading(false)
    }
  }

  const register = async (email, password, fullName, role) => {
    setLoading(true)
    try {
      const res = await authApi.register(email, password, fullName, role)
      const accessToken = res.data.access_token
      const u = res.data.user
      handleAuthSuccess(
        accessToken,
        u ? { email: u.email, id: u.user_id, role: u.role, full_name: u.full_name } : { email, role, full_name: fullName }
      )
      return { success: true }
    } catch (err) {
      const message = err.response?.data?.detail || 'Registration failed'
      return { success: false, error: message }
    } finally {
      setLoading(false)
    }
  }

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
    localStorage.removeItem('labsense_token')
    localStorage.removeItem('labsense_user')
  }, [])

  const isAuthenticated = !!token && !!user
  const isAdmin = () => user?.role === 'ADMIN'
  const isProfessor = () => user?.role === 'PROFESSOR' || user?.role === 'ADMIN'
  const isStudent = () => user?.role === 'STUDENT'

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        loading,
        isAuthenticated,
        login,
        register,
        logout,
        isAdmin,
        isProfessor,
        isStudent,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
