import React, { useEffect, useState } from 'react'
import { timetableApi } from '../../api/endpoints'
import { apiError } from '../../lib/hooks'
import { formatClock, formatDateShort, isoWeekday, nextOccurrence, parseLocalDate, toLocalISODate, weekdayName } from '../../lib/time'
import Modal from '../ui/Modal'
import { useToast } from '../ui/Feedback'

const CancelSlotModal = ({ slot, onClose, onCancelled }) => {
  const toast = useToast()
  const [date, setDate] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (slot) setDate(toLocalISODate(nextOccurrence(slot.day_of_week)))
  }, [slot])

  const today = toLocalISODate(new Date())
  const wrongDay = slot && date && isoWeekday(parseLocalDate(date)) !== Number(slot.day_of_week)
  const inPast = date && date < today

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (wrongDay || inPast) return
    setSubmitting(true)
    try {
      await timetableApi.cancelSlot(slot.timetable_id, date)
      toast.success(`${slot.course_code || 'Class'} cancelled for ${formatDateShort(date)}`)
      onCancelled?.()
      onClose()
    } catch (err) {
      toast.error(apiError(err, 'Could not cancel the class'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={!!slot}
      onClose={onClose}
      onSubmit={handleSubmit}
      busy={submitting}
      size="sm"
      title={`Cancel ${slot?.course_code || 'class'} for one date`}
      description={
        slot
          ? `${weekdayName(slot.day_of_week)}s, ${formatClock(slot.start_time)}–${formatClock(slot.end_time)}. The lab reads Open instead of Occupied on that date; other weeks are unaffected.`
          : undefined
      }
      footer={
        <>
          <button type="button" className="btn btn--secondary" onClick={onClose} disabled={submitting}>
            Keep class
          </button>
          <button type="submit" className="btn btn--danger" disabled={submitting || wrongDay || inPast || !date}>
            {submitting ? 'Cancelling…' : 'Cancel class'}
          </button>
        </>
      }
    >
      <div className="field">
        <label className="field__label" htmlFor="cancel_date">
          Date
        </label>
        <input
          id="cancel_date"
          type="date"
          className="input"
          value={date}
          min={today}
          onChange={(e) => setDate(e.target.value)}
          required
        />
        {wrongDay && (
          <span className="field__error">
            That date is a {weekdayName(isoWeekday(parseLocalDate(date)))}. This class runs on {weekdayName(slot.day_of_week)}s.
          </span>
        )}
        {inPast && <span className="field__error">Choose today or a later date.</span>}
      </div>
    </Modal>
  )
}

export default CancelSlotModal
