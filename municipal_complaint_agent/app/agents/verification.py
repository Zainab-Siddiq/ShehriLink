"""
Agent 7 - Resolution Verification (closed-loop check).

1. The assigned team "reports" the work done.
2. We collect independent evidence (a citizen follow-up).
   In the hackathon demo the evidence is MOCKED and controllable with
   `verification_scenario` (success / fail_once / fail_twice / fail_<n> / always_fail).
3. The agent judges whether the problem is REALLY resolved (LLM or keyword rules).
4. On failure it increments `retry_count`; the router then replans or escalates.
"""
import re

from app.data import mock_data
from app.data.mock_database import get_verification_provider
from app.graph.state import VERIFICATION_FAILED, VERIFIED, ComplaintState, log
from app.llm import run_structured
from app.models.schemas import VerificationJudgement, VerificationResult

AGENT = "Resolution Verification Agent"

_NEGATIVE = re.compile(r"\bstill\b|\bnot\b|n't\b|\bno\b|\bnever\b|\bunresolved\b|\bagain\b|\bworse\b|\bfailed\b")
_POSITIVE = re.compile(r"working|fixed|resolved|restored|repaired|cleared|clear\b|cleaned|collected|done|better|yes")


def judge_with_rules(category: str, citizen_feedback: str) -> VerificationResult:
    """Keyword judge. The citizen's feedback wins over the team's own claim."""
    text = citizen_feedback.lower()
    if _NEGATIVE.search(text):
        phrase = mock_data.FAILURE_PHRASES.get(category, mock_data.FAILURE_PHRASES["other"])
        return VerificationResult(resolved=False, verification_status="failed",
                                  reason=f"Citizen verification indicates {phrase}.")
    if _POSITIVE.search(text):
        return VerificationResult(resolved=True, verification_status="verified",
                                  reason="The reported issue is confirmed resolved.")
    return VerificationResult(resolved=False, verification_status="failed",
                              reason="Citizen feedback does not confirm the issue is resolved.")


def verification_node(state: ComplaintState) -> dict:
    category = state.category or "other"
    attempt = state.retry_count + 1
    team_name = state.assigned_team_name or "Field team"

    evidence = get_verification_provider().get_resolution_evidence(
        category=category, team_name=team_name, attempt=attempt, scenario=state.verification_scenario)
    report, feedback = evidence["team_report"], evidence["citizen_feedback"]

    system = ("You verify whether a municipal complaint is truly resolved. A field team claims it is fixed. "
              "The citizen's follow-up is independent evidence and takes priority over the team's claim. "
              "If the citizen says the problem persists, resolved=false. Give a one-sentence reason.")
    user = (f"Complaint: {state.description}\nTeam report: {report}\nCitizen follow-up: {feedback}")
    judgement, errors = run_structured(AGENT, VerificationJudgement, system, user)
    if judgement is not None:
        result = VerificationResult(resolved=judgement.resolved,
                                    verification_status="verified" if judgement.resolved else "failed",
                                    reason=judgement.reason)
    else:
        result = judge_with_rules(category, feedback)

    attempt_entry = log(team_name, "Reported resolution attempt", report, message="Resolution attempted",
                        details={"attempt": attempt, "team_id": state.assigned_team})
    if result.resolved:
        verdict = log(AGENT, "Verified resolution", "verified", message="Verification passed",
                      details={"attempt": attempt, "citizen_feedback": feedback, "reason": result.reason})
        return {"team_report": report, "citizen_feedback": feedback, "resolved": True,
                "verification_status": "verified", "verification_reason": result.reason,
                "status": VERIFIED, "history": [attempt_entry, verdict], "errors": errors}

    verdict = log(AGENT, "Verification failed", "failed", status="failed", message="Verification failed",
                  details={"attempt": attempt, "citizen_feedback": feedback, "reason": result.reason})
    return {"team_report": report, "citizen_feedback": feedback, "resolved": False,
            "verification_status": "failed", "verification_reason": result.reason,
            "retry_count": attempt, "status": VERIFICATION_FAILED,
            "history": [attempt_entry, verdict], "errors": errors}
