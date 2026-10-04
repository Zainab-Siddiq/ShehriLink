from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Verification
from ..schemas import VerificationCreate, VerificationOut, VerificationResponse
from ..services.lifecycle import get_complaint_or_404
from ..services.workflow import submit_verification

router = APIRouter(tags=["Verification"])


@router.get("/complaints/{complaint_id}/verifications", response_model=List[VerificationOut])
def list_verifications(complaint_id: str, db: Session = Depends(get_db)):
    c = get_complaint_or_404(db, complaint_id)
    return db.query(Verification).filter(Verification.complaint_id == c.id).order_by(Verification.id).all()


@router.post("/complaints/{complaint_id}/verifications", response_model=VerificationResponse, status_code=201)
def post_verification(complaint_id: str, data: VerificationCreate, db: Session = Depends(get_db)):
    """THE closed loop. passed -> verified -> closed. failed -> verification_failed -> reopened (cycle+1).
    next_action tells the agent what to do: none | replan | escalated."""
    c = get_complaint_or_404(db, complaint_id)
    v, next_action = submit_verification(db, c, data)
    db.commit()
    db.refresh(v)
    db.refresh(c)
    return {"verification": v, "complaint": c, "next_action": next_action}
