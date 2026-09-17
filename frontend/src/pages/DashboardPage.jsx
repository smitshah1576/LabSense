import React, { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FiLayers, FiPlus, FiRefreshCw, FiSearch } from 'react-icons/fi'
import { adminApi } from '../api/endpoints'
import { useAuth } from '../hooks/useAuth'
import { useLabState } from '../hooks/useLabState'
import { useLabs } from '../context/LabsContext'
import { useLabPcs } from '../hooks/useLabPcs'
import { mergeLivePcs, summarizePcs } from '../lib/pcState'
import { apiError, useDocumentTitle } from '../lib/hooks'
import LabCard from '../components/Dashboard/LabCard'
import PageHeader from '../components/ui/PageHeader'
import EmptyState from '../components/ui/EmptyState'
import Modal from '../components/ui/Modal'
import { useToast } from '../components/ui/Feedback'

const Stat = ({ label, value, total, foot, tone }) => (
  <div className="card stat">
    <div className="stat__label">
      {tone && <span className={`dot tone-${tone}`} aria-hidden="true" />}
      {label}
    </div>
    <div className="stat__value">
      {value}
      {total !== undefined && <small>/ {total}</small>}
    </div>
    {foot && <div className="stat__foot">{foot}</div>}
  </div>
)

const EMPTY_LAB = { lab_id: '', lab_name: '', operating_start_time: '08:00', operating_end_time: '20:00' }

