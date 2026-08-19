import React, { useState } from 'react'
import { damageReportsApi } from '../../api/endpoints'
import {
  FiCheck,
  FiX,
  FiClock,
  FiAlertCircle,
  FiUser,
  FiMonitor,
} from 'react-icons/fi'

const ReportReviewList = ({ reports = [], onReportResolved, loading = false }) => {
  const [resolvingId, setResolvingId] = useState(null)

  const handleResolve = async (reportId, status) => {
    setResolvingId(reportId)
    try {
      await damageReportsApi.resolveReport(reportId, status)
      if (onReportResolved) onReportResolved()
    } catch (err) {
      console.error('Failed to resolve damage report:', err)
      alert(err.response?.data?.detail || 'Failed to update report status')
    } finally {
      setResolvingId(null)
    }
  }

  const formatDate = (isoString) => {
    if (!isoString) return ''
    try {
      const d = new Date(isoString)
      return `${d.toLocaleDateString()} at ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
    } catch {
      return isoString
    }
  }

  const getStatusBadge = (status) => {
    switch ((status || '').toUpperCase()) {
      case 'PENDING':
        return <span className="badge badge-maintenance">Pending Review</span>
      case 'APPROVED':
        return <span className="badge badge-closed">Approved (In Maint.)</span>
      case 'DISMISSED':
        return <span className="badge badge-ghost" style={{ border: '1px solid var(--border-subtle)' }}>Dismissed</span>
      default:
        return <span className="badge badge-ghost">{status}</span>
    }
  }

  if (loading) {
    return (
      <div className="glass-panel" style={{ textAlign: 'center', padding: '2.5rem' }}>
        <p style={{ color: 'var(--text-secondary)' }}>Loading damage report queue...</p>
      </div>
    )
  }

  if (reports.length === 0) {
    return (
      <div className="glass-panel" style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-muted)' }}>
        <FiCheck size={40} style={{ opacity: 0.4, color: 'var(--color-success)', marginBottom: '0.5rem' }} />
        <p>No damage reports in this queue.</p>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
      {reports.map((report) => {
        const isPending = (report.status || '').toUpperCase() === 'PENDING'
        const isResolving = resolvingId === report.id

        return (
          <div
            key={report.id}
            className="glass-card"
            style={{
              padding: '1.25rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
              borderLeft: isPending ? '3px solid var(--color-warning)' : '1px solid var(--border-glass)',
            }}
          >
            <div className="flex-between">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.35rem',
                    fontFamily: 'JetBrains Mono, monospace',
                    fontWeight: 600,
                    fontSize: '0.95rem',
                    color: 'var(--text-primary)',
                  }}
                >
                  <FiMonitor size={15} style={{ color: 'var(--color-primary)' }} />
                  <span>PC: {report.pc_id}</span>
                </div>
                {getStatusBadge(report.status)}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <FiClock size={12} />
                <span>{formatDate(report.created_at)}</span>
              </div>
            </div>

            <div
              style={{
                fontSize: '0.875rem',
                color: 'var(--text-secondary)',
                lineHeight: 1.5,
                background: 'hsla(220, 20%, 8%, 0.5)',
                padding: '0.75rem 0.9rem',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-glass)',
              }}
            >
              {report.description}
            </div>

            <div className="flex-between" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <FiUser size={12} />
                <span>Reported by User #{report.reported_by}</span>
              </div>

              {isPending && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <button
                    onClick={() => handleResolve(report.id, 'DISMISSED')}
                    disabled={isResolving}
                    className="btn btn-ghost btn-sm"
                    style={{ color: 'var(--text-muted)' }}
                    title="Dismiss report as invalid/resolved"
                  >
                    <FiX size={14} />
                    <span>Dismiss</span>
                  </button>

                  <button
                    onClick={() => handleResolve(report.id, 'APPROVED')}
                    disabled={isResolving}
                    className="btn btn-danger btn-sm"
                    title="Approve report (puts PC into Maintenance mode)"
                  >
                    <FiCheck size={14} />
                    <span>{isResolving ? 'Processing...' : 'Approve & Put in Maintenance'}</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default ReportReviewList
