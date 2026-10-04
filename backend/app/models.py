from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base
from .enums import ALL_STATUSES
from .utils import utcnow

_STATUS_LIST = ",".join(f"'{s}'" for s in ALL_STATUSES)


class User(Base):
    """Citizen (or staff) account. Citizens are auto-created from complaint contact info."""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(40), unique=True, index=True)
    email = Column(String(120))
    role = Column(String(20), nullable=False, default="citizen")
    created_at = Column(DateTime, nullable=False, default=utcnow)


class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False, unique=True)
    code = Column(String(20), nullable=False, unique=True)
    description = Column(String(255))
    categories = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class Zone(Base):
    __tablename__ = "zones"
    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False, unique=True)
    code = Column(String(20), nullable=False, unique=True)
    description = Column(String(255))
    center_lat = Column(Float)
    center_lng = Column(Float)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, unique=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    department = relationship("Department")
    zone = relationship("Zone")
    technicians = relationship("Technician", back_populates="team", order_by="Technician.id")


class Technician(Base):
    __tablename__ = "technicians"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(40))
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    skills = Column(String(255))
    is_available = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    team = relationship("Team", back_populates="technicians")


class Complaint(Base):
    __tablename__ = "complaints"
    __table_args__ = (
        CheckConstraint(f"status IN ({_STATUS_LIST})", name="ck_complaint_status"),
        CheckConstraint("priority IS NULL OR priority IN ('low','medium','high','critical')",
                        name="ck_complaint_priority"),
        Index("ix_complaints_zone_category", "zone_id", "category"),
    )
    id = Column(Integer, primary_key=True)
    reference_no = Column(String(30), nullable=False, unique=True, index=True)
    citizen_id = Column(Integer, ForeignKey("users.id"), index=True)
    citizen_name = Column(String(120))
    citizen_contact = Column(String(60))
    raw_text = Column(Text, nullable=False)
    address_text = Column(String(255))
    latitude = Column(Float)
    longitude = Column(Float)
    category = Column(String(60), index=True)
    subcategory = Column(String(60))
    priority = Column(String(20), index=True)
    status = Column(String(30), nullable=False, default="submitted", index=True)
    zone_id = Column(Integer, ForeignKey("zones.id"), index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), index=True)
    current_cycle = Column(Integer, nullable=False, default=1)
    reopen_count = Column(Integer, nullable=False, default=0)
    duplicate_of_id = Column(Integer, ForeignKey("complaints.id"), index=True)
    simulation_mode = Column(String(40))
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    resolved_at = Column(DateTime)
    closed_at = Column(DateTime)

    citizen = relationship("User")
    zone = relationship("Zone")
    department = relationship("Department")
    assignments = relationship("Assignment", order_by="Assignment.id")
    verifications = relationship("Verification", order_by="Verification.id")
    status_history = relationship("StatusHistory", order_by="StatusHistory.id")
    activity_logs = relationship("AgentActivityLog", order_by="AgentActivityLog.id")


class Assignment(Base):
    """Append-only: every assignment attempt is its own row."""
    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint("status IN ('assigned','in_progress','completed','failed','cancelled')",
                        name="ck_assignment_status"),
        Index("ix_assignments_complaint_cycle", "complaint_id", "cycle"),
    )
    id = Column(Integer, primary_key=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    cycle = Column(Integer, nullable=False, default=1)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    technician_id = Column(Integer, ForeignKey("technicians.id"), index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    status = Column(String(20), nullable=False, default="assigned", index=True)
    assigned_by = Column(String(20), nullable=False, default="agent")
    reason = Column(Text)
    previous_assignment_id = Column(Integer, ForeignKey("assignments.id"))
    assigned_at = Column(DateTime, nullable=False, default=utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    resolution_notes = Column(Text)
    resolution_photo_url = Column(String(500))
    created_at = Column(DateTime, nullable=False, default=utcnow)

    team = relationship("Team")
    technician = relationship("Technician")

    @property
    def team_name(self):
        return self.team.name if self.team else None

    @property
    def technician_name(self):
        return self.technician.name if self.technician else None


class Verification(Base):
    """Append-only: every verification attempt is stored, failed ones are never deleted."""
    __tablename__ = "verifications"
    __table_args__ = (
        CheckConstraint("result IN ('passed','failed')", name="ck_verification_result"),
        UniqueConstraint("complaint_id", "attempt_number", name="uq_verification_attempt"),
    )
    id = Column(Integer, primary_key=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), index=True)
    cycle = Column(Integer, nullable=False, default=1)
    attempt_number = Column(Integer, nullable=False, default=1)
    method = Column(String(40), nullable=False, default="citizen_followup")
    result = Column(String(10), nullable=False)
    confidence = Column(Float)
    evidence = Column(Text)
    failure_reason = Column(Text)
    verified_by = Column(String(80))
    created_at = Column(DateTime, nullable=False, default=utcnow)


class StatusHistory(Base):
    __tablename__ = "status_history"
    id = Column(Integer, primary_key=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    from_status = Column(String(30))
    to_status = Column(String(30), nullable=False)
    cycle = Column(Integer, nullable=False, default=1)
    changed_by = Column(String(80))
    reason = Column(Text)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class AgentActivityLog(Base):
    __tablename__ = "agent_activity_logs"
    id = Column(Integer, primary_key=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    cycle = Column(Integer, nullable=False, default=1)
    agent_name = Column(String(80), nullable=False)
    step = Column(String(80))
    event_type = Column(String(20), nullable=False, default="info")
    message = Column(Text, nullable=False)
    data = Column(JSON)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class AgentResult(Base):
    """Full structured output of each pipeline stage (per cycle)."""
    __tablename__ = "agent_results"
    __table_args__ = (Index("ix_agent_results_complaint_stage", "complaint_id", "stage"),)
    id = Column(Integer, primary_key=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    cycle = Column(Integer, nullable=False, default=1)
    stage = Column(String(30), nullable=False)  # understanding/investigation/decision/replan
    agent_name = Column(String(80))
    summary = Column(Text)
    confidence = Column(Float)
    payload = Column(JSON)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ComplaintRelation(Base):
    __tablename__ = "complaint_relations"
    __table_args__ = (
        UniqueConstraint("complaint_id", "related_complaint_id", "relation_type", name="uq_relation"),
        CheckConstraint("complaint_id != related_complaint_id", name="ck_relation_not_self"),
        CheckConstraint("relation_type IN ('duplicate','related','recurring')", name="ck_relation_type"),
    )
    id = Column(Integer, primary_key=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    related_complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    relation_type = Column(String(20), nullable=False, default="related")
    similarity_score = Column(Float)
    reason = Column(Text)
    detected_by = Column(String(80))
    created_at = Column(DateTime, nullable=False, default=utcnow)
