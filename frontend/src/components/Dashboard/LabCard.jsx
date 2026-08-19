import React from 'react'
import { useNavigate } from 'react-router-dom'
import StatusIndicator from './StatusIndicator'
import {
  FiClock,
  FiMonitor,
  FiArrowRight,
} from 'react-icons/fi'

const LabCard = ({ lab }) => {
  const navigate = useNavigate()

  const labState = (lab.state || 'OPEN').toUpperCase()
  const availableCount = lab.available_pcs !== undefined ? lab.available_pcs : '–'
  const totalCapacity = 5  // Lab A has 5 PCs as per seed data

  const getStateBorderGradient = () => {
    switch (labState) {
      case 'OPEN':
        return 'linear-gradient(135deg, hsla(142, 71%, 45%, 0.3) 0%, transparent 60%)'
      case 'OCCUPIED':
        return 'linear-gradient(135deg, hsla(217, 91%, 60%, 0.3) 0%, transparent 60%)'
      case 'CLOSED':
        return 'linear-gradient(135deg, hsla(0, 84%, 60%, 0.3) 0%, transparent 60%)'
      default:
        return 'none'
    }
  }

  const formatTime = (timeStr) => {
    if (!timeStr) return '--:--'
    if (typeof timeStr === 'string' && timeStr.includes(':')) {
      const parts = timeStr.split(':')
      return `${parts[0]}:${parts[1]}`
    }
    return timeStr
  }

  return (
    <div
      onClick={() => navigate(`/labs/${lab.lab_id}`)}
      className="glass-card-hover lab-card"
      style={{
        background: `radial-gradient(circle at top left, hsla(220, 20%, 16%, 0.8), hsla(220, 20%, 9%, 0.95))`,
        borderTop: `2px solid ${
          labState === 'OPEN'
            ? 'var(--color-success)'
            : labState === 'OCCUPIED'
            ? 'var(--color-primary)'
            : 'var(--color-danger)'
        }`,
      }}
    >
      <div className="lab-card-header">
        <div>
          <h3 className="lab-name">{lab.lab_name}</h3>
        </div>
        <StatusIndicator state={labState} />
      </div>

      {/* PC Availability Stat Box */}
      <div className="lab-stat-row">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: 'var(--radius-sm)',
              background: 'hsla(217, 91%, 60%, 0.12)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--color-primary)',
            }}
          >
            <FiMonitor size={16} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              Workstations
            </span>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              Live Availability
            </span>
          </div>
        </div>

        <div style={{ textAlign: 'right' }}>
          <span className="lab-stat-num">
            {availableCount}
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 400 }}>
              /{totalCapacity}
            </span>
          </span>
          <div style={{ fontSize: '0.68rem', color: 'var(--color-success)', fontWeight: 500 }}>
            Available Now
          </div>
        </div>
      </div>

      {/* Operating Hours & Footer */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '0.75rem',
          color: 'var(--text-secondary)',
          paddingTop: '0.5rem',
          borderTop: '1px solid var(--border-glass)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <FiClock size={13} style={{ color: 'var(--text-muted)' }} />
          <span>
            {formatTime(lab.operating_start_time)} – {formatTime(lab.operating_end_time)}
          </span>
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.3rem',
            color: 'var(--color-primary)',
            fontWeight: 600,
          }}
        >
          <span>View Lab</span>
          <FiArrowRight size={13} />
        </div>
      </div>
    </div>
  )
}

export default LabCard
