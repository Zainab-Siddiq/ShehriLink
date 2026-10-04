"""
HttpRepository - connects the agent backend to the Database Backend (FastAPI + SQLite).

This is the ONLY integration code between the two backends. The agents, the
LangGraph workflow and the frontend are unchanged: the agents keep reading and
writing through the `ComplaintRepository` contract (see mock_database.py).

How it works
------------
* READS (teams, open complaints) come from the Database Backend:
    GET /teams, GET /complaints, GET /departments, GET /zones
  Processed results are read with GET /agent-activity/snapshots (one request, no per-complaint calls).
* WRITES happen once the workflow has finished (`save_processed_complaint`).
  The final state + timeline are replayed into the Database Backend through its
  existing endpoints, in the order its state machine requires:
    POST /complaints
    POST /complaints/{id}/understanding | investigation | decision
    POST /complaints/{id}/assignments, PATCH /assignments/{id}   (once per attempt)
    POST /complaints/{id}/verifications                           (once per attempt)
    PATCH /complaints/{id}/status  (only to mirror an ESCALATED result)
    POST /agent-activity           (one row holding the final agent state)
  A failed verification makes the Database Backend reopen the complaint itself
  (verification_failed -> reopened); the replay then sends the replan decision
  and the next assignment, exactly as described in the backend README.
* The frontend keeps using the agent API (/api/...). The final agent state is
  stored in the Database Backend as the `agent_final_state` activity row, so
  results survive a restart of the agent backend.

Vocabulary differences between the two projects (Zone A-D / 8 departments vs.
6 zones / 5 departments) are translated by the small tables below. Nothing in
either project's data had to be changed. Edit the tables if your team wants a
different mapping.

Enable with the environment variable DB_BACKEND_URL (see .env.example / README).
"""
import copy
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from app.data import mock_data
from app.data.mock_database import MockRepository

SNAPSHOT_STEP = "agent_final_state"

# --------------------------------------------------------------- vocabulary maps
# agent department name -> Database Backend department code
AGENT_DEPARTMENT_TO_DB_CODE = {
    "Electrical Department": "ELEC",
    "Roads Department": "ROADS",
    "Water Department": "WATER",
    "Drainage Department": "SAN",
    "Sanitation Department": "SAN",
    "Parks Department": "PARKS",
    "Sewerage Department": "WATER",           # backend: Water covers "leaks and sewage"
    "General Services Department": "SAN",     # backend has no general-purpose department
}
DEFAULT_DB_DEPARTMENT_CODE = "SAN"

# agent zone -> Database Backend zone code (used when writing)
AGENT_ZONE_TO_DB_CODE = {"Zone A": "SAD", "Zone B": "CLF", "Zone C": "GUL", "Zone D": "KOR"}
# Database Backend zone code -> agent zone (used when reading teams)
DB_ZONE_CODE_TO_AGENT_ZONE = {"SAD": "Zone A", "CLF": "Zone B", "GUL": "Zone C", "KOR": "Zone D",
                              "NNZ": "Zone C", "MAL": "Zone D"}

# Database Backend complaint category -> agent category (used when reading complaints)
DB_CATEGORY_TO_AGENT = {
    "streetlight": "streetlight", "power_outage": "electricity", "electrical_hazard": "electricity",
    "pothole": "road", "road_damage": "road", "traffic_signal": "road",
    "water_leak": "water", "no_water": "water", "sewage": "sewerage",
    "garbage": "garbage", "drain_blockage": "drainage",
    "park_maintenance": "parks", "tree_fall": "parks",
}

OPEN_STATUSES = ("submitted,processing,assigned,in_progress,resolved,verification_pending,"
                 "verified,verification_failed,reopened,escalated")
_VALID_PRIORITIES = {"low", "medium", "high", "critical"}
_REFERENCE_NO = re.compile(r"MC-\d+")


class DatabaseBackendError(RuntimeError):
    """The Database Backend is unreachable or rejected a request."""


def _clip(text: Optional[str], limit: int) -> Optional[str]:
    text = (text or "").strip()
    return text[:limit] if text else None


