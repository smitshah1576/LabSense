import React, { createContext, useContext, useEffect, useState } from 'react'

const STORAGE_KEY = 'labsense_theme'
const ThemeContext = createContext(null)

const readPreference = () => {
  try {
    return localStorage.getItem(STORAGE_KEY) || 'system'
  } catch {
    return 'system'
  }
}

const systemPrefersDark = () =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches

export const ThemeProvider = ({ children }) => {
  const [preference, setPreference] = useState(readPreference)
  const [systemDark, setSystemDark] = useState(systemPrefersDark)

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (e) => setSystemDark(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const resolved = preference === 'system' ? (systemDark ? 'dark' : 'light') : preference

  useEffect(() => {
    document.documentElement.dataset.theme = resolved
  }, [resolved])

  const choose = (next) => {
    setPreference(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      /* storage unavailable — the choice still applies for this session */
    }
  }

  return (
    <ThemeContext.Provider value={{ preference, resolved, setPreference: choose }}>
      {children}
    </ThemeContext.Provider>
  )
}

export const useTheme = () => useContext(ThemeContext)
