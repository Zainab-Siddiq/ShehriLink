"""Unit tests: each agent on its own (rule-based mode) + LLM fallback behaviour."""
import pytest

from app.agents.assignment import assignment_node, select_team
from app.agents.classification import classification_node, classify_with_rules
from app.agents.department import department_node
from app.agents.history import history_node
from app.agents.location import location_node
from app.agents.priority import assess_priority_rules, priority_node
from app.agents.verification import judge_with_rules, verification_node
from app.data import mock_database
from app.data.mock_data import parse_scenario
from app.graph.state import ComplaintState
from app.models.schemas import ClassificationResult, PriorityResult
from app.utils.similarity import text_similarity


def S(description="x", **kw) -> ComplaintState:
    return ComplaintState(complaint_id="T-1", description=description, **kw)


# ----------------------------------------------------------- classification
@pytest.mark.parametrize("text,category", [
    ("Streetlight outside my house has not worked for three days.", "streetlight"),
    ("Huge pothole on the road near my school", "road"),
    ("No water supply since morning", "water"),
    ("The drain is blocked and rainwater is stuck", "drainage"),
    ("Garbage has not been collected for a week", "garbage"),
    ("Mosquito spraying needed, dengue cases rising", "sanitation"),
    ("Broken swing in the children's park", "parks"),
    ("Sewage is overflowing", "sewerage"),
    ("There is an open manhole on the road", "sewerage"),
    ("Transformer sparking, power cut since last night", "electricity"),
    ("I would like to know the office timings", "other"),
])
def test_classification_categories(text, category):
    assert classify_with_rules(text).category == category


def test_classification_confidence_and_subcategory():
    r = classify_with_rules("Streetlight outside my house has not worked for three days.")
    assert r.subcategory == "streetlight_not_working"
    assert 0.9 <= r.confidence <= 1.0


def test_classification_node_logs_history():
    out = classification_node(S("Streetlight not working"))
    assert out["category"] == "streetlight"
    assert out["history"][0].agent == "Classification Agent"
    assert out["history"][0].timestamp


# ----------------------------------------------------------------- location
def test_location_found_and_zone_mapped():
    out = location_node(S("Streetlight outside my house in Hayatabad Phase 3", location="Hayatabad Phase 3"))
    assert out["area"] == "Hayatabad"
    assert out["zone"] == "Zone B"
    assert out["location_text"] == "Hayatabad Phase 3"


def test_location_from_description_only():
    out = location_node(S("Garbage is piling up in Gulbahar Street 4"))
    assert (out["area"], out["zone"]) == ("Gulbahar", "Zone C")


def test_location_missing_is_unknown_not_invented():
    out = location_node(S("Streetlight outside my house is broken"))
    assert out["area"] == "unknown" and out["zone"] == "unknown"
    assert out["location_confidence"] == 0.0


def test_location_unrecognised_text_keeps_area_unknown():
    out = location_node(S("broken light", location="Mars Colony"))
    assert out["area"] == "unknown" and out["location_text"] == "Mars Colony"


# ------------------------------------------------------------------ duplicate
def _dup_state(text, area, loc_text, category="streetlight", cid="T-9"):
    return ComplaintState(complaint_id=cid, description=text, category=category, area=area, location_text=loc_text)


def test_duplicate_detected_with_different_wording():
    s = _dup_state("Streetlight outside my house in Hayatabad Phase 3 hasn't worked for three days.",
                   "Hayatabad", "Hayatabad Phase 3")
    out = history_node(s)
    assert out["duplicate"] is True and out["related_complaint_id"] == "102"


def test_not_duplicate_in_other_area():
    out = history_node(_dup_state("Streetlight is broken in Saddar", "Saddar", "Saddar"))
    assert out["duplicate"] is False


def test_not_duplicate_in_other_phase():
    out = history_node(_dup_state("Streetlight broken near Hayatabad Phase 5", "Hayatabad", "Hayatabad Phase 5"))
    assert out["duplicate"] is False


def test_closed_complaints_are_ignored():
    # complaint 109 (University Town streetlight) is CLOSED
    out = history_node(_dup_state("Streetlight not working in University Town", "University Town", "University Town"))
    assert out["duplicate"] is False


def test_similarity_is_not_exact_matching():
    assert text_similarity("Streetlight broken", "streetlight has stopped working") > 0.9
    assert text_similarity("Streetlight broken", "garbage piled up") == 0.0


# ------------------------------------------------------------------- priority
@pytest.mark.parametrize("category,text,expected", [
    ("streetlight", "Streetlight not working in front of my house", "MEDIUM"),
    ("sewerage", "Open manhole right outside the primary school", "HIGH"),
    ("parks", "Broken decorative light in the park", "LOW"),
    ("sewerage", "Sewage overflow flooding the main road, hundreds of residents affected", "CRITICAL"),
    ("water", "Main water pipe burst, whole colony without water and street flooded", "CRITICAL"),
    ("streetlight", "Streetlight not working near the hospital gate", "HIGH"),
    ("electricity", "Live wire hanging low, a child was injured", "CRITICAL"),
    ("garbage", "Garbage not collected", "MEDIUM"),
])
def test_priority_rules(category, text, expected):
    priority, reason = assess_priority_rules(category, "", text)
    assert priority == expected
    assert reason


