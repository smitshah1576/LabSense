import React from 'react'
import { Link } from 'react-router-dom'
import { FiArrowRight, FiMonitor, FiPackage, FiSearch } from 'react-icons/fi'
import EmptyState from '../ui/EmptyState'

const MAX_CHIPS = 8

const escapeRegExp = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const Highlight = ({ text, query }) => {
  if (!query) return text
  const parts = text.split(new RegExp(`(${escapeRegExp(query)})`, 'ig'))
  return parts.map((part, i) => (part.toLowerCase() === query.toLowerCase() ? <mark key={i}>{part}</mark> : part))
}

const SoftwareResults = ({ results = [], query = '', loading = false, showLab = true, minLength = 2 }) => {
  if (query.length < minLength) {
    return (
      <div className="card">
        <EmptyState
          icon={FiPackage}
          title="Search installed software"
          description="Type at least two characters to find which workstations have a package installed."
        />
      </div>
    )
  }

  if (loading && results.length === 0) {
    return <div className="skeleton" style={{ height: 160 }} />
  }

  if (results.length === 0) {
    return (
      <div className="card">
        <EmptyState
          icon={FiSearch}
          title={`No workstations have “${query}”`}
          description="Package names are matched as reported by dpkg and pip — try a shorter or different name, e.g. “python3” rather than “Python 3.11”."
        />
      </div>
    )
  }

  const groups = results.reduce((acc, item) => {
    const key = item.lab_id || 'unassigned'
    if (!acc[key]) acc[key] = { lab_id: item.lab_id, lab_name: item.lab_name || item.lab_id, pcs: [] }
    acc[key].pcs.push(item)
    return acc
  }, {})

  const groupList = Object.values(groups).sort((a, b) => String(a.lab_name).localeCompare(String(b.lab_name)))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, opacity: loading ? 0.6 : 1, transition: 'opacity 120ms' }}>
      <div className="muted">
        <b style={{ color: 'var(--text)', fontWeight: 600 }}>{results.length}</b> {results.length === 1 ? 'workstation' : 'workstations'}
        {showLab && (
          <>
            {' '}
            in <b style={{ color: 'var(--text)', fontWeight: 600 }}>{groupList.length}</b> {groupList.length === 1 ? 'lab' : 'labs'}
          </>
        )}
      </div>

      {groupList.map((group) => (
        <section key={group.lab_id} className="card result">
          {showLab && (
            <header className="card__header">
              <div>
                <div className="card__title">{group.lab_name}</div>
                <div className="subtle" style={{ fontSize: 12 }}>
                  {group.pcs.length} {group.pcs.length === 1 ? 'workstation' : 'workstations'}
                </div>
              </div>
              <Link to={`/labs/${group.lab_id}`} className="btn btn--ghost btn--sm">
                View lab <FiArrowRight size={13} />
              </Link>
            </header>
          )}
          {group.pcs
            .slice()
            .sort((a, b) => a.pc_id.localeCompare(b.pc_id, undefined, { numeric: true }))
            .map((pc, i) => {
              const pkgs = pc.matching_packages || []
              return (
                <div key={pc.pc_id} className="result__row" style={!showLab && i === 0 ? { borderTop: 0 } : undefined}>
                  <div className="result__pc">
                    <FiMonitor size={14} />
                    <span className="mono">{pc.pc_id}</span>
                  </div>
                  <div className="chips">
                    {pkgs.slice(0, MAX_CHIPS).map((pkg) => (
                      <span key={pkg} className="chip chip--pkg">
                        <Highlight text={pkg} query={query} />
                      </span>
                    ))}
                    {pkgs.length > MAX_CHIPS && <span className="subtle" style={{ fontSize: 12 }}>+{pkgs.length - MAX_CHIPS} more</span>}
                  </div>
                </div>
              )
            })}
        </section>
      ))}
    </div>
  )
}

export default SoftwareResults
