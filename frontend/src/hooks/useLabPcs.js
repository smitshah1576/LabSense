import { useCallback, useEffect, useState } from 'react'
import { pcsApi } from '../api/endpoints'

// Fetch the PC list for every lab. The lab endpoint has no per-lab counts, so
// the overview builds them from these lists plus live WebSocket state.
export const useLabPcs = (labs) => {
  const [pcsByLab, setPcsByLab] = useState({})
  const [loading, setLoading] = useState(true)

  const labKey = labs.map((l) => l.lab_id).join('|')

  const refresh = useCallback(async () => {
    const ids = labKey ? labKey.split('|') : []
    const results = await Promise.all(
      ids.map((id) =>
        pcsApi
          .getLabPCs(id)
          .then((res) => [id, Array.isArray(res.data) ? res.data : []])
          .catch(() => [id, []])
      )
    )
    setPcsByLab(Object.fromEntries(results))
    setLoading(false)
  }, [labKey])

  useEffect(() => {
    refresh()
  }, [refresh])

  return { pcsByLab, loading, refresh }
}