def _unit(value: Any) -> Optional[float]:
    """A confidence/similarity value usable by the backend (0..1) or None."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if 0.0 <= v <= 1.0 else None


class HttpRepository(MockRepository):
    """ComplaintRepository backed by the Database Backend.

    Inherits `get_areas`, `get_area_aliases` and `get_department_names` from
    MockRepository: the Database Backend has no areas table and the agents use
    their own department vocabulary, so those stay static reference data."""

    def __init__(self, base_url: str, team_capacity: Optional[int] = None, timeout: float = 15.0) -> None:
        super().__init__()
        import httpx  # already listed in requirements.txt

        self._httpx = httpx
        self.base_url = base_url.rstrip("/")
        self.team_capacity = team_capacity or int(os.getenv("TEAM_CAPACITY", "5"))
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)
        self._dept_ids: Optional[Dict[str, int]] = None
        self._zone_ids: Dict[str, int] = {}
        self._zone_codes: Dict[int, str] = {}
        self._index: Dict[str, int] = {}                 # agent complaint_id -> database id

    # ------------------------------------------------------------------ http
    def _request(self, method: str, path: str, *, allow_404: bool = False, **kwargs) -> Any:
        try:
            resp = self._client.request(method, path, **kwargs)
        except self._httpx.HTTPError as exc:
            raise DatabaseBackendError(
                f"Cannot reach the database backend at {self.base_url} ({type(exc).__name__}). "
                f"Start it first: cd backend && uvicorn app.main:app --port 8001") from exc
        if allow_404 and resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise DatabaseBackendError(f"Database backend {method} {path} failed ({resp.status_code}): {detail}")
        return resp.json()

    # ------------------------------------------------------- reference lookups
    def _load_reference(self, force: bool = False) -> None:
        if self._dept_ids is not None and not force:
            return
        self._dept_ids = {d["code"]: d["id"] for d in self._request("GET", "/departments")}
        zones = self._request("GET", "/zones")
        self._zone_ids = {z["code"]: z["id"] for z in zones}
        self._zone_codes = {z["id"]: z["code"] for z in zones}

    def _dept_id(self, agent_department: Optional[str]) -> int:
        code = AGENT_DEPARTMENT_TO_DB_CODE.get(agent_department or "", DEFAULT_DB_DEPARTMENT_CODE)
        self._load_reference()
        if code not in self._dept_ids:
            self._load_reference(force=True)
        if code not in self._dept_ids:
            raise DatabaseBackendError(f"Department '{code}' does not exist in the database backend. "
                                       f"Seed it: cd backend && python -m app.seed.seed_data --reset")
        return self._dept_ids[code]

    def _zone_id(self, agent_zone: Optional[str]) -> Optional[int]:
        code = AGENT_ZONE_TO_DB_CODE.get(agent_zone or "")
        if code is None:
            return None
        self._load_reference()
        if code not in self._zone_ids:
            self._load_reference(force=True)
        return self._zone_ids.get(code)

    def _db_id_of_reference(self, ref: Optional[str]) -> Optional[int]:
        """Database id for a reference number such as MC-0004 (None for anything else)."""
        if not ref or not _REFERENCE_NO.fullmatch(str(ref).upper()):
            return None
        row = self._request("GET", f"/complaints/{str(ref).upper()}", allow_404=True)
        return row["id"] if row else None

    # ----------------------------------------------------------------- reads
    @staticmethod
    def _agent_category(category: Optional[str]) -> str:
        if category in mock_data.CITIZEN_FEEDBACK:        # already an agent category (incl. "other")
            return category
        return DB_CATEGORY_TO_AGENT.get(category or "", "other")

    @staticmethod
    def _area_in(text: Optional[str]) -> Optional[str]:
        """Known area name mentioned in a free-text address (the backend stores no area)."""
        if not text:
            return None
        low = text.lower()
        names = {a.lower(): a for a in mock_data.AREAS}
        names.update({alias: area for alias, area in mock_data.AREA_ALIASES.items()})
        for key in sorted(names, key=len, reverse=True):
            if key in low:
                return names[key]
        return None

    def get_open_complaints(self, category: Optional[str] = None) -> List[dict]:
        rows = self._request("GET", "/complaints", params={"status": OPEN_STATUSES, "limit": 200})
        out: List[dict] = []
        for c in rows:
            cat = self._agent_category(c.get("category"))
            if category and cat != category:
                continue
            addr = c.get("address_text")
            out.append({"complaint_id": c["reference_no"], "description": c["raw_text"], "category": cat,
                        "area": self._area_in(addr), "location_text": addr, "status": c["status"].upper()})
        out.extend(super().get_open_complaints(category))   # reference complaints known to the agents
        return out

    def get_teams(self, department: str) -> List[dict]:
        dept_id = self._dept_id(department)
        rows = self._request("GET", "/teams", params={"department_id": dept_id})
        teams = []
        for t in rows:
            zone_code = self._zone_codes.get(t["zone_id"])
            teams.append({
                "team_id": str(t["id"]), "name": t["name"], "department": department,
                "zone": DB_ZONE_CODE_TO_AGENT_ZONE.get(zone_code, t.get("zone_name") or "unknown"),
                "available": bool(t["is_active"]) and t.get("available_technicians", 0) > 0,
                "active_tasks": t.get("active_assignments", 0),
                "capacity": self.team_capacity,
            })
        return teams

    # ---------------------------------------------------------------- writes
    @staticmethod
    def _attempts(history: List[dict]) -> List[dict]:
        """One entry per assignment attempt, rebuilt from the agents' timeline."""
        attempts: List[dict] = []
        cur: Optional[dict] = None
        for h in history:
            action, details = h.get("action"), h.get("details") or {}
            if h.get("agent") == "Assignment Agent" and action in ("Assigned team", "Reassigned team"):
                cur = {"team_id": h.get("result"), "reason": details.get("reason"), "report": None,
                       "passed": None, "feedback": None, "verdict": None}
                attempts.append(cur)
            elif cur is not None and action == "Reported resolution attempt":
                cur["report"] = h.get("result")
            elif cur is not None and action == "Verified resolution":
                cur.update(passed=True, feedback=details.get("citizen_feedback"), verdict=details.get("reason"))
            elif cur is not None and action == "Verification failed":
                cur.update(passed=False, feedback=details.get("citizen_feedback"), verdict=details.get("reason"))
        return attempts

    def _create(self, s: dict) -> Tuple[int, dict]:
        """Create the complaint and record the pre-assignment stages. Returns (database id, routing decision)."""
        history = s.get("history") or []
        desc = (s.get("description") or "").strip()
        if len(desc) < 5:                       # backend requires >= 5 characters
            desc = desc.ljust(5, ".")
        zone_id = self._zone_id(s.get("zone"))

        c = self._request("POST", "/complaints", json={
            "raw_text": desc[:2000], "address_text": _clip(s.get("location"), 255), "zone_id": zone_id,
            "simulation_mode": _clip(s.get("verification_scenario"), 40)})
        db_id = c["id"]
        base = f"/complaints/{db_id}"

        category = s.get("category") or "other"
        self._request("POST", f"{base}/understanding", json={
            "agent_name": "Classification Agent", "category": category, "subcategory": s.get("subcategory"),
            "summary": f"Classified as {category}/{s.get('subcategory')}",
            "confidence": _unit(s.get("classification_confidence"))})

        relations = []
        related_id = self._db_id_of_reference(s.get("related_complaint_id")) if s.get("duplicate") else None
        if related_id is not None and related_id != db_id:
            similarity = next((_unit((h.get("details") or {}).get("similarity")) for h in history
                               if h.get("agent") == "History/Duplicate Agent"), None)
            relations.append({"related_complaint_id": related_id, "relation_type": "duplicate",
                              "similarity_score": similarity, "reason": s.get("duplicate_reason"),
                              "detected_by": "History/Duplicate Agent"})
        self._request("POST", f"{base}/investigation", json={
            "agent_name": "Location/History Agent", "zone_id": zone_id, "relations": relations,
            "is_duplicate": False,    # the agents keep processing duplicates, so only link them
            "findings": {"area": s.get("area"), "zone": s.get("zone"), "location_text": s.get("location_text"),
                         "duplicate": bool(s.get("duplicate")), "related_complaint_id": s.get("related_complaint_id")},
            "summary": " ".join(x for x in (f"Location: {s.get('area')} / {s.get('zone')}.",
                                            s.get("duplicate_reason")) if x),
            "confidence": _unit(s.get("location_confidence"))})

        decision = self._decision(s)
        self._request("POST", f"{base}/decision", json=decision)
        return db_id, decision

    def _decision(self, s: dict) -> dict:
        priority = (s.get("priority") or "medium").lower()
        return {
            "agent_name": "Priority/Department Agent",
            "priority": priority if priority in _VALID_PRIORITIES else "medium",
            "department_id": self._dept_id(s.get("department")),
            "rationale": " | ".join(x for x in (s.get("priority_reason"), s.get("department_reason")) if x) or None,
            "is_replan": False}

    def _sync_attempts(self, db_id: int, s: dict, decision: dict) -> None:
        """Bring the assignments/verifications of the database up to date with the agents' timeline.
        Idempotent: attempts that are already stored are skipped, so a complaint saved while waiting for a
        manual verification can be saved again after the officer's verdict."""
        base = f"/complaints/{db_id}"
        stored = self._request("GET", f"{base}/assignments")
        verified = len(self._request("GET", f"{base}/verifications"))
        for i, a in enumerate(self._attempts(s.get("history") or [])):
            if i < len(stored):
                assignment = stored[i]
            else:
                if i > 0:   # the previous verification failed -> the backend reopened it -> replan
                    self._request("POST", f"{base}/decision", json={
                        **decision, "is_replan": True, "agent_name": "Replanning Agent",
                        "rationale": "Replanning after failed verification"})
                assignment = self._request("POST", f"{base}/assignments", json={
                    "team_id": int(a["team_id"]), "assigned_by": "agent", "agent_name": "Assignment Agent",
                    "reason": a["reason"]})
            aid, status = assignment["id"], assignment["status"]

            if a["passed"] is None and a["report"] is None:     # waiting for a manual verification
                if status == "assigned":
                    self._request("PATCH", f"/assignments/{aid}", json={"status": "in_progress"})
                break
            if status in ("assigned", "in_progress"):
                if status == "assigned":
                    self._request("PATCH", f"/assignments/{aid}", json={"status": "in_progress"})
                self._request("PATCH", f"/assignments/{aid}", json={
                    "status": "completed", "resolution_notes": a["report"]})
            if a["passed"] is None:             # no verification result was recorded
                break
            if i < verified:                    # this verdict is already stored
                continue
            outcome = self._request("POST", f"{base}/verifications", json={
                "result": "passed" if a["passed"] else "failed", "method": "citizen_followup",
                "assignment_id": aid, "evidence": a["feedback"],
                "failure_reason": None if a["passed"] else (a["verdict"] or "Issue not resolved"),
                "verified_by": "Resolution Verification Agent"})
            if outcome["next_action"] == "escalated":   # the backend escalated by itself
                break

    def _persist(self, s: dict, db_id: Optional[int] = None) -> int:
        """Write the agents' result to the database. With `db_id` the complaint already exists
        (saved earlier while it waited for a manual verification) and only the new steps are added."""
        if db_id is None:
            db_id, decision = self._create(s)
        else:
            decision = self._decision(s)
        base = f"/complaints/{db_id}"
        self._sync_attempts(db_id, s, decision)

        # Mirror an escalation the backend has not applied itself (e.g. no team was available).
        current = self._request("GET", base)
        if s.get("status") == "ESCALATED" and current["status"] != "escalated":
            self._request("PATCH", f"{base}/status", json={
                "status": "escalated", "changed_by": "Escalation Agent",
                "reason": s.get("escalation_reason") or "Escalated by the agent workflow"})

        # The full agent result (what the frontend displays), kept next to the normalised rows.
        self._request("POST", "/agent-activity", json={
            "complaint_id": db_id, "agent_name": "Agent Workflow", "step": SNAPSHOT_STEP, "event_type": "info",
            "message": f"Agent workflow finished: {s.get('status')}",
            "data": {"complaint_id": str(s["complaint_id"]), "state": s}})
        return db_id

    def save_processed_complaint(self, result: dict) -> None:
        state = copy.deepcopy(result)
        cid = str(state["complaint_id"])
        self._index[cid] = self._persist(state, self._index.get(cid))

    # ----------------------------------------------------- reading results back
    # Nothing is cached here except the (permanent) agent id -> database id mapping: on a serverless host
    # every request may be served by a different instance, so a cached state would go stale.
    def _snapshots(self, **params) -> List[Tuple[int, dict]]:
        """(database id, final agent state) of the latest snapshot per complaint, newest first (one request)."""
        rows = self._request("GET", "/agent-activity/snapshots", params={"step": SNAPSHOT_STEP, **params})
        return [(r["complaint_id"], r["data"]["state"]) for r in rows if (r.get("data") or {}).get("state")]

    def _snapshot(self, db_id: int) -> Optional[dict]:
        rows = self._request("GET", f"/complaints/{db_id}/agent-activity", allow_404=True) or []
        state = None
        for r in rows:                      # oldest -> newest, keep the latest snapshot
            data = r.get("data") or {}
            if r.get("step") == SNAPSHOT_STEP and data.get("state"):
                state = data["state"]
        return state

    def get_processed_complaint(self, complaint_id: str) -> Optional[dict]:
        cid = str(complaint_id)
        if _REFERENCE_NO.fullmatch(cid.upper()):            # a database reference such as MC-0004
            db_id = self._db_id_of_reference(cid)
            state = self._snapshot(db_id) if db_id is not None else None
            return copy.deepcopy(state) if state is not None else None
        found = self._snapshots(agent_complaint_id=cid, limit=1)
        if not found:
            return None
        self._index[cid] = found[0][0]
        return copy.deepcopy(found[0][1])

    def list_processed_complaints(self) -> List[dict]:
        return [copy.deepcopy(state) for _, state in self._snapshots(limit=200)]


def configure_from_env() -> bool:
    """Use the Database Backend when DB_BACKEND_URL is set (agents keep their mock data otherwise).
    Safe to call more than once."""
    from app.data.mock_database import get_repository, set_repository

    url = os.getenv("DB_BACKEND_URL", "").strip()
    if not url:
        return False
    current = get_repository()
    if not (isinstance(current, HttpRepository) and current.base_url == url.rstrip("/")):
        set_repository(HttpRepository(url))
    return True
