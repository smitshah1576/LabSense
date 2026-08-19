import React, { useState } from 'react'
import PCCard from './PCCard'
import { FiMonitor, FiFilter } from 'react-icons/fi'

const PCGrid = ({ pcs = [], onStatusChanged }) => {
  const [filter, setFilter] = useState('ALL')

  const filteredPcs = pcs.filter((pc) => {
    if (filter === 'ALL') return true
    const st = (pc.current_state || 'AVAILABLE').toUpperCase()
    return st === filter
  })

  const counts = {
    ALL: pcs.length,
    AVAILABLE: pcs.filter((p) => (p.current_state || 'AVAILABLE').toUpperCase() === 'AVAILABLE').length,
    IN_USE: pcs.filter((p) => (p.current_state || '').toUpperCase() === 'IN_USE').length,
    AVAILABLE_SLEEP: pcs.filter((p) => (p.current_state || '').toUpperCase() === 'AVAILABLE_SLEEP').length,
    MAINTENANCE: pcs.filter((p) => (p.current_state || '').toUpperCase() === 'MAINTENANCE').length,
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Quick filter tabs */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          flexWrap: 'wrap',
          background: 'hsla(220, 20%, 9%, 0.6)',
          padding: '0.4rem',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-glass)',
        }}
      >
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.3rem', paddingLeft: '0.5rem' }}>
          <FiFilter size={12} /> Filter:
        </span>

        {[
          { key: 'ALL', label: 'All PCs' },
          { key: 'AVAILABLE', label: 'Available' },
          { key: 'IN_USE', label: 'In Use' },
          { key: 'AVAILABLE_SLEEP', label: 'Sleep' },
          { key: 'MAINTENANCE', label: 'Maintenance' },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key)}
            className="btn btn-sm"
            style={{
              background: filter === tab.key ? 'var(--bg-tertiary)' : 'transparent',
              color: filter === tab.key ? 'var(--text-primary)' : 'var(--text-secondary)',
              border: filter === tab.key ? '1px solid var(--border-glass-hover)' : '1px solid transparent',
              padding: '0.25rem 0.65rem',
              fontSize: '0.78rem',
            }}
          >
            {tab.label} ({counts[tab.key] || 0})
          </button>
        ))}
      </div>

      {filteredPcs.length === 0 ? (
        <div
          className="glass-panel"
          style={{
            textAlign: 'center',
            padding: '3rem 1rem',
            color: 'var(--text-muted)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '0.75rem',
          }}
        >
          <FiMonitor size={36} style={{ opacity: 0.4 }} />
          <p>No workstations match the selected filter.</p>
        </div>
      ) : (
        <div className="grid-container grid-5">
          {filteredPcs.map((pc) => (
            <PCCard key={pc.pc_id} pc={pc} onStatusChanged={onStatusChanged} />
          ))}
        </div>
      )}
    </div>
  )
}

export default PCGrid
