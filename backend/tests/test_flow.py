import os

# Use a throwaway DB so tests never touch municipal.db
os.environ["DATABASE_URL"] = "sqlite:///./test_municipal.db"
if os.path.exists("test_municipal.db"):
    os.remove("test_municipal.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

ELEC_DEPT, GULSHAN_ZONE, ELEC_GULSHAN_TEAM = 1, 3, 1


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        assert c.post("/demo/reset").status_code == 200
        yield c


def new_complaint(client, text="Streetlight outside my house hasn't worked for 3 days.", phone="0300-0000000"):
    r = client.post("/complaints", json={"citizen_name": "Test", "citizen_contact": phone, "raw_text": text})
    assert r.status_code == 201, r.text
    return r.json()


def run_pipeline(client, cid):
    assert client.post(f"/complaints/{cid}/understanding",
                       json={"category": "streetlight", "subcategory": "not_working"}).json()["status"] == "processing"
    r = client.post(f"/complaints/{cid}/investigation", json={"zone_id": GULSHAN_ZONE, "relations": []})
    assert r.json()["zone_id"] == GULSHAN_ZONE
    r = client.post(f"/complaints/{cid}/decision", json={"priority": "high", "department_id": ELEC_DEPT})
    assert r.json()["priority"] == "high"


def test_swagger_loads(client):
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    paths = spec.json()["paths"]
    for p in ["/complaints", "/complaints/{complaint_id}", "/complaints/{complaint_id}/history",
              "/complaints/{complaint_id}/related", "/complaints/{complaint_id}/assignments",
              "/complaints/{complaint_id}/verifications", "/complaints/{complaint_id}/agent-activity",
              "/complaints/{complaint_id}/status", "/complaints/{complaint_id}/reopen",
              "/complaints/{complaint_id}/context", "/assignments/{assignment_id}",
              "/departments", "/zones", "/teams", "/agent-activity"]:
        assert p in paths, p
    assert client.get("/health").json() == {"status": "ok"}


def test_seed_data(client):
    assert len(client.get("/departments").json()) == 5
    assert len(client.get("/zones").json()) >= 5
    assert len(client.get("/teams").json()) >= 8
    assert len(client.get("/complaints", params={"limit": 200}).json()) == 11
    # seeded failed-verification scenario (MC-0005) and closed complaint (MC-0001)
    assert client.get("/complaints/MC-0001").json()["status"] == "closed"
    v = client.get("/complaints/MC-0005/verifications").json()
    assert v[0]["result"] == "failed"
    a = client.get("/complaints/MC-0005/assignments").json()
    assert [x["status"] for x in a] == ["failed", "in_progress"] and a[1]["previous_assignment_id"] == a[0]["id"]
    assert client.get("/dashboard/stats").json()["total_complaints"] == 11
    assert any(x["value"] == "closed" for x in client.get("/meta/enums").json()["statuses"])


def test_closed_loop_fail_then_pass(client):
    cid = new_complaint(client)["id"]
    assert client.get(f"/complaints/{cid}").json()["status"] == "submitted"
    run_pipeline(client, cid)

    a1 = client.post(f"/complaints/{cid}/assignments",
                     json={"team_id": ELEC_GULSHAN_TEAM, "technician_id": 1, "reason": "closest"}).json()
    assert a1["status"] == "assigned" and a1["cycle"] == 1
    assert client.get(f"/complaints/{cid}").json()["status"] == "assigned"

    # guard rails: cannot close / verify early
    assert client.patch(f"/complaints/{cid}/status", json={"status": "closed"}).status_code == 422
    assert client.post(f"/complaints/{cid}/verifications", json={"result": "passed"}).status_code == 409

    # in_progress -> resolved -> verification_pending
    assert client.patch(f"/assignments/{a1['id']}", json={"status": "in_progress"}).json()["status"] == "in_progress"
    assert client.get(f"/complaints/{cid}").json()["status"] == "in_progress"
    client.patch(f"/assignments/{a1['id']}", json={"status": "completed", "resolution_notes": "Replaced bulb"})
    assert client.get(f"/complaints/{cid}").json()["status"] == "verification_pending"

    # verification FAILED -> verification_failed -> reopened, cycle 2
    r = client.post(f"/complaints/{cid}/verifications",
                    json={"result": "failed", "failure_reason": "Light still off"}).json()
    assert r["next_action"] == "replan"
    assert r["complaint"]["status"] == "reopened"
    assert r["complaint"]["current_cycle"] == 2 and r["complaint"]["reopen_count"] == 1

    # replan + reassign (different team member, new row, old one preserved)
    r = client.post(f"/complaints/{cid}/decision",
                    json={"priority": "critical", "department_id": ELEC_DEPT, "is_replan": True})
    assert r.json()["status"] == "processing"
    a2 = client.post(f"/complaints/{cid}/assignments",
                     json={"team_id": ELEC_GULSHAN_TEAM, "technician_id": 2, "reason": "retry"}).json()
    assert a2["previous_assignment_id"] == a1["id"] and a2["cycle"] == 2 and a2["id"] != a1["id"]

    client.patch(f"/assignments/{a2['id']}", json={"status": "in_progress"})
    client.patch(f"/assignments/{a2['id']}", json={"status": "completed"})
    assert client.get(f"/complaints/{cid}").json()["status"] == "verification_pending"
    r = client.post(f"/complaints/{cid}/verifications", json={"result": "passed"}).json()
    assert r["next_action"] == "none"
    assert r["complaint"]["status"] == "closed" and r["complaint"]["closed_at"] is not None

    # full history preserved
    statuses = [s["to_status"] for s in client.get(f"/complaints/{cid}/history").json()]
    expected = ["submitted", "processing", "assigned", "in_progress", "resolved", "verification_pending",
                "verification_failed", "reopened", "processing", "assigned", "in_progress", "resolved",
                "verification_pending", "verified", "closed"]
    assert statuses == expected, statuses
    cycles = {s["cycle"] for s in client.get(f"/complaints/{cid}/history").json()}
    assert cycles == {1, 2}
    assigns = client.get(f"/complaints/{cid}/assignments").json()
    assert [a["status"] for a in assigns] == ["failed", "completed"]
    vers = client.get(f"/complaints/{cid}/verifications").json()
    assert [v["result"] for v in vers] == ["failed", "passed"]
    assert [v["attempt_number"] for v in vers] == [1, 2] and [v["cycle"] for v in vers] == [1, 2]
    assert vers[0]["assignment_id"] == a1["id"] and vers[1]["assignment_id"] == a2["id"]
    logs = client.get(f"/complaints/{cid}/agent-activity").json()
    assert {l["cycle"] for l in logs} == {1, 2} and len(logs) > 15
    assert len(client.get(f"/complaints/{cid}/agent-activity", params={"cycle": 2}).json()) < len(logs)
    since = logs[-3]["id"]
    assert len(client.get(f"/complaints/{cid}/agent-activity", params={"since_id": since}).json()) == 2

    # cannot verify again once closed
    assert client.post(f"/complaints/{cid}/verifications", json={"result": "passed"}).status_code == 409

    # context has everything
    ctx = client.get(f"/complaints/{cid}/context").json()
    assert ctx["complaint"]["status"] == "closed"
    assert len(ctx["assignments"]) == 2 and len(ctx["verifications"]) == 2
    assert ctx["zone"]["id"] == GULSHAN_ZONE and ctx["department"]["id"] == ELEC_DEPT
    assert set(ctx["agent_results"]) >= {"understanding", "investigation", "decision", "replan"}
    assert ctx["allowed_next_statuses"] == ["reopened"]
    assert ctx["current_assignment"] is None


def test_duplicate_and_related(client):
    master = new_complaint(client, phone="0300-1")
    dup = new_complaint(client, text="Street light is dead on my street, please fix.", phone="0300-2")
    run_pipeline(client, master["id"])
    # related link via investigation
    client.post(f"/complaints/{dup['id']}/understanding", json={"category": "streetlight"})
    r = client.post(f"/complaints/{dup['id']}/investigation", json={
        "zone_id": GULSHAN_ZONE, "is_duplicate": True, "duplicate_of_id": master["id"],
        "relations": [{"related_complaint_id": 2, "relation_type": "related", "similarity_score": 0.8,
                       "reason": "Same block"}],
        "summary": "Same fault", "confidence": 0.9})
    assert r.status_code == 200 and r.json()["status"] == "duplicate" and r.json()["duplicate_of_id"] == master["id"]
    rel = client.get(f"/complaints/{dup['id']}/related").json()
    assert {x["relation_type"] for x in rel} == {"related", "duplicate"}
    assert any(x["related_reference_no"] == master["reference_no"] for x in rel)
    # master sees the link too
    assert any(x["relation_type"] == "duplicate" for x in client.get(f"/complaints/{master['id']}/related").json())
    # manual link endpoint + candidates endpoint
    assert client.post(f"/complaints/{master['id']}/related",
                       json={"related_complaint_id": 3, "relation_type": "related"}).status_code == 201
    assert client.get(f"/complaints/{master['id']}/similar").status_code == 200
    # closing the master auto-closes the duplicate
    team = ELEC_GULSHAN_TEAM
    a = client.post(f"/complaints/{master['id']}/assignments", json={"team_id": team}).json()
    client.patch(f"/assignments/{a['id']}", json={"status": "completed"})
    client.post(f"/complaints/{master['id']}/verifications", json={"result": "passed"})
    assert client.get(f"/complaints/{dup['id']}").json()["status"] == "closed"


def test_validation_and_guards(client):
    assert client.post("/complaints", json={"raw_text": "x"}).status_code == 422
    assert client.get("/complaints/99999").status_code == 404
    cid = new_complaint(client, phone="0300-3")["id"]
    run_pipeline(client, cid)
    # wrong department team -> 422 (Roads team 4 vs Electrical complaint)
    assert client.post(f"/complaints/{cid}/assignments", json={"team_id": 4}).status_code == 422
    # PATCH and PUT update work, status is not editable that way
    assert client.put(f"/complaints/{cid}", json={"priority": "medium"}).status_code == 200
    r = client.patch(f"/complaints/{cid}", json={"priority": "low"})
    assert r.status_code == 200 and r.json()["priority"] == "low"
    # agent free-form activity
    r = client.post("/agent-activity", json={"complaint_id": cid, "agent_name": "investigator",
                                             "message": "Checking nearby complaints"})
    assert r.status_code == 201
    assert client.get("/activity/recent").json()[0]["message"] == "Checking nearby complaints"


def test_escalation_after_max_reopens(client):
    cid = new_complaint(client, phone="0300-4")["id"]
    run_pipeline(client, cid)
    last = None
    for i in range(3):
        a = client.post(f"/complaints/{cid}/assignments", json={"team_id": ELEC_GULSHAN_TEAM}).json()
        client.patch(f"/assignments/{a['id']}", json={"status": "completed"})
        last = client.post(f"/complaints/{cid}/verifications", json={"result": "failed"}).json()
    assert last["next_action"] == "escalated" and last["complaint"]["status"] == "escalated"
    assert last["complaint"]["current_cycle"] == 4
    assert len(client.get(f"/complaints/{cid}/assignments").json()) == 3


def test_reopen_closed_complaint(client):
    cid = new_complaint(client, phone="0300-5")["id"]
    run_pipeline(client, cid)
    a = client.post(f"/complaints/{cid}/assignments", json={"team_id": ELEC_GULSHAN_TEAM}).json()
    client.patch(f"/assignments/{a['id']}", json={"status": "completed"})
    client.post(f"/complaints/{cid}/verifications", json={"result": "passed"})
    r = client.post(f"/complaints/{cid}/reopen", json={"reason": "Light is off again"}).json()
    assert r["next_action"] == "replan" and r["complaint"]["status"] == "reopened"
    assert r["complaint"]["current_cycle"] == 2 and r["complaint"]["closed_at"] is None
    assert client.post(f"/complaints/{cid}/reopen", json={"reason": "again please"}).status_code == 409


def test_demo_streetlight_scenario(client):
    """The exact hackathon scenario on seeded complaint MC-0011 using the demo simulators."""
    c = client.get("/complaints/MC-0011").json()
    assert c["raw_text"] == "Streetlight outside my house hasn't worked for 3 days."
    cid = c["id"]
    run_pipeline(client, cid)
    client.post(f"/complaints/{cid}/assignments", json={"team_id": ELEC_GULSHAN_TEAM, "technician_id": 1})
    assert client.post(f"/demo/complaints/{cid}/simulate-technician").json()["status"] == "verification_pending"
    r = client.post(f"/demo/complaints/{cid}/simulate-verification").json()
    assert r["verification"]["result"] == "failed" and r["next_action"] == "replan"
    client.post(f"/complaints/{cid}/decision", json={"priority": "critical", "department_id": 1, "is_replan": True})
    client.post(f"/complaints/{cid}/assignments", json={"team_id": ELEC_GULSHAN_TEAM, "technician_id": 2})
    client.post(f"/demo/complaints/{cid}/simulate-technician")
    r = client.post(f"/demo/complaints/{cid}/simulate-verification").json()
    assert r["verification"]["result"] == "passed" and r["complaint"]["status"] == "closed"
