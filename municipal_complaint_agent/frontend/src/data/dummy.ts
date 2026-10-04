/**
 * Dummy data for the admin side and for tracking demo IDs.
 * Deterministic (seeded) so the dashboard looks the same on every load.
 * Replace with real endpoints (GET /api/complaints, /api/stats) once the backend has them.
 */
import { AREAS } from '../lib/constants'
import type { Complaint, ComplaintStatus, HistoryEntry, Priority, StepStatus, Team } from '../lib/types'

function rng(seed: number) {
  return () => {
    seed = (seed * 1664525 + 1013904223) % 4294967296
    return seed / 4294967296
  }
}
const rand = rng(20261004)
function pick<T>(a: T[]): T {
  return a[Math.floor(rand() * a.length)]
}

interface Tpl {
  category: string
  subcategory: string
  dept: string
  code: string
  prio: Priority
  texts: string[]
}
const TEMPLATES: Tpl[] = [
  { category: 'streetlight', subcategory: 'streetlight_not_working', dept: 'Electrical Department', code: 'ELEC', prio: 'MEDIUM',
    texts: ['The streetlight in front of my house has not worked for three days.', 'Whole street is dark at night, lights are not turning on.'] },
  { category: 'road', subcategory: 'pothole', dept: 'Roads Department', code: 'ROAD', prio: 'MEDIUM',
    texts: ['Big pothole on the main road, bikes are slipping.', 'Road is broken after the rain and cars are getting damaged.'] },
  { category: 'water', subcategory: 'no_water_supply', dept: 'Water Department', code: 'WATR', prio: 'HIGH',
    texts: ['No water supply in our street since yesterday morning.', 'Water pipeline is leaking and wasting water.'] },
  { category: 'drainage', subcategory: 'blocked_drain', dept: 'Drainage Department', code: 'DRAN', prio: 'MEDIUM',
    texts: ['The drain is blocked and dirty water is on the road.', 'Rainwater is not draining, the street is flooded.'] },
  { category: 'garbage', subcategory: 'garbage_not_collected', dept: 'Sanitation Department', code: 'SANI', prio: 'LOW',
    texts: ['Garbage has not been collected for a week and it smells.', 'Waste piled up near the market corner.'] },
  { category: 'sewerage', subcategory: 'open_manhole', dept: 'Sewerage Department', code: 'SEWR', prio: 'CRITICAL',
    texts: ['Open manhole near the school gate, children could fall in.', 'Sewage is overflowing into the street.'] },
  { category: 'parks', subcategory: 'park_maintenance', dept: 'Parks Department', code: 'PARK', prio: 'LOW',
    texts: ['Park benches are broken and the grass is overgrown.', 'The park lights and swings need repair.'] },
]

const areaNames = Object.keys(AREAS)
const BASE = Date.UTC(2026, 9, 4, 12)
const iso = (ms: number) => new Date(ms).toISOString().slice(0, 19) + '+00:00'

function entry(agent: string, message: string, result: string, status: StepStatus, ts: string): HistoryEntry {
  return { agent, action: message, result, status, message, timestamp: ts, details: {} }
}

