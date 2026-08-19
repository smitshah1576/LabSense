import React, { useState } from 'react'
import { useAuth } from '../../hooks/useAuth'
import { pcsApi } from '../../api/endpoints'
import StatusIndicator from './StatusIndicator'
import {
  FiCpu,
  FiClock,
  FiLock,
  FiUnlock,
  FiUserCheck,
  FiTool,
  FiActivity,
} from 'react-icons/fi'

const STATE_LABELS = {
  AVAILABLE: 'Available',
  IN_USE: 'In Use',
  AVAILABLE_SLEEP: 'Sleep',
  MAINTENANCE: 'Maintenance',
}

const PCCard = ({ pc, liveState, onStatusChanged }) => {
  const { isProfessor, isAdmin } = useAuth()
  const [loadingToggle, setLoadingToggle] = useState(false)

  // Merge DB data with live WebSocket state
  const currentStatus = (liveState?.status || pc.current_state || 'AVAILABLE').toUpperCase()
  const isMaintenance = currentStatus === 'MAINTENANCE'
  const sessionActive = liveState?.session_active ?? pc.session_active ?? false
  const screenLocked = liveState?.screen_locked ?? pc.screen_locked ?? false
  const cpuPercent = liveState?.cpu_percent ?? pc.cpu_percent ?? 0
  const idleSeconds = liveState?.idle_seconds ?? pc.idle_seconds ?? 0
  const lastHeartbeat = liveState?.last_heartbeat_at ?? pc.last_heartbeat_at

  const getStateCardClass = () => {
    switch (currentStatus) {
      case 'AVAILABLE':
        return 'state-available'
      case 'IN_USE':
        return 'state-in-use'
      case 'AVAILABLE_SLEEP':
        return 'state-sleep'
      case 'MAINTENANCE':
        return 'state-maintenance'
      default:
        return ''
    }
  }

  const handleToggleMaintenance = async (e) => {
    e.stopPropagation()
    setLoadingToggle(true)
    try {
      await pcsApi.toggleMaintenance(pc.pc_id, !isMaintenance)
      if (onStatusChanged) {
        onStatusChanged(pc.pc_id, !isMaintenance ? 'MAINTENANCE' : 'AVAILABLE')
      }
    } catch (err) {
      console.error('Failed to toggle maintenance mode:', err)
      alert(err.response?.data?.detail || 'Failed to update maintenance state')
    } finally {
      setLoadingToggle(false)
    }
  }

  const formatIdleTime = (seconds) => {
    if (!seconds || seconds <= 0) return '0s'
    if (seconds < 60) return `${seconds}s`
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}m ${secs}s`
  }

  const formatHeartbeat = (ts) => {
    if (!ts) return 'Never'
    try {
      const d = new Date(ts)
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    } catch {
      return ts
    }
  }

  return (
    <div className={`pc-card ${getStateCardClass()}`}>
      <div className="pc-header">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
          <span className="pc-hostname">{pc.pc_id}</span>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            {STATE_LABELS[currentStatus] || currentStatus}
          </span>
        </div>
        <StatusIndicator state={currentStatus} />
      </div>

      {/* Telemetry Display */}
      <div className="pc-telemetry-grid">
        <div className="pc-telemetry-item">
          <span className="pc-telemetry-label">CPU Load</span>
          <span className="pc-telemetry-val" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <FiCpu size={12} style={{ color: 'var(--color-primary)' }} />
            {typeof cpuPercent === 'number' ? `${cpuPercent.toFixed(1)}%` : '0.0%'}
          </span>
        </div>

        <div className="pc-telemetry-item">
          <span className="pc-telemetry-label">Idle Time</span>
          <span className="pc-telemetry-val" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <FiClock size={12} style={{ color: 'var(--color-warning)' }} />
            {formatIdleTime(idleSeconds)}
          </span>
        </div>

        <div className="pc-telemetry-item">
          <span className="pc-telemetry-label">Session</span>
          <span className="pc-telemetry-val" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.74rem' }}>
            <FiUserCheck size={12} style={{ color: sessionActive ? 'var(--color-success)' : 'var(--text-muted)' }} />
            {sessionActive ? 'Active' : 'No User'}
          </span>
        </div>

        <div className="pc-telemetry-item">
          <span className="pc-telemetry-label">Screen</span>
          <span className="pc-telemetry-val" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.74rem' }}>
            {screenLocked ? (
              <>
                <FiLock size={12} style={{ color: 'var(--color-warning)' }} />
                <span>Locked</span>
              </>
            ) : (
              <>
                <FiUnlock size={12} style={{ color: 'var(--color-success)' }} />
                <span>Unlocked</span>
              </>
            )}
          </span>
        </div>
      </div>

      <div className="pc-footer">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
          <FiActivity size={11} />
          <span>Heartbeat: {formatHeartbeat(lastHeartbeat)}</span>
        </div>

        {(isAdmin() || isProfessor()) && (
          <button
            onClick={handleToggleMaintenance}
            disabled={loadingToggle}
            className={`btn btn-sm ${isMaintenance ? 'btn-success' : 'btn-ghost'}`}
            style={{
              padding: '0.2rem 0.55rem',
              fontSize: '0.7rem',
              borderRadius: 'var(--radius-sm)',
              border: isMaintenance ? 'none' : '1px solid var(--border-subtle)',
            }}
            title={isMaintenance ? 'Clear maintenance mode' : 'Mark PC for maintenance'}
          >
            <FiTool size={11} />
            <span>{loadingToggle ? '...' : isMaintenance ? 'Resolve' : 'Maint.'}</span>
          </button>
        )}
      </div>
    </div>
  )
}

export default PCCard
