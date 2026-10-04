"""
Non-LLM control nodes of the graph: REPLAN, CLOSE and ESCALATE.
"""
from app.graph.state import CLOSED, ESCALATED, REPLANNING, ComplaintState, log


def await_verification_node(state: ComplaintState) -> dict:
    """Manual mode: the complaint stays open (ASSIGNED) until an officer verifies it."""
    entry = log("Resolution Verification Agent", "Awaiting manual verification", "pending", status="info",
                message="Waiting for an officer to verify the fix",
                details={"team_id": state.assigned_team})
    return {"verification_status": "pending", "history": [entry]}


def replan_node(state: ComplaintState) -> dict:
    """Verification failed but retries remain: remember the failed team so the
    Assignment Agent picks a different one, then loop back to assignment."""
    failed = list(state.failed_teams)
    if state.assigned_team and state.assigned_team not in failed:
        failed.append(state.assigned_team)
    entry = log("Replanning Agent", "Replanning after failed verification",
                f"retry {state.retry_count} of {state.max_retries}", status="replanning", message="Replanning",
                details={"excluded_teams": failed, "reason": state.verification_reason})
    return {"failed_teams": failed, "assigned_team": None, "assigned_team_name": None,
            "status": REPLANNING, "history": [entry]}


def close_node(state: ComplaintState) -> dict:
    entry = log("Closure Agent", "Closed complaint", "CLOSED", message="Complaint closed",
                details={"retries_used": state.retry_count})
    return {"status": CLOSED, "resolved": True, "history": [entry]}


def escalate_node(state: ComplaintState) -> dict:
    if state.assigned_team is None:      # reached from the Assignment Agent: nobody could take it
        reason = state.escalation_reason or "No suitable team available."
    else:
        reason = (f"Verification failed {state.retry_count} time(s) (limit {state.max_retries}); "
                  f"escalated to a human supervisor.")
    entry = log("Escalation Agent", "Escalated complaint", "ESCALATED", status="escalated",
                message="Complaint escalated to supervisor", details={"reason": reason})
    return {"status": ESCALATED, "resolved": False, "escalation_reason": reason, "history": [entry]}
