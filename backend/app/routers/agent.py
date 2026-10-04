from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..enums import S
from ..models import AgentActivityLog, AgentResult, Complaint, Department, Zone
from ..schemas import (ActivityCreate, ActivityOut, AgentResultOut, ComplaintOut, DecisionIn,
                       InvestigationIn, RelationIn, UnderstandingIn)
from ..services.lifecycle import change_status, get_complaint_or_404, log_activity
from ..services.workflow import add_relation

router = APIRouter(tags=["Agent"])


def _check_open(c: Complaint):
    if c.status not in (S.SUBMITTED, S.PROCESSING, S.REOPENED):
        raise HTTPException(409, f"Agent stage output can only be recorded while the complaint is "
                                 f"submitted/processing/reopened (current: '{c.status}')")


def _ensure_processing(db: Session, c: Complaint, agent: str):
    if c.status in (S.SUBMITTED, S.REOPENED):
        change_status(db, c, S.PROCESSING, agent, "Agent pipeline started")


def _save_result(db: Session, c: Complaint, stage: str, agent: str, summary, confidence, payload: dict):
    db.add(AgentResult(complaint_id=c.id, cycle=c.current_cycle, stage=stage, agent_name=agent,
                       summary=summary, confidence=confidence, payload=payload))
    db.flush()


@router.post("/complaints/{complaint_id}/understanding", response_model=ComplaintOut)
def post_understanding(complaint_id: str, data: UnderstandingIn, db: Session = Depends(get_db)):
    c = get_complaint_or_404(db, complaint_id)
    _check_open(c)
    _ensure_processing(db, c, data.agent_name)
    c.category = data.category
    c.subcategory = data.subcategory
    _save_result(db, c, "understanding", data.agent_name, data.summary, data.confidence, data.model_dump())
    log_activity(db, c, data.agent_name, data.summary or f"Classified as {data.category}/{data.subcategory}",
                 step="understanding", event_type="decision",
                 data={"category": data.category, "subcategory": data.subcategory, "confidence": data.confidence})
    db.commit()
    db.refresh(c)
    return c


@router.post("/complaints/{complaint_id}/investigation", response_model=ComplaintOut)
def post_investigation(complaint_id: str, data: InvestigationIn, db: Session = Depends(get_db)):
    c = get_complaint_or_404(db, complaint_id)
    _check_open(c)
    if data.zone_id is not None and not db.get(Zone, data.zone_id):
        raise HTTPException(422, f"Zone {data.zone_id} does not exist")
    master = None
    if data.is_duplicate:
        if data.duplicate_of_id is None:
            raise HTTPException(422, "duplicate_of_id is required when is_duplicate is true")
        master = db.get(Complaint, data.duplicate_of_id)
        if not master or master.id == c.id:
            raise HTTPException(422, f"duplicate_of_id {data.duplicate_of_id} is invalid")

    _ensure_processing(db, c, data.agent_name)
    if data.zone_id is not None:
        c.zone_id = data.zone_id
    for rel in data.relations:
        rel.detected_by = data.agent_name if rel.detected_by == "agent" else rel.detected_by
        add_relation(db, c, rel)
    _save_result(db, c, "investigation", data.agent_name, data.summary, data.confidence, data.model_dump())
    log_activity(db, c, data.agent_name,
                 data.summary or f"Investigation complete: zone {c.zone_id}, {len(data.relations)} related complaint(s)",
                 step="investigation", event_type="decision",
                 data={"zone_id": c.zone_id, "relations": len(data.relations), "is_duplicate": data.is_duplicate})
    if master:
        c.duplicate_of_id = master.id
        add_relation(db, c, RelationIn(related_complaint_id=master.id, relation_type="duplicate",
                                       similarity_score=data.confidence, reason=data.summary,
                                       detected_by=data.agent_name))
        change_status(db, c, S.DUPLICATE, data.agent_name, f"Duplicate of {master.reference_no}")
    db.commit()
    db.refresh(c)
    return c


@router.post("/complaints/{complaint_id}/decision", response_model=ComplaintOut)
def post_decision(complaint_id: str, data: DecisionIn, db: Session = Depends(get_db)):
    c = get_complaint_or_404(db, complaint_id)
    _check_open(c)
    if not db.get(Department, data.department_id):
        raise HTTPException(422, f"Department {data.department_id} does not exist")
    _ensure_processing(db, c, data.agent_name)
    c.priority = data.priority
    c.department_id = data.department_id
    stage = "replan" if data.is_replan else "decision"
    _save_result(db, c, stage, data.agent_name, data.rationale, data.confidence, data.model_dump())
    log_activity(db, c, data.agent_name,
                 data.rationale or f"Priority {data.priority}, department {data.department_id}",
                 step=stage, event_type="decision",
                 data={"priority": data.priority, "department_id": data.department_id, "is_replan": data.is_replan})
    db.commit()
    db.refresh(c)
    return c


@router.get("/complaints/{complaint_id}/agent-results", response_model=List[AgentResultOut])
def list_agent_results(complaint_id: str, db: Session = Depends(get_db)):
    c = get_complaint_or_404(db, complaint_id)
    return db.query(AgentResult).filter(AgentResult.complaint_id == c.id).order_by(AgentResult.id).all()


@router.get("/complaints/{complaint_id}/agent-activity", response_model=List[ActivityOut])
def list_agent_activity(complaint_id: str, since_id: int = Query(0, ge=0, description="Only rows with id > since_id (for polling)"),
                        cycle: Optional[int] = None, db: Session = Depends(get_db)):
    c = get_complaint_or_404(db, complaint_id)
    q = db.query(AgentActivityLog).filter(AgentActivityLog.complaint_id == c.id, AgentActivityLog.id > since_id)
    if cycle is not None:
        q = q.filter(AgentActivityLog.cycle == cycle)
    return q.order_by(AgentActivityLog.id).all()


@router.get("/agent-activity/snapshots", response_model=List[ActivityOut])
def list_snapshots(step: str = Query("agent_final_state", description="Activity step that holds a result snapshot"),
                   agent_complaint_id: Optional[str] = Query(None, description="Only the snapshot whose data.complaint_id matches"),
                   limit: int = Query(200, ge=1, le=500), db: Session = Depends(get_db)):
    """The latest snapshot row of every complaint (newest first), in ONE query. The agent backend stores its
    final workflow state this way, so it can list/look up results without one request per complaint."""
    latest = (select(func.max(AgentActivityLog.id)).where(AgentActivityLog.step == step)
              .group_by(AgentActivityLog.complaint_id))
    q = db.query(AgentActivityLog).filter(AgentActivityLog.id.in_(latest))
    if agent_complaint_id is not None:
        q = q.filter(AgentActivityLog.data["complaint_id"].as_string() == agent_complaint_id)
    return q.order_by(AgentActivityLog.id.desc()).limit(limit).all()


@router.post("/agent-activity", response_model=ActivityOut, status_code=201)
def post_agent_activity(data: ActivityCreate, db: Session = Depends(get_db)):
    """Agents write free-form 'thinking out loud' lines to the timeline."""
    c = db.get(Complaint, data.complaint_id)
    if not c:
        raise HTTPException(404, f"Complaint {data.complaint_id} not found")
    row = log_activity(db, c, data.agent_name, data.message, step=data.step,
                       event_type=data.event_type, data=data.data, cycle=data.cycle)
    db.commit()
    db.refresh(row)
    return row
