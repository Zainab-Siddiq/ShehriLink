from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..config import MAX_REOPENS
from ..enums import S, TRANSITIONS
from ..models import AgentActivityLog, Complaint, StatusHistory
from ..utils import utcnow


def get_complaint_or_404(db: Session, key) -> Complaint:
    """Accepts numeric id ('5') or reference number ('MC-0005')."""
    key = str(key).strip()
    if key.isdigit():
        c = db.get(Complaint, int(key))
    else:
        c = db.query(Complaint).filter(Complaint.reference_no == key.upper()).first()
    if not c:
        raise HTTPException(404, f"Complaint '{key}' not found")
    return c


def log_activity(db: Session, c: Complaint, agent_name: str, message: str,
                 step: Optional[str] = None, event_type: str = "info",
                 data: Optional[Dict[str, Any]] = None, cycle: Optional[int] = None) -> AgentActivityLog:
    row = AgentActivityLog(
        complaint_id=c.id, cycle=cycle or c.current_cycle, agent_name=agent_name,
        step=step, event_type=event_type, message=message, data=data,
    )
    db.add(row)
    db.flush()
    return row


def change_status(db: Session, c: Complaint, to_status: str, changed_by: str = "system",
                  reason: Optional[str] = None) -> Complaint:
    """The ONLY place a complaint's status changes. Validates, writes history + activity log."""
    allowed = TRANSITIONS.get(c.status, [])
    if to_status not in allowed:
        raise HTTPException(
            409, f"Invalid status transition '{c.status}' -> '{to_status}'. Allowed from '{c.status}': {allowed}")
    from_status = c.status
    now = utcnow()
    c.status = to_status
    c.updated_at = now
    if to_status == S.RESOLVED:
        c.resolved_at = now
    elif to_status == S.CLOSED:
        c.closed_at = now
    elif to_status == S.REOPENED:
        c.resolved_at = None
        c.closed_at = None
    db.add(StatusHistory(complaint_id=c.id, from_status=from_status, to_status=to_status,
                         cycle=c.current_cycle, changed_by=changed_by, reason=reason))
    log_activity(db, c, "system", f"Status changed: {from_status} -> {to_status}" + (f" ({reason})" if reason else ""),
                 step="status_change", event_type="status_change",
                 data={"from": from_status, "to": to_status, "changed_by": changed_by})
    db.flush()
    return c


def reopen_complaint(db: Session, c: Complaint, changed_by: str, reason: str) -> str:
    """verification_failed|closed -> reopened (new cycle). Escalates after MAX_REOPENS.
    Returns the next action for the agent: 'replan' or 'escalated'."""
    c.current_cycle += 1
    c.reopen_count += 1
    change_status(db, c, S.REOPENED, changed_by, reason)
    if c.reopen_count >= MAX_REOPENS:
        change_status(db, c, S.ESCALATED, "system",
                      f"Reopened {c.reopen_count} times (limit {MAX_REOPENS}); escalating to a human supervisor")
        return "escalated"
    return "replan"
