// Time and date formatting. Dates are handled in the browser's local zone,
// which is also the zone lab timetables are written in.

export const WEEKDAYS = [
  { value: 1, name: 'Monday', short: 'Mon' },
  { value: 2, name: 'Tuesday', short: 'Tue' },
  { value: 3, name: 'Wednesday', short: 'Wed' },
  { value: 4, name: 'Thursday', short: 'Thu' },
  { value: 5, name: 'Friday', short: 'Fri' },
  { value: 6, name: 'Saturday', short: 'Sat' },
  { value: 7, name: 'Sunday', short: 'Sun' },
]

export const weekdayName = (value) => WEEKDAYS.find((d) => d.value === Number(value))?.name || ''

// "09:00:00" -> "09:00"
export const formatClock = (value) => {
  if (!value) return '--:--'
  const parts = String(value).split(':')
  return parts.length >= 2 ? `${parts[0].padStart(2, '0')}:${parts[1]}` : String(value)
}

export const formatDuration = (seconds) => {
  const s = Math.max(0, Math.floor(Number(seconds) || 0))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ${String(s % 60).padStart(2, '0')}s`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ${String(m % 60).padStart(2, '0')}m`
  return `${Math.floor(h / 24)}d ${h % 24}h`
}

export const relativeTime = (value, now = Date.now()) => {
  if (!value) return null
  const t = new Date(value).getTime()
  if (Number.isNaN(t)) return null
  const diff = Math.round((now - t) / 1000)
  if (diff < 5) return 'just now'
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return new Date(t).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

export const formatDateTime = (value) => {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return d.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

// Local calendar date as YYYY-MM-DD. toISOString() would give the UTC date,
// which is the previous day for the first 5.5 hours of every day in IST.
export const toLocalISODate = (date) => {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export const parseLocalDate = (iso) => {
  const [y, m, d] = String(iso).split('-').map(Number)
  return new Date(y, (m || 1) - 1, d || 1)
}

// "2026-09-17" -> "Thu, 17 Sep"
export const formatDateShort = (value) => {
  if (!value) return ''
  return parseLocalDate(value).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })
}

// Monday = 1 ... Sunday = 7, matching master_timetables.day_of_week.
export const isoWeekday = (date) => ((date.getDay() + 6) % 7) + 1

export const addDays = (date, days) => {
  const d = new Date(date)
  d.setDate(d.getDate() + days)
  return d
}

export const startOfWeek = (date = new Date()) => {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  return addDays(d, -(isoWeekday(d) - 1))
}

// Next date (today included) that falls on the given ISO weekday.
export const nextOccurrence = (dayOfWeek, from = new Date()) => {
  const base = new Date(from.getFullYear(), from.getMonth(), from.getDate())
  const delta = (Number(dayOfWeek) - isoWeekday(base) + 7) % 7
  return addDays(base, delta)
}

// "HH:MM[:SS]" -> minutes since midnight
export const clockToMinutes = (value) => {
  const [h, m] = String(value || '0:0').split(':').map(Number)
  return (h || 0) * 60 + (m || 0)
}
