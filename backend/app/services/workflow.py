from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..enums import ACTIVE_ASSIGNMENT, A, S
from ..models import Assignment, Complaint, ComplaintRelation, Team, Technician, Verification
from ..schemas import AssignmentCreate, AssignmentUpdate, RelationIn, VerificationCreate
from ..utils import utcnow
from .lifecycle import change_status, log_activity, reopen_complaint


# ---------------- Relations ----------------
def add_relation(db: Session, c: Complaint, rel: RelationIn) -> ComplaintRelation:
    other = db.get(Complaint, rel.related_complaint_id)
    if not other:
        raise HTTPException(422, f"Related complaint {rel.related_complaint_id} does not exist")
    if other.id == c.id:
        raise HTTPException(422, "A complaint cannot be related to itself")
    existing = db.query(ComplaintRelation).filter(
        ComplaintRelation.complaint_id == c.id,
        ComplaintRelation.related_complaint_id == other.id,
        ComplaintRelation.relation_type == rel.relation_type).first()
    if existing:
        existing.similarity_score = rel.similarity_score
        existing.reason = rel.reason
        return existing
    r = ComplaintRelation(complaint_id=c.id, related_complaint_id=other.id,
                          relation_type=rel.relation_type, similarity_score=rel.similarity_score,
                          reason=rel.reason, detected_by=rel.detected_by)
    db.add(r)
    db.flush()
    log_activity(db, c, rel.detected_by, f"Linked to {other.reference_no} as {rel.relation_type}"
                 + (f": {rel.reason}" if rel.reason else ""), step="relation", event_type="info",
                 data={"related_complaint_id": other.id, "relation_type": rel.relation_type,
                       "similarity_score": rel.similarity_score})
    return r


def relation_view(db: Session, c_id: int, r: ComplaintRelation) -> dict:
    other_id = r.related_complaint_id if r.complaint_id == c_id else r.complaint_id
    other = db.get(Complaint, other_id)
    return {
        "id": r.id, "complaint_id": c_id, "related_complaint_id": other_id,
        "relation_type": r.relation_type, "similarity_score": r.similarity_score,
        "reason": r.reason, "detected_by": r.detected_by, "created_at": r.created_at,
        "related_reference_no": other.reference_no if other else None,
        "related_status": other.status if other else None,
        "related_raw_text": other.raw_text if other else None,
    }


def list_relations(db: Session, c: Complaint) -> List[dict]:
    rows = (db.query(ComplaintRelation)
            .filter((ComplaintRelation.complaint_id == c.id) | (ComplaintRelation.related_complaint_id == c.id))
            .order_by(ComplaintRelation.id).all())
    return [relation_view(db, c.id, r) for r in rows]


# ---------------- Assignments ----------------
def active_assignment(db: Session, c: Complaint) -> Optional[Assignment]:
    return (db.query(Assignment)
            .filter(Assignment.complaint_id == c.id, Assignment.status.in_(ACTIVE_ASSIGNMENT))
            .order_by(Assignment.id.desc()).first())


def cancel_active_assignments(db: Session, c: Complaint, reason: str) -> None:
    rows = db.query(Assignment).filter(Assignment.complaint_id == c.id,
                                       Assignment.status.in_(ACTIVE_ASSIGNMENT)).all()
    for a in rows:
        a.status = A.CANCELLED
        a.resolution_notes = ((a.resolution_notes + " | ") if a.resolution_notes else "") + f"Cancelled: {reason}"
        log_activity(db, c, "system", f"Assignment #{a.id} cancelled: {reason}", step="assignment", event_type="action")


def create_assignment(db: Session, c: Complaint, data: AssignmentCreate) -> Assignment:
    if c.status == S.SUBMITTED:  # forgiving: pipeline skipped 'processing'
        change_status(db, c, S.PROCESSING, data.agent_name or data.assigned_by, "Auto-moved to processing before assignment")
    if c.status not in (S.PROCESSING, S.REOPENED, S.ASSIGNED, S.IN_PROGRESS, S.ESCALATED):
        raise HTTPException(409, f"Cannot assign a complaint in status '{c.status}'.")

    team = db.get(Team, data.team_id)
    if not team:
        raise HTTPException(404, f"Team {data.team_id} not found")
    if not team.is_active:
        raise HTTPException(422, f"Team '{team.name}' is not active")
    tech = None
    if data.technician_id is not None:
        tech = db.get(Technician, data.technician_id)
        if not tech:
            raise HTTPException(404, f"Technician {data.technician_id} not found")
        if tech.team_id != team.id:
            raise HTTPException(422, f"Technician {tech.id} does not belong to team {team.id}")
    if c.department_id is None:
        c.department_id = team.department_id
    elif c.department_id != team.department_id:
        raise HTTPException(422, f"Team '{team.name}' belongs to department {team.department_id} "
                                 f"but the complaint is routed to department {c.department_id}")

    actives = db.query(Assignment).filter(Assignment.complaint_id == c.id,
                                          Assignment.status.in_(ACTIVE_ASSIGNMENT)).order_by(Assignment.id).all()
    for old in actives:
        old.status = A.CANCELLED
        old.resolution_notes = "Cancelled: reassigned to another team/technician"
    prev = actives[-1] if actives else (db.query(Assignment).filter(Assignment.complaint_id == c.id)
                                        .order_by(Assignment.id.desc()).first())

    agent = data.agent_name or ("dispatcher" if data.assigned_by == "agent" else "human")
    a = Assignment(complaint_id=c.id, cycle=c.current_cycle, team_id=team.id,
                   technician_id=tech.id if tech else None, department_id=team.department_id,
                   status=A.ASSIGNED, assigned_by=data.assigned_by, reason=data.reason,
                   previous_assignment_id=prev.id if prev else None)
    db.add(a)
    db.flush()

    if c.status != S.ASSIGNED:
        change_status(db, c, S.ASSIGNED, agent, data.reason)
    log_activity(db, c, agent,
                 f"{'Reassigned' if prev else 'Assigned'} to {team.name}" + (f" / {tech.name}" if tech else "")
                 + (f": {data.reason}" if data.reason else ""),
                 step="assignment", event_type="action",
                 data={"assignment_id": a.id, "team_id": team.id, "technician_id": a.technician_id,
                       "previous_assignment_id": a.previous_assignment_id})
    return a


