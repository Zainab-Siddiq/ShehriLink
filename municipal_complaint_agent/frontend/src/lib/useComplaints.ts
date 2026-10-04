import { useCallback, useEffect, useMemo, useState } from 'react'
import { DUMMY_COMPLAINTS } from '../data/dummy'
import { listComplaints } from './api'
import type { Complaint } from './types'

/**
 * Admin data source: complaints really processed by the backend (newest first)
 * followed by the sample data set. A live complaint replaces a sample one with the same id.
 */
export function useComplaints() {
  const [live, setLive] = useState<Complaint[]>([])
  const [loading, setLoading] = useState(true)

  const [nonce, setNonce] = useState(0)
  const reload = useCallback(() => setNonce((n) => n + 1), [])

  useEffect(() => {
    let alive = true
    listComplaints().then((rows) => {
      if (!alive) return
      // the backend does not stamp a submit time, so use the first timeline entry
      setLive(rows.map((c) => ({ ...c, submitted_at: c.submitted_at ?? c.history[0]?.timestamp })))
      setLoading(false)
    })
    return () => { alive = false }
  }, [nonce])

  const complaints = useMemo(() => {
    const ids = new Set(live.map((c) => c.complaint_id))
    return [...live, ...DUMMY_COMPLAINTS.filter((c) => !ids.has(c.complaint_id))]
  }, [live])

  return { complaints, liveCount: live.length, liveIds: new Set(live.map((c) => c.complaint_id)), loading, reload }
}
