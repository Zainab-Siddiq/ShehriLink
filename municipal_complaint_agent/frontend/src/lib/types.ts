export type Priority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type ComplaintStatus =
  | 'RECEIVED' | 'ASSIGNED' | 'VERIFIED' | 'VERIFICATION_FAILED' | 'REPLANNING' | 'CLOSED' | 'ESCALATED'
export type StepStatus = 'success' | 'failed' | 'replanning' | 'escalated' | 'info'

export interface HistoryEntry {
  agent: string
  action: string
  result: string
  status: StepStatus
  message: string
  timestamp: string
  details: Record<string, unknown>
}

/** Mirrors the backend ComplaintState (app/graph/state.py). */
export interface Complaint {
  complaint_id: string
  description: string
  location: string | null
  category: string | null
  subcategory: string | null
  classification_confidence: number | null
  area: string | null
  zone: string | null
  location_text: string | null
  location_confidence: number | null
  duplicate: boolean
  related_complaint_id: string | null
  duplicate_reason: string | null
  priority: Priority | null
  priority_reason: string | null
  department: string | null
  department_reason: string | null
  assigned_team: string | null
  assigned_team_name: string | null
  assignment_reason: string | null
  failed_teams: string[]
  verification_scenario: string
  team_report: string | null
  citizen_feedback: string | null
  verification_status: 'pending' | 'verified' | 'failed'
  verification_reason: string | null
  resolved: boolean
  retry_count: number
  max_retries: number
  escalation_reason: string | null
  status: ComplaintStatus
  history: HistoryEntry[]
  errors: string[]
  /** frontend-only, used by the dummy admin data */
  submitted_at?: string
}

export interface Team {
  team_id: string
  name: string
  department: string
  zone: string
  available: boolean
  active_tasks: number
  capacity: number
}
