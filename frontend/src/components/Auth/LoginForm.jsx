import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import {
  FiMonitor,
  FiMail,
  FiLock,
  FiUser,
  FiArrowRight,
  FiAlertCircle,
  FiShield,
} from 'react-icons/fi'

const LoginForm = () => {
  const [isRegister, setIsRegister] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState('STUDENT')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const { login, register } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (isRegister) {
        const res = await register(email, password, fullName, role)
        if (res.success) {
          navigate('/')
        } else {
          setError(res.error || 'Failed to register account')
        }
      } else {
        const res = await login(email, password)
        if (res.success) {
          navigate('/')
        } else {
          setError(res.error || 'Invalid email or password')
        }
      }
    } catch (err) {
      setError('An unexpected error occurred. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="glass-card"
      style={{
        width: '100%',
        maxWidth: '440px',
        padding: '2.5rem 2rem',
        borderRadius: 'var(--radius-lg)',
        boxShadow: 'var(--shadow-lg)',
        background: 'hsla(220, 20%, 10%, 0.85)',
        border: '1px solid var(--border-glass-hover)',
      }}
    >
      {/* Brand Header */}
      <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
        <div
          className="brand-icon"
          style={{
            width: '48px',
            height: '48px',
            margin: '0 auto 1rem auto',
            borderRadius: 'var(--radius-md)',
          }}
        >
          <FiMonitor size={26} />
        </div>
        <h2 style={{ fontSize: '1.75rem', fontWeight: 800, letterSpacing: '-0.025em' }}>
          Lab<span style={{ color: 'var(--color-primary)' }}>Sense</span>
        </h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
          {isRegister ? 'Create an account to monitor campus labs' : 'Real-time smart campus lab intelligence'}
        </p>
      </div>

      {error && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.75rem 1rem',
            borderRadius: 'var(--radius-sm)',
            background: 'hsla(0, 84%, 60%, 0.15)',
            border: '1px solid var(--color-danger)',
            color: 'var(--color-danger)',
            fontSize: '0.85rem',
            marginBottom: '1.25rem',
          }}
        >
          <FiAlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
        {isRegister && (
          <div className="input-group">
            <label className="input-label">Full Name</label>
            <div className="search-input-wrapper">
              <span className="search-input-icon" style={{ left: '0.75rem' }}>
                <FiUser size={16} />
              </span>
              <input
                type="text"
                className="input"
                style={{ paddingLeft: '2.3rem' }}
                placeholder="Dr. Alan Turing"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />
            </div>
          </div>
        )}

        <div className="input-group">
          <label className="input-label">Email Address</label>
          <div className="search-input-wrapper">
            <span className="search-input-icon" style={{ left: '0.75rem' }}>
              <FiMail size={16} />
            </span>
            <input
              type="email"
              className="input"
              style={{ paddingLeft: '2.3rem' }}
              placeholder="user@campus.edu"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
        </div>

        <div className="input-group">
          <label className="input-label">Password</label>
          <div className="search-input-wrapper">
            <span className="search-input-icon" style={{ left: '0.75rem' }}>
              <FiLock size={16} />
            </span>
            <input
              type="password"
              className="input"
              style={{ paddingLeft: '2.3rem' }}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
        </div>

        {isRegister && (
          <div className="input-group">
            <label className="input-label">Select Role</label>
            <div className="search-input-wrapper">
              <span className="search-input-icon" style={{ left: '0.75rem' }}>
                <FiShield size={16} />
              </span>
              <select
                className="select"
                style={{ paddingLeft: '2.3rem' }}
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                <option value="STUDENT" style={{ background: '#131722' }}>Student</option>
                <option value="PROFESSOR" style={{ background: '#131722' }}>Professor / Instructor</option>
                <option value="ADMIN" style={{ background: '#131722' }}>System Administrator</option>
              </select>
            </div>
          </div>
        )}

        <button
          type="submit"
          className="btn btn-primary"
          disabled={loading}
          style={{ width: '100%', padding: '0.75rem', marginTop: '0.5rem' }}
        >
          <span>{loading ? 'Please wait...' : isRegister ? 'Create Account' : 'Sign In'}</span>
          <FiArrowRight size={16} />
        </button>
      </form>

      {/* Switch between Login and Register */}
      <div style={{ textAlign: 'center', marginTop: '1.5rem', paddingTop: '1.25rem', borderTop: '1px solid var(--border-glass)' }}>
        <button
          type="button"
          onClick={() => {
            setIsRegister(!isRegister)
            setError('')
          }}
          className="btn btn-ghost"
          style={{ fontSize: '0.85rem' }}
        >
          {isRegister
            ? 'Already have an account? Sign In'
            : "Don't have an account? Create one"}
        </button>
      </div>
    </div>
  )
}

export default LoginForm
