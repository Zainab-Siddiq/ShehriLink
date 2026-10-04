"""
Agent 6 - Assignment.

Deterministic on purpose (a dispatcher must be predictable). It considers:
  1. Department  - only teams of the selected department
  2. Availability - team.available and active_tasks < capacity
  3. Zone        - exact zone match > all-zone rapid-response team > other zones
  4. Replanning  - teams that already FAILED verification are tried last
  5. Workload    - fewest active tasks wins ties
If no team can take the job -> assigned_team is None and the graph escalates.
"""
from typing import List, Optional

from app.data.mock_database import get_repository
from app.graph.state import ASSIGNED, ComplaintState, log
from app.models.schemas import AssignmentResult

AGENT = "Assignment Agent"


def select_team(department: str, zone: Optional[str], failed_teams: List[str]) -> AssignmentResult:
    teams = get_repository().get_teams(department)
    eligible = [t for t in teams if t["available"] and t["active_tasks"] < t["capacity"]]
    if not eligible:
        return AssignmentResult(reason=f"No available team in the {department} "
                                       f"({len(teams)} team(s) found, none can take new work).")
    zone_known = bool(zone) and zone != "unknown"

    def rank(t: dict) -> tuple:
        if zone_known:
            zone_rank = 0 if t["zone"] == zone else (1 if t["zone"] == "ALL" else 2)
        else:
            zone_rank = 0 if t["zone"] == "ALL" else 1
        return (1 if t["team_id"] in failed_teams else 0, zone_rank, t["active_tasks"], t["team_id"])

    team = min(eligible, key=rank)

    # Human-readable reason
    if failed_teams:
        reason = (f"Reassigned after failed verification by {', '.join(failed_teams)}: "
                  f"{team['name']} ({team['zone']}) is the best remaining available {department} team.")
    elif zone_known and team["zone"] == zone:
        reason = f"{team['name']} handles {department} complaints in {zone}."
    elif zone_known and team["zone"] == "ALL":
        reason = f"No available {department} team is dedicated to {zone}; {team['name']} covers all zones."
    elif zone_known:
        reason = (f"No available {department} team covers {zone}; {team['name']} ({team['zone']}) "
                  f"is the nearest available option.")
    else:
        reason = f"Location zone unknown; {team['name']} was picked as the available {department} team with the lowest workload."
    return AssignmentResult(assigned_team=team["team_id"], team_name=team["name"], reason=reason)


def assignment_node(state: ComplaintState) -> dict:
    result = select_team(state.department or "General Services Department", state.zone, state.failed_teams)
    is_retry = bool(state.failed_teams)

    if result.assigned_team is None:
        entry = log(AGENT, "No suitable team found", "escalation required", status="failed",
                    message="No suitable team available", details={"reason": result.reason})
        return {"assigned_team": None, "assigned_team_name": None, "assignment_reason": result.reason,
                "escalation_reason": result.reason, "history": [entry]}

    entry = log(AGENT, "Reassigned team" if is_retry else "Assigned team", result.assigned_team,
                message="New team assigned" if is_retry else "Team assigned",
                details={"team_name": result.team_name, "reason": result.reason})
    return {"assigned_team": result.assigned_team, "assigned_team_name": result.team_name,
            "assignment_reason": result.reason, "status": ASSIGNED, "history": [entry]}
