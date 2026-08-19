import React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useLabState } from '../../hooks/useLabState'
import { FiMonitor, FiLogOut, FiActivity, FiUser } from 'react-icons/fi'

const Navbar = () => {
  const { user, logout } = useAuth()
  const { connected } = useLabState()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const getRoleBadgeClass = (role) => {
    switch (role) {
      case 'ADMIN':
        return 'badge-maintenance'
      case 'PROFESSOR':
        return 'badge-sleep'
      default:
        return 'badge-in-use'
    }
  }

  return (
    <header className="navbar">
      <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
        <Link to="/" className="nav-brand">
          <div className="brand-icon">
            <FiMonitor size={20} />
          </div>
          <span>
            Lab<span style={{ color: 'var(--color-primary)' }}>Sense</span>
          </span>
        </Link>

        {/* Live sync indicator */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.75rem',
            padding: '0.25rem 0.65rem',
            borderRadius: 'var(--radius-full)',
            background: connected ? 'hsla(142, 71%, 45%, 0.1)' : 'hsla(38, 92%, 50%, 0.1)',
            border: `1px solid ${connected ? 'hsla(142, 71%, 45%, 0.25)' : 'hsla(38, 92%, 50%, 0.25)'}`,
            color: connected ? 'var(--color-success)' : 'var(--color-warning)',
          }}
          title={connected ? 'Real-time WebSocket connected' : 'Connecting to live updates...'}
        >
          <span
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              backgroundColor: connected ? 'var(--color-success)' : 'var(--color-warning)',
              boxShadow: connected ? '0 0 6px var(--color-success)' : '0 0 6px var(--color-warning)',
            }}
          />
          <span style={{ fontWeight: 500 }}>
            {connected ? 'LIVE SYNC' : 'CONNECTING...'}
          </span>
        </div>
      </div>

      <div className="nav-user">
        {user && (
          <div className="user-badge">
            <div className="user-avatar">
              {user.full_name ? user.full_name.charAt(0).toUpperCase() : user.email.charAt(0).toUpperCase()}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', textAlign: 'left', lineHeight: 1.2 }}>
              <span style={{ fontWeight: 600, fontSize: '0.82rem' }}>
                {user.full_name || user.email.split('@')[0]}
              </span>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                {user.email}
              </span>
            </div>
            <span className={`badge ${getRoleBadgeClass(user.role)}`} style={{ fontSize: '0.65rem', padding: '0.15rem 0.45rem' }}>
              {user.role}
            </span>
          </div>
        )}

        <button
          onClick={handleLogout}
          className="btn btn-ghost btn-sm"
          title="Sign out of LabSense"
          style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-secondary)' }}
        >
          <FiLogOut size={16} />
          <span>Logout</span>
        </button>
      </div>
    </header>
  )
}

export default Navbar
