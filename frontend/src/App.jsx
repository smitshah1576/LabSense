import React from 'react'
import { Route, Routes } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { WebSocketProvider } from './context/WebSocketContext'
import { LabsProvider } from './context/LabsContext'
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
          <Route path="/login" element={<LoginPage />} />

          {/* Every signed-in page shares one Layout, so the sidebar stays
              mounted (and does not refetch) while navigating. */}
          <Route
            element={
              <ProtectedRoute>
                <LabsProvider>
                  <Layout />
                </LabsProvider>
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<DashboardPage />} />
            <Route path="/labs/:labId" element={<LabDetailPage />} />
            <Route path="/software" element={<SoftwarePage />} />
            <Route
              path="/timetable"
              element={
                <ProtectedRoute allowedRoles={['ADMIN', 'PROFESSOR']}>
                  <TimetablePage />
                </ProtectedRoute>
              }
            />
            <Route path="/damage-reports" element={<DamageReportsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </WebSocketProvider>
    </AuthProvider>
  )
}

export default App
