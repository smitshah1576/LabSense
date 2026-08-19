import React, { useState } from 'react'
import { timetableApi } from '../../api/endpoints'
import { FiX, FiCalendar, FiAlertCircle } from 'react-icons/fi'

const CancelSlotModal = ({ slot, onClose, onSlotCancelled }) => {
  const today = new Date().toISOString().split('T')[0]
  const [date, setDate] = useState(today)
  const [reason, setReason] = useState('Cancelled by faculty')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  if (!slot) return null

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      await timetableApi.cancelSlot(slot.id, date, reason)
      if (onSlotCancelled) onSlotCancelled()
      onClose()
    } catch (err) {
      console.error('Failed to cancel slot:', err)
      setError(err.response?.data?.detail || 'Failed to cancel slot for this date')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <FiAlertCircle size={20} style={{ color: 'var(--color-warning)' }} />
            <h4 className="modal-title">Cancel Timetable Session</h4>
          </div>
          <button className="btn btn-ghost btn-icon" onClick={onClose}>
            <FiX size={18} />
          </button>
        </div>

        {error && (
          <div
            style={{
              padding: '0.75rem',
              borderRadius: 'var(--radius-sm)',
              background: 'hsla(0, 84%, 60%, 0.15)',
              border: '1px solid var(--color-danger)',
              color: 'var(--color-danger)',
              fontSize: '0.85rem',
            }}
          >
            {error}
          </div>
        )}

        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          Cancelling slot: <strong style={{ color: 'var(--text-primary)' }}>{slot.start_time} – {slot.end_time}</strong>. Workstations in this lab will immediately become marked as available during this time.
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="input-group">
            <label className="input-label">Cancellation Date</label>
            <input
              type="date"
              className="input"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
            />
          </div>

          <div className="input-group">
            <label className="input-label">Reason for Cancellation</label>
            <input
              type="text"
              className="input"
              placeholder="e.g. Faculty on leave / Special holiday"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              required
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
              disabled={submitting}
            >
              Back
            </button>
            <button
              type="submit"
              className="btn btn-danger"
              disabled={submitting}
            >
              {submitting ? 'Cancelling...' : 'Confirm Cancellation'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default CancelSlotModal
