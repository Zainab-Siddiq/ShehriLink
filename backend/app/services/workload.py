from sqlalchemy import func
from sqlalchemy.orm import Session

from ..enums import ACTIVE_ASSIGNMENT
from ..models import Assignment


def team_loads(db: Session) -> dict:
    rows = (db.query(Assignment.team_id, func.count(Assignment.id))
            .filter(Assignment.status.in_(ACTIVE_ASSIGNMENT)).group_by(Assignment.team_id).all())
    return {team_id: n for team_id, n in rows}


def technician_loads(db: Session) -> dict:
    rows = (db.query(Assignment.technician_id, func.count(Assignment.id))
            .filter(Assignment.status.in_(ACTIVE_ASSIGNMENT), Assignment.technician_id.isnot(None))
            .group_by(Assignment.technician_id).all())
    return {tech_id: n for tech_id, n in rows}
