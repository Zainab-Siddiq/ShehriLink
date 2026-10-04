from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import Base, engine, get_db
from ..enums import S
from ..models import Verification
from ..schemas import AssignmentUpdate, ComplaintOut, VerificationCreate, VerificationResponse
from ..seed.seed_data import seed
from ..services.lifecycle import get_complaint_or_404
from ..services.workflow import active_assignment, submit_verification, update_assignment

router = APIRouter(prefix="/demo", tags=["Demo helpers"])


@router.post("/seed")
def demo_seed(db: Session = Depends(get_db)):
    """Load mock data (does nothing if data already exists)."""
    result = seed(db)
    db.commit()
    return result


@router.post("/reset")
def demo_reset(db: Session = Depends(get_db)):
    """Wipe ALL data and reload mock data."""
    db.close()  # release any connection before dropping tables
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    result = seed(db)
    db.commit()
    return result


@router.post("/complaints/{complaint_id}/simulate-technician", response_model=ComplaintOut)
def simulate_technician(complaint_id: str, db: Session = Depends(get_db)):
    """Starts and completes the active assignment (no technician UI needed for the demo)."""
    c = get_complaint_or_404(db, complaint_id)
    a = active_assignment(db, c)
    if not a:
        raise HTTPException(409, "Complaint has no active assignment")
    update_assignment(db, a, AssignmentUpdate(status="in_progress"))
    update_assignment(db, a, AssignmentUpdate(status="completed",
                                              resolution_notes="[simulated] Technician completed the job"))
    db.commit()
    db.refresh(c)
    return c


@router.post("/complaints/{complaint_id}/simulate-verification", response_model=VerificationResponse)
def simulate_verification(complaint_id: str, db: Session = Depends(get_db)):
    """If complaint.simulation_mode == 'fail_first_verification', the 1st verification FAILS, later ones PASS."""
    c = get_complaint_or_404(db, complaint_id)
    if c.status != S.VERIFICATION_PENDING:
        raise HTTPException(409, f"Complaint is '{c.status}', expected 'verification_pending'")
    prior = db.query(Verification).filter(Verification.complaint_id == c.id).count()
    fail = c.simulation_mode == "fail_first_verification" and prior == 0
    data = VerificationCreate(
        result="failed" if fail else "passed", method="citizen_followup", confidence=0.9,
        evidence="[simulated] Citizen says the light is still off" if fail else "[simulated] Citizen confirms issue is fixed",
        failure_reason="[simulated] Issue persists after repair" if fail else None,
        verified_by="verifier_agent")
    v, next_action = submit_verification(db, c, data)
    db.commit()
    db.refresh(v)
    db.refresh(c)
    return {"verification": v, "complaint": c, "next_action": next_action}
