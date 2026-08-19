import React from 'react'
import { Link } from 'react-router-dom'
import { FiMonitor, FiLayers, FiCheck, FiExternalLink, FiPackage } from 'react-icons/fi'

const SoftwareResults = ({ results = [], searchQuery = '', loading = false }) => {
  if (loading) {
    return (
      <div className="glass-panel" style={{ textAlign: 'center', padding: '3rem 1rem' }}>
        <div style={{ color: 'var(--text-secondary)' }}>Searching installed software packages across campus...</div>
      </div>
    )
  }

  if (!searchQuery) {
    return (
      <div className="glass-panel" style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-muted)' }}>
        <FiPackage size={40} style={{ opacity: 0.4, marginBottom: '0.75rem' }} />
        <p>Enter a software name above to find workstations with it installed.</p>
      </div>
    )
  }

  if (results.length === 0) {
    return (
      <div className="glass-panel" style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-muted)' }}>
        <p>No workstations found with software matching "{searchQuery}".</p>
      </div>
    )
  }

  // Group results by lab
  const groupedByLab = results.reduce((acc, item) => {
    const labKey = item.lab_id || 'unassigned'
    if (!acc[labKey]) {
      acc[labKey] = {
        lab_id: item.lab_id,
        lab_name: item.lab_name || `Lab #${item.lab_id}`,
        pcs: [],
      }
    }
    acc[labKey].pcs.push(item)
    return acc
  }, {})

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
        Found <strong style={{ color: 'var(--color-primary)' }}>{results.length}</strong> matching workstation(s) across{' '}
        <strong style={{ color: 'var(--text-primary)' }}>{Object.keys(groupedByLab).length}</strong> lab(s)
      </div>

      {Object.values(groupedByLab).map((group) => (
        <div key={group.lab_id} className="glass-card" style={{ padding: '1.25rem' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '1rem',
              paddingBottom: '0.6rem',
              borderBottom: '1px solid var(--border-glass)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <div
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: 'var(--radius-sm)',
                  background: 'hsla(217, 91%, 60%, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--color-primary)',
                }}
              >
                <FiLayers size={14} />
              </div>
              <h4 style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                {group.lab_name}
              </h4>
              <span className="badge badge-in-use" style={{ fontSize: '0.7rem' }}>
                {group.pcs.length} {group.pcs.length === 1 ? 'PC' : 'PCs'} Available
              </span>
            </div>

            <Link
              to={`/labs/${group.lab_id}`}
              className="btn btn-ghost btn-sm"
              style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: 'var(--color-primary)' }}
            >
              <span>Go to Lab</span>
              <FiExternalLink size={13} />
            </Link>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '0.75rem' }}>
            {group.pcs.map((pc) => (
              <div
                key={pc.pc_id}
                style={{
                  padding: '0.75rem',
                  borderRadius: 'var(--radius-sm)',
                  background: 'hsla(220, 20%, 8%, 0.6)',
                  border: '1px solid var(--border-glass)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.4rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <FiMonitor size={14} style={{ color: 'var(--color-primary)' }} />
                  <span style={{ fontWeight: 600, fontSize: '0.85rem', fontFamily: 'JetBrains Mono, monospace' }}>
                    {pc.hostname || pc.pc_id}
                  </span>
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                  ID: {pc.pc_id}
                </div>
                <div
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.3rem',
                    fontSize: '0.72rem',
                    color: 'var(--color-success)',
                    marginTop: '0.2rem',
                  }}
                >
                  <FiCheck size={12} />
                  <span>Matches "{searchQuery}"</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export default SoftwareResults
