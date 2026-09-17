import React, { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { FiArrowRight, FiLayers } from 'react-icons/fi'
import { timetableApi } from '../api/endpoints'
import { useLabs } from '../context/LabsContext'
import TimetableView from '../components/Timetable/TimetableView'
import PageHeader from '../components/ui/PageHeader'
import EmptyState from '../components/ui/EmptyState'
import { StatusPill } from '../components/ui/StatusPill'
import { apiError, useDocumentTitle } from '../lib/hooks'
import { useToast } from '../components/ui/Feedback'

const TimetablePage = () => {
  useDocumentTitle('Timetable')
  const toast = useToast()
  const { labs, loading: labsLoading, refresh: refreshLabs } = useLabs()
  const [params, setParams] = useSearchParams()
  const selectedLabId = params.get('lab') || labs[0]?.lab_id || ''
  const selectedLab = labs.find((l) => l.lab_id === selectedLabId)

  const [timetable, setTimetable] = useState([])
  const [cancellations, setCancellations] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    if (!selectedLabId) {
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const [tt, cancel] = await Promise.all([
        timetableApi.getLabTimetable(selectedLabId),
        timetableApi.getLabCancellations(selectedLabId),
      ])
      setTimetable(tt.data || [])
      setCancellations(cancel.data || [])
    } catch (err) {
      toast.error(apiError(err, 'Could not load the timetable'))
    } finally {
      setLoading(false)
    }
  }, [selectedLabId, toast])

  useEffect(() => {
    load()
  }, [load])

  return (
    <>
      <PageHeader
        title="Timetable"
        description="Weekly classes decide when a lab is Occupied. Cancel a single date without changing the weekly schedule."
        actions={
          labs.length > 0 && (
            <>
              <label className="sr-only" htmlFor="tt-lab">
                Lab
              </label>
              <select
                id="tt-lab"
                className="select"
                style={{ width: 220 }}
                value={selectedLabId}
                onChange={(e) => setParams({ lab: e.target.value }, { replace: true })}
              >
                {labs.map((lab) => (
                  <option key={lab.lab_id} value={lab.lab_id}>
                    {lab.lab_name}
                  </option>
                ))}
              </select>
            </>
          )
        }
      />

      {!labsLoading && labs.length === 0 ? (
        <div className="card">
          <EmptyState icon={FiLayers} title="No labs yet" description="Create a lab from the overview before adding its timetable." />
        </div>
      ) : (
        <>
          {selectedLab && (
            <div className="toolbar" style={{ marginBottom: 18 }}>
              <div className="inline-meta" style={{ gap: 10 }}>
                <span style={{ fontWeight: 600 }}>{selectedLab.lab_name}</span>
                <StatusPill kind="lab" state={selectedLab.state} />
              </div>
              <Link to={`/labs/${selectedLab.lab_id}`} className="btn btn--ghost btn--sm">
                View lab <FiArrowRight size={13} />
              </Link>
            </div>
          )}
          {loading ? (
            <div className="skeleton" style={{ height: 240 }} />
          ) : (
            <TimetableView
              labId={selectedLabId}
              timetable={timetable}
              cancellations={cancellations}
              onChanged={() => {
                load()
                refreshLabs()
              }}
            />
          )}
        </>
      )}
    </>
  )
}

export default TimetablePage
