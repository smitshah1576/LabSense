import React, { useState } from 'react'
import { FiMonitor } from 'react-icons/fi'
import PCCard from './PCCard'
import EmptyState from '../ui/EmptyState'
import { PC_STATE_ORDER, pcStateMeta, summarizePcs } from '../../lib/pcState'
import { useNow } from '../../lib/hooks'

const PCGrid = ({ pcs = [], canMaintain, canDelete, busyPcId, onToggleMaintenance, onDelete, actions }) => {
  const [filter, setFilter] = useState('ALL')
  const now = useNow(1000)
  const counts = summarizePcs(pcs)
  const visible = filter === 'ALL' ? pcs : pcs.filter((pc) => pc.current_state === filter)
  const sorted = [...visible].sort((a, b) => a.pc_id.localeCompare(b.pc_id, undefined, { numeric: true }))

  const options = [{ key: 'ALL', label: 'All', count: counts.total }].concat(
    PC_STATE_ORDER.map((s) => ({ key: s, label: pcStateMeta(s).label, count: counts[s], tone: pcStateMeta(s).tone }))
  )

  return (
    <>
      <div className="toolbar">
        <div className="seg" role="group" aria-label="Filter workstations by state">
          {options.map((o) => (
            <button
              key={o.key}
              type="button"
              className="seg__item"
              aria-pressed={filter === o.key}
              onClick={() => setFilter(o.key)}
            >
              {o.tone && <span className={`dot tone-${o.tone}`} aria-hidden="true" style={{ width: 6, height: 6 }} />}
              {o.label}
              <span className="seg__count">{o.count}</span>
            </button>
          ))}
        </div>
        {actions}
      </div>

      {pcs.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={FiMonitor}
            title="No workstations registered"
            description="Register a workstation, then deploy the agent on that machine with the matching PC ID."
          />
        </div>
      ) : sorted.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={FiMonitor}
            title={`No workstations are ${pcStateMeta(filter).label.toLowerCase()}`}
            action={
              <button type="button" className="btn btn--secondary btn--sm" onClick={() => setFilter('ALL')}>
                Show all
              </button>
            }
          />
        </div>
      ) : (
        <div className="grid grid--pcs">
          {sorted.map((pc) => (
            <PCCard
              key={pc.pc_id}
              pc={pc}
              now={now}
              canMaintain={canMaintain}
              canDelete={canDelete}
              busy={busyPcId === pc.pc_id}
              onToggleMaintenance={onToggleMaintenance}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}
    </>
  )
}

export default PCGrid