def update_assignment(db: Session, a: Assignment, data: AssignmentUpdate) -> Assignment:
    c = db.get(Complaint, a.complaint_id)
    now = utcnow()
    if data.status and data.status != a.status:
        if a.status not in ACTIVE_ASSIGNMENT:
            raise HTTPException(409, f"Assignment #{a.id} is already '{a.status}' and can no longer change")
        if data.status == A.FAILED:
            raise HTTPException(422, "Assignments are marked 'failed' automatically by a failed verification")
        if data.status == A.IN_PROGRESS:
            a.status = A.IN_PROGRESS
            a.started_at = now
            if c.status == S.ASSIGNED:
                change_status(db, c, S.IN_PROGRESS, "technician", "Technician started work")
        elif data.status == A.COMPLETED:
            if a.status == A.ASSIGNED:  # auto-start
                a.started_at = now
                if c.status == S.ASSIGNED:
                    change_status(db, c, S.IN_PROGRESS, "technician", "Technician started work")
            if data.resolution_notes is not None:
                a.resolution_notes = data.resolution_notes
            a.status = A.COMPLETED
            a.completed_at = now
            change_status(db, c, S.RESOLVED, "technician", data.resolution_notes or "Work completed")
            change_status(db, c, S.VERIFICATION_PENDING, "system", "Awaiting verification before closing")
        elif data.status == A.CANCELLED:
            a.status = A.CANCELLED
            if c.status in (S.ASSIGNED, S.IN_PROGRESS):
                change_status(db, c, S.PROCESSING, "human", "Assignment cancelled; needs reassignment")
    if data.resolution_notes is not None:
        a.resolution_notes = data.resolution_notes
    if data.resolution_photo_url is not None:
        a.resolution_photo_url = data.resolution_photo_url
    log_activity(db, c, "system", f"Assignment #{a.id} updated (status: {a.status})", step="assignment", event_type="action")
    db.flush()
    return a


# ---------------- Verification (the closed loop) ----------------
def submit_verification(db: Session, c: Complaint, data: VerificationCreate):
    """Returns (verification, next_action). next_action: none | replan | escalated."""
    if c.status != S.VERIFICATION_PENDING:
        raise HTTPException(409, f"Complaint is '{c.status}'. Verification is only accepted when status is 'verification_pending'.")

    if data.assignment_id is not None:
        a = db.get(Assignment, data.assignment_id)
        if not a or a.complaint_id != c.id:
            raise HTTPException(422, f"Assignment {data.assignment_id} does not belong to this complaint")
    else:
        a = (db.query(Assignment).filter(Assignment.complaint_id == c.id, Assignment.status == A.COMPLETED)
             .order_by(Assignment.id.desc()).first())

    attempt = (db.query(func.count(Verification.id)).filter(Verification.complaint_id == c.id).scalar() or 0) + 1
    failure_reason = data.failure_reason or ("Issue not resolved" if data.result == "failed" else None)
    v = Verification(complaint_id=c.id, assignment_id=a.id if a else None, cycle=c.current_cycle,
                     attempt_number=attempt, method=data.method, result=data.result,
                     confidence=data.confidence, evidence=data.evidence,
                     failure_reason=failure_reason, verified_by=data.verified_by)
    db.add(v)
    db.flush()
    log_activity(db, c, data.verified_by, f"Verification attempt #{attempt}: {data.result.upper()}"
                 + (f" - {failure_reason}" if failure_reason else ""),
                 step="verification", event_type="decision",
                 data={"verification_id": v.id, "result": data.result, "confidence": data.confidence})

    if data.result == "passed":
        change_status(db, c, S.VERIFIED, data.verified_by, "Verification passed")
        change_status(db, c, S.CLOSED, "system", "Closed after successful verification")
        for dup in db.query(Complaint).filter(Complaint.duplicate_of_id == c.id, Complaint.status == S.DUPLICATE).all():
            change_status(db, dup, S.CLOSED, "system", f"Master complaint {c.reference_no} was closed")
        return v, "none"

    # FAILED -> atomic: mark assignment failed, verification_failed, reopen (new cycle)
    if a:
        a.status = A.FAILED
    change_status(db, c, S.VERIFICATION_FAILED, data.verified_by, failure_reason)
    next_action = reopen_complaint(db, c, data.verified_by, f"Verification failed: {failure_reason}")
    return v, next_action
