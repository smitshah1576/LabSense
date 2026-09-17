import React from 'react'
import { Link } from 'react-router-dom'
import { FiArrowRight, FiClock } from 'react-icons/fi'
import { StackBar, StateLegend, StatusPill } from '../ui/StatusPill'
import { formatClock } from '../../lib/time'

const LabCard = ({ lab, counts, loading }) => (
  <Link to={`/labs/${lab.lab_id}`} className="card lab-card">
    <div className="lab-card__top">
      <div style={{ minWidth: 0 }}>
        <div className="lab-card__name">{lab.lab_name}</div>
        <div className="lab-card__id mono">{lab.lab_id}</div>
      </div>
      <StatusPill kind="lab" state={lab.state} />
    </div>

    <div>
      <div className="lab-card__avail">
        <span className="lab-card__avail-num">{loading ? '–' : counts.free}</span>
        <span className="lab-card__avail-label">
          of {loading ? '–' : counts.total} {counts.total === 1 ? 'workstation' : 'workstations'} free
        </span>
      </div>
      <div style={{ margin: '12px 0 10px' }}>
        <StackBar counts={counts} />
      </div>
      {counts.total > 0 ? (
        <StateLegend counts={counts} hideEmpty />
      ) : (
        <div className="legend subtle">{loading ? 'Loading workstations…' : 'No workstations registered'}</div>
      )}
    </div>

    <div className="lab-card__foot">
      <span className="inline-meta">
        <FiClock size={13} />
        <span className="num">
          {formatClock(lab.operating_start_time)} – {formatClock(lab.operating_end_time)}
        </span>
      </span>
      <span className="inline-meta" style={{ color: 'var(--text)', fontWeight: 500 }}>
        Open lab <FiArrowRight size={13} style={{ color: 'inherit' }} />
      </span>
    </div>
  </Link>
)

export default LabCard
