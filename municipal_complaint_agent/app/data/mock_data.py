"""
Realistic MOCK municipal data (illustrative - based on Peshawar-style areas).

Everything the agents need from "the city" lives here: departments, zones,
areas, teams, existing complaints, verification scripts and demo scenarios.
A teammate replaces this with PostgreSQL by implementing `ComplaintRepository`
in `mock_database.py` - agents never import this file directly.
"""
import re
from typing import Dict, List, Optional

# ------------------------------------------------------------------ departments
# code is used to build team ids (e.g. ELEC-B)
DEPARTMENTS = [
    {"code": "ELEC", "name": "Electrical Department", "short": "Electrical"},
    {"code": "ROAD", "name": "Roads Department", "short": "Roads"},
    {"code": "WATR", "name": "Water Department", "short": "Water"},
    {"code": "DRAN", "name": "Drainage Department", "short": "Drainage"},
    {"code": "SANI", "name": "Sanitation Department", "short": "Sanitation"},
    {"code": "PARK", "name": "Parks Department", "short": "Parks"},
    {"code": "SEWR", "name": "Sewerage Department", "short": "Sewerage"},
    {"code": "GENL", "name": "General Services Department", "short": "General Services"},
]

# complaint category -> responsible department
CATEGORY_TO_DEPARTMENT = {
    "streetlight": "Electrical Department",
    "electricity": "Electrical Department",
    "road": "Roads Department",
    "water": "Water Department",
    "drainage": "Drainage Department",
    "garbage": "Sanitation Department",
    "sanitation": "Sanitation Department",
    "parks": "Parks Department",
    "sewerage": "Sewerage Department",
    "other": "General Services Department",
}

# ------------------------------------------------------------------ zones/areas
ZONES = ["Zone A", "Zone B", "Zone C", "Zone D"]

# area -> zone (the Location Agent maps extracted areas through this table)
AREAS: Dict[str, str] = {
    "University Town": "Zone A",
    "Canal Town": "Zone A",
    "Tehkal": "Zone A",
    "Hayatabad": "Zone B",
    "Regi Model Town": "Zone B",
    "Industrial Estate": "Zone B",
    "Saddar": "Zone C",
    "Gulbahar": "Zone C",
    "Peshawar Cantt": "Zone C",
    "Ring Road": "Zone D",
    "Warsak Road": "Zone D",
    "Charsadda Road": "Zone D",
}

# alternative spellings -> canonical area name
AREA_ALIASES = {
    "univ town": "University Town",
    "uni town": "University Town",
    "regi": "Regi Model Town",
    "cantt": "Peshawar Cantt",
    "cantonment": "Peshawar Cantt",
    "saddar bazaar": "Saddar",
}

# ------------------------------------------------------------------------ teams
# One team per department per zone (A-D) + one all-zone "Rapid Response" team.
# `available=False` or `active_tasks >= capacity` makes a team ineligible.
def _build_teams() -> List[dict]:
    teams = []
    for dept in DEPARTMENTS:
        for letter, zone in zip("ABCD", ZONES):
            teams.append({
                "team_id": f"{dept['code']}-{letter}",
                "name": f"{dept['short']} Team {letter}",
                "department": dept["name"],
                "zone": zone,
                "available": True,
                "active_tasks": (ord(letter) - ord("A")) % 3,   # deterministic fake workload
                "capacity": 5,
            })
        teams.append({
            "team_id": f"{dept['code']}-RR",
            "name": f"{dept['short']} Rapid Response Team",
            "department": dept["name"],
            "zone": "ALL",
            "available": True,
            "active_tasks": 1,
            "capacity": 5,
        })
    return teams


TEAMS: List[dict] = _build_teams()

# A few teams made unavailable to show that availability is respected.
for _t in TEAMS:
    if _t["team_id"] == "ELEC-C":
        _t["available"] = False          # on leave
    if _t["team_id"] == "ROAD-B":
        _t["active_tasks"] = _t["capacity"]  # fully booked

# ------------------------------------------------------------ existing complaints
# Used by the History/Duplicate Agent.
EXISTING_COMPLAINTS: List[dict] = [
    {"complaint_id": "101", "description": "Large pothole on the main road near the bus stop in Saddar",
     "category": "road", "area": "Saddar", "location_text": "Saddar", "status": "OPEN"},
    {"complaint_id": "102", "description": "Streetlight broken near Hayatabad Phase 3",
     "category": "streetlight", "area": "Hayatabad", "location_text": "Hayatabad Phase 3", "status": "OPEN"},
    {"complaint_id": "103", "description": "Garbage piled up in Gulbahar street 4 for several days",
     "category": "garbage", "area": "Gulbahar", "location_text": "Gulbahar Street 4", "status": "OPEN"},
    {"complaint_id": "104", "description": "Sewage overflowing onto the road in Regi Model Town",
     "category": "sewerage", "area": "Regi Model Town", "location_text": "Regi Model Town", "status": "OPEN"},
    {"complaint_id": "105", "description": "No water supply in University Town Block C since morning",
     "category": "water", "area": "University Town", "location_text": "University Town Block C", "status": "OPEN"},
    {"complaint_id": "106", "description": "Drain blocked outside the shops in Saddar",
     "category": "drainage", "area": "Saddar", "location_text": "Saddar", "status": "OPEN"},
    {"complaint_id": "107", "description": "Park benches broken in Canal Town park",
     "category": "parks", "area": "Canal Town", "location_text": "Canal Town park", "status": "OPEN"},
    {"complaint_id": "108", "description": "Streetlight flickering on Ring Road near the flyover",
     "category": "streetlight", "area": "Ring Road", "location_text": "Ring Road", "status": "OPEN"},
    # CLOSED complaints are ignored by duplicate detection.
    {"complaint_id": "109", "description": "Streetlight not working in University Town",
     "category": "streetlight", "area": "University Town", "location_text": "University Town", "status": "CLOSED"},
]

