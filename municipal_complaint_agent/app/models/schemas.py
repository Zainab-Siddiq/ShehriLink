"""
Pydantic schemas: the structured outputs of every agent + API request model.

Using `Literal` types means an LLM (or our fallback rules) can never return a
category/priority that is not on the allowed list - validation fails instead.
"""
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------- vocabularies
Category = Literal[
    "streetlight", "road", "water", "drainage", "garbage",
    "sanitation", "parks", "sewerage", "electricity", "other",
]
CATEGORIES = list(Category.__args__)  # type: ignore[attr-defined]

Priority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
PRIORITY_LEVELS = list(Priority.__args__)  # type: ignore[attr-defined]


# ------------------------------------------------------------- agent outputs
class ClassificationResult(BaseModel):
    category: Category
    subcategory: str = Field(description="snake_case sub-type, e.g. streetlight_not_working")
    confidence: float = Field(ge=0.0, le=1.0)


class LocationExtraction(BaseModel):
    """What the LLM is asked for. The zone is NOT asked for - code maps area -> zone."""
    area: str = Field(description="Known area name, or 'unknown'")
    location_text: str = Field(description="Most specific location phrase, or 'unknown'")
    confidence: float = Field(ge=0.0, le=1.0)


class LocationResult(BaseModel):
    area: str
    zone: str
    location_text: str
    confidence: float = Field(ge=0.0, le=1.0)


class DuplicateJudgement(BaseModel):
    """Used only when an LLM is asked to settle an ambiguous duplicate check."""
    duplicate: bool
    reason: str


class DuplicateResult(BaseModel):
    duplicate: bool
    related_complaint_id: Optional[str] = None
    reason: str


class PriorityResult(BaseModel):
    priority: Priority
    reason: str


class DepartmentResult(BaseModel):
    department: str
    reason: str


class AssignmentResult(BaseModel):
    assigned_team: Optional[str] = None   # None => nobody suitable => escalation
    team_name: Optional[str] = None
    reason: str


class VerificationJudgement(BaseModel):
    """Used when an LLM judges the team report vs. the citizen's feedback."""
    resolved: bool
    reason: str


class VerificationResult(BaseModel):
    resolved: bool
    verification_status: Literal["verified", "failed"]
    reason: str


# ----------------------------------------------------------------- timeline
class HistoryEntry(BaseModel):
    """One line of the 'Agent Activity Timeline' shown by the frontend."""
    agent: str
    action: str
    result: str
    # success -> ✓   failed -> ✗   replanning -> ↻   escalated -> ⚠   info -> •
    status: Literal["success", "failed", "replanning", "escalated", "info"] = "success"
    message: str = ""        # short human-readable timeline text
    timestamp: str
    details: Dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------- API
class ProcessComplaintRequest(BaseModel):
    complaint_id: str = Field(min_length=1, examples=["C-1001"])
    description: str = Field(min_length=3, examples=[
        "Streetlight outside my house in Hayatabad Phase 3 has not worked for three days."])
    location: Optional[str] = Field(default=None, examples=["Hayatabad Phase 3"])
    verification_scenario: Optional[str] = Field(
        default=None,
        description="manual (stay open until an officer verifies) | success | fail_once | fail_twice | fail_<n> | always_fail",
        examples=["success"],
    )

    @field_validator("verification_scenario")
    @classmethod
    def _check_scenario(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Imported here to avoid a circular import at module load time.
        from app.data.mock_data import parse_scenario
        parse_scenario(v)  # raises ValueError for unknown scenarios -> HTTP 422
        return v.strip().lower()


class ManualVerificationRequest(BaseModel):
    passed: bool = Field(description="true = the fix is confirmed (closes the complaint); false = not fixed")
    note: Optional[str] = Field(default=None, max_length=500, description="Officer's remark (optional)")
