import React, { useState, useEffect, useCallback, useContext } from 'react'
import { useParams, Link } from 'react-router-dom'
import { labsApi, pcsApi, softwareApi, timetableApi, adminApi } from '../api/endpoints'
import { AuthContext } from '../context/AuthContext'
import { useLabState } from '../hooks/useLabState'
import PCGrid from '../components/Dashboard/PCGrid'
import StatusIndicator from '../components/Dashboard/StatusIndicator'
import SearchBar from '../components/Software/SearchBar'
import SoftwareResults from '../components/Software/SoftwareResults'
import TimetableView from '../components/Timetable/TimetableView'
import CancelSlotModal from '../components/Timetable/CancelSlotModal'
import {
  FiArrowLeft,
  FiClock,
  FiMonitor,
  FiSearch,
  FiCalendar,
  FiRefreshCw,
  FiAlertTriangle,
  FiPlus,
} from 'react-icons/fi'

const LabDetailPage = () => {
  const { labId } = useParams()
  const [lab, setLab] = useState(null)
  const [pcs, setPcs] = useState([])
  const [timetable, setTimetable] = useState([])
  const [cancellations, setCancellations] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('workstations') // 'workstations' | 'timetable' | 'software'

  const { isAdmin } = useContext(AuthContext)

  // Lab-specific software search
  const [softwareQuery, setSoftwareQuery] = useState('')
  const [softwareResults, setSoftwareResults] = useState([])
  const [softwareLoading, setSoftwareLoading] = useState(false)

  // Slot cancellation modal
  const [cancellingSlot, setCancellingSlot] = useState(null)

  const { pcStates, labStates } = useLabState()

  const loadLabData = useCallback(async () => {
    try {
      const [labRes, pcsRes, ttRes, cancelRes] = await Promise.all([
        labsApi.getLab(labId),
        pcsApi.getLabPCs(labId),
        timetableApi.getLabTimetable(labId),
        timetableApi.getLabCancellations(labId),
      ])

      setLab(labRes.data)
      setPcs(pcsRes.data || [])
      setTimetable(ttRes.data || [])
      setCancellations(cancelRes.data || [])
    } catch (err) {
      console.error('Failed to load lab detail:', err)
    } finally {
      setLoading(false)
    }
  }, [labId])

  useEffect(() => {
    loadLabData()
  }, [loadLabData])

  // Merge PCs with WebSocket live states
  const livePcs = pcs.map((pc) => {
    const wsPcState = pcStates[pc.pc_id]
    if (wsPcState) {
      return {
        ...pc,
        current_state: wsPcState.status || pc.current_state,
        session_active: wsPcState.session_active !== undefined ? wsPcState.session_active : pc.session_active,
        screen_locked: wsPcState.screen_locked !== undefined ? wsPcState.screen_locked : pc.screen_locked,
        cpu_percent: wsPcState.cpu_percent !== undefined ? wsPcState.cpu_percent : pc.cpu_percent,
        idle_seconds: wsPcState.idle_seconds !== undefined ? wsPcState.idle_seconds : pc.idle_seconds,
        last_heartbeat_at: wsPcState.last_heartbeat_at || pc.last_heartbeat_at,
      }
    }
    return pc
  })

  // Merge Lab state
  const currentLabState = labStates[labId] || lab?.state || 'OPEN'

  const handleSoftwareSearch = async (q) => {
    setSoftwareQuery(q)
    if (!q || q.length < 2) {
      setSoftwareResults([])
      return
    }
    setSoftwareLoading(true)
    try {
      const res = await softwareApi.searchLab(labId, q)
      if (Array.isArray(res.data)) {
        setSoftwareResults(res.data)
      }
    } catch (err) {
      console.error('Lab software search error:', err)
    } finally {
      setSoftwareLoading(false)
    }
  }

  const handlePcStatusChange = (pcId, newStatus) => {
    setPcs((prev) =>
      prev.map((p) => (p.pc_id === pcId ? { ...p, current_state: newStatus } : p))
    )
  }

  const handleCreatePC = async () => {
    try {
      await adminApi.createPC(labId)
      loadLabData() // Refresh to fetch new PC
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create PC')
    }
  }

  const handleDeletePC = async (pcId) => {
    try {
      await adminApi.deletePC(pcId)
      loadLabData()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to delete PC')
    }
  }

  const availablePcCount = livePcs.filter(
    (p) => (p.current_state || 'AVAILABLE').toUpperCase() === 'AVAILABLE'
  ).length

  if (loading && !lab) {
    return (
      <div className="page-container">
        <div className="glass-panel skeleton" style={{ height: '140px' }} />
        <div className="glass-panel skeleton" style={{ height: '300px' }} />
      </div>
    )
  }

  if (!lab) {
    return (
      <div className="page-container">
        <div className="glass-panel" style={{ textAlign: 'center', padding: '3rem 1rem' }}>
          <p>Lab #{labId} not found.</p>
          <Link to="/" className="btn btn-primary" style={{ marginTop: '1rem' }}>
            Back to Dashboard
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="page-container">
      {/* Navigation Breadcrumb */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Link to="/" className="btn btn-ghost btn-sm" style={{ paddingLeft: '0.4rem' }}>
          <FiArrowLeft size={16} />
          <span>All Labs</span>
        </Link>
      </div>

      {/* Lab Header Hero Card */}
      <div
        className="glass-card"
        style={{
          padding: '1.75rem',
          background: 'linear-gradient(135deg, hsla(220, 20%, 14%, 0.85) 0%, hsla(220, 20%, 8%, 0.95) 100%)',
          borderLeft: `4px solid ${
            currentLabState === 'OPEN'
              ? 'var(--color-success)'
              : currentLabState === 'OCCUPIED'
              ? 'var(--color-primary)'
              : 'var(--color-danger)'
          }`,
        }}
      >
        <div className="flex-between" style={{ flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.4rem' }}>
              <h1 style={{ fontSize: '1.85rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
                {lab.lab_name}
              </h1>
              <StatusIndicator state={currentLabState} />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <FiClock size={14} style={{ color: 'var(--color-warning)' }} />
                <span>
                  Operating Hours: {lab.operating_start_time} – {lab.operating_end_time}
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <FiMonitor size={14} style={{ color: 'var(--color-success)' }} />
                <span>
                  Workstations: <strong style={{ color: 'var(--color-success)' }}>{availablePcCount}</strong> / {livePcs.length} Available
                </span>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Link
              to="/damage-reports"
              className="btn btn-secondary btn-sm"
              title="Report an issue in this lab"
            >
              <FiAlertTriangle size={14} style={{ color: 'var(--color-warning)' }} />
              <span>Report Issue</span>
            </Link>

            <button
              onClick={loadLabData}
              className="btn btn-ghost btn-sm"
              title="Refresh data"
            >
              <FiRefreshCw size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid var(--border-glass)',
          paddingBottom: '0.5rem',
        }}
      >
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            onClick={() => setActiveTab('workstations')}
            className={`btn ${activeTab === 'workstations' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ fontSize: '0.85rem', padding: '0.5rem 1rem' }}
          >
            <FiMonitor size={15} />
            <span>Live Workstations ({livePcs.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('timetable')}
            className={`btn ${activeTab === 'timetable' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ fontSize: '0.85rem', padding: '0.5rem 1rem' }}
          >
            <FiCalendar size={15} />
            <span>Lab Timetable & Schedule</span>
          </button>

          <button
            onClick={() => setActiveTab('software')}
            className={`btn ${activeTab === 'software' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ fontSize: '0.85rem', padding: '0.5rem 1rem' }}
          >
            <FiSearch size={15} />
            <span>Installed Software Locator</span>
          </button>
        </div>
        
        {isAdmin() && activeTab === 'workstations' && (
          <button
            onClick={handleCreatePC}
            className="btn btn-primary btn-sm"
          >
            <FiPlus size={14} />
            <span>Add PC</span>
          </button>
        )}
      </div>

      {/* Tab 1: Live PC Grid */}
      {activeTab === 'workstations' && (
        <div>
          <PCGrid pcs={livePcs} onStatusChanged={handlePcStatusChange} onDeletePC={handleDeletePC} />
        </div>
      )}

      {/* Tab 2: Timetable */}
      {activeTab === 'timetable' && (
        <div>
          <TimetableView
            labId={labId}
            timetable={timetable}
            cancellations={cancellations}
            onSlotCancelRequested={(slot) => setCancellingSlot(slot)}
            onTimetableChanged={loadLabData}
          />
        </div>
      )}

      {/* Tab 3: Lab Software Search */}
      {activeTab === 'software' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div className="glass-card" style={{ padding: '1.25rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem', color: 'var(--text-secondary)' }}>
              Search installed applications in {lab.lab_name}:
            </h3>
            <SearchBar
              onSearch={handleSoftwareSearch}
              placeholder={`Search packages inside ${lab.lab_name} (e.g., Anaconda, Docker, Eclipse, GDB)...`}
              loading={softwareLoading}
            />
          </div>

          <SoftwareResults
            results={softwareResults}
            searchQuery={softwareQuery}
            loading={softwareLoading}
          />
        </div>
      )}

      {/* Cancellation Modal */}
      {cancellingSlot && (
        <CancelSlotModal
          slot={cancellingSlot}
          onClose={() => setCancellingSlot(null)}
          onSlotCancelled={loadLabData}
        />
      )}
    </div>
  )
}

export default LabDetailPage
