import React from 'react'
import { Routes, Route } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { WebSocketProvider } from './context/WebSocketContext'
import ProtectedRoute from './components/Auth/ProtectedRoute'
import Layout from './components/Layout/Layout'

import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import LabDetailPage from './pages/LabDetailPage'
import SoftwarePage from './pages/SoftwarePage'
import TimetablePage from './pages/TimetablePage'
import DamageReportsPage from './pages/DamageReportsPage'
import NotFoundPage from './pages/NotFoundPage'

function App() {
  return (
    <AuthProvider>
      <WebSocketProvider>
        <Routes>
          {/* Public Authentication Route */}
          <Route path="/login" element={<LoginPage />} />

          {/* Protected Routes wrapped in Layout */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout>
                  <DashboardPage />
                </Layout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/labs/:labId"
            element={
              <ProtectedRoute>
                <Layout>
                  <LabDetailPage />
                </Layout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/software"
            element={
              <ProtectedRoute>
                <Layout>
                  <SoftwarePage />
                </Layout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/timetable"
            element={
              <ProtectedRoute allowedRoles={['ADMIN', 'PROFESSOR']}>
                <Layout>
                  <TimetablePage />
                </Layout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/damage-reports"
            element={
              <ProtectedRoute>
                <Layout>
                  <DamageReportsPage />
                </Layout>
              </ProtectedRoute>
            }
          />

          {/* Catch-all 404 Route */}
          <Route
            path="*"
            element={
              <Layout>
                <NotFoundPage />
              </Layout>
            }
          />
        </Routes>
      </WebSocketProvider>
    </AuthProvider>
  )
}

export default App
