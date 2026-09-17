import React, { useMemo, useState } from 'react'
import { FiCalendar, FiPlus, FiTrash2, FiXCircle } from 'react-icons/fi'
import { timetableApi } from '../../api/endpoints'
import { useAuth } from '../../hooks/useAuth'
import { apiError, useNow } from '../../lib/hooks'
import {
  WEEKDAYS,
  addDays,
  clockToMinutes,
  formatClock,
  formatDateShort,
  isoWeekday,
  startOfWeek,
  toLocalISODate,
  weekdayName,
} from '../../lib/time'
import Modal from '../ui/Modal'
import EmptyState from '../ui/EmptyState'
import { useConfirm, useToast } from '../ui/Feedback'
import CancelSlotModal from './CancelSlotModal'

const EMPTY_SLOT = { day_of_week: 1, start_time: '09:00', end_time: '11:00', course_code: '' }

const TimetableView = ({ labId, timetable = [], cancellations = [], onChanged }) => {
  const { isAdmin, isProfessor } = useAuth()
  const toast = useToast()
  const confirm = useConfirm()
  const now = useNow(30_000)

  const [adding, setAdding] = useState(false)
  const [draft, setDraft] = useState(EMPTY_SLOT)
  const [saving, setSaving] = useState(false)
  const [cancelling, setCancelling] = useState(null)

  const today = new Date(now)
  const todayISO = toLocalISODate(today)
  const weekStart = startOfWeek(today)
  const nowMinutes = today.getHours() * 60 + today.getMinutes()

  const slotsById = useMemo(() => Object.fromEntries(timetable.map((s) => [s.timetable_id, s])), [timetable])

  const upcoming = useMemo(
    () =>
      cancellations
        .filter((c) => c.cancelled_for_date >= todayISO && slotsById[c.timetable_id])
        .sort((a, b) => a.cancelled_for_date.localeCompare(b.cancelled_for_date)),
    [cancellations, slotsById, todayISO]
  )

  const draftInvalid = clockToMinutes(draft.end_time) <= clockToMinutes(draft.start_time)

  const handleAdd = async (e) => {
    e.preventDefault()
    if (draftInvalid) return
    setSaving(true)
    try {
      await timetableApi.createTimetableEntry(labId, {
        lab_id: labId,
        day_of_week: Number(draft.day_of_week),
        start_time: `${draft.start_time}:00`,
        end_time: `${draft.end_time}:00`,
        course_code: draft.course_code.trim() || null,
      })
      toast.success('Class added to the timetable')
      setAdding(false)
      setDraft(EMPTY_SLOT)
      onChanged?.()
    } catch (err) {
      toast.error(apiError(err, 'Could not add the class'))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (slot) => {
    const ok = await confirm({
      title: 'Delete this class?',
      message: `${slot.course_code || 'Class'} on ${weekdayName(slot.day_of_week)}s, ${formatClock(slot.start_time)}–${formatClock(
        slot.end_time
      )}. This removes it from every week, along with its cancellations.`,
      confirmLabel: 'Delete class',
      tone: 'danger',
    })
    if (!ok) return
    try {
      await timetableApi.deleteTimetableEntry(slot.timetable_id)
      toast.success('Class deleted')
      onChanged?.()
    } catch (err) {
      toast.error(apiError(err, 'Could not delete the class'))
    }
  }

  return (
    <>
      <div className="toolbar">
        <div className="muted">
          Week of {weekStart.toLocaleDateString(undefined, { day: 'numeric', month: 'long' })}. The lab reads{' '}
          <b style={{ color: 'var(--text)', fontWeight: 500 }}>Occupied</b> during a scheduled class.
        </div>
        {isAdmin() && (
          <button type="button" className="btn btn--primary btn--sm" onClick={() => setAdding(true)}>
            <FiPlus size={14} /> Add class
          </button>
        )}
      </div>

      {timetable.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={FiCalendar}
            title="No classes scheduled"
            description="With no timetable, this lab reads Open for its whole operating window."
          />
        </div>
      ) : (
        <div className="week">
          {WEEKDAYS.map((day) => {
            const date = addDays(weekStart, day.value - 1)
            const dateISO = toLocalISODate(date)
            const isToday = day.value === isoWeekday(today)
            const slots = timetable
              .filter((s) => Number(s.day_of_week) === day.value)
              .sort((a, b) => String(a.start_time).localeCompare(String(b.start_time)))

            return (
              <section key={day.value} className={`day ${isToday ? 'day--today' : ''}`} aria-label={day.name}>
                <header className="day__head">
                  <span className="day__name">{day.short}</span>
                  <span className="day__date">{isToday ? 'Today' : date.getDate()}</span>
                </header>
                <div className="day__slots">
                  {slots.length === 0 && <div className="day__empty">—</div>}
                  {slots.map((slot) => {
                    const cancelled = cancellations.some(
                      (c) => c.timetable_id === slot.timetable_id && c.cancelled_for_date === dateISO
                    )
                    const live =
                      isToday &&
                      !cancelled &&
                      nowMinutes >= clockToMinutes(slot.start_time) &&
                      nowMinutes <= clockToMinutes(slot.end_time)
                    return (
                      <div key={slot.timetable_id} className={`slot ${cancelled ? 'slot--cancelled' : ''} ${live ? 'slot--live' : ''}`}>
                        <div className="slot__time">
                          {formatClock(slot.start_time)}–{formatClock(slot.end_time)}
                        </div>
                        <div className="slot__course">{slot.course_code || 'Class'}</div>
                        {cancelled && <div className="slot__tag subtle">Cancelled this week</div>}
                        {live && (
                          <div className="slot__tag" style={{ color: 'var(--inuse-fg)' }}>
                            In session
                          </div>
                        )}
                        {(isProfessor() || isAdmin()) && (
                          <div className="slot__actions">
                            <button
                              type="button"
                              className="btn btn--ghost"
                              onClick={() => setCancelling(slot)}
                              title="Cancel this class on one date"
                            >
                              <FiXCircle size={12} /> Cancel
                            </button>
                            {isAdmin() && (
                              <button
                                type="button"
                                className="btn btn--danger-ghost"
                                onClick={() => handleDelete(slot)}
                                aria-label="Delete class"
                                title="Delete class"
                              >
                                <FiTrash2 size={12} />
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </section>
            )
          })}
        </div>
      )}

      {upcoming.length > 0 && (
        <section className="section">
          <div className="section__header">
            <h3 className="section__title">Upcoming cancellations</h3>
          </div>
          <div className="card list">
            {upcoming.map((c) => {
              const slot = slotsById[c.timetable_id]
              return (
                <div key={c.cancellation_id} className="list__row">
                  <div>
                    <div style={{ fontWeight: 500 }}>{slot.course_code || 'Class'}</div>
                    <div className="subtle num" style={{ fontSize: 12.5 }}>
                      {formatClock(slot.start_time)}–{formatClock(slot.end_time)}
                    </div>
                  </div>
                  <span className="pill tone-neutral num">{c.cancelled_for_date === todayISO ? 'Today' : formatDateShort(c.cancelled_for_date)}</span>
                </div>
              )
            })}
          </div>
        </section>
      )}

      <Modal
        open={adding}
        onClose={() => setAdding(false)}
        onSubmit={handleAdd}
        busy={saving}
        title="Add class"
        description="A weekly recurring class. The lab reads Occupied during it."
        footer={
          <>
            <button type="button" className="btn btn--secondary" onClick={() => setAdding(false)} disabled={saving}>
              Cancel
            </button>
            <button type="submit" className="btn btn--primary" disabled={saving || draftInvalid}>
              {saving ? 'Adding…' : 'Add class'}
            </button>
          </>
        }
      >
        <div className="field">
          <label className="field__label" htmlFor="slot_course">
            Course code
          </label>
          <input
            id="slot_course"
            className="input"
            placeholder="CS208"
            value={draft.course_code}
            onChange={(e) => setDraft({ ...draft, course_code: e.target.value })}
          />
        </div>
        <div className="field">
          <label className="field__label" htmlFor="slot_day">
            Day
          </label>
          <select
            id="slot_day"
            className="select"
            value={draft.day_of_week}
            onChange={(e) => setDraft({ ...draft, day_of_week: Number(e.target.value) })}
          >
            {WEEKDAYS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field-row">
          <div className="field">
            <label className="field__label" htmlFor="slot_start">
              Starts
            </label>
            <input
              id="slot_start"
              type="time"
              className="input"
              value={draft.start_time}
              onChange={(e) => setDraft({ ...draft, start_time: e.target.value })}
              required
            />
          </div>
          <div className="field">
            <label className="field__label" htmlFor="slot_end">
              Ends
            </label>
            <input
              id="slot_end"
              type="time"
              className="input"
              value={draft.end_time}
              onChange={(e) => setDraft({ ...draft, end_time: e.target.value })}
              required
            />
          </div>
        </div>
        {draftInvalid && <div className="field__error">The class must end after it starts.</div>}
      </Modal>

      <CancelSlotModal slot={cancelling} onClose={() => setCancelling(null)} onCancelled={onChanged} />
    </>
  )
}

export default TimetableView
