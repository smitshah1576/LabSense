import React from 'react'
import { NavLink } from 'react-router-dom'
import { FiAlertTriangle, FiCalendar, FiGrid, FiMonitor, FiPackage } from 'react-icons/fi'
import { useAuth } from '../../hooks/useAuth'
import { useLabs } from '../../context/LabsContext'
import { labStateMeta } from '../../lib/pcState'

const navClass = ({ isActive }) => `nav-link ${isActive ? 'active' : ''}`

const Sidebar = ({ open }) => {
  const { isProfessor, isAdmin } = useAuth()
  const { labs, loading } = useLabs()

  return (
    <aside className={`sidebar ${open ? 'sidebar--open' : ''}`} aria-label="Primary">
      <NavLink to="/" className="sidebar__brand">
        <span className="brand-mark" aria-hidden="true">
          <FiMonitor size={15} />
        </span>
        LabSense
      </NavLink>

      <nav className="sidebar__nav">
        <NavLink to="/" end className={navClass}>
          <FiGrid size={16} />
          <span className="nav-link__label">Overview</span>
        </NavLink>
        <NavLink to="/software" className={navClass}>
          <FiPackage size={16} />
          <span className="nav-link__label">Software</span>
        </NavLink>
        {isProfessor() && (
          <NavLink to="/timetable" className={navClass}>
            <FiCalendar size={16} />
            <span className="nav-link__label">Timetable</span>
          </NavLink>
        )}
        <NavLink to="/damage-reports" className={navClass}>
          <FiAlertTriangle size={16} />
          <span className="nav-link__label">{isAdmin() ? 'Reports' : 'Report an issue'}</span>
        </NavLink>

        <div className="nav-section">
          <div className="nav-section__title">Labs</div>
          {loading && labs.length === 0 && <div className="nav-link subtle">Loading…</div>}
          {!loading && labs.length === 0 && <div className="nav-link subtle">No labs yet</div>}
          {labs.map((lab) => {
            const meta = labStateMeta(lab.state)
            return (
              <NavLink key={lab.lab_id} to={`/labs/${lab.lab_id}`} className={navClass} title={`${lab.lab_name} — ${meta.label}`}>
                <span className={`dot tone-${meta.tone}`} aria-hidden="true" style={{ margin: '0 4px' }} />
                <span className="nav-link__label">{lab.lab_name}</span>
                <span className="nav-link__meta">{meta.label}</span>
              </NavLink>
            )
          })}
        </div>
      </nav>

      <div className="sidebar__footer">Campus lab monitor</div>
    </aside>
  )
}

export default Sidebar
