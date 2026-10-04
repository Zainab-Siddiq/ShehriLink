from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..enums import MANAGED_STATUSES, S, TRANSITIONS
from ..models import (AgentResult, Assignment, Complaint, Department, StatusHistory, User,
                      Verification, Zone)
from ..schemas import (ComplaintCreate, ComplaintOut, ComplaintUpdate, ContextOut,
                       RelationIn, RelationOut, ReopenRequest, ReopenResponse, StatusChange,
                       StatusHistoryOut)
from ..services.lifecycle import change_status, get_complaint_or_404, log_activity, reopen_complaint
from ..services.similarity import find_similar
from ..services.workflow import (active_assignment, add_relation, cancel_active_assignments,
                                 list_relations, relation_view)

router = APIRouter(prefix="/complaints", tags=["Complaints"])


@router.post("", response_model=ComplaintOut, status_code=201)
def create_complaint(data: ComplaintCreate, db: Session = Depends(get_db)):
    if data.zone_id is not None and not db.get(Zone, data.zone_id):
        raise HTTPException(422, f"Zone {data.zone_id} does not exist")
    user = None
    if data.citizen_id is not None:
        user = db.get(User, data.citizen_id)
        if not user:
            raise HTTPException(422, f"User {data.citizen_id} does not exist")
    elif data.citizen_contact:
        user = db.query(User).filter(User.phone == data.citizen_contact).first()
        if not user:
            user = User(name=data.citizen_name or "Citizen", phone=data.citizen_contact, role="citizen")
            db.add(user)
            db.flush()
    c = Complaint(
        reference_no=f"TMP-{uuid4().hex[:12]}",
        citizen_id=user.id if user else None,
        citizen_name=data.citizen_name or (user.name if user else None),
        citizen_contact=data.citizen_contact,
        raw_text=data.raw_text, address_text=data.address_text,
        latitude=data.latitude, longitude=data.longitude,
        zone_id=data.zone_id, simulation_mode=data.simulation_mode,
        status=S.SUBMITTED, current_cycle=1, reopen_count=0,
    )
    db.add(c)
    db.flush()
    c.reference_no = f"MC-{c.id:04d}"
    db.add(StatusHistory(complaint_id=c.id, from_status=None, to_status=S.SUBMITTED, cycle=1,
                         changed_by="citizen", reason="Complaint submitted"))
    log_activity(db, c, "system", "Complaint received", step="intake", event_type="action")
    db.commit()
    db.refresh(c)
    return c


