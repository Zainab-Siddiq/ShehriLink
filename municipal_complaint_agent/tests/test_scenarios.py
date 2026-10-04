"""The 5 hackathon demo scenarios, end to end (same data as `python run.py demo`)."""
from app.data.mock_data import DEMO_SCENARIOS
from app.graph.workflow import process_complaint


def run(key):
    req = next(s["request"] for s in DEMO_SCENARIOS if s["key"] == key)
    return process_complaint(**req)


def test_1_normal_flow():
    s = run("normal")
    assert s.category == "streetlight" and s.priority == "MEDIUM"
    assert s.department == "Electrical Department" and s.assigned_team == "ELEC-A"
    assert s.verification_status == "verified" and s.status == "CLOSED" and s.resolved
    assert s.duplicate is False          # the only similar complaint (#109) is already closed


def test_2_high_priority_open_manhole_near_school():
    s = run("high_priority")
    assert s.priority == "HIGH"
    assert "school" in s.priority_reason.lower()
    assert s.department == "Sewerage Department" and s.status == "CLOSED"


def test_3_duplicate_detected():
    s = run("duplicate")
    assert s.duplicate is True and s.related_complaint_id == "102"
    assert s.zone == "Zone B" and s.assigned_team == "ELEC-B"


def test_4_failed_verification_replan_reassign_success():
    s = run("failed_verification")
    assert s.retry_count == 1 and s.status == "CLOSED" and s.resolved
    statuses = [h.status for h in s.history]
    assert "failed" in statuses and "replanning" in statuses
    assigned = [h.result for h in s.history if h.agent == "Assignment Agent"]
    assert len(assigned) == 2 and assigned[0] != assigned[1]


def test_5_max_retries_escalates():
    s = run("max_retry")
    assert s.retry_count == s.max_retries == 3
    assert s.status == "ESCALATED" and s.resolved is False
    assert s.history[-1].status == "escalated"
    assert "limit 3" in s.escalation_reason