# ------------------------------------------------- mock verification responses
# Scenario names (controllable from the API request or the VERIFICATION_SCENARIO env var):
#   success      -> first verification passes
#   fail_once    -> 1st verification fails, 2nd passes
#   fail_twice   -> 1st and 2nd fail, 3rd passes
#   fail_<n>     -> first n verifications fail, then pass
#   always_fail  -> never passes (demonstrates escalation)
#   manual       -> no simulation: the complaint stays open until an officer verifies it
SCENARIO_HELP = {
    "manual": "Complaint stays open (team assigned) until an officer verifies it by hand.",
    "success": "Verification passes on the first attempt.",
    "fail_once": "First verification fails -> replan -> second passes.",
    "fail_twice": "Two failures, then success.",
    "always_fail": "Every verification fails -> escalation after max retries.",
}


def parse_scenario(name: str) -> Optional[int]:
    """Return how many verifications FAIL before success (None = always fail)."""
    n = (name or "success").strip().lower()
    if n in ("success", "manual"):      # "manual" never reaches the mock provider (see await_verification_node)
        return 0
    if n == "fail_once":
        return 1
    if n == "fail_twice":
        return 2
    if n == "always_fail":
        return None
    m = re.fullmatch(r"fail_(\d+)", n)
    if m:
        return int(m.group(1))
    raise ValueError(
        f"Unknown verification scenario '{name}'. Use manual, success, fail_once, fail_twice, fail_<n> or always_fail.")


# What the field team reports after "fixing" the problem.
TEAM_REPORTS = {
    "streetlight": "Streetlight repaired.",
    "road": "Road surface repaired.",
    "water": "Water supply line repaired.",
    "drainage": "Drain cleared.",
    "garbage": "Garbage collected.",
    "sanitation": "Area cleaned.",
    "parks": "Park issue fixed.",
    "sewerage": "Sewer line cleared.",
    "electricity": "Electrical fault repaired.",
    "other": "Complaint resolved.",
}

# Simulated citizen follow-up: (positive answer, negative answer)
CITIZEN_FEEDBACK = {
    "streetlight": ("Streetlight is working.", "Streetlight is still not working."),
    "road": ("The road has been repaired.", "The road is still damaged."),
    "water": ("Water supply has been restored.", "Water is still not coming."),
    "drainage": ("The drain is clear now.", "The drain is still blocked."),
    "garbage": ("The garbage has been cleared.", "The garbage is still lying there."),
    "sanitation": ("The area has been cleaned.", "The area is still dirty."),
    "parks": ("The park issue has been fixed.", "The park issue is still not fixed."),
    "sewerage": ("The sewer problem is fixed.", "The sewer is still overflowing."),
    "electricity": ("Power has been restored.", "Power is still not restored."),
    "other": ("The issue has been resolved.", "The issue is still not resolved."),
}

# Used to build the human-readable failure reason.
FAILURE_PHRASES = {
    "streetlight": "the streetlight remains non-functional",
    "road": "the road remains damaged",
    "water": "the water supply remains unrestored",
    "drainage": "the drain remains blocked",
    "garbage": "the garbage remains uncollected",
    "sanitation": "the area remains unclean",
    "parks": "the park issue remains unfixed",
    "sewerage": "the sewer problem persists",
    "electricity": "the power problem persists",
    "other": "the issue remains unresolved",
}

# ---------------------------------------------------------------- demo scenarios
# Used by run.py, GET /api/scenarios and the tests.
DEMO_SCENARIOS: List[dict] = [
    {
        "key": "normal",
        "title": "Test 1 - Normal: broken streetlight -> assigned -> verified -> closed",
        "request": {
            "complaint_id": "C-1001",
            "description": "The streetlight in front of my house in University Town has been broken for two days.",
            "location": "University Town",
            "verification_scenario": "success",
        },
    },
    {
        "key": "high_priority",
        "title": "Test 2 - High priority: open manhole near a school",
        "request": {
            "complaint_id": "C-1002",
            "description": "There is an open manhole right outside Government Primary School in Saddar. Children could fall in.",
            "location": "Saddar",
            "verification_scenario": "success",
        },
    },
    {
        "key": "duplicate",
        "title": "Test 3 - Duplicate: similar to existing complaint #102",
        "request": {
            "complaint_id": "C-1003",
            "description": "Streetlight outside my house in Hayatabad Phase 3 hasn't worked for three days.",
            "location": "Hayatabad Phase 3",
            "verification_scenario": "success",
        },
    },
    {
        "key": "failed_verification",
        "title": "Test 4 - Failed verification: fixed -> fails -> replan -> reassign -> verified",
        "request": {
            "complaint_id": "C-1004",
            "description": "The streetlight in front of my house in Canal Town is not working since yesterday.",
            "location": "Canal Town",
            "verification_scenario": "fail_once",
        },
    },
    {
        "key": "max_retry",
        "title": "Test 5 - Maximum retries: verification keeps failing -> escalation",
        "request": {
            "complaint_id": "C-1005",
            "description": "There has been no water supply in our street in Regi Model Town for two days.",
            "location": "Regi Model Town",
            "verification_scenario": "always_fail",
        },
    },
]
