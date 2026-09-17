import React, { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FiChevronDown, FiLogOut, FiMenu, FiMonitor, FiMoon, FiSun } from 'react-icons/fi'
import { useAuth } from '../../hooks/useAuth'
import { useLabState } from '../../hooks/useLabState'
import { useTheme } from '../../context/ThemeContext'

const THEME_CYCLE = { system: 'light', light: 'dark', dark: 'system' }
const THEME_ICON = { system: FiMonitor, light: FiSun, dark: FiMoon }
const THEME_LABEL = { system: 'System theme', light: 'Light theme', dark: 'Dark theme' }

const initials = (user) => {
  const source = user?.full_name || user?.email || '?'
  const parts = source.split(/[\s@.]+/).filter(Boolean)
  return ((parts[0]?.[0] || '') + (user?.full_name ? parts[1]?.[0] || '' : '')).toUpperCase()
}

const Navbar = ({ onMenu }) => {
  const { user, logout } = useAuth()
  const { connected } = useLabState()
  const { preference, setPreference } = useTheme()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!menuOpen) return undefined
    const onDown = (e) => menuRef.current && !menuRef.current.contains(e.target) && setMenuOpen(false)
    const onKey = (e) => e.key === 'Escape' && setMenuOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [menuOpen])

  const ThemeIcon = THEME_ICON[preference] || FiMonitor
  const displayName = user?.full_name || user?.email?.split('@')[0] || 'Account'

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="topbar">
      <button type="button" className="btn btn--ghost btn--icon topbar__menu" onClick={onMenu} aria-label="Open navigation">
        <FiMenu size={18} />
      </button>

      <div
        className={`live ${connected ? 'live--on' : ''}`}
        title={connected ? 'Receiving live updates' : 'Reconnecting to live updates…'}
      >
        <span className="live__dot" aria-hidden="true" />
        <span className="live__text">{connected ? 'Live' : 'Reconnecting…'}</span>
      </div>

      <div className="topbar__spacer" />

      <button
        type="button"
        className="btn btn--ghost btn--icon"
        onClick={() => setPreference(THEME_CYCLE[preference] || 'system')}
        title={`${THEME_LABEL[preference]} — click to change`}
        aria-label={`${THEME_LABEL[preference]}. Change theme`}
      >
        <ThemeIcon size={16} />
      </button>

      {user && (
        <div className="user-menu" ref={menuRef}>
          <button
            type="button"
            className="user-menu__trigger"
            onClick={() => setMenuOpen((v) => !v)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
          >
            <span className="avatar" aria-hidden="true">
              {initials(user)}
            </span>
            <span className="user-menu__text">
              <span className="user-menu__name" style={{ display: 'block' }}>
                {displayName}
              </span>
              <span className="user-menu__role">{(user.role || '').toLowerCase()}</span>
            </span>
            <FiChevronDown size={14} className="subtle" />
          </button>

          {menuOpen && (
            <div className="menu" role="menu">
              <div className="menu__header">
                <div style={{ fontWeight: 500 }}>{displayName}</div>
                <div className="subtle" style={{ fontSize: 12 }}>
                  {user.email}
                </div>
              </div>
              <button type="button" role="menuitem" className="menu__item" onClick={handleLogout}>
                <FiLogOut size={15} />
                Sign out
              </button>
            </div>
          )}
        </div>
      )}
    </header>
  )
}

export default Navbar
