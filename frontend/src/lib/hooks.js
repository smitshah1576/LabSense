import { useEffect, useState } from 'react'

// Re-render on an interval so relative times ("12s ago") stay current.
export const useNow = (intervalMs = 1000) => {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(id)
  }, [intervalMs])
  return now
}

export const useDebouncedValue = (value, delayMs = 300) => {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(id)
  }, [value, delayMs])
  return debounced
}

export const useDocumentTitle = (title) => {
  useEffect(() => {
    document.title = title ? `${title} · LabSense` : 'LabSense'
  }, [title])
}

// Turn an axios error into a sentence worth showing to a person.
export const apiError = (err, fallback = 'Something went wrong') => {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg
  if (err && !err.response) return 'Could not reach the server. Check that the backend is running.'
  return fallback
}
