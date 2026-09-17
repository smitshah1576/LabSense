import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { FiLoader } from 'react-icons/fi'
import { useAuth } from '../../hooks/useAuth'

const ProtectedRoute = ({ children, allowedRoles }) => {
  const { isAuthenticated, user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="center-screen">
        <FiLoader className="spin" size={20} aria-label="Signing in" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return <Navigate to="/" replace />
  }

  return children
}

export default ProtectedRoute
