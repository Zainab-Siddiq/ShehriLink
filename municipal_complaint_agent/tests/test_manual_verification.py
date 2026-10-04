"""Manual mode: the complaint stays open until an officer verifies it."""
from fastapi.testclient import TestClient

from app.graph.workflow import process_complaint, verify_manually
from app.main import app

STREETLIGHT = dict(complaint_id="M-1", description="Streetlight not working in Canal Town", location="Canal Town",
                   verification_scenario="manual")


def test_manual_complaint_stays_open():
    s = process_complaint(**STREETLIGHT)
    assert s.status == "ASSIGNED" and not s.resolved and s.verification_status == "pending"
    assert s.assigned_team and s.history[-1].action == "Awaiting manual verification"


def test_manual_pass_closes():
    process_complaint(**STREETLIGHT)
    s = verify_manually("M-1", True, "Light is on again")
    assert s.status == "CLOSED" and s.resolved and s.retry_count == 0
    assert s.citizen_feedback == "Light is on again"


def test_manual_fail_reassigns_then_stays_open():
    first = process_complaint(**STREETLIGHT)
    s = verify_manually("M-1", False)
    assert s.status == "ASSIGNED" and s.retry_count == 1 and s.verification_status == "pending"
    assert s.assigned_team != first.assigned_team and first.assigned_team in s.failed_teams
    assert verify_manually("M-1", True).status == "CLOSED"


def test_manual_fail_until_escalated():
    process_complaint(**STREETLIGHT)
    for _ in range(2):
        assert verify_manually("M-1", False).status == "ASSIGNED"
    s = verify_manually("M-1", False)
    assert s.status == "ESCALATED" and s.retry_count == 3


def test_api_verify_errors_and_flow():
    c = TestClient(app)
    assert c.post("/api/complaints/NOPE/verify", json={"passed": True}).status_code == 404
    r = c.post("/api/complaints/process", json=STREETLIGHT)
    assert r.status_code == 200 and r.json()["status"] == "ASSIGNED"
    r = c.post("/api/complaints/M-1/verify", json={"passed": True})
    assert r.status_code == 200 and r.json()["status"] == "CLOSED"
    assert c.post("/api/complaints/M-1/verify", json={"passed": True}).status_code == 409   # already closed


def test_non_manual_complaint_cannot_be_verified_by_hand():
    process_complaint("M-2", "Streetlight not working in Canal Town", "Canal Town", "success")
    try:
        verify_manually("M-2", True)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
    else:
        raise AssertionError("expected ManualVerificationError")
