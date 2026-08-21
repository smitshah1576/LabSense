import React, { useState, useEffect, useCallback } from 'react'
import { labsApi, timetableApi } from '../api/endpoints'
import TimetableView from '../components/Timetable/TimetableView'
import CancelSlotModal from '../components/Timetable/CancelSlotModal'
import { FiCalendar, FiLayers, FiRefreshCw } from 'react-icons/fi'

const TimetablePage = () => {
  const [labs, setLabs] = useState([])
  const [selectedLabId, setSelectedLabId] = useState('')
  const [timetable, setTimetable] = useState([])
  const [cancellations, setCancellations] = useState([])
  const [loading, setLoading] = useState(true)
  const [cancellingSlot, setCancellingSlot] = useState(null)

  // Fetch list of labs on mount
  useEffect(() => {
    labsApi
      .getLabs()
      .then((res) => {
        if (Array.isArray(res.data)) {
          setLabs(res.data)
          if (res.data.length > 0) {
            setSelectedLabId(res.data[0].lab_id)
          }
        }
      })
      .catch((err) => console.error('Failed to fetch labs for timetable:', err))
  }, [])

  // Fetch timetable and cancellations whenever selected lab changes
  const loadTimetableData = useCallback(async () => {
    if (!selectedLabId) return
    setLoading(true)
    try {
      const [ttRes, cancelRes] = await Promise.all([
        timetableApi.getLabTimetable(selectedLabId),
        timetableApi.getLabCancellations(selectedLabId),
      ])
      setTimetable(ttRes.data || [])
      setCancellations(cancelRes.data || [])
    } catch (err) {
      console.error('Failed to load timetable data:', err)
    } finally {
      setLoading(false)
    }
  }, [selectedLabId])

  useEffect(() => {
    loadTimetableData()
  }, [loadTimetableData])

  const currentLab = labs.find((l) => String(l.id) === String(selectedLabId))

  return (
    <div className="page-container">
      <div className="page-header">
        <div className="page-title-group">
          <h1 className="page-title">
            <FiCalendar style={{ color: 'var(--color-primary)' }} />
            Campus Timetable & Slot Allocations
          </h1>
          <p className="page-subtitle">
            Manage lab occupancy schedules and cancel lecture slots dynamically
          </p>
        </div>

        <div className="page-actions">
          <button onClick={loadTimetableData} className="btn btn-secondary btn-sm">
            <FiRefreshCw size={14} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Lab Selector Panel */}
      <div className="glass-card" style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.9rem', fontWeight: 500 }}>
          <FiLayers size={16} style={{ color: 'var(--color-primary)' }} />
          <span>Select Lab:</span>
        </div>

        <select
          className="select"
          style={{ maxWidth: '320px' }}
          value={selectedLabId}
          onChange={(e) => setSelectedLabId(e.target.value)}
        >
          {labs.map((lab) => (
            <option key={lab.lab_id} value={lab.lab_id} style={{ background: '#131722' }}>
              {lab.lab_name}
            </option>
          ))}
        </select>
      </div>

      {/* Timetable Grid View */}
      {loading ? (
        <div className="glass-panel skeleton" style={{ height: '320px' }} />
      ) : (
        <TimetableView
          labId={selectedLabId}
          timetable={timetable}
          cancellations={cancellations}
          onSlotCancelRequested={(slot) => setCancellingSlot(slot)}
          onTimetableChanged={loadTimetableData}
        />
      )}

      {/* Cancellation Modal */}
      {cancellingSlot && (
        <CancelSlotModal
          slot={cancellingSlot}
          onClose={() => setCancellingSlot(null)}
          onSlotCancelled={loadTimetableData}
        />
      )}
    </div>
  )
}

export default TimetablePage
