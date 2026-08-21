import React, { useState, useEffect } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { labsApi } from '../../api/endpoints'
import {
  FiGrid,
  FiSearch,
  FiCalendar,
  FiAlertTriangle,
  FiLayers,
  FiChevronDown,
  FiChevronRight,
  FiCpu,
} from 'react-icons/fi'

const Sidebar = () => {
  const { isProfessor, isAdmin } = useAuth()
  const location = useLocation()
  const [labs, setLabs] = useState([])
  const [labsOpen, setLabsOpen] = useState(true)

  useEffect(() => {
    let mounted = true
    labsApi
      .getLabs()
      .then((res) => {
        if (mounted && Array.isArray(res.data)) {
          setLabs(res.data)
        }
      })
      .catch((err) => {
        console.warn('Could not fetch labs for sidebar:', err)
      })
    return () => {
      mounted = false
    }
  }, [])

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <NavLink to="/" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div className="brand-icon" style={{ width: '28px', height: '28px' }}>
            <FiCpu size={16} />
          </div>
          <span style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--text-primary)' }}>
            Lab<span style={{ color: 'var(--color-primary)' }}>Sense</span>
          </span>
        </NavLink>
      </div>

      <div className="sidebar-content">
        <div className="sidebar-section-title">Navigation</div>

        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            `sidebar-link ${isActive ? 'active' : ''}`
          }
        >
          <span className="sidebar-link-icon">
            <FiGrid size={18} />
          </span>
          <span>Dashboard</span>
        </NavLink>

        <NavLink
          to="/software"
          className={({ isActive }) =>
            `sidebar-link ${isActive ? 'active' : ''}`
          }
        >
          <span className="sidebar-link-icon">
            <FiSearch size={18} />
          </span>
          <span>Software Search</span>
        </NavLink>

        {isProfessor() && (
          <NavLink
            to="/timetable"
            className={({ isActive }) =>
              `sidebar-link ${isActive ? 'active' : ''}`
            }
          >
            <span className="sidebar-link-icon">
              <FiCalendar size={18} />
            </span>
            <span>Timetable</span>
          </NavLink>
        )}

        <NavLink
          to="/damage-reports"
          className={({ isActive }) =>
            `sidebar-link ${isActive ? 'active' : ''}`
          }
        >
          <span className="sidebar-link-icon">
            <FiAlertTriangle size={18} />
          </span>
          <span>Damage Reports</span>
        </NavLink>

        {/* Labs List / Collapsible Section */}
        <div style={{ marginTop: '0.75rem' }}>
          <div
            onClick={() => setLabsOpen(!labsOpen)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.5rem 0.75rem',
              cursor: 'pointer',
              color: 'var(--text-muted)',
              fontSize: '0.75rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              userSelect: 'none',
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <FiLayers size={14} />
              <span>Campus Labs</span>
            </span>
            {labsOpen ? <FiChevronDown size={14} /> : <FiChevronRight size={14} />}
          </div>

          {labsOpen && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem', paddingLeft: '0.5rem', marginTop: '0.25rem' }}>
              {labs.length === 0 ? (
                <div style={{ padding: '0.5rem 0.75rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  Loading labs...
                </div>
              ) : (
                labs.map((lab) => (
                  <NavLink
                    key={lab.lab_id}
                    to={`/labs/${lab.lab_id}`}
                    className={({ isActive }) =>
                      `sidebar-link ${isActive ? 'active' : ''}`
                    }
                    style={{ fontSize: '0.84rem', padding: '0.5rem 0.75rem' }}
                  >
                    <span
                      style={{
                        width: '7px',
                        height: '7px',
                        borderRadius: '50%',
                        backgroundColor:
                          lab.state === 'OPEN'
                            ? 'var(--color-success)'
                            : lab.state === 'OCCUPIED'
                            ? 'var(--color-primary)'
                            : 'var(--color-danger)',
                      }}
                    />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {lab.name}
                    </span>
                  </NavLink>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      <div className="sidebar-footer">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: 'var(--color-success)',
              display: 'inline-block',
            }}
          />
          <span>LabSense v1.0 • Smart Campus</span>
        </div>
      </div>
    </aside>
  )
}

export default Sidebar
