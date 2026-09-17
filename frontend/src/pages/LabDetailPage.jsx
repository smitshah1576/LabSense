import React, { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { FiCalendar, FiChevronRight, FiClock, FiHash, FiMonitor, FiPackage, FiPlus, FiRefreshCw, FiTrash2 } from 'react-icons/fi'
import { adminApi, labsApi, pcsApi, timetableApi } from '../api/endpoints'
import { useAuth } from '../hooks/useAuth'
import { useLabState } from '../hooks/useLabState'
import { useLabs } from '../context/LabsContext'
import { useSoftwareSearch } from '../hooks/useSoftwareSearch'
import { mergeLivePcs, summarizePcs } from '../lib/pcState'
import { apiError, useDocumentTitle } from '../lib/hooks'
import { formatClock } from '../lib/time'
import PCGrid from '../components/Dashboard/PCGrid'
import TimetableView from '../components/Timetable/TimetableView'
import SearchBar from '../components/Software/SearchBar'
import SoftwareResults from '../components/Software/SoftwareResults'
import EmptyState from '../components/ui/EmptyState'
import { StackBar, StateLegend, StatusPill } from '../components/ui/StatusPill'
import { useConfirm, useToast } from '../components/ui/Feedback'

const TABS = [
  { key: 'workstations', label: 'Workstations', icon: FiMonitor },
  { key: 'schedule', label: 'Schedule', icon: FiCalendar },
  { key: 'software', label: 'Software', icon: FiPackage },
]

const LabSoftware = ({ labId, labName }) => {
  const [query, setQuery] = useState('')
  const search = useSoftwareSearch(query, labId)
  return (
    <>
      <div style={{ maxWidth: 520, marginBottom: 16 }}>
        <SearchBar value={query} onChange={setQuery} loading={search.loading} placeholder={`Search packages in ${labName}`} />
      </div>
      <SoftwareResults results={search.results} query={search.query} loading={search.loading} showLab={false} minLength={search.minLength} />
    </>
  )
}

const LabDetailPage = () => {
  const { labId } = useParams()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const tab = TABS.some((t) => t.key === params.get('tab')) ? params.get('tab') : 'workstations'

  const { isAdmin, isProfessor } = useAuth()
  const { pcStates } = useLabState()
  const { refresh: refreshLabs } = useLabs()
  const toast = useToast()
  const confirm = useConfirm()

  const [lab, setLab] = useState(null)
  const [pcs, setPcs] = useState([])
  const [timetable, setTimetable] = useState([])
  const [cancellations, setCancellations] = useState([])
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [busyPcId, setBusyPcId] = useState(null)
  const [addingPc, setAddingPc] = useState(false)

  useDocumentTitle(lab?.lab_name)

  const load = useCallback(async () => {
    try {
      const [labRes, pcsRes, ttRes, cancelRes] = await Promise.all([
        labsApi.getLab(labId),
        pcsApi.getLabPCs(labId),
        timetableApi.getLabTimetable(labId),
        timetableApi.getLabCancellations(labId),
      ])
      setLab(labRes.data)
      setPcs(pcsRes.data || [])
      setTimetable(ttRes.data || [])
      setCancellations(cancelRes.data || [])
      setNotFound(false)
    } catch (err) {
      if (err?.response?.status === 404) setNotFound(true)
      else toast.error(apiError(err, 'Could not load this lab'))
    } finally {
      setLoading(false)
    }
  }, [labId, toast])

  useEffect(() => {
    setLoading(true)
    setLab(null)
    load()
  }, [load])

  const livePcs = mergeLivePcs(pcs, pcStates)
  const counts = summarizePcs(livePcs)

  const selectTab = (key) => setParams(key === 'workstations' ? {} : { tab: key }, { replace: true })

  const handleRefresh = async () => {
    setRefreshing(true)
    await load()
    setRefreshing(false)
  }

  const handleToggleMaintenance = async (pc) => {
    const entering = pc.current_state !== 'MAINTENANCE'
    setBusyPcId(pc.pc_id)
    try {
      await pcsApi.toggleMaintenance(pc.pc_id, entering)
      setPcs((prev) => prev.map((p) => (p.pc_id === pc.pc_id ? { ...p, current_state: entering ? 'MAINTENANCE' : 'AVAILABLE' } : p)))
      toast.success(entering ? `${pc.pc_id} marked for maintenance` : `${pc.pc_id} returned to service`)
    } catch (err) {
      toast.error(apiError(err, 'Could not update maintenance'))
    } finally {
      setBusyPcId(null)
    }
  }

  const handleAddPc = async () => {
    setAddingPc(true)
    try {
      const res = await adminApi.createPC(labId)
      toast.success(`Registered ${res.data.pc_id}. Deploy the agent with --pc-id ${res.data.pc_id}.`)
      load()
    } catch (err) {
      toast.error(apiError(err, 'Could not add a workstation'))
    } finally {
      setAddingPc(false)
    }
  }

  const handleDeletePc = async (pc) => {
    const ok = await confirm({
      title: `Remove ${pc.pc_id}?`,
      message: 'Its state history and damage reports are deleted too. A running agent with this ID will be rejected.',
      confirmLabel: 'Remove workstation',
      tone: 'danger',
    })
    if (!ok) return
    try {
      await adminApi.deletePC(pc.pc_id)
      toast.success(`${pc.pc_id} removed`)
      load()
    } catch (err) {
      toast.error(apiError(err, 'Could not remove the workstation'))
    }
  }

  const handleDeleteLab = async () => {
    const ok = await confirm({
      title: `Delete ${lab.lab_name}?`,
      message: `This permanently deletes the lab, its ${counts.total} ${
        counts.total === 1 ? 'workstation' : 'workstations'
      }, their history and reports, and its timetable.`,
      confirmLabel: 'Delete lab',
      tone: 'danger',
    })
    if (!ok) return
    try {
      await adminApi.deleteLab(labId)
      toast.success(`${lab.lab_name} deleted`)
      refreshLabs()
      navigate('/')
    } catch (err) {
      toast.error(apiError(err, 'Could not delete the lab'))
    }
  }

  const breadcrumb = (
    <>
      <Link to="/">Overview</Link>
      <FiChevronRight size={13} />
      <span style={{ color: 'var(--text-2)' }}>{lab?.lab_name || labId}</span>
    </>
  )

  if (loading && !lab) {
    return (
      <>
        <div className="skeleton" style={{ height: 96, marginBottom: 24 }} />
        <div className="grid grid--pcs">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton" style={{ height: 196 }} />
          ))}
        </div>
      </>
    )
  }

  if (notFound || !lab) {
    return (
      <div className="card">
        <EmptyState
          icon={FiMonitor}
          title="Lab not found"
          description={`There is no lab with the ID “${labId}”. It may have been deleted.`}
          action={
            <Link to="/" className="btn btn--secondary">
              Back to overview
            </Link>
          }
        />
      </div>
    )
  }

  return (
    <>
      <nav className="breadcrumb" aria-label="Breadcrumb">
        {breadcrumb}
      </nav>

      <header className="lab-hero">
        <div style={{ minWidth: 0 }}>
          <div className="lab-hero__title">
            <h1 className="page-header__title">{lab.lab_name}</h1>
            <StatusPill kind="lab" state={lab.state} size="lg" />
          </div>
          <div className="lab-hero__meta">
            <span className="inline-meta">
              <FiClock size={14} />
              <span className="num">
                Open {formatClock(lab.operating_start_time)}–{formatClock(lab.operating_end_time)}
              </span>
            </span>
            <span className="inline-meta">
              <FiHash size={14} />
              <span className="mono">{lab.lab_id}</span>
            </span>
          </div>
          <div className="page-header__actions" style={{ marginTop: 16 }}>
            <button type="button" className="btn btn--secondary btn--sm" onClick={handleRefresh} disabled={refreshing}>
              <FiRefreshCw size={13} className={refreshing ? 'spin' : ''} /> Refresh
            </button>
            {isAdmin() && (
              <button type="button" className="btn btn--danger-ghost btn--sm" onClick={handleDeleteLab}>
                <FiTrash2 size={13} /> Delete lab
              </button>
            )}
          </div>
        </div>

        <div className="card lab-hero__summary" style={{ padding: 16 }}>
          <div className="lab-card__avail">
            <span className="lab-card__avail-num">{counts.free}</span>
            <span className="lab-card__avail-label">
              of {counts.total} {counts.total === 1 ? 'workstation' : 'workstations'} free
            </span>
          </div>
          <StackBar counts={counts} />
          <StateLegend counts={counts} />
        </div>
      </header>

      <div className="tabs" role="tablist">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button key={key} type="button" role="tab" className="tab" aria-selected={tab === key} onClick={() => selectTab(key)}>
            <Icon size={15} />
            {label}
            {key === 'workstations' && <span className="tab__count">{counts.total}</span>}
            {key === 'schedule' && <span className="tab__count">{timetable.length}</span>}
          </button>
        ))}
      </div>

      {tab === 'workstations' && (
        <PCGrid
          pcs={livePcs}
          canMaintain={isProfessor()}
          canDelete={isAdmin()}
          busyPcId={busyPcId}
          onToggleMaintenance={handleToggleMaintenance}
          onDelete={handleDeletePc}
          actions={
            isAdmin() && (
              <button type="button" className="btn btn--primary btn--sm" onClick={handleAddPc} disabled={addingPc}>
                <FiPlus size={14} /> {addingPc ? 'Adding…' : 'Add workstation'}
              </button>
            )
          }
        />
      )}

      {tab === 'schedule' && (
        <TimetableView labId={labId} timetable={timetable} cancellations={cancellations} onChanged={() => { load(); refreshLabs() }} />
      )}

      {tab === 'software' && <LabSoftware labId={labId} labName={lab.lab_name} />}
    </>
  )
}

export default LabDetailPage
