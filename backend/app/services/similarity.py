from datetime import timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from ..enums import S
from ..models import Complaint
from ..utils import utcnow


def find_similar(db: Session, c: Complaint, days: int = 30, include_closed: bool = False,
                 zone_id: Optional[int] = None, category: Optional[str] = None,
                 limit: int = 10) -> List[Complaint]:
    """Candidate duplicates: same zone + category, recent. Plain SQL, no AI."""
    zone_id = zone_id or c.zone_id
    category = category or c.category
    if zone_id is None and category is None:
        return []
    q = db.query(Complaint).filter(Complaint.id != c.id,
                                   Complaint.created_at >= utcnow() - timedelta(days=days))
    if zone_id is not None:
        q = q.filter(Complaint.zone_id == zone_id)
    if category is not None:
        q = q.filter(Complaint.category == category)
    if not include_closed:
        q = q.filter(Complaint.status.notin_([S.CLOSED, S.DUPLICATE]))
    return q.order_by(Complaint.id.desc()).limit(limit).all()
