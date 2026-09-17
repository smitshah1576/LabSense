import React, { useEffect, useState } from 'react'
import { FiCheckCircle, FiSend } from 'react-icons/fi'
import { damageReportsApi, pcsApi } from '../../api/endpoints'
import { useLabs } from '../../context/LabsContext'
import { apiError } from '../../lib/hooks'
import { useToast } from '../ui/Feedback'

const MAX_LENGTH = 1000

const ReportForm = ({ initialLabId = '', initialPcId = '', onSubmitted }) => {
  const toast = useToast()
  const { labs } = useLabs()
  const [labId, setLabId] = useState(initialLabId)
  const [pcs, setPcs] = useState([])
  const [pcsLoading, setPcsLoading] = useState(false)
  const [pcId, setPcId] = useState(initialPcId)
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submittedFor, setSubmittedFor] = useState(null)

  // Default to the first lab once the list arrives.
  useEffect(() => {
    if (!labId && labs.length > 0) setLabId(labs[0].lab_id)
  }, [labs, labId])

  useEffect(() => {
    if (!labId) return
    let active = true
    setPcsLoading(true)
    pcsApi
      .getLabPCs(labId)
      .then((res) => {
        if (!active) return
        const list = (res.data || []).slice().sort((a, b) => a.pc_id.localeCompare(b.pc_id, undefined, { numeric: true }))
        setPcs(list)
        setPcId((current) => (list.some((p) => p.pc_id === current) ? current : list[0]?.pc_id || ''))
      })
      .catch(() => active && setPcs([]))
      .finally(() => active && setPcsLoading(false))
    return () => {
      active = false
    }
  }, [labId])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!pcId || !description.trim()) return
    setSubmitting(true)
    try {
      await damageReportsApi.submitReport(pcId, description.trim())
      setSubmittedFor(pcId)
      setDescription('')
      toast.success(`Report sent for ${pcId}`)
      onSubmitted?.()
    } catch (err) {
      toast.error(apiError(err, 'Could not send the report'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="card" onSubmit={handleSubmit}>
      <div className="card__header">
        <div>
          <div className="card__title">Report an issue</div>
          <div className="subtle" style={{ fontSize: 12.5 }}>
            Broken hardware, missing peripherals, software that won't start.
          </div>
        </div>
      </div>

      <div className="card__body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {submittedFor && (
          <div className="alert alert--success" role="status">
            <FiCheckCircle size={15} />
            <span>
              Thanks — your report for <span className="mono">{submittedFor}</span> is with the lab administrators.
            </span>
          </div>
        )}

        <div className="field-row">
          <div className="field">
            <label className="field__label" htmlFor="report_lab">
              Lab
            </label>
            <select id="report_lab" className="select" value={labId} onChange={(e) => setLabId(e.target.value)} required>
              {labs.map((lab) => (
                <option key={lab.lab_id} value={lab.lab_id}>
                  {lab.lab_name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label className="field__label" htmlFor="report_pc">
              Workstation
            </label>
            <select
              id="report_pc"
              className="select mono"
              value={pcId}
              onChange={(e) => setPcId(e.target.value)}
              disabled={pcsLoading || pcs.length === 0}
              required
            >
              {pcs.length === 0 && <option value="">{pcsLoading ? 'Loading…' : 'No workstations in this lab'}</option>}
              {pcs.map((pc) => (
                <option key={pc.pc_id} value={pc.pc_id}>
                  {pc.pc_id}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="field">
          <label className="field__label" htmlFor="report_desc">
            What's wrong?
          </label>
          <textarea
            id="report_desc"
            className="textarea"
            rows={5}
            maxLength={MAX_LENGTH}
            placeholder="e.g. The monitor flickers and goes black after a few minutes."
            value={description}
            onChange={(e) => {
              setDescription(e.target.value)
              setSubmittedFor(null)
            }}
            required
          />
          <span className="field__hint num" style={{ textAlign: 'right' }}>
            {description.length}/{MAX_LENGTH}
          </span>
        </div>
      </div>

      <div className="modal__foot" style={{ borderRadius: '0 0 12px 12px' }}>
        <button type="submit" className="btn btn--primary" disabled={submitting || !pcId || !description.trim()}>
          <FiSend size={14} /> {submitting ? 'Sending…' : 'Send report'}
        </button>
      </div>
    </form>
  )
}

export default ReportForm