@router.get("", response_model=List[ComplaintOut])
def list_complaints(
    response: Response,
    status: Optional[str] = Query(None, description="One status or comma-separated list"),
    priority: Optional[str] = None,
    zone_id: Optional[int] = None,
    department_id: Optional[int] = None,
    category: Optional[str] = None,
    search: Optional[str] = Query(None, description="Matches complaint text, address, reference"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Complaint)
    if status:
        q = q.filter(Complaint.status.in_([s.strip() for s in status.split(",")]))
    if priority:
        q = q.filter(Complaint.priority == priority)
    if zone_id is not None:
        q = q.filter(Complaint.zone_id == zone_id)
    if department_id is not None:
        q = q.filter(Complaint.department_id == department_id)
    if category:
        q = q.filter(Complaint.category == category)
    if search:
        like = f"%{search}%"
        q = q.filter(Complaint.raw_text.ilike(like) | Complaint.address_text.ilike(like)
                     | Complaint.reference_no.ilike(like))
    response.headers["X-Total-Count"] = str(q.count())
    return q.order_by(Complaint.id.desc()).offset(offset).limit(limit).all()


@router.get("/{complaint_id}", response_model=ComplaintOut)
def get_complaint(complaint_id: str, db: Session = Depends(get_db)):
    return get_complaint_or_404(db, complaint_id)


@router.put("/{complaint_id}", response_model=ComplaintOut)
@router.patch("/{complaint_id}", response_model=ComplaintOut)
def update_complaint(complaint_id: str, data: ComplaintUpdate, db: Session = Depends(get_db)):
    c = get_complaint_or_404(db, complaint_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("zone_id") is not None and not db.get(Zone, changes["zone_id"]):
        raise HTTPException(422, f"Zone {changes['zone_id']} does not exist")
    if changes.get("department_id") is not None and not db.get(Department, changes["department_id"]):
        raise HTTPException(422, f"Department {changes['department_id']} does not exist")
    for k, v in changes.items():
        setattr(c, k, v)
    if changes:
        log_activity(db, c, "system", f"Complaint fields updated: {', '.join(changes)}", step="update",
                     event_type="info", data=changes)
    db.commit()
    db.refresh(c)
    return c


@router.get("/{complaint_id}/history", response_model=List[StatusHistoryOut])
def get_history(complaint_id: str, db: Session = Depends(get_db)):
    c = get_complaint_or_404(db, complaint_id)
    return db.query(StatusHistory).filter(StatusHistory.complaint_id == c.id).order_by(StatusHistory.id).all()


@router.get("/{complaint_id}/related", response_model=List[RelationOut])
def get_related(complaint_id: str, db: Session = Depends(get_db)):
    return list_relations(db, get_complaint_or_404(db, complaint_id))


@router.post("/{complaint_id}/related", response_model=RelationOut, status_code=201)
def create_related(complaint_id: str, data: RelationIn, db: Session = Depends(get_db)):
    c = get_complaint_or_404(db, complaint_id)
    r = add_relation(db, c, data)
    db.commit()
    return relation_view(db, c.id, r)


@router.get("/{complaint_id}/similar", response_model=List[ComplaintOut])
def get_similar(complaint_id: str, days: int = Query(30, ge=1, le=365), include_closed: bool = False,
                zone_id: Optional[int] = None, category: Optional[str] = None,
                db: Session = Depends(get_db)):
    """Candidate duplicates (same zone + category, recent). The agent decides what is a duplicate."""
    c = get_complaint_or_404(db, complaint_id)
    return find_similar(db, c, days=days, include_closed=include_closed, zone_id=zone_id, category=category)


@router.get("/{complaint_id}/context", response_model=ContextOut)
def get_context(complaint_id: str, db: Session = Depends(get_db)):
    """Everything about a complaint in one call (used by agents and the dashboard detail view)."""
    c = get_complaint_or_404(db, complaint_id)
    assignments = db.query(Assignment).filter(Assignment.complaint_id == c.id).order_by(Assignment.id).all()
    results = db.query(AgentResult).filter(AgentResult.complaint_id == c.id).order_by(AgentResult.id).all()
    latest = {r.stage: r for r in results}  # later rows overwrite earlier ones
    return {
        "complaint": c,
        "zone": db.get(Zone, c.zone_id) if c.zone_id else None,
        "department": db.get(Department, c.department_id) if c.department_id else None,
        "current_assignment": active_assignment(db, c),
        "assignments": assignments,
        "verifications": db.query(Verification).filter(Verification.complaint_id == c.id).order_by(Verification.id).all(),
        "agent_results": latest,
        "relations": list_relations(db, c),
        "allowed_next_statuses": TRANSITIONS.get(c.status, []),
    }


@router.patch("/{complaint_id}/status", response_model=ComplaintOut)
def patch_status(complaint_id: str, data: StatusChange, db: Session = Depends(get_db)):
    """Guarded manual transition. Only processing / duplicate / escalated can be set directly.
    Everything else must go through its dedicated endpoint (this protects the verification loop)."""
    c = get_complaint_or_404(db, complaint_id)
    if data.status in MANAGED_STATUSES:
        raise HTTPException(422, f"Status '{data.status}' cannot be set directly. Use: {MANAGED_STATUSES[data.status]}")
    change_status(db, c, data.status, data.changed_by, data.reason)
    cancel_active_assignments(db, c, f"complaint moved to '{data.status}'")
    db.commit()
    db.refresh(c)
    return c


@router.post("/{complaint_id}/reopen", response_model=ReopenResponse)
def reopen(complaint_id: str, data: ReopenRequest, db: Session = Depends(get_db)):
    """Reopen a closed complaint (citizen says it's still broken), or finish a stuck verification_failed."""
    c = get_complaint_or_404(db, complaint_id)
    if c.status not in (S.CLOSED, S.VERIFICATION_FAILED):
        raise HTTPException(409, f"Only 'closed' or 'verification_failed' complaints can be reopened (current: '{c.status}')")
    next_action = reopen_complaint(db, c, data.requested_by, data.reason)
    db.commit()
    db.refresh(c)
    return {"complaint": c, "next_action": next_action}