def test_priority_reason_matches_spec_example():
    _, reason = assess_priority_rules("sewerage", "open_manhole", "Open manhole near a school")
    assert reason == "Open manhole near a school presents a significant safety risk."


# ----------------------------------------------------------------- department
def test_department_mapping():
    expected = {"streetlight": "Electrical Department", "road": "Roads Department", "water": "Water Department",
                "drainage": "Drainage Department", "garbage": "Sanitation Department",
                "parks": "Parks Department", "sewerage": "Sewerage Department",
                "other": "General Services Department"}
    for cat, dept in expected.items():
        assert department_node(S(category=cat, subcategory=f"{cat}_x"))["department"] == dept


# ----------------------------------------------------------------- assignment
def test_assignment_prefers_zone_team():
    out = assignment_node(S(department="Electrical Department", zone="Zone B"))
    assert out["assigned_team"] == "ELEC-B"
    assert out["assignment_reason"] == "Electrical Team B handles Electrical Department complaints in Zone B."


def test_assignment_skips_unavailable_team():
    # ELEC-C is marked unavailable -> rapid response team takes Zone C
    assert assignment_node(S(department="Electrical Department", zone="Zone C"))["assigned_team"] == "ELEC-RR"


def test_assignment_skips_team_at_capacity():
    # ROAD-B is fully booked
    assert assignment_node(S(department="Roads Department", zone="Zone B"))["assigned_team"] == "ROAD-RR"


def test_assignment_unknown_zone_still_assigns():
    assert assignment_node(S(department="Water Department", zone="unknown"))["assigned_team"] == "WATR-RR"


def test_assignment_avoids_failed_teams():
    r = select_team("Electrical Department", "Zone B", failed_teams=["ELEC-B"])
    assert r.assigned_team == "ELEC-RR"


def test_assignment_no_team_returns_escalation():
    class Empty(mock_database.MockRepository):
        def get_teams(self, department):
            return []
    mock_database.set_repository(Empty())
    out = assignment_node(S(department="Electrical Department", zone="Zone B"))
    assert out["assigned_team"] is None
    assert out["history"][0].status == "failed"


# --------------------------------------------------------------- verification
def test_judge_rules():
    ok = judge_with_rules("streetlight", "Streetlight is working.")
    assert ok.resolved and ok.verification_status == "verified"
    assert ok.reason == "The reported issue is confirmed resolved."
    bad = judge_with_rules("streetlight", "Streetlight is still not working.")
    assert not bad.resolved and bad.verification_status == "failed"
    assert bad.reason == "Citizen verification indicates the streetlight remains non-functional."


def test_scenario_parser():
    assert parse_scenario("success") == 0 and parse_scenario("fail_once") == 1
    assert parse_scenario("fail_twice") == 2 and parse_scenario("fail_5") == 5
    assert parse_scenario("always_fail") is None
    with pytest.raises(ValueError):
        parse_scenario("banana")


def test_verification_node_success_and_failure():
    base = dict(category="streetlight", assigned_team="ELEC-B", assigned_team_name="Electrical Team B")
    ok = verification_node(S(verification_scenario="success", **base))
    assert ok["resolved"] is True and ok["verification_status"] == "verified"
    bad = verification_node(S(verification_scenario="always_fail", **base))
    assert bad["resolved"] is False and bad["retry_count"] == 1
    assert [h.status for h in bad["history"]] == ["success", "failed"]


# ------------------------------------------------- LLM mode & graceful fallback
@pytest.fixture
def llm_on(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("API_KEY", "sk-test-not-real")


def test_llm_failure_falls_back_to_rules(llm_on, monkeypatch):
    from app.llm import LLMClient, LLMError

    def boom(self, schema, system, user):
        raise LLMError("simulated outage")
    monkeypatch.setattr(LLMClient, "structured", boom)

    out = classification_node(S("Streetlight not working"))
    assert out["category"] == "streetlight"                     # rules took over
    assert "simulated outage" in out["errors"][0]               # failure is reported, not raised


def test_llm_result_is_used_when_available(llm_on, monkeypatch):
    from app.llm import LLMClient
    monkeypatch.setattr(LLMClient, "structured", lambda self, schema, system, user:
                        ClassificationResult(category="road", subcategory="road_pothole", confidence=0.88))
    out = classification_node(S("anything"))
    assert out["category"] == "road" and out["errors"] == []


def test_llm_cannot_jump_priority_more_than_one_level(llm_on, monkeypatch):
    from app.llm import LLMClient
    monkeypatch.setattr(LLMClient, "structured", lambda self, schema, system, user:
                        PriorityResult(priority="CRITICAL", reason="Looks scary"))
    out = priority_node(S("Streetlight not working", category="streetlight", subcategory="streetlight_not_working"))
    assert out["priority"] == "HIGH"          # baseline MEDIUM + at most one level
    assert "guardrails" in out["priority_reason"]


def test_llm_provider_objects_can_be_built():
    """Smoke test: provider classes exist and construct with a dummy key (no network call)."""
    from app.llm import _build_chat_model
    assert _build_chat_model("openai", "gpt-4o-mini", "sk-dummy", "", 5.0) is not None
    assert _build_chat_model("anthropic", "claude-haiku-4-5-20251001", "sk-dummy", "", 5.0) is not None
