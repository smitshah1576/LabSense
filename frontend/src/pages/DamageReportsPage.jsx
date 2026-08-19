import React, { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../hooks/useAuth'
import { damageReportsApi } from '../api/endpoints'
import ReportForm from '../components/DamageReport/ReportForm'
import ReportReviewList from '../components/DamageReport/ReportReviewList'
import {
  FiAlertTriangle,
  FiList,
  FiPlusCircle,
  FiRefreshCw,
  FiCheckCircle,
} from 'react-icons/fi'

const DamageReportsPage = () => {
  const { isAdmin } = useAuth()
  const [reports, setReports] = useState([])
  const [pendingOnly, setPendingOnly] = useState(true)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState(isAdmin() ? 'review' : 'submit')

  const fetchReports = useCallback(async () => {
    if (!isAdmin()) return
    setLoading(true)
    try {
      const res = pendingOnly
        ? await damageReportsApi.getPendingReports()
        : await damageReportsApi.getReports()
      if (Array.isArray(res.data)) {
        setReports(res.data)
      }
    } catch (err) {
      console.error('Failed to fetch damage reports:', err)
    } finally {
      setLoading(false)
    }
  }, [isAdmin, pendingOnly])

  useEffect(() => {
    fetchReports()
  }, [fetchReports])

  return (
    <div className="page-container">
      <div className="page-header">
        <div className="page-title-group">
          <h1 className="page-title">
            <FiAlertTriangle style={{ color: 'var(--color-warning)' }} />
            Damage Reports & Maintenance
          </h1>
          <p className="page-subtitle">
            Report malfunctioning lab hardware, faulty mice/keyboards, or review incoming incident reports
          </p>
        </div>

        {isAdmin() && activeTab === 'review' && (
          <div className="page-actions">
            <button
              onClick={() => setPendingOnly(!pendingOnly)}
              className="btn btn-secondary btn-sm"
            >
              {pendingOnly ? 'Show All History' : 'Show Pending Only'}
            </button>

            <button onClick={fetchReports} className="btn btn-ghost btn-sm">
              <FiRefreshCw size={14} />
            </button>
          </div>
        )}
      </div>

      {/* Tabs for Admin / Students */}
      {isAdmin() && (
        <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid var(--border-glass)', paddingBottom: '0.5rem' }}>
          <button
            onClick={() => setActiveTab('review')}
            className={`btn ${activeTab === 'review' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ fontSize: '0.85rem' }}
          >
            <FiList size={15} />
            <span>Admin Review Queue ({reports.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('submit')}
            className={`btn ${activeTab === 'submit' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ fontSize: '0.85rem' }}
          >
            <FiPlusCircle size={15} />
            <span>Submit New Ticket</span>
          </button>
        </div>
      )}

      {/* View 1: Submit Form */}
      {(!isAdmin() || activeTab === 'submit') && (
        <div style={{ maxWidth: '720px' }}>
          <ReportForm onReportSubmitted={fetchReports} />
        </div>
      )}

      {/* View 2: Admin Review Queue */}
      {isAdmin() && activeTab === 'review' && (
        <div>
          <ReportReviewList
            reports={reports}
            onReportResolved={fetchReports}
            loading={loading}
          />
        </div>
      )}
    </div>
  )
}

export default DamageReportsPage
