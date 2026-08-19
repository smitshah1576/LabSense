import React from 'react'

const StatusIndicator = ({ state, showLabel = true, size = 'md' }) => {
  const normalizedState = (state || 'UNKNOWN').toUpperCase()

  const getStateDetails = (st) => {
    switch (st) {
      case 'AVAILABLE':
      case 'OPEN':
        return {
          key: 'available',
          label: st === 'OPEN' ? 'Open' : 'Available',
          badgeClass: st === 'OPEN' ? 'badge-open' : 'badge-available',
        }
      case 'IN_USE':
      case 'OCCUPIED':
        return {
          key: 'in-use',
          label: st === 'OCCUPIED' ? 'Occupied' : 'In Use',
          badgeClass: st === 'OCCUPIED' ? 'badge-occupied' : 'badge-in-use',
        }
      case 'SLEEP':
      case 'AVAILABLE_SLEEP':
        return {
          key: 'sleep',
          label: 'Sleep',
          badgeClass: 'badge-sleep',
        }
      case 'MAINTENANCE':
        return {
          key: 'maintenance',
          label: 'Maintenance',
          badgeClass: 'badge-maintenance',
        }
      case 'CLOSED':
        return {
          key: 'closed',
          label: 'Closed',
          badgeClass: 'badge-closed',
        }
      default:
        return {
          key: 'unknown',
          label: st,
          badgeClass: 'badge-ghost',
        }
    }
  }

  const { key, label, badgeClass } = getStateDetails(normalizedState)

  return (
    <div className="status-indicator-wrapper">
      <div className="status-dot-container">
        <div className={`status-pulse-ring ${key}`} />
        <div className={`status-dot ${key}`} />
      </div>
      {showLabel && <span className={`badge ${badgeClass}`}>{label}</span>}
    </div>
  )
}

export default StatusIndicator
