import React from 'react'
import { Link } from 'react-router-dom'
import { FiAlertCircle, FiArrowLeft } from 'react-icons/fi'

const NotFoundPage = () => {
  return (
    <div
      style={{
        minHeight: '70vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem',
      }}
    >
      <div
        className="glass-card"
        style={{
          maxWidth: '480px',
          width: '100%',
          textAlign: 'center',
          padding: '3rem 2rem',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '1.25rem',
        }}
      >
        <div
          style={{
            width: '64px',
            height: '64px',
            borderRadius: '50%',
            background: 'hsla(0, 84%, 60%, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--color-danger)',
          }}
        >
          <FiAlertCircle size={32} />
        </div>

        <h1 style={{ fontSize: '3rem', fontWeight: 800, lineHeight: 1 }}>404</h1>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
          Page Not Found
        </h2>
        <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>
          The requested campus lab resource or page does not exist or has been relocated.
        </p>

        <Link to="/" className="btn btn-primary" style={{ marginTop: '0.5rem' }}>
          <FiArrowLeft size={16} />
          <span>Return to Dashboard</span>
        </Link>
      </div>
    </div>
  )
}

export default NotFoundPage
