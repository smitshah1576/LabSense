import React from 'react'
import { PC_STATE_ORDER, labStateMeta, pcStateMeta } from '../../lib/pcState'

export const StatusPill = ({ state, kind = 'pc', size }) => {
  const meta = kind === 'lab' ? labStateMeta(state) : pcStateMeta(state)
  return (
    <span className={`pill tone-${meta.tone} ${size === 'lg' ? 'pill--lg' : ''}`}>
      <span className="pill__dot" aria-hidden="true" />
      {meta.label}
    </span>
  )
}

// Proportional bar of PC states, e.g. 3 available / 1 in use / 1 asleep.
export const StackBar = ({ counts }) => {
  const total = counts.total || 0
  return (
    <div
      className="stackbar"
      role="img"
      aria-label={PC_STATE_ORDER.map((s) => `${counts[s]} ${pcStateMeta(s).label.toLowerCase()}`).join(', ')}
    >
      {total > 0 &&
        PC_STATE_ORDER.filter((s) => counts[s] > 0).map((s) => (
          <span key={s} className={`stackbar__seg tone-${pcStateMeta(s).tone}`} style={{ flexGrow: counts[s] }} />
        ))}
    </div>
  )
}

export const StateLegend = ({ counts, hideEmpty = false }) => (
  <div className="legend">
    {PC_STATE_ORDER.filter((s) => !hideEmpty || counts[s] > 0).map((s) => {
      const meta = pcStateMeta(s)
      return (
        <span key={s} className={`legend__item tone-${meta.tone}`}>
          <span className="dot" aria-hidden="true" />
          <b>{counts[s]}</b> {meta.label.toLowerCase()}
        </span>
      )
    })}
  </div>
)

export default StatusPill
