import { useEffect, useRef, useState } from 'react'
import { softwareApi } from '../api/endpoints'
import { useDebouncedValue } from '../lib/hooks'

const MIN_LENGTH = 2

// Debounced software search that ignores responses from superseded queries,
// so a slow reply for "py" can't overwrite the results for "python".
export const useSoftwareSearch = (query, labId) => {
  const debounced = useDebouncedValue(query.trim(), 250)
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const requestId = useRef(0)

  useEffect(() => {
    const id = ++requestId.current
    if (debounced.length < MIN_LENGTH) {
      setResults([])
      setLoading(false)
      setError(null)
      return
    }
    setLoading(true)
    const request = labId ? softwareApi.searchLab(labId, debounced) : softwareApi.searchGlobal(debounced)
    request
      .then((res) => {
        if (id !== requestId.current) return
        setResults(Array.isArray(res.data) ? res.data : [])
        setError(null)
      })
      .catch((err) => {
        if (id !== requestId.current) return
        setResults([])
        setError(err)
      })
      .finally(() => {
        if (id === requestId.current) setLoading(false)
      })
  }, [debounced, labId])

  // While typing, report "loading" so the UI doesn't flash an empty state.
  const pending = query.trim() !== debounced && query.trim().length >= MIN_LENGTH
  return { results, loading: loading || pending, error, query: debounced, minLength: MIN_LENGTH }
}