const DashboardPage = () => {
  useDocumentTitle('Overview')
  const navigate = useNavigate()
  const toast = useToast()
  const { isAdmin } = useAuth()
  const { pcStates } = useLabState()
  const { labs, loading: labsLoading, refresh: refreshLabs } = useLabs()
  const { pcsByLab, loading: pcsLoading, refresh: refreshPcs } = useLabPcs(labs)

  const [query, setQuery] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [creating, setCreating] = useState(false)
  const [newLab, setNewLab] = useState(EMPTY_LAB)
  const [saving, setSaving] = useState(false)

  const perLab = useMemo(() => {
    const out = {}
    labs.forEach((lab) => {
      out[lab.lab_id] = summarizePcs(mergeLivePcs(pcsByLab[lab.lab_id] || [], pcStates))
    })
    return out
  }, [labs, pcsByLab, pcStates])

  const totals = useMemo(() => {
    const t = { total: 0, free: 0, IN_USE: 0, AVAILABLE_SLEEP: 0, MAINTENANCE: 0 }
    Object.values(perLab).forEach((c) => {
      t.total += c.total
      t.free += c.free
      t.IN_USE += c.IN_USE
      t.AVAILABLE_SLEEP += c.AVAILABLE_SLEEP
      t.MAINTENANCE += c.MAINTENANCE
    })
    return t
  }, [perLab])

  const openLabs = labs.filter((l) => l.state === 'OPEN').length
  const inSession = labs.filter((l) => l.state === 'OCCUPIED').length
  const occupancy = totals.total ? Math.round((totals.IN_USE / totals.total) * 100) : 0
  const loading = labsLoading || pcsLoading

  const handleRefresh = async () => {
    setRefreshing(true)
    await Promise.all([refreshLabs(), refreshPcs()])
    setRefreshing(false)
  }

  const handleSearch = (e) => {
    e.preventDefault()
    const q = query.trim()
    navigate(q ? `/software?q=${encodeURIComponent(q)}` : '/software')
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await adminApi.createLab({ ...newLab, lab_id: newLab.lab_id.trim(), lab_name: newLab.lab_name.trim() })
      toast.success(`Created ${newLab.lab_name.trim()}`)
      setCreating(false)
      setNewLab(EMPTY_LAB)
      refreshLabs()
    } catch (err) {
      toast.error(apiError(err, 'Could not create the lab'))
    } finally {
      setSaving(false)
    }
  }

  const today = new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })

  return (
    <>
      <PageHeader
        title="Overview"
        description={`${today} · ${labs.length} ${labs.length === 1 ? 'lab' : 'labs'} monitored`}
        actions={
          <>
            <form onSubmit={handleSearch} className="input-icon" style={{ width: 240 }} role="search">
              <input
                type="search"
                className="input"
                placeholder="Find software…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                aria-label="Find software"
              />
              <FiSearch size={15} />
            </form>
            <button
              type="button"
              className="btn btn--secondary btn--icon"
              onClick={handleRefresh}
              disabled={refreshing}
              aria-label="Refresh"
              title="Refresh"
            >
              <FiRefreshCw size={15} className={refreshing ? 'spin' : ''} />
            </button>
            {isAdmin() && (
              <button type="button" className="btn btn--primary" onClick={() => setCreating(true)}>
                <FiPlus size={15} /> New lab
              </button>
            )}
          </>
        }
      />

      <div className="grid grid--stats">
        <Stat
          tone="available"
          label="Free now"
          value={loading ? '–' : totals.free}
          total={loading ? undefined : totals.total}
          foot={totals.AVAILABLE_SLEEP ? `Includes ${totals.AVAILABLE_SLEEP} asleep` : 'Across all labs'}
        />
        <Stat tone="in-use" label="In use" value={loading ? '–' : totals.IN_USE} foot={`${occupancy}% occupancy`} />
        <Stat
          tone="neutral"
          label="Labs open for walk-in"
          value={labsLoading ? '–' : openLabs}
          total={labsLoading ? undefined : labs.length}
          foot={inSession ? `${inSession} with a class in session` : 'No classes in session'}
        />
        <Stat
          tone="maintenance"
          label="Under maintenance"
          value={loading ? '–' : totals.MAINTENANCE}
          foot={totals.MAINTENANCE ? 'Out of service' : 'All workstations in service'}
        />
      </div>

      <section className="section">
        <div className="section__header">
          <h2 className="section__title">Labs</h2>
        </div>

        {labsLoading && labs.length === 0 ? (
          <div className="grid grid--labs">
            {[0, 1, 2].map((i) => (
              <div key={i} className="skeleton" style={{ height: 212 }} />
            ))}
          </div>
        ) : labs.length === 0 ? (
          <div className="card">
            <EmptyState
              icon={FiLayers}
              title="No labs yet"
              description={isAdmin() ? 'Create a lab, then register its workstations.' : 'An administrator has not set up any labs yet.'}
              action={
                isAdmin() && (
                  <button type="button" className="btn btn--primary" onClick={() => setCreating(true)}>
                    <FiPlus size={15} /> New lab
                  </button>
                )
              }
            />
          </div>
        ) : (
          <div className="grid grid--labs">
            {labs.map((lab) => (
              <LabCard key={lab.lab_id} lab={lab} counts={perLab[lab.lab_id]} loading={pcsLoading} />
            ))}
          </div>
        )}
      </section>

      <Modal
        open={creating}
        onClose={() => setCreating(false)}
        onSubmit={handleCreate}
        busy={saving}
        title="New lab"
        description="Workstations are added from the lab page afterwards."
        footer={
          <>
            <button type="button" className="btn btn--secondary" onClick={() => setCreating(false)} disabled={saving}>
              Cancel
            </button>
            <button type="submit" className="btn btn--primary" disabled={saving}>
              {saving ? 'Creating…' : 'Create lab'}
            </button>
          </>
        }
      >
        <div className="field">
          <label className="field__label" htmlFor="lab_name">
            Name
          </label>
          <input
            id="lab_name"
            className="input"
            placeholder="Computer Lab 408"
            value={newLab.lab_name}
            onChange={(e) => setNewLab({ ...newLab, lab_name: e.target.value })}
            required
          />
        </div>
        <div className="field">
          <label className="field__label" htmlFor="lab_id">
            Lab ID
          </label>
          <input
            id="lab_id"
            className="input mono"
            placeholder="408"
            value={newLab.lab_id}
            onChange={(e) => setNewLab({ ...newLab, lab_id: e.target.value })}
            required
          />
          <span className="field__hint">Used in URLs and to generate workstation IDs (e.g. 40801). Cannot be changed later.</span>
        </div>
        <div className="field-row">
          <div className="field">
            <label className="field__label" htmlFor="lab_open">
              Opens
            </label>
            <input
              id="lab_open"
              type="time"
              className="input"
              value={newLab.operating_start_time}
              onChange={(e) => setNewLab({ ...newLab, operating_start_time: e.target.value })}
              required
            />
          </div>
          <div className="field">
            <label className="field__label" htmlFor="lab_close">
              Closes
            </label>
            <input
              id="lab_close"
              type="time"
              className="input"
              value={newLab.operating_end_time}
              onChange={(e) => setNewLab({ ...newLab, operating_end_time: e.target.value })}
              required
            />
          </div>
        </div>
      </Modal>
    </>
  )
}

export default DashboardPage
