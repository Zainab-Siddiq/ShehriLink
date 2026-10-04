import type { ComplaintStatus, Priority } from './types'

export const AREAS: Record<string, string> = {
  'University Town': 'Zone A', 'Canal Town': 'Zone A', Tehkal: 'Zone A',
  Hayatabad: 'Zone B', 'Regi Model Town': 'Zone B', 'Industrial Estate': 'Zone B',
  Saddar: 'Zone C', Gulbahar: 'Zone C', 'Peshawar Cantt': 'Zone C',
  'Ring Road': 'Zone D', 'Warsak Road': 'Zone D', 'Charsadda Road': 'Zone D',
}
export const ZONES = ['Zone A', 'Zone B', 'Zone C', 'Zone D']

export const CATEGORIES = [
  'streetlight', 'road', 'water', 'drainage', 'garbage', 'sanitation', 'parks', 'sewerage', 'electricity', 'other',
]

export const DEPARTMENTS = [
  'Electrical Department', 'Roads Department', 'Water Department', 'Drainage Department',
  'Sanitation Department', 'Parks Department', 'Sewerage Department', 'General Services Department',
]

export const PRIORITIES: Priority[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
export const STATUSES: ComplaintStatus[] = [
  'RECEIVED', 'ASSIGNED', 'VERIFIED', 'VERIFICATION_FAILED', 'REPLANNING', 'CLOSED', 'ESCALATED',
]

export const STATUS_LABEL: Record<ComplaintStatus, string> = {
  RECEIVED: 'Received', ASSIGNED: 'Team assigned', VERIFIED: 'Verified',
  VERIFICATION_FAILED: 'Verification failed', REPLANNING: 'Replanning', CLOSED: 'Closed', ESCALATED: 'Escalated',
}

export const SCENARIOS = [
  { value: 'manual', label: 'Manual verification', hint: 'Stays open until an officer verifies it' },
  { value: 'success', label: 'Fixed first time', hint: 'Verification passes immediately' },
  { value: 'fail_once', label: 'Fails once, then fixed', hint: 'Replans and reassigns a new team' },
  { value: 'fail_twice', label: 'Fails twice, then fixed', hint: 'Two replans before it passes' },
  { value: 'always_fail', label: 'Never fixed', hint: 'Escalates to a human supervisor' },
]

export const label = (s: string | null | undefined) =>
  s ? s.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase()) : '—'
