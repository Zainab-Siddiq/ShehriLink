from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Assignment
from ..schemas import AssignmentCreate, AssignmentOut, AssignmentUpdate
from ..services.lifecycle import get_complaint_or_404
from ..services.workflow import create_assignment, update_assignment

router = APIRouter(tags=["Assignments"])


@router.get("/complaints/{complaint_id}/assignments", response_model=List[AssignmentOut])
def list_assignments(complaint_id: str, db: Session = Depends(get_db)):
    c = get_complaint_or_404(db, complaint_id)
    return db.query(Assignment).filter(Assignment.complaint_id == c.id).order_by(Assignment.id).all()


@router.post("/complaints/{complaint_id}/assignments", response_model=AssignmentOut, status_code=201)
def post_assignment(complaint_id: str, data: AssignmentCreate, db: Session = Depends(get_db)):
    """Create an assignment or a reassignment (old active assignment is cancelled, never overwritten)."""
    c = get_complaint_or_404(db, complaint_id)
    a = create_assignment(db, c, data)
    db.commit()
    db.refresh(a)
    return a


@router.get("/assignments/{assignment_id}", response_model=AssignmentOut)
def get_assignment(assignment_id: int, db: Session = Depends(get_db)):
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(404, f"Assignment {assignment_id} not found")
    return a


@router.patch("/assignments/{assignment_id}", response_model=AssignmentOut)
def patch_assignment(assignment_id: int, data: AssignmentUpdate, db: Session = Depends(get_db)):
    """status=in_progress (start), status=completed (done -> complaint goes to verification_pending),
    status=cancelled, or just update resolution_notes / resolution_photo_url."""
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(404, f"Assignment {assignment_id} not found")
    update_assignment(db, a, data)
    db.commit()
    db.refresh(a)
    return a
