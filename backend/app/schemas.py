from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    AssignedByLit, AssignmentStatusLit, EventTypeLit, PriorityLit, RelationTypeLit,
    StatusLit, VerificationMethodLit, VerificationResultLit,
)


class In(BaseModel):
    pass


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Reference data ----------
class UserOut(Out):
    id: int
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    role: str
    created_at: datetime


class DepartmentOut(Out):
    id: int
    name: str
    code: str
    description: Optional[str] = None
    categories: List[str] = []


class ZoneOut(Out):
    id: int
    name: str
    code: str
    description: Optional[str] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None


class TeamOut(Out):
    id: int
    name: str
    department_id: int
    zone_id: int
    is_active: bool
    department_name: Optional[str] = None
    zone_name: Optional[str] = None
    technician_count: int = 0
    available_technicians: int = 0
    active_assignments: int = 0


class TechnicianOut(Out):
    id: int
    name: str
    phone: Optional[str] = None
    team_id: int
    team_name: Optional[str] = None
    department_id: Optional[int] = None
    zone_id: Optional[int] = None
    skills: Optional[str] = None
    is_available: bool
    active_assignments: int = 0


# ---------- Complaints ----------
class ComplaintCreate(In):
    citizen_name: Optional[str] = Field(None, max_length=120)
    citizen_contact: Optional[str] = Field(None, max_length=60)
    citizen_id: Optional[int] = None
    raw_text: str = Field(..., min_length=5, max_length=2000)
    address_text: Optional[str] = Field(None, max_length=255)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    zone_id: Optional[int] = None
    simulation_mode: Optional[str] = Field(None, max_length=40)


class ComplaintUpdate(In):
    """Fields editable via PUT/PATCH. Status is NOT editable here (use /status)."""
    category: Optional[str] = None
    subcategory: Optional[str] = None
    priority: Optional[PriorityLit] = None
    zone_id: Optional[int] = None
    department_id: Optional[int] = None
    address_text: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    simulation_mode: Optional[str] = None


class ComplaintOut(Out):
    id: int
    reference_no: str
    citizen_id: Optional[int] = None
    citizen_name: Optional[str] = None
    citizen_contact: Optional[str] = None
    raw_text: str
    address_text: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    priority: Optional[str] = None
    status: str
    zone_id: Optional[int] = None
    department_id: Optional[int] = None
    current_cycle: int
    reopen_count: int
    duplicate_of_id: Optional[int] = None
    simulation_mode: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None


class StatusChange(In):
    status: StatusLit
    changed_by: str = "human"
    reason: Optional[str] = None


class ReopenRequest(In):
    reason: str = Field(..., min_length=3)
    requested_by: str = "citizen"


class ReopenResponse(Out):
    complaint: ComplaintOut
    next_action: Literal["replan", "escalated"]


class StatusHistoryOut(Out):
    id: int
    complaint_id: int
    from_status: Optional[str] = None
    to_status: str
    cycle: int
    changed_by: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime


# ---------- Assignments ----------
class AssignmentCreate(In):
    team_id: int
    technician_id: Optional[int] = None
    assigned_by: AssignedByLit = "agent"
    agent_name: Optional[str] = None
    reason: Optional[str] = None


class AssignmentUpdate(In):
    status: Optional[AssignmentStatusLit] = None
    resolution_notes: Optional[str] = None
    resolution_photo_url: Optional[str] = Field(None, max_length=500)


class AssignmentOut(Out):
    id: int
    complaint_id: int
    cycle: int
    team_id: int
    team_name: Optional[str] = None
    technician_id: Optional[int] = None
    technician_name: Optional[str] = None
    department_id: int
    status: str
    assigned_by: str
    reason: Optional[str] = None
    previous_assignment_id: Optional[int] = None
    assigned_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    resolution_photo_url: Optional[str] = None


# ---------- Verification ----------
class VerificationCreate(In):
    result: VerificationResultLit
    method: VerificationMethodLit = "citizen_followup"
    assignment_id: Optional[int] = None
    confidence: float = Field(1.0, ge=0, le=1)
    evidence: Optional[str] = None
    failure_reason: Optional[str] = None
    verified_by: str = "verifier_agent"


class VerificationOut(Out):
    id: int
    complaint_id: int
    assignment_id: Optional[int] = None
    cycle: int
    attempt_number: int
    method: str
    result: str
    confidence: Optional[float] = None
    evidence: Optional[str] = None
    failure_reason: Optional[str] = None
    verified_by: Optional[str] = None
    created_at: datetime


class VerificationResponse(Out):
    verification: VerificationOut
    complaint: ComplaintOut
    next_action: Literal["none", "replan", "escalated"]


# ---------- Related / duplicates ----------
class RelationIn(In):
    related_complaint_id: int
    relation_type: RelationTypeLit = "related"
    similarity_score: Optional[float] = Field(None, ge=0, le=1)
    reason: Optional[str] = None
    detected_by: str = "agent"


class RelationOut(Out):
    id: int
    complaint_id: int
    related_complaint_id: int
    relation_type: str
    similarity_score: Optional[float] = None
    reason: Optional[str] = None
    detected_by: Optional[str] = None
    created_at: datetime
    related_reference_no: Optional[str] = None
    related_status: Optional[str] = None
    related_raw_text: Optional[str] = None


# ---------- Agent activity / results ----------
class ActivityCreate(In):
    complaint_id: int
    agent_name: str = Field(..., min_length=1, max_length=80)
    message: str = Field(..., min_length=1)
    step: Optional[str] = None
    event_type: EventTypeLit = "info"
    data: Optional[Dict[str, Any]] = None
    cycle: Optional[int] = Field(None, ge=1)


class ActivityOut(Out):
    id: int
    complaint_id: int
    cycle: int
    agent_name: str
    step: Optional[str] = None
    event_type: str
    message: str
    data: Optional[Dict[str, Any]] = None
    created_at: datetime
    reference_no: Optional[str] = None


class AgentResultOut(Out):
    id: int
    complaint_id: int
    cycle: int
    stage: str
    agent_name: Optional[str] = None
    summary: Optional[str] = None
    confidence: Optional[float] = None
    payload: Optional[Dict[str, Any]] = None
    created_at: datetime


class UnderstandingIn(In):
    agent_name: str = "understanding_agent"
    category: str = Field(..., min_length=1)
    subcategory: Optional[str] = None
    extracted: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0, le=1)


class InvestigationIn(In):
    agent_name: str = "investigator"
    zone_id: Optional[int] = None
    relations: List[RelationIn] = Field(default_factory=list)
    is_duplicate: bool = False
    duplicate_of_id: Optional[int] = None
    findings: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0, le=1)


class DecisionIn(In):
    agent_name: str = "decision_agent"
    priority: PriorityLit
    department_id: int
    rationale: Optional[str] = None
    is_replan: bool = False
    confidence: Optional[float] = Field(None, ge=0, le=1)


# ---------- Context (one-call read for agents / dashboard detail) ----------
class ContextOut(Out):
    complaint: ComplaintOut
    zone: Optional[ZoneOut] = None
    department: Optional[DepartmentOut] = None
    current_assignment: Optional[AssignmentOut] = None
    assignments: List[AssignmentOut]
    verifications: List[VerificationOut]
    agent_results: Dict[str, AgentResultOut]
    relations: List[RelationOut]
    allowed_next_statuses: List[str]
