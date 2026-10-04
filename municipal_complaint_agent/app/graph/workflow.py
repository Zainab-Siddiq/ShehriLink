"""
The LangGraph workflow.

START -> classification -> location -> history -> priority -> department
      -> assignment -> verification -> (close | replan -> assignment | escalate)
"""
from functools import lru_cache
from typing import Optional

from langgraph.graph import END, START, StateGraph

from app.agents import (assignment_node, await_verification_node, classification_node, close_node, department_node,
                        escalate_node, history_node, location_node, priority_node, replan_node, verification_node)
from app.config import get_settings
from app.data import mock_data
from app.data.mock_database import get_repository
from app.graph.routing import route_after_assignment, route_after_verification
from app.graph.state import ASSIGNED, VERIFICATION_FAILED, VERIFIED, ComplaintState, log


def build_graph():
    g = StateGraph(ComplaintState)

    # NOTE: node names must differ from state field names (e.g. "priority"), hence the *_agent suffix.
    g.add_node("classification_agent", classification_node)
    g.add_node("location_agent", location_node)
    g.add_node("history_agent", history_node)
    g.add_node("priority_agent", priority_node)
    g.add_node("department_agent", department_node)
    g.add_node("assignment_agent", assignment_node)
    g.add_node("verification_agent", verification_node)
    g.add_node("await_verification", await_verification_node)
    g.add_node("replan", replan_node)
    g.add_node("close", close_node)
    g.add_node("escalate", escalate_node)

    # straight pipeline
    g.add_edge(START, "classification_agent")
    g.add_edge("classification_agent", "location_agent")
    g.add_edge("location_agent", "history_agent")
    g.add_edge("history_agent", "priority_agent")
    g.add_edge("priority_agent", "department_agent")
    g.add_edge("department_agent", "assignment_agent")

    # assignment: team found -> verify (or wait for a manual verification), otherwise escalate
    g.add_conditional_edges("assignment_agent", route_after_assignment,
                            {"verify": "verification_agent", "await": "await_verification", "escalate": "escalate"})
    g.add_edge("await_verification", END)
    # decision after verification: close / replan (loop) / escalate
    g.add_conditional_edges("verification_agent", route_after_verification,
                            {"close": "close", "replan": "replan", "escalate": "escalate"})
    g.add_edge("replan", "assignment_agent")   # <- the closed loop

    g.add_edge("close", END)
    g.add_edge("escalate", END)
    return g.compile()


@lru_cache(maxsize=1)
def get_graph():
    return build_graph()


def process_complaint(
    complaint_id: str,
    description: str,
    location: Optional[str] = None,
    verification_scenario: Optional[str] = None,
) -> ComplaintState:
    """Run one complaint through the whole workflow and return the final state."""
    settings = get_settings()
    initial = ComplaintState(
        complaint_id=complaint_id,
        description=description,
        location=location,
        verification_scenario=(verification_scenario or settings.verification_scenario),
        max_retries=settings.max_retries,
    )
    # Hard safety net on top of max_retries: LangGraph aborts if steps exceed this.
    config = {"recursion_limit": 30 + 5 * settings.max_retries}
    final = get_graph().invoke(initial, config=config)
    if isinstance(final, dict):
        final = ComplaintState.model_validate(final)
    get_repository().save_processed_complaint(final.model_dump())
    return final


# ------------------------------------------------------------ manual verification
class ManualVerificationError(Exception):
    """The complaint cannot be verified by hand (unknown id, or not waiting for verification)."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def _apply(state: ComplaintState, update: dict) -> None:
    """Merge an agent's partial update into the state (history/errors are appended, like the graph does)."""
    for key, value in update.items():
        if key in ("history", "errors"):
            getattr(state, key).extend(value)
        else:
            setattr(state, key, value)


def verify_manually(complaint_id: str, passed: bool, note: Optional[str] = None) -> ComplaintState:
    """An officer confirms (passed) or rejects (not passed) the fix of a complaint that is waiting in
    manual mode. Passed -> closed. Not passed -> the usual closed loop: replan with another team, or
    escalate once `max_retries` failed verifications are reached."""
    data = get_repository().get_processed_complaint(complaint_id)
    if data is None:
        raise ManualVerificationError(f"Complaint '{complaint_id}' has not been processed.", 404)
    state = ComplaintState.model_validate(data)
    if state.verification_scenario != "manual" or state.status != ASSIGNED or state.verification_status != "pending":
        raise ManualVerificationError(
            f"Complaint '{complaint_id}' is not waiting for manual verification (status {state.status}).", 409)

    team_name = state.assigned_team_name or "Field team"
    attempt = state.retry_count + 1
    category = state.category if state.category in mock_data.TEAM_REPORTS else "other"
    report = f"{team_name} reports: {mock_data.TEAM_REPORTS[category]}"
    feedback = (note or "").strip() or ("Officer confirmed the issue is resolved." if passed
                                        else "Officer found the issue is not resolved.")
    agent = "Resolution Verification Agent"

    reported = log(team_name, "Reported resolution attempt", report, message="Resolution attempted",
                   details={"attempt": attempt, "team_id": state.assigned_team})
    state.team_report, state.citizen_feedback, state.verification_reason = report, feedback, feedback
    if passed:
        verdict = log(agent, "Verified resolution", "verified", message="Verification passed (manual)",
                      details={"attempt": attempt, "citizen_feedback": feedback, "reason": feedback, "manual": True})
        _apply(state, {"resolved": True, "verification_status": "verified", "status": VERIFIED,
                       "history": [reported, verdict]})
        _apply(state, close_node(state))
    else:
        verdict = log(agent, "Verification failed", "failed", status="failed", message="Verification failed (manual)",
                      details={"attempt": attempt, "citizen_feedback": feedback, "reason": feedback, "manual": True})
        _apply(state, {"resolved": False, "verification_status": "failed", "retry_count": attempt,
                       "status": VERIFICATION_FAILED, "history": [reported, verdict]})
        if route_after_verification(state) == "escalate":
            _apply(state, escalate_node(state))
        else:
            _apply(state, replan_node(state))
            _apply(state, assignment_node(state))
            if route_after_assignment(state) == "await":
                _apply(state, await_verification_node(state))
            else:
                _apply(state, escalate_node(state))

    get_repository().save_processed_complaint(state.model_dump())
    return state
