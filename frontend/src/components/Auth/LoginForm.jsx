import React, { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { FiAlertCircle, FiArrowRight, FiLoader } from 'react-icons/fi'
import { useAuth } from '../../hooks/useAuth'

const LoginForm = () => {
  const [isRegister, setIsRegister] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState('STUDENT')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const { login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const res = isRegister ? await register(email, password, fullName, role) : await login(email, password)
      if (res.success) {
        navigate(location.state?.from?.pathname || '/', { replace: true })
      } else {
        setError(res.error || (isRegister ? 'Could not create the account.' : 'Incorrect email or password.'))
      }
    } catch {
      setError('Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const switchMode = () => {
    setIsRegister((v) => !v)
    setError('')
  }

  return (
    <div className="auth__form">
      <h2>{isRegister ? 'Create an account' : 'Sign in'}</h2>
      <p>{isRegister ? 'Get live access to lab availability.' : 'Welcome back. Sign in with your campus account.'}</p>

      <form onSubmit={handleSubmit} className="auth__fields">
        {error && (
          <div className="alert alert--error" role="alert">
            <FiAlertCircle size={15} />
            <span>{error}</span>
          </div>
        )}

        {isRegister && (
          <div className="field">
            <label className="field__label" htmlFor="fullName">
              Full name
            </label>
            <input
              id="fullName"
              className="input"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              autoComplete="name"
              required
            />
          </div>
        )}

        <div className="field">
          <label className="field__label" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            className="input"
            placeholder="you@campus.edu"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            autoFocus
            required
          />
        </div>

        <div className="field">
          <label className="field__label" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={isRegister ? 'new-password' : 'current-password'}
            required
          />
        </div>

        {isRegister && (
          <div className="field">
            <label className="field__label" htmlFor="role">
              Role
            </label>
            <select id="role" className="select" value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="STUDENT">Student</option>
              <option value="PROFESSOR">Professor</option>
              <option value="ADMIN">Administrator</option>
            </select>
          </div>
        )}

        <button type="submit" className="btn btn--primary btn--lg btn--block" disabled={submitting} style={{ marginTop: 6 }}>
          {submitting ? <FiLoader size={16} className="spin" /> : null}
          {submitting ? 'Please wait…' : isRegister ? 'Create account' : 'Sign in'}
          {!submitting && <FiArrowRight size={16} />}
        </button>
      </form>

      <p className="auth__switch">
        {isRegister ? 'Already have an account? ' : 'New to LabSense? '}
        <button type="button" className="link" onClick={switchMode}>
          {isRegister ? 'Sign in' : 'Create an account'}
        </button>
      </p>
    </div>
  )
}

export default LoginForm
