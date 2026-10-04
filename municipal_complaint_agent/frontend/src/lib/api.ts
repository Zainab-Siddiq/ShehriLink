import type { Complaint } from './types'
import { findDummy } from '../data/dummy'

export interface SubmitPayload {
  complaint_id: string
  description: string
  location?: string
  verification_scenario?: string
}

const OFFLINE = 'Cannot reach the server. Start the backend with "python run.py" and try again.'

async function parse<T>(res: Response): Promise<T> {
  // the dev proxy answers 502/503/504 when nothing is listening on the backend port
  if ([502, 503, 504].includes(res.status)) throw new Error(OFFLINE)
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join(', ')
    } catch { /* body was not JSON */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

/** Runs the full agent workflow on the backend. */
export async function submitComplaint(payload: SubmitPayload): Promise<Complaint> {
  let res: Response
  try {
    res = await fetch('/api/complaints/process', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    })
  } catch {
    throw new Error(OFFLINE)
  }
  return parse<Complaint>(res)
}

/** Officer's manual verification: passed closes the complaint, not passed reassigns it (or escalates). */
export async function verifyComplaint(id: string, passed: boolean, note?: string): Promise<Complaint> {
  let res: Response
  try {
    res = await fetch(`/api/complaints/${encodeURIComponent(id)}/verify`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ passed, note: note?.trim() || undefined }),
    })
  } catch {
    throw new Error(OFFLINE)
  }
  return parse<Complaint>(res)
}

/** Backend first (complaints processed this session), then the demo data set. */
export async function getComplaint(id: string): Promise<Complaint | null> {
  try {
    const res = await fetch(`/api/complaints/${encodeURIComponent(id)}`)
    if (res.ok) return (await res.json()) as Complaint
  } catch { /* backend offline: fall through to demo data */ }
  return findDummy(id) ?? null
}

/** Complaints processed by the backend since it started (newest first). Empty if the backend is offline. */
export async function listComplaints(): Promise<Complaint[]> {
  try {
    const res = await fetch('/api/complaints')
    return res.ok ? ((await res.json()) as Complaint[]) : []
  } catch {
    return []
  }
}

export async function getHealth(): Promise<{ llm_provider: string; llm_enabled: boolean } | null> {
  try {
    const res = await fetch('/api/health')
    return res.ok ? await res.json() : null
  } catch { return null }
}

export function newComplaintId(): string {
  return `C-${Math.floor(1000 + Math.random() * 9000)}`
}
