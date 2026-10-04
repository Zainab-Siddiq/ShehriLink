from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..enums import ALL_STATUSES, PRIORITIES, STATUS_META, TRANSITIONS, S
from ..models import AgentActivityLog, Complaint, Department, Verification
from ..schemas import ActivityOut

router = APIRouter(tags=["Dashboard"])


@router.get("/dashboard/stats")
def dashboard_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(Complaint.id)).scalar() or 0
    by_status = {s: n for s, n in db.query(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status).all()}
    by_priority = {(p or "unset"): n for p, n in
                   db.query(Complaint.priority, func.count(Complaint.id)).group_by(Complaint.priority).all()}
    by_department = {name: n for name, n in
                     db.query(Department.name, func.count(Complaint.id))
                     .join(Complaint, Complaint.department_id == Department.id).group_by(Department.name).all()}
    ver = {r: n for r, n in db.query(Verification.result, func.count(Verification.id)).group_by(Verification.result).all()}
    reopened = db.query(func.count(Complaint.id)).filter(Complaint.reopen_count > 0).scalar() or 0
    closed = by_status.get(S.CLOSED, 0)
    finished = closed + by_status.get(S.DUPLICATE, 0)
    return {
        "total_complaints": total,
        "open_complaints": total - finished,
        "closed_complaints": closed,
        "by_status": by_status,
        "by_priority": by_priority,
        "by_department": by_department,
        "verification": {"passed": ver.get("passed", 0), "failed": ver.get("failed", 0)},
        "reopened_complaints": reopened,
        "reopen_rate": round(reopened / total, 3) if total else 0.0,
        "awaiting_verification": by_status.get(S.VERIFICATION_PENDING, 0),
        "escalated": by_status.get(S.ESCALATED, 0),
    }


@router.get("/activity/recent", response_model=List[ActivityOut])
def recent_activity(limit: int = Query(30, ge=1, le=200), db: Session = Depends(get_db)):
    rows = (db.query(AgentActivityLog, Complaint.reference_no)
            .join(Complaint, Complaint.id == AgentActivityLog.complaint_id)
            .order_by(AgentActivityLog.id.desc()).limit(limit).all())
    return [{
        "id": r.id, "complaint_id": r.complaint_id, "cycle": r.cycle, "agent_name": r.agent_name,
        "step": r.step, "event_type": r.event_type, "message": r.message, "data": r.data,
        "created_at": r.created_at, "reference_no": ref,
    } for r, ref in rows]


@router.get("/meta/enums")
def meta_enums(db: Session = Depends(get_db)):
    cats = sorted({c for d in db.query(Department).all() for c in (d.categories or [])})
    return {
        "statuses": [{"value": s, "label": STATUS_META[s][0], "color": STATUS_META[s][1]} for s in ALL_STATUSES],
        "priorities": PRIORITIES,
        "categories": cats,
        "relation_types": ["duplicate", "related", "recurring"],
        "assignment_statuses": ["assigned", "in_progress", "completed", "failed", "cancelled"],
        "verification_results": ["passed", "failed"],
        "transitions": TRANSITIONS,
    }
