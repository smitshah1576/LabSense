import React, { useState } from 'react'
import { useAuth } from '../../hooks/useAuth'
import { timetableApi } from '../../api/endpoints'
import {
  FiCalendar,
  FiClock,
  FiXCircle,
  FiPlus,
  FiTrash2,
  FiAlertCircle,
} from 'react-icons/fi'

const DAYS = [
  { id: 0, name: 'Monday', short: 'Mon' },
  { id: 1, name: 'Tuesday', short: 'Tue' },
  { id: 2, name: 'Wednesday', short: 'Wed' },
  { id: 3, name: 'Thursday', short: 'Thu' },
  { id: 4, name: 'Friday', short: 'Fri' },
  { id: 5, name: 'Saturday', short: 'Sat' },
]

const TimetableView = ({
  labId,
  timetable = [],
  cancellations = [],
  onSlotCancelRequested,
  onTimetableChanged,
}) => {
  const { isAdmin, isProfessor } = useAuth()
  const [showAddModal, setShowAddModal] = useState(false)
  const [addDay, setAddDay] = useState(0)
  const [addStartTime, setAddStartTime] = useState('09:00')
  const [addEndTime, setAddEndTime] = useState('11:00')
  const [adding, setAdding] = useState(false)

  const formatTime = (timeStr) => {
    if (!timeStr) return ''
    if (typeof timeStr === 'string' && timeStr.includes(':')) {
      const parts = timeStr.split(':')
      return `${parts[0]}:${parts[1]}`
    }
    return timeStr
  }

  const handleDeleteSlot = async (slotId) => {
    if (!window.confirm('Are you sure you want to permanently delete this timetable slot?')) return
    try {
      await timetableApi.deleteTimetableEntry(slotId)
      if (onTimetableChanged) onTimetableChanged()
    } catch (err) {
      console.error('Failed to delete timetable slot:', err)
      alert(err.response?.data?.detail || 'Failed to delete slot')
    }
  }

  const handleAddSlot = async (e) => {
    e.preventDefault()
    setAdding(true)
    try {
      await timetableApi.createTimetableEntry(labId, {
        day_of_week: parseInt(addDay, 10),
        start_time: `${addStartTime}:00`,
        end_time: `${addEndTime}:00`,
      })
      setShowAddModal(false)
      if (onTimetableChanged) onTimetableChanged()
    } catch (err) {
      console.error('Failed to create timetable slot:', err)
      alert(err.response?.data?.detail || 'Failed to create slot')
    } finally {
      setAdding(false)
    }
  }

  // Check if slot has active cancellations
  const isSlotCancelled = (slotId) => {
    return cancellations.some((c) => c.timetable_id === slotId)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div className="flex-between">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <FiCalendar size={18} style={{ color: 'var(--color-primary)' }} />
          <h3 style={{ fontSize: '1.15rem', fontWeight: 600 }}>Weekly Schedule</h3>
        </div>

        {isAdmin() && (
          <button
            onClick={() => setShowAddModal(true)}
            className="btn btn-primary btn-sm"
          >
            <FiPlus size={15} />
            <span>Add Slot</span>
          </button>
        )}
      </div>

      {/* Grid of Days */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '1rem',
        }}
      >
        {DAYS.map((day) => {
          const daySlots = timetable
            .filter((t) => t.day_of_week === day.id)
            .sort((a, b) => (a.start_time || '').localeCompare(b.start_time || ''))

          return (
            <div
              key={day.id}
              className="glass-card"
              style={{
                display: 'flex',
                flexDirection: 'column',
                borderRadius: 'var(--radius-md)',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  background: 'hsla(220, 20%, 10%, 0.9)',
                  padding: '0.65rem 0.85rem',
                  borderBottom: '1px solid var(--border-glass)',
                  fontWeight: 600,
                  fontSize: '0.875rem',
                  color: 'var(--text-primary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <span>{day.name}</span>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  {daySlots.length} {daySlots.length === 1 ? 'slot' : 'slots'}
                </span>
              </div>

              <div
                style={{
                  padding: '0.75rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.6rem',
                  minHeight: '140px',
                }}
              >
                {daySlots.length === 0 ? (
                  <div
                    style={{
                      flex: 1,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '0.75rem',
                      color: 'var(--text-muted)',
                    }}
                  >
                    No scheduled sessions
                  </div>
                ) : (
                  daySlots.map((slot) => {
                    const cancelled = isSlotCancelled(slot.id)
                    return (
                      <div
                        key={slot.id}
                        style={{
                          background: cancelled
                            ? 'hsla(0, 84%, 60%, 0.1)'
                            : 'hsla(217, 91%, 60%, 0.12)',
                          border: `1px solid ${
                            cancelled
                              ? 'hsla(0, 84%, 60%, 0.3)'
                              : 'hsla(217, 91%, 60%, 0.25)'
                          }`,
                          borderRadius: 'var(--radius-sm)',
                          padding: '0.6rem',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '0.35rem',
                          position: 'relative',
                        }}
                      >
                        <div className="flex-between">
                          <span
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.3rem',
                              fontSize: '0.78rem',
                              fontFamily: 'JetBrains Mono, monospace',
                              fontWeight: 600,
                              color: cancelled
                                ? 'var(--color-danger)'
                                : 'var(--color-primary)',
                              textDecoration: cancelled ? 'line-through' : 'none',
                            }}
                          >
                            <FiClock size={12} />
                            {formatTime(slot.start_time)} – {formatTime(slot.end_time)}
                          </span>

                          {cancelled && (
                            <span
                              className="badge badge-closed"
                              style={{ fontSize: '0.6rem', padding: '0.1rem 0.35rem' }}
                            >
                              Cancelled
                            </span>
                          )}
                        </div>

                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          Lab Session
                        </div>

                        {/* Action buttons for Professor / Admin */}
                        {(isAdmin() || isProfessor()) && (
                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'flex-end',
                              gap: '0.35rem',
                              marginTop: '0.2rem',
                              paddingTop: '0.3rem',
                              borderTop: '1px solid var(--border-glass)',
                            }}
                          >
                            {!cancelled && (
                              <button
                                onClick={() => onSlotCancelRequested(slot)}
                                className="btn btn-ghost btn-sm"
                                style={{
                                  padding: '0.15rem 0.4rem',
                                  fontSize: '0.68rem',
                                  color: 'var(--color-warning)',
                                }}
                                title="Cancel session for a specific date"
                              >
                                <FiXCircle size={12} />
                                <span>Cancel Slot</span>
                              </button>
                            )}

                            {isAdmin() && (
                              <button
                                onClick={() => handleDeleteSlot(slot.id)}
                                className="btn btn-ghost btn-sm"
                                style={{
                                  padding: '0.15rem 0.4rem',
                                  fontSize: '0.68rem',
                                  color: 'var(--color-danger)',
                                }}
                                title="Permanently delete slot"
                              >
                                <FiTrash2 size={12} />
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Add Slot Modal */}
      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h4 className="modal-title">Add Timetable Slot</h4>
              <button
                className="btn btn-ghost btn-icon"
                onClick={() => setShowAddModal(false)}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleAddSlot} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="input-group">
                <label className="input-label">Day of Week</label>
                <select
                  className="select"
                  value={addDay}
                  onChange={(e) => setAddDay(e.target.value)}
                >
                  {DAYS.map((d) => (
                    <option key={d.id} value={d.id} style={{ background: '#131722' }}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="input-group">
                  <label className="input-label">Start Time</label>
                  <input
                    type="time"
                    className="input"
                    value={addStartTime}
                    onChange={(e) => setAddStartTime(e.target.value)}
                    required
                  />
                </div>
                <div className="input-group">
                  <label className="input-label">End Time</label>
                  <input
                    type="time"
                    className="input"
                    value={addEndTime}
                    onChange={(e) => setAddEndTime(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowAddModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={adding}
                >
                  {adding ? 'Adding...' : 'Create Slot'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default TimetableView