function build(i: number, status: ComplaintStatus): Complaint {
  const t = pick(TEMPLATES)
  const area = pick(areaNames)
  const zone = AREAS[area]
  const letter = zone.slice(-1) // "Zone B" -> "B"
  const short = t.dept.split(' ')[0]
  const teamId = `${t.code}-${letter}`
  const teamName = `${short} Team ${letter}`
  const rrId = `${t.code}-RR`
  const rrName = `${short} Rapid Response Team`

  const createdMs = BASE - Math.floor(rand() * 13) * 864e5 - Math.floor(rand() * 20) * 36e5
  const at = (min: number) => iso(createdMs + min * 60000)
  const priority: Priority = rand() < 0.2 ? pick<Priority>(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']) : t.prio

  const recovered = status === 'CLOSED' && rand() < 0.35 // closed after one failed attempt
  const retries = status === 'ESCALATED' ? 3 : recovered || status === 'REPLANNING' ? 1 : 0
  const finalTeamId = recovered ? rrId : teamId
  const finalTeamName = recovered ? rrName : teamName

  const h: HistoryEntry[] = [
    entry('Classification Agent', 'Classification completed', t.category, 'success', at(0)),
    entry('Location Agent', 'Location identified', `${area} (${zone})`, 'success', at(1)),
    entry('History/Duplicate Agent', 'Duplicate check completed', 'no duplicate', 'success', at(1)),
    entry('Priority Agent', 'Priority determined', priority, 'success', at(2)),
    entry('Department Agent', 'Department selected', t.dept, 'success', at(2)),
    entry('Assignment Agent', 'Team assigned', teamId, 'success', at(3)),
  ]
  if (status !== 'RECEIVED') h.push(entry(teamName, 'Resolution attempted', '', 'success', at(60)))

  if (status === 'CLOSED' && !recovered) {
    h.push(entry('Resolution Verification Agent', 'Verification passed', 'verified', 'success', at(300)))
    h.push(entry('Closure Agent', 'Complaint closed', 'CLOSED', 'success', at(301)))
  } else if (recovered) {
    h.push(entry('Resolution Verification Agent', 'Verification failed', 'failed', 'failed', at(300)))
    h.push(entry('Replanning Agent', 'Replanning', 'retry 1 of 3', 'replanning', at(301)))
    h.push(entry('Assignment Agent', 'New team assigned', rrId, 'success', at(302)))
    h.push(entry(rrName, 'Resolution attempted', '', 'success', at(420)))
    h.push(entry('Resolution Verification Agent', 'Verification passed', 'verified', 'success', at(600)))
    h.push(entry('Closure Agent', 'Complaint closed', 'CLOSED', 'success', at(601)))
  } else if (status === 'ESCALATED') {
    const nextTeams = [rrId, `${t.code}-${letter === 'A' ? 'B' : 'A'}`]
    for (let r = 1; r <= 3; r++) {
      h.push(entry('Resolution Verification Agent', 'Verification failed', 'failed', 'failed', at(200 * r)))
      if (r < 3) {
        h.push(entry('Replanning Agent', 'Replanning', `retry ${r} of 3`, 'replanning', at(200 * r + 1)))
        h.push(entry('Assignment Agent', 'New team assigned', nextTeams[r - 1], 'success', at(200 * r + 2)))
      }
    }
    h.push(entry('Escalation Agent', 'Escalated to supervisor', 'ESCALATED', 'escalated', at(700)))
  } else if (status === 'REPLANNING') {
    h.push(entry('Resolution Verification Agent', 'Verification failed', 'failed', 'failed', at(300)))
    h.push(entry('Replanning Agent', 'Replanning', 'retry 1 of 3', 'replanning', at(301)))
  }

  return {
    complaint_id: `C-${2001 + i}`,
    description: pick(t.texts),
    location: area,
    category: t.category,
    subcategory: t.subcategory,
    classification_confidence: +(0.8 + rand() * 0.19).toFixed(2),
    area,
    zone,
    location_text: area,
    location_confidence: +(0.85 + rand() * 0.14).toFixed(2),
    duplicate: false,
    related_complaint_id: null,
    duplicate_reason: null,
    priority,
    priority_reason: `Rule engine baseline for ${t.category} in ${area}.`,
    department: t.dept,
    department_reason: `Category "${t.category}" is handled by the ${t.dept}.`,
    assigned_team: status === 'RECEIVED' ? null : finalTeamId,
    assigned_team_name: status === 'RECEIVED' ? null : finalTeamName,
    assignment_reason: 'Available team in the same zone with the lowest workload.',
    failed_teams: retries ? [teamId] : [],
    verification_scenario: 'success',
    team_report: status === 'RECEIVED' ? null : 'Team reports the issue has been fixed on site.',
    citizen_feedback:
      status === 'CLOSED' ? 'Yes, the problem is solved. Thank you.' : status === 'ESCALATED' ? 'No, the problem is still there.' : null,
    verification_status: status === 'CLOSED' ? 'verified' : retries ? 'failed' : 'pending',
    verification_reason: status === 'CLOSED' ? 'The reported issue is confirmed resolved.' : null,
    resolved: status === 'CLOSED',
    retry_count: retries,
    max_retries: 3,
    escalation_reason: status === 'ESCALATED' ? 'Verification failed 3 times. A supervisor must take over.' : null,
    status,
    history: h,
    errors: [],
    submitted_at: iso(createdMs),
  }
}

const MIX: ComplaintStatus[] = [
  ...Array<ComplaintStatus>(22).fill('CLOSED'),
  ...Array<ComplaintStatus>(7).fill('ASSIGNED'),
  ...Array<ComplaintStatus>(3).fill('REPLANNING'),
  ...Array<ComplaintStatus>(5).fill('ESCALATED'),
  ...Array<ComplaintStatus>(3).fill('RECEIVED'),
]
export const DUMMY_COMPLAINTS: Complaint[] = MIX.map((s, i) => build(i, s)).sort((a, b) =>
  (b.submitted_at ?? '').localeCompare(a.submitted_at ?? ''),
)

export const findDummy = (id: string) =>
  DUMMY_COMPLAINTS.find((c) => c.complaint_id.toLowerCase() === id.trim().toLowerCase())

export const DUMMY_TEAMS: Team[] = (() => {
  const depts: [string, string, string][] = [
    ['ELEC', 'Electrical', 'Electrical Department'], ['ROAD', 'Roads', 'Roads Department'],
    ['WATR', 'Water', 'Water Department'], ['DRAN', 'Drainage', 'Drainage Department'],
    ['SANI', 'Sanitation', 'Sanitation Department'], ['SEWR', 'Sewerage', 'Sewerage Department'],
  ]
  const out: Team[] = []
  for (const [code, short, full] of depts) {
    'ABCD'.split('').forEach((l) =>
      out.push({
        team_id: `${code}-${l}`, name: `${short} Team ${l}`, department: full, zone: `Zone ${l}`,
        available: rand() > 0.12, active_tasks: Math.floor(rand() * 5), capacity: 5,
      }),
    )
    out.push({
      team_id: `${code}-RR`, name: `${short} Rapid Response Team`, department: full, zone: 'All zones',
      available: true, active_tasks: Math.floor(rand() * 3), capacity: 4,
    })
  }
  return out
})()

export function dailyCounts(list: Complaint[] = DUMMY_COMPLAINTS, days = 14) {
  const latest = Math.max(BASE, ...list.map((c) => (c.submitted_at ? new Date(c.submitted_at).getTime() : 0)))
  const end = new Date(latest)
  const out: { date: Date; received: number; closed: number }[] = []
  for (let d = days - 1; d >= 0; d--) {
    const date = new Date(Date.UTC(end.getUTCFullYear(), end.getUTCMonth(), end.getUTCDate()) - d * 864e5)
    const key = date.toISOString().slice(0, 10)
    const same = list.filter((c) => c.submitted_at?.startsWith(key))
    out.push({ date, received: same.length, closed: same.filter((c) => c.status === 'CLOSED').length })
  }
  return out
}
