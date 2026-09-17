import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { FiMonitor } from 'react-icons/fi'
import LoginForm from '../components/Auth/LoginForm'
import { useAuth } from '../hooks/useAuth'
import { useDocumentTitle } from '../lib/hooks'

// Decorative only: a miniature lab, to say what the product does at a glance.
const PREVIEW = ['available', 'in-use', 'in-use', 'available', 'sleep', 'in-use', 'available', 'maintenance', 'available', 'in-use']

const LoginPage = () => {
  const { isAuthenticated } = useAuth()
  const location = useLocation()
  useDocumentTitle('Sign in')

  if (isAuthenticated) return <Navigate to={location.state?.from?.pathname || '/'} replace />

  return (
    <div className="auth">
      <aside className="auth__aside">
        <div className="auth__brand">
          <span className="brand-mark" aria-hidden="true">
            <FiMonitor size={15} />
          </span>
          LabSense
        </div>

        <div className="auth__pitch">
          <h1>Know which lab machines are free before you walk over.</h1>
          <p>Live workstation status, lab schedules and installed software for every lab on campus, in one place.</p>
          <div className="auth__preview" aria-hidden="true">
            {PREVIEW.map((tone, i) => (
              <div key={i} className={`auth__preview-pc tone-${tone}`}>
                <i style={{ background: 'var(--tone-dot)' }} />
                <b />
                <b />
              </div>
            ))}
          </div>
        </div>

        <div className="auth__foot">Smart Campus Lab Resource Allocator &amp; Live Monitor</div>
      </aside>

      <main className="auth__main">
        <LoginForm />
      </main>
    </div>
  )
}

export default LoginPage
