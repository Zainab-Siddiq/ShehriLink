from math import asin, cos, radians, sin, sqrt
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Department, Team, Technician, User, Zone
from ..schemas import DepartmentOut, TeamOut, TechnicianOut, UserOut, ZoneOut
from ..services.workload import team_loads, technician_loads

router = APIRouter(tags=["Reference data"])


@router.get("/departments", response_model=List[DepartmentOut])
def list_departments(db: Session = Depends(get_db)):
    return db.query(Department).order_by(Department.id).all()


@router.get("/zones", response_model=List[ZoneOut])
def list_zones(db: Session = Depends(get_db)):
    return db.query(Zone).order_by(Zone.id).all()


def _km(lat1, lng1, lat2, lng2):
    p1, p2 = radians(lat1), radians(lat2)
    a = sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(lng2 - lng1) / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


@router.get("/zones/resolve")
def resolve_zone(lat: float = Query(..., ge=-90, le=90), lng: float = Query(..., ge=-180, le=180),
                 db: Session = Depends(get_db)):
    """Nearest zone to a coordinate (distance to zone centers)."""
    zones = db.query(Zone).filter(Zone.center_lat.isnot(None), Zone.center_lng.isnot(None)).all()
    if not zones:
        raise HTTPException(404, "No zones with coordinates")
    best = min(zones, key=lambda z: _km(lat, lng, z.center_lat, z.center_lng))
    return {"zone": ZoneOut.model_validate(best), "distance_km": round(_km(lat, lng, best.center_lat, best.center_lng), 2)}


@router.get("/teams", response_model=List[TeamOut])
def list_teams(department_id: Optional[int] = None, zone_id: Optional[int] = None,
               is_active: Optional[bool] = None, db: Session = Depends(get_db)):
    q = db.query(Team)
    if department_id is not None:
        q = q.filter(Team.department_id == department_id)
    if zone_id is not None:
        q = q.filter(Team.zone_id == zone_id)
    if is_active is not None:
        q = q.filter(Team.is_active == is_active)
    loads = team_loads(db)
    return [{
        "id": t.id, "name": t.name, "department_id": t.department_id, "zone_id": t.zone_id,
        "is_active": t.is_active, "department_name": t.department.name, "zone_name": t.zone.name,
        "technician_count": len(t.technicians),
        "available_technicians": sum(1 for x in t.technicians if x.is_available),
        "active_assignments": loads.get(t.id, 0),
    } for t in q.order_by(Team.id).all()]


@router.get("/technicians", response_model=List[TechnicianOut])
def list_technicians(team_id: Optional[int] = None, department_id: Optional[int] = None,
                     zone_id: Optional[int] = None, available: Optional[bool] = None,
                     db: Session = Depends(get_db)):
    q = db.query(Technician).join(Team, Technician.team_id == Team.id)
    if team_id is not None:
        q = q.filter(Technician.team_id == team_id)
    if department_id is not None:
        q = q.filter(Team.department_id == department_id)
    if zone_id is not None:
        q = q.filter(Team.zone_id == zone_id)
    if available is not None:
        q = q.filter(Technician.is_available == available)
    loads = technician_loads(db)
    return [{
        "id": t.id, "name": t.name, "phone": t.phone, "team_id": t.team_id, "team_name": t.team.name,
        "department_id": t.team.department_id, "zone_id": t.team.zone_id, "skills": t.skills,
        "is_available": t.is_available, "active_assignments": loads.get(t.id, 0),
    } for t in q.order_by(Technician.id).all()]


@router.get("/users", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.id).all()
