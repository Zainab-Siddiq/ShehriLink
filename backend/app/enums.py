from typing import Literal


class S:
    """Complaint statuses."""
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    VERIFICATION_PENDING = "verification_pending"
    VERIFIED = "verified"
    CLOSED = "closed"
    VERIFICATION_FAILED = "verification_failed"
    REOPENED = "reopened"
    DUPLICATE = "duplicate"
    ESCALATED = "escalated"


class A:
    """Assignment statuses."""
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


ALL_STATUSES = [
    S.SUBMITTED, S.PROCESSING, S.ASSIGNED, S.IN_PROGRESS, S.RESOLVED,
    S.VERIFICATION_PENDING, S.VERIFIED, S.CLOSED, S.VERIFICATION_FAILED,
    S.REOPENED, S.DUPLICATE, S.ESCALATED,
]
ACTIVE_ASSIGNMENT = [A.ASSIGNED, A.IN_PROGRESS]
PRIORITIES = ["low", "medium", "high", "critical"]

# Allowed transitions. Anything else -> HTTP 409.
TRANSITIONS = {
    S.SUBMITTED: [S.PROCESSING, S.DUPLICATE],
    S.PROCESSING: [S.ASSIGNED, S.DUPLICATE, S.ESCALATED],
    S.ASSIGNED: [S.IN_PROGRESS, S.PROCESSING, S.ESCALATED],
    S.IN_PROGRESS: [S.RESOLVED, S.ASSIGNED, S.PROCESSING, S.ESCALATED],
    S.RESOLVED: [S.VERIFICATION_PENDING],
    S.VERIFICATION_PENDING: [S.VERIFIED, S.VERIFICATION_FAILED],
    S.VERIFIED: [S.CLOSED],
    S.VERIFICATION_FAILED: [S.REOPENED],
    S.REOPENED: [S.PROCESSING, S.ASSIGNED, S.IN_PROGRESS, S.ESCALATED],
    S.CLOSED: [S.REOPENED],
    S.DUPLICATE: [S.CLOSED],
    S.ESCALATED: [S.PROCESSING, S.ASSIGNED],
}

# Statuses that can ONLY be reached through a dedicated endpoint (guard rails).
MANAGED_STATUSES = {
    S.ASSIGNED: "POST /complaints/{id}/assignments",
    S.IN_PROGRESS: "PATCH /assignments/{id} with status=in_progress",
    S.RESOLVED: "PATCH /assignments/{id} with status=completed",
    S.VERIFICATION_PENDING: "PATCH /assignments/{id} with status=completed",
    S.VERIFIED: "POST /complaints/{id}/verifications with result=passed",
    S.CLOSED: "POST /complaints/{id}/verifications with result=passed",
    S.VERIFICATION_FAILED: "POST /complaints/{id}/verifications with result=failed",
    S.REOPENED: "POST /complaints/{id}/reopen",
}

STATUS_META = {
    S.SUBMITTED: ("Submitted", "#6b7280"),
    S.PROCESSING: ("Processing", "#3b82f6"),
    S.ASSIGNED: ("Assigned", "#8b5cf6"),
    S.IN_PROGRESS: ("In Progress", "#f59e0b"),
    S.RESOLVED: ("Resolved", "#10b981"),
    S.VERIFICATION_PENDING: ("Verification Pending", "#06b6d4"),
    S.VERIFIED: ("Verified", "#22c55e"),
    S.CLOSED: ("Closed", "#16a34a"),
    S.VERIFICATION_FAILED: ("Verification Failed", "#ef4444"),
    S.REOPENED: ("Reopened", "#f97316"),
    S.DUPLICATE: ("Duplicate", "#9ca3af"),
    S.ESCALATED: ("Escalated", "#dc2626"),
}

StatusLit = Literal[
    "submitted", "processing", "assigned", "in_progress", "resolved",
    "verification_pending", "verified", "closed", "verification_failed",
    "reopened", "duplicate", "escalated",
]
PriorityLit = Literal["low", "medium", "high", "critical"]
AssignmentStatusLit = Literal["assigned", "in_progress", "completed", "failed", "cancelled"]
VerificationResultLit = Literal["passed", "failed"]
VerificationMethodLit = Literal["citizen_followup", "technician_report", "sensor", "agent_check", "human"]
RelationTypeLit = Literal["duplicate", "related", "recurring"]
EventTypeLit = Literal["info", "decision", "action", "status_change", "warning", "error"]
AssignedByLit = Literal["agent", "human"]
