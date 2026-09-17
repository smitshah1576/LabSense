import React, { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { FiInbox, FiList, FiPlus, FiRefreshCw } from 'react-icons/fi'
import { damageReportsApi } from '../api/endpoints'
import { useAuth } from '../hooks/useAuth'
import ReportForm from '../components/DamageReport/ReportForm'
import ReportReviewList from '../components/DamageReport/ReportReviewList'
import PageHeader from '../components/ui/PageHeader'
import { useConfirm, useToast } from '../components/ui/Feedback'
import { apiError, useDocumentTitle } from '../lib/hooks'

const HowItWorks = () => (
  <aside className="card card--pad">
    <div className="card__title" style={{ marginBottom: 14 }}>
      What happens next
    </div>
    <ol className="steps">
      <li>
        <b>An administrator reviews it</b>
        Usually the same day the lab is open.
      </li>
      <li>
        <b>The workstation is taken out of service</b>
        If the problem is confirmed it is marked Maintenance, so nobody is sent to it.
      </li>
      <li>
        <b>It returns once fixed</b>
        The workstation shows as available again automatically.
      </li>
    </ol>
  </aside>
)

const AdminReports = ({ initialLabId, initialPcId }) => {
  const toast = useToast()
  const confirm = useConfirm()
  const [params, setParams] = useSearchParams()
  const [pending, setPending] = useState([])
  const [all, setAll] = useState([])
  const [loading, setLoading] = useState(true)
  const [resolvingId, setResolvingId] = useState(null)

  const view = params.get('view') || (initialPcId ? 'new' : 'queue')
  const setView = (v) => {
    const next = new URLSearchParams(params)
    next.set('view', v)
    setParams(next, { replace: true })
  }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [p, a] = await Promise.all([damageReportsApi.getPendingReports(), damageReportsApi.getReports()])
      setPending(p.data || [])
      setAll(a.data || [])
    } catch (err) {
      toast.error(apiError(err, 'Could not load reports'))
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  const handleResolve = async (report, status) => {
    if (status === 'APPROVED') {
      const ok = await confirm({
        title: `Approve report for ${report.pc_id}?`,
        message: 'The workstation will be marked Maintenance and shown as out of service until someone returns it to service.',
        confirmLabel: 'Approve',
      })
      if (!ok) return
    }
    setResolvingId(report.report_id)
    try {
      await damageReportsApi.resolveReport(report.report_id, status)
      toast.success(status === 'APPROVED' ? `${report.pc_id} is now in maintenance` : 'Report dismissed')
      load()
    } catch (err) {
      toast.error(apiError(err, 'Could not update the report'))
    } finally {
      setResolvingId(null)
    }
  }

  const tabs = [
    { key: 'queue', label: 'Needs review', icon: FiInbox, count: pending.length },
    { key: 'history', label: 'All reports', icon: FiList, count: all.length },
    { key: 'new', label: 'New report', icon: FiPlus },
  ]

  return (
    <>
      <PageHeader
        title="Reports"
        description="Issues reported by lab users. Approving a report puts the workstation into maintenance."
        actions={
          <button type="button" className="btn btn--secondary btn--icon" onClick={load} disabled={loading} aria-label="Refresh" title="Refresh">
            <FiRefreshCw size={15} className={loading ? 'spin' : ''} />
          </button>
        }
      />

      <div className="tabs" role="tablist">
        {tabs.map(({ key, label, icon: Icon, count }) => (
          <button key={key} type="button" role="tab" className="tab" aria-selected={view === key} onClick={() => setView(key)}>
            <Icon size={15} />
            {label}
            {count !== undefined && <span className="tab__count">{count}</span>}
          </button>
        ))}
      </div>

      {view === 'queue' && (
        <ReportReviewList
          reports={pending}
          loading={loading}
          resolvingId={resolvingId}
          onResolve={handleResolve}
          emptyTitle="Nothing to review"
          emptyDescription="New reports from lab users will appear here."
        />
      )}
      {view === 'history' && (
        <ReportReviewList
          reports={all}
          loading={loading}
          resolvingId={resolvingId}
          onResolve={handleResolve}
          emptyTitle="No reports yet"
          emptyDescription="Every report ever submitted, and how it was resolved, is listed here."
        />
      )}
      {view === 'new' && (
        <div style={{ maxWidth: 640 }}>
          <ReportForm initialLabId={initialLabId} initialPcId={initialPcId} onSubmitted={load} />
        </div>
      )}
    </>
  )
}

const DamageReportsPage = () => {
  const { isAdmin } = useAuth()
  const [params] = useSearchParams()
  const initialLabId = params.get('lab') || ''
  const initialPcId = params.get('pc') || ''
  useDocumentTitle(isAdmin() ? 'Reports' : 'Report an issue')

  if (isAdmin()) return <AdminReports initialLabId={initialLabId} initialPcId={initialPcId} />

  return (
    <>
      <PageHeader title="Report an issue" description="Tell the lab administrators about a problem with a workstation." />
      <div className="layout-aside">
        <ReportForm initialLabId={initialLabId} initialPcId={initialPcId} />
        <HowItWorks />
      </div>
    </>
  )
}

export default DamageReportsPage
