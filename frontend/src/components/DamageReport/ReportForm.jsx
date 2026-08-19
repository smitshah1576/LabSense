import React, { useState, useEffect } from 'react'
import { labsApi, pcsApi, damageReportsApi } from '../../api/endpoints'
import { FiAlertTriangle, FiCheckCircle, FiSend } from 'react-icons/fi'

const ReportForm = ({ onReportSubmitted, prefilledPcId = '' }) => {
  const [labs, setLabs] = useState([])
  const [selectedLab, setSelectedLab] = useState('')
  const [labPcs, setLabPcs] = useState([])
  const [pcId, setPcId] = useState(prefilledPcId)
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [successMsg, setSuccessMsg] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    labsApi
      .getLabs()
      .then((res) => {
        if (Array.isArray(res.data)) {
          setLabs(res.data)
          if (res.data.length > 0 && !selectedLab) {
            setSelectedLab(res.data[0].id)
          }
        }
      })
      .catch((err) => console.warn('Could not load labs for report form:', err))
  }, [])

  useEffect(() => {
    if (selectedLab) {
      pcsApi
        .getLabPCs(selectedLab)
        .then((res) => {
          if (Array.isArray(res.data)) {
            setLabPcs(res.data)
            if (res.data.length > 0 && !prefilledPcId) {
              setPcId(res.data[0].id)
            }
          }
        })
        .catch((err) => console.warn('Could not load PCs for selected lab:', err))
    }
  }, [selectedLab, prefilledPcId])

  useEffect(() => {
    if (prefilledPcId) {
      setPcId(prefilledPcId)
    }
  }, [prefilledPcId])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!pcId || !description.trim()) {
      setErrorMsg('Please select a PC and provide a description of the issue.')
      return
    }

    setSubmitting(true)
    setErrorMsg('')
    setSuccessMsg('')

    try {
      await damageReportsApi.submitReport(pcId, description.trim())
      setSuccessMsg(`Damage report for workstation "${pcId}" submitted successfully!`)
      setDescription('')
      if (onReportSubmitted) onReportSubmitted()
    } catch (err) {
      console.error('Failed to submit report:', err)
      setErrorMsg(err.response?.data?.detail || 'Failed to submit report. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="glass-card" style={{ padding: '1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1.25rem' }}>
        <div
          style={{
            width: '32px',
            height: '32px',
            borderRadius: 'var(--radius-sm)',
            background: 'hsla(38, 92%, 50%, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--color-warning)',
          }}
        >
          <FiAlertTriangle size={18} />
        </div>
        <div>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            Report Hardware or Software Issue
          </h3>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Notify lab administrators of faulty monitors, peripherals, or software glitches
          </p>
        </div>
      </div>

      {successMsg && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.85rem',
            borderRadius: 'var(--radius-sm)',
            background: 'hsla(142, 71%, 45%, 0.15)',
            border: '1px solid var(--color-success)',
            color: 'var(--color-success)',
            fontSize: '0.875rem',
            marginBottom: '1rem',
          }}
        >
          <FiCheckCircle size={18} />
          <span>{successMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div
          style={{
            padding: '0.85rem',
            borderRadius: 'var(--radius-sm)',
            background: 'hsla(0, 84%, 60%, 0.15)',
            border: '1px solid var(--color-danger)',
            color: 'var(--color-danger)',
            fontSize: '0.875rem',
            marginBottom: '1rem',
          }}
        >
          {errorMsg}
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <div className="input-group">
            <label className="input-label">Filter by Lab</label>
            <select
              className="select"
              value={selectedLab}
              onChange={(e) => setSelectedLab(e.target.value)}
            >
              {labs.map((l) => (
                <option key={l.id} value={l.id} style={{ background: '#131722' }}>
                  {l.name}
                </option>
              ))}
            </select>
          </div>

          <div className="input-group">
            <label className="input-label">Workstation / PC</label>
            <select
              className="select"
              value={pcId}
              onChange={(e) => setPcId(e.target.value)}
              required
            >
              {labPcs.length === 0 ? (
                <option value="" style={{ background: '#131722' }}>
                  No PCs in selected lab
                </option>
              ) : (
                labPcs.map((pc) => (
                  <option key={pc.id} value={pc.id} style={{ background: '#131722' }}>
                    {pc.hostname ? `${pc.hostname} (${pc.id})` : pc.id}
                  </option>
                ))
              )}
            </select>
          </div>
        </div>

        <div className="input-group">
          <label className="input-label">Detailed Description of Problem</label>
          <textarea
            className="textarea"
            rows={4}
            placeholder="Describe the issue (e.g., keyboard keys unresponsive, blue screen on boot, missing mouse)..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
          />
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={submitting || !pcId}
          >
            <FiSend size={15} />
            <span>{submitting ? 'Submitting...' : 'Submit Damage Report'}</span>
          </button>
        </div>
      </form>
    </div>
  )
}

export default ReportForm
