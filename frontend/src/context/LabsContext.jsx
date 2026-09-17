import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { labsApi } from '../api/endpoints'

// The lab list is shown in the sidebar and on several pages. Lab state
// (Open / Occupied / Closed) is computed per request and never pushed over
// the WebSocket, so poll it once a minute to cross timetable boundaries.
const REFRESH_MS = 60_000

const LabsContext = createContext(null)

export const LabsProvider = ({ children }) => {
  const [labs, setLabs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const res = await labsApi.getLabs()
      setLabs(Array.isArray(res.data) ? res.data : [])
      setError(null)
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, REFRESH_MS)
    return () => clearInterval(id)
  }, [refresh])

  return <LabsContext.Provider value={{ labs, loading, error, refresh }}>{children}</LabsContext.Provider>
}

export const useLabs = () => useContext(LabsContext)
