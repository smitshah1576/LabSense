import React from 'react'
import { FiCheck, FiInbox, FiMonitor, FiTool, FiX } from 'react-icons/fi'
import EmptyState from '../ui/EmptyState'
import { formatDateTime, relativeTime } from '../../lib/time'

const STATUS = {
  PENDING: { label: 'Pending', tone: 'maintenance' },
  APPROVED: { label: 'Approved', tone: 'available' },
  DISMISSED: { label: 'Dismissed', tone: 'neutral' },
}

const ReportReviewList = ({ reports = [], loading, resolvingId, onResolve, emptyTitle, emptyDescription }) => {
  if (loading && reports.length === 0) return <div className="skeleton" style={{ height: 180 }} />

  if (reports.length === 0) {
    return (
      <div className="card">
        <EmptyState icon={FiInbox} title={emptyTitle} description={emptyDescription} />
      </div>
    )
  }

  return (
    <div className="card" style={{ opacity: loading ? 0.6 : 1 }}>
      {reports.map((report) => {
        const status = STATUS[(report.status || '').toUpperCase()] || { label: report.status, tone: 'neutral' }
        const pending = report.status === 'PENDING'
        const busy = resolvingId === report.report_id
        return (
          <article key={report.report_id} className="report">
            <div style={{ minWidth: 0 }}>
              <div className="report__head">
                <span className="inline-meta" style={{ fontWeight: 500 }}>
                  <FiMonitor size={14} />
                  <span className="mono">{report.pc_id}</span>
                </span>
                <span className={`pill tone-${status.tone}`}>
                  <span className="pill__dot" aria-hidden="true" />
                  {status.label}
                </span>
              </div>
              <p className="report__text">{report.issue_description}</p>
              <div className="report__meta">
                <span title={formatDateTime(report.created_at)}>Reported {relativeTime(report.created_at)}</span>
                <span>by user #{report.reported_by}</span>
                <span className="subtle">Report #{report.report_id}</span>
                {!pending && report.resolved_at && (
                  <span>
                    {status.label} {relativeTime(report.resolved_at)}
                    {report.resolved_by ? ` by user #${report.resolved_by}` : ''}
                  </span>
                )}
              </div>
            </div>

            {pending && onResolve && (
              <div className="report__actions">
                <button type="button" className="btn btn--secondary btn--sm" onClick={() => onResolve(report, 'DISMISSED')} disabled={busy}>
                  <FiX size={13} /> Dismiss
                </button>
                <button
                  type="button"
                  className="btn btn--primary btn--sm"
                  onClick={() => onResolve(report, 'APPROVED')}
                  disabled={busy}
                  title="Approve and put this workstation into maintenance"
                >
                  {busy ? <FiCheck size={13} /> : <FiTool size={13} />} Approve
                </button>
              </div>
            )}
          </article>
        )
      })}
    </div>
  )
}

export default ReportReviewList
