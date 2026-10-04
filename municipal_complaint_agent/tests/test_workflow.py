"""Graph structure, loop prevention, state/history contract and the HTTP API."""
import pytest
from fastapi.testclient import TestClient

from app.graph.workflow import build_graph, process_complaint
from app.main import app

STREETLIGHT = dict(complaint_id="W-1", description="Streetlight not working in Canal Town", location="Canal Town")


def test_graph_has_all_nodes():
    nodes = set(build_graph().get_graph().nodes)
    for n in ["classification_agent", "location_agent", "history_agent", "priority_agent", "department_agent",
              "assignment_agent", "verification_agent", "replan", "close", "escalate"]:
        assert n in nodes


def test_happy_path_history_order():
    s = process_complaint(**STREETLIGHT)
    assert s.status == "CLOSED" and s.resolved and s.retry_count == 0
    msgs = [h.message for h in s.history]
    assert msgs == ["Classification completed", "Location identified", "Duplicate check completed",
                    "Priority determined", "Department selected", "Team assigned", "Resolution attempted",
                    "Verification passed", "Complaint closed"]
    assert all(h.timestamp for h in s.history)


@pytest.mark.parametrize("scenario,retries,status", [
    ("success", 0, "CLOSED"), ("fail_once", 1, "CLOSED"), ("fail_twice", 2, "CLOSED"),
    ("always_fail", 3, "ESCALATED"),
])
def test_retry_counts(scenario, retries, status):
    s = process_complaint(**STREETLIGHT, verification_scenario=scenario)
    assert (s.retry_count, s.status) == (retries, status)


def test_no_infinite_loop_with_custom_max(monkeypatch):
    monkeypatch.setenv("MAX_RETRIES", "5")
    s = process_complaint(**STREETLIGHT, verification_scenario="always_fail")
    assert s.status == "ESCALATED" and s.retry_count == 5 and s.max_retries == 5
    assert sum(1 for h in s.history if h.status == "replanning") == 4


def test_each_reassignment_uses_a_different_team():
    s = process_complaint(**STREETLIGHT, verification_scenario="always_fail")
    teams = [h.result for h in s.history if h.agent == "Assignment Agent"]
    assert len(teams) == 3 and len(set(teams)) == 3


def test_missing_location_still_completes():
    s = process_complaint(complaint_id="W-2", description="Streetlight is not working outside my house")
    assert s.area == "unknown" and s.status == "CLOSED"


def test_unmapped_category_goes_to_general_services():
    s = process_complaint(complaint_id="W-3", description="Please tell me the complaint office timings")
    assert s.category == "other" and s.department == "General Services Department"


# ------------------------------------------------------------------------ API
client = TestClient(app)


def test_api_health_and_scenarios():
    assert client.get("/api/health").json()["llm_provider"] == "mock"
    data = client.get("/api/scenarios").json()
    assert len(data["demo_requests"]) == 5 and "always_fail" in data["verification_scenarios"]


def test_api_process_matches_spec_shape():
    r = client.post("/api/complaints/process", json={
        "complaint_id": "C-1001",
        "description": "Streetlight outside my house in Hayatabad Phase 3 has not worked for three days.",
        "location": "Hayatabad Phase 3"})
    assert r.status_code == 200
    body = r.json()
    for key in ["complaint_id", "category", "priority", "department", "assigned_team", "status", "resolved", "history"]:
        assert key in body
    assert body["category"] == "streetlight" and body["department"] == "Electrical Department"
    assert body["assigned_team"] == "ELEC-B" and body["status"] == "CLOSED" and body["resolved"] is True
    assert body["history"][0]["agent"] == "Classification Agent"


def test_api_get_processed_complaint():
    client.post("/api/complaints/process", json={"complaint_id": "C-GET", "description": "No water supply in Saddar"})
    assert client.get("/api/complaints/C-GET").json()["category"] == "water"
    assert client.get("/api/complaints/DOES-NOT-EXIST").status_code == 404


def test_api_validation_errors():
    assert client.post("/api/complaints/process", json={"complaint_id": "x"}).status_code == 422
    bad = client.post("/api/complaints/process", json={
        "complaint_id": "x", "description": "streetlight off", "verification_scenario": "banana"})
    assert bad.status_code == 422
