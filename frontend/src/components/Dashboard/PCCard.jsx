import React from 'react'
import { Link } from 'react-router-dom'
import { FiFlag, FiLoader, FiLock, FiMonitor, FiTool, FiTrash2, FiUnlock, FiUser, FiUserX } from 'react-icons/fi'
import StatusPill from '../ui/StatusPill'
import { pcStateMeta } from '../../lib/pcState'
import { formatDuration, relativeTime } from '../../lib/time'

const cpuTone = (cpu) => (cpu >= 85 ? 'meter__fill--max' : cpu >= 30 ? 'meter__fill--hot' : '')

const PCCard = ({ pc, now, canMaintain, canDelete, busy, onToggleMaintenance, onDelete }) => {
  const state = pc.current_state
  const meta = pcStateMeta(state)
  const isMaintenance = state === 'MAINTENANCE'
  const asleep = state === 'AVAILABLE_SLEEP'
  const cpu = Math.max(0, Math.min(100, Number(pc.cpu_percent) || 0))
  const updated = relativeTime(pc.last_heartbeat_at, now)

  return (
    <article className={`card pc tone-${meta.tone}`} aria-label={`${pc.pc_id}, ${meta.label}`}>
      <div className="pc__head">
        <div className="pc__name">
          <FiMonitor size={14} />
          <span className="mono">{pc.pc_id}</span>
        </div>
        <StatusPill state={state} />
      </div>

      <div className="pc__body">
        {pc.has_telemetry ? (
          <>
            {asleep && <div className="pc__stale">Last reported before sleeping</div>}
            <dl className={`kv ${asleep ? 'kv--dim' : ''}`}>
              <div>
                <dt className="kv__label">CPU</dt>
                <dd className="kv__value">{cpu.toFixed(1)}%</dd>
                <div className="meter" aria-hidden="true">
                  <div className={`meter__fill ${cpuTone(cpu)}`} style={{ width: `${cpu}%` }} />
                </div>
              </div>
              <div>
                <dt className="kv__label">Idle</dt>
                <dd className="kv__value">{formatDuration(pc.idle_seconds)}</dd>
              </div>
              <div>
                <dt className="kv__label">Session</dt>
                <dd className="kv__value">
                  {pc.session_active ? <FiUser size={13} /> : <FiUserX size={13} />}
                  {pc.session_active ? 'Signed in' : 'No one'}
                </dd>
              </div>
              <div>
                <dt className="kv__label">Screen</dt>
                <dd className="kv__value">
                  {pc.screen_locked ? <FiLock size={13} /> : <FiUnlock size={13} />}
                  {pc.screen_locked ? 'Locked' : 'Unlocked'}
                </dd>
              </div>
            </dl>
          </>
        ) : (
          <div className="pc__waiting">
            <FiLoader size={14} />
            Waiting for the first heartbeat
          </div>
        )}
      </div>

      <footer className="pc__foot">
        <span className="num" title={pc.last_heartbeat_at ? new Date(pc.last_heartbeat_at).toLocaleString() : undefined}>
          {updated ? `Updated ${updated}` : 'No reports yet'}
        </span>
        <div className="pc__actions">
          <Link
            to={`/damage-reports?lab=${encodeURIComponent(pc.lab_id || '')}&pc=${encodeURIComponent(pc.pc_id)}`}
            className="btn btn--ghost btn--icon btn--sm"
            title="Report an issue"
            aria-label={`Report an issue with ${pc.pc_id}`}
          >
            <FiFlag size={13} />
          </Link>
          {canMaintain && (
            <button
              type="button"
              className="btn btn--ghost btn--icon btn--sm"
              onClick={() => onToggleMaintenance(pc)}
              disabled={busy}
              title={isMaintenance ? 'Return to service' : 'Mark for maintenance'}
              aria-label={isMaintenance ? `Return ${pc.pc_id} to service` : `Mark ${pc.pc_id} for maintenance`}
              aria-pressed={isMaintenance}
              style={isMaintenance ? { color: 'var(--maint-fg)' } : undefined}
            >
              {busy ? <FiLoader size={13} className="spin" /> : <FiTool size={13} />}
            </button>
          )}
          {canDelete && (
            <button
              type="button"
              className="btn btn--danger-ghost btn--icon btn--sm"
              onClick={() => onDelete(pc)}
              title="Remove workstation"
              aria-label={`Remove ${pc.pc_id}`}
            >
              <FiTrash2 size={13} />
            </button>
          )}
        </div>
      </footer>
    </article>
  )
}

export default PCCard
