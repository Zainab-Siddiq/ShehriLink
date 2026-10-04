"""
Conditional-edge functions: they only READ the state and return the name of
the next branch. All loop-prevention logic lives here.
"""
from app.graph.state import ComplaintState


def route_after_assignment(state: ComplaintState) -> str:
    # No team could be assigned -> a human must handle it.
    if not state.assigned_team:
        return "escalate"
    # Manual mode: stop here (complaint stays open); an officer verifies it later.
    return "await" if state.verification_scenario == "manual" else "verify"


def route_after_verification(state: ComplaintState) -> str:
    if state.resolved:
        return "close"
    # retry_count = failed verifications so far. Once it reaches max_retries we
    # stop looping (this is what prevents an infinite replan cycle).
    if state.retry_count >= state.max_retries:
        return "escalate"
    return "replan"
