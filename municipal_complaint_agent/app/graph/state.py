"""
Shared LangGraph state.

Every agent receives this object and returns a *partial update* (a dict).
`history` and `errors` use the `operator.add` reducer, so each agent simply
returns a list with its new entries and LangGraph appends them.
"""
import operator
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.schemas import HistoryEntry

# --- status values --------------------------------------------------------
RECEIVED = "RECEIVED"
ASSIGNED = "ASSIGNED"
VERIFIED = "VERIFIED"
VERIFICATION_FAILED = "VERIFICATION_FAILED"
REPLANNING = "REPLANNING"
CLOSED = "CLOSED"        # final: resolved and verified
ESCALATED = "ESCALATED"  # final: needs a human supervisor


class ComplaintState(BaseModel):
    # ---- input -----------------------------------------------------------
    complaint_id: str
    description: str
    location: Optional[str] = None            # raw location given by the citizen

    # ---- classification agent -------------------------------------------
    category: Optional[str] = None
    subcategory: Optional[str] = None
    classification_confidence: Optional[float] = None

    # ---- location agent --------------------------------------------------
    area: Optional[str] = None
    zone: Optional[str] = None
    location_text: Optional[str] = None
    location_confidence: Optional[float] = None

    # ---- history / duplicate agent ---------------------------------------
    duplicate: bool = False
    related_complaint_id: Optional[str] = None
    duplicate_reason: Optional[str] = None

    # ---- priority agent --------------------------------------------------
    priority: Optional[str] = None
    priority_reason: Optional[str] = None

    # ---- department agent ------------------------------------------------
    department: Optional[str] = None
    department_reason: Optional[str] = None

    # ---- assignment agent ------------------------------------------------
    assigned_team: Optional[str] = None       # team_id, e.g. "ELEC-B"
    assigned_team_name: Optional[str] = None
    assignment_reason: Optional[str] = None
    failed_teams: List[str] = Field(default_factory=list)  # teams that failed verification

    # ---- verification agent ----------------------------------------------
    verification_scenario: str = "success"    # demo control (mock verification)
    team_report: Optional[str] = None
    citizen_feedback: Optional[str] = None
    verification_status: str = "pending"      # pending | verified | failed
    verification_reason: Optional[str] = None
    resolved: bool = False

    # ---- replan loop -----------------------------------------------------
    retry_count: int = 0                      # number of FAILED verifications so far
    max_retries: int = 3                      # escalate when retry_count reaches this
    escalation_reason: Optional[str] = None

    # ---- overall ---------------------------------------------------------
    status: str = RECEIVED
    history: Annotated[List[HistoryEntry], operator.add] = Field(default_factory=list)
    errors: Annotated[List[str], operator.add] = Field(default_factory=list)


def log(
    agent: str,
    action: str,
    result: str,
    status: str = "success",
    message: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> HistoryEntry:
    """Create one timeline entry (the agent returns it inside `history=[...]`)."""
    return HistoryEntry(
        agent=agent,
        action=action,
        result=str(result),
        status=status,  # type: ignore[arg-type]
        message=message or action,
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        details=details or {},
    )
