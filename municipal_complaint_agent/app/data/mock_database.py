"""
Data-access layer (the ONLY place agents get municipal data from).

`ComplaintRepository` is the contract. `MockRepository` implements it with the
in-memory data from `mock_data.py`.

>>> To connect PostgreSQL: create `PostgresRepository(ComplaintRepository)`,
>>> implement the methods below with SQL, and call `set_repository(...)` at
>>> startup (e.g. in app/main.py). No agent code has to change.
"""
import copy
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from app.data import mock_data


class ComplaintRepository(ABC):
    """Everything the agents need from the database."""

    @abstractmethod
    def get_open_complaints(self, category: Optional[str] = None) -> List[dict]:
        """Open complaints (status != CLOSED), optionally filtered by category.
        Dict keys: complaint_id, description, category, area, location_text, status."""

    @abstractmethod
    def get_areas(self) -> Dict[str, str]:
        """{area name: zone name}"""

    @abstractmethod
    def get_area_aliases(self) -> Dict[str, str]:
        """{lower-case alias: canonical area name}"""

    @abstractmethod
    def get_department_names(self) -> List[str]:
        """All department names."""

    @abstractmethod
    def get_teams(self, department: str) -> List[dict]:
        """Teams of a department. Keys: team_id, name, department, zone,
        available, active_tasks, capacity. zone == 'ALL' means every zone."""

    @abstractmethod
    def save_processed_complaint(self, result: dict) -> None:
        """Persist the final state of a processed complaint."""

    @abstractmethod
    def get_processed_complaint(self, complaint_id: str) -> Optional[dict]:
        """Fetch a previously processed complaint (final state) or None."""

    def list_processed_complaints(self) -> List[dict]:
        """All processed complaints, newest first (used by the officer dashboard)."""
        return []


class MockRepository(ComplaintRepository):
    def __init__(self) -> None:
        self._processed: Dict[str, dict] = {}

    def get_open_complaints(self, category: Optional[str] = None) -> List[dict]:
        rows = [c for c in mock_data.EXISTING_COMPLAINTS if c["status"].upper() != "CLOSED"]
        if category:
            rows = [c for c in rows if c["category"] == category]
        return copy.deepcopy(rows)

    def get_areas(self) -> Dict[str, str]:
        return dict(mock_data.AREAS)

    def get_area_aliases(self) -> Dict[str, str]:
        return dict(mock_data.AREA_ALIASES)

    def get_department_names(self) -> List[str]:
        return [d["name"] for d in mock_data.DEPARTMENTS]

    def get_teams(self, department: str) -> List[dict]:
        return copy.deepcopy([t for t in mock_data.TEAMS if t["department"] == department])

    def save_processed_complaint(self, result: dict) -> None:
        self._processed[str(result["complaint_id"])] = result

    def get_processed_complaint(self, complaint_id: str) -> Optional[dict]:
        return self._processed.get(str(complaint_id))

    def list_processed_complaints(self) -> List[dict]:
        # dicts keep insertion order, so reversed = most recently first processed
        return copy.deepcopy(list(reversed(self._processed.values())))


# ----------------------------------------------------------------- verification
class VerificationProvider(ABC):
    """Where the 'resolution evidence' comes from.

    Mock: simulated team report + simulated citizen follow-up.
    Real system: team app report + SMS/app follow-up with the citizen."""

    @abstractmethod
    def get_resolution_evidence(self, *, category: str, team_name: str, attempt: int, scenario: str) -> dict:
        """Return {"team_report": str, "citizen_feedback": str}."""


class MockVerificationProvider(VerificationProvider):
    def get_resolution_evidence(self, *, category: str, team_name: str, attempt: int, scenario: str) -> dict:
        failures = mock_data.parse_scenario(scenario)      # None = always fail
        should_fail = failures is None or attempt <= failures
        cat = category if category in mock_data.CITIZEN_FEEDBACK else "other"
        positive, negative = mock_data.CITIZEN_FEEDBACK[cat]
        return {
            "team_report": f"{team_name} reports: {mock_data.TEAM_REPORTS[cat]}",
            "citizen_feedback": negative if should_fail else positive,
        }


# ------------------------------------------------------------ global accessors
_repository: ComplaintRepository = MockRepository()
_verification_provider: VerificationProvider = MockVerificationProvider()


def get_repository() -> ComplaintRepository:
    return _repository


def set_repository(repo: ComplaintRepository) -> None:
    """Swap the data source (PostgreSQL, test doubles, ...)."""
    global _repository
    _repository = repo


def get_verification_provider() -> VerificationProvider:
    return _verification_provider


def set_verification_provider(provider: VerificationProvider) -> None:
    global _verification_provider
    _verification_provider = provider
