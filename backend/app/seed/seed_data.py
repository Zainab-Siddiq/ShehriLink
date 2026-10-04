"""Seed / mock data. Run:  python -m app.seed.seed_data --reset"""
import sys
from datetime import timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from ..database import Base, SessionLocal, engine, init_db
from ..models import (AgentActivityLog, AgentResult, Assignment, Complaint, ComplaintRelation,
                      Department, StatusHistory, Team, Technician, User, Verification, Zone)
from ..utils import utcnow

DEPARTMENTS = [
    ("Electrical", "ELEC", "Streetlights, power faults, electrical hazards", ["streetlight", "power_outage", "electrical_hazard"]),
    ("Roads", "ROADS", "Potholes, road damage, traffic signals", ["pothole", "road_damage", "traffic_signal"]),
    ("Water", "WATER", "Water supply, leaks and sewage", ["water_leak", "no_water", "sewage"]),
    ("Sanitation", "SAN", "Garbage collection and drain cleaning", ["garbage", "drain_blockage"]),
    ("Parks", "PARKS", "Parks, trees and public green spaces", ["park_maintenance", "tree_fall"]),
]
ZONES = [
    ("Saddar", "SAD", "Old city centre", 24.8607, 67.0104),
    ("Clifton", "CLF", "Coastal residential area", 24.8138, 67.0300),
    ("Gulshan-e-Iqbal", "GUL", "Dense residential area", 24.9215, 67.0920),
    ("North Nazimabad", "NNZ", "Residential and commercial", 24.9400, 67.0400),
    ("Korangi", "KOR", "Industrial and residential", 24.8300, 67.1200),
    ("Malir", "MAL", "Eastern residential area", 24.8930, 67.2000),
]
# (team name, dept code, zone code, [(technician, phone, skills, available)])
TEAMS = [
    ("Electrical Team Gulshan", "ELEC", "GUL", [("Imran Qureshi", "0300-1000001", "streetlight,wiring", True), ("Bilal Ahmed", "0300-1000002", "streetlight,transformer", True)]),
    ("Electrical Team Saddar", "ELEC", "SAD", [("Faisal Mehmood", "0300-1000003", "wiring", True), ("Adnan Siddiqui", "0300-1000004", "streetlight", False)]),
    ("Electrical Team Clifton", "ELEC", "CLF", [("Kamran Ali", "0300-1000005", "streetlight", True), ("Zeeshan Raza", "0300-1000006", "transformer", True)]),
    ("Roads Team North", "ROADS", "NNZ", [("Hassan Javed", "0300-1000007", "asphalt", True), ("Usman Ghani", "0300-1000008", "asphalt,signals", True)]),
    ("Roads Team Korangi", "ROADS", "KOR", [("Tariq Hussain", "0300-1000009", "asphalt", True), ("Naveed Akhtar", "0300-1000010", "signals", True)]),
    ("Water Team Gulshan", "WATER", "GUL", [("Shahid Khan", "0300-1000011", "pipes", True), ("Rashid Mirza", "0300-1000012", "pipes,valves", True)]),
    ("Water Team Malir", "WATER", "MAL", [("Javed Iqbal", "0300-1000013", "pipes,sewage", True), ("Asif Lodhi", "0300-1000014", "sewage", False)]),
    ("Sanitation Team Saddar", "SAN", "SAD", [("Nadeem Baig", "0300-1000015", "garbage", True), ("Waqar Younis", "0300-1000016", "drains", True)]),
    ("Sanitation Team Korangi", "SAN", "KOR", [("Salman Farooq", "0300-1000017", "garbage", True), ("Arif Hussain", "0300-1000018", "drains", True)]),
    ("Parks Team Clifton", "PARKS", "CLF", [("Saeed Anwar", "0300-1000019", "trees", True), ("Mushtaq Ali", "0300-1000020", "gardening", True)]),
]

PATH = ["submitted", "processing", "assigned", "in_progress", "resolved", "verification_pending", "verified", "closed"]


def _path(upto, cycle=1):
    out = []
    for s in PATH[:upto]:
        by = "citizen" if s == "submitted" else ("technician" if s in ("in_progress", "resolved") else "system")
        out.append((s, cycle, by, None))
    return out


def seed(db: Session) -> dict:
    if db.query(Department).count() > 0:
        return {"seeded": False, "message": "Database already has data. Use POST /demo/reset to wipe and reseed."}
    now = utcnow()
    D, Z, T, TECH, users = {}, {}, {}, {}, {}

    for name, code, desc, cats in DEPARTMENTS:
        D[code] = Department(name=name, code=code, description=desc, categories=cats)
        db.add(D[code])
    for name, code, desc, lat, lng in ZONES:
        Z[code] = Zone(name=name, code=code, description=desc, center_lat=lat, center_lng=lng)
        db.add(Z[code])
    db.flush()
    for tname, dcode, zcode, techs in TEAMS:
        t = Team(name=tname, department_id=D[dcode].id, zone_id=Z[zcode].id, is_active=True)
        db.add(t)
        db.flush()
        T[tname] = t
        for n, ph, skills, avail in techs:
            TECH[n] = Technician(name=n, phone=ph, team_id=t.id, skills=skills, is_available=avail)
            db.add(TECH[n])
    db.flush()

    # ---------- helpers ----------
    def mk(text, zone, dept, category, priority, status, address, lat, lng, name, phone,
           days=0, hours=0, cycle=1, reopen=0, sub=None, sim=None, dup_of=None):
        created = now - timedelta(days=days, hours=hours)
        u = users.get(phone)
        if not u:
            u = User(name=name, phone=phone, role="citizen")
            db.add(u)
            db.flush()
            users[phone] = u
        c = Complaint(reference_no=f"TMP-{uuid4().hex[:10]}", citizen_id=u.id, citizen_name=name,
                      citizen_contact=phone, raw_text=text, address_text=address, latitude=lat, longitude=lng,
                      category=category, subcategory=sub, priority=priority, status=status,
                      zone_id=Z[zone].id if zone else None, department_id=D[dept].id if dept else None,
                      current_cycle=cycle, reopen_count=reopen, duplicate_of_id=dup_of.id if dup_of else None,
                      simulation_mode=sim, created_at=created, updated_at=created)
        db.add(c)
        db.flush()
        c.reference_no = f"MC-{c.id:04d}"
        db.add(AgentActivityLog(complaint_id=c.id, cycle=1, agent_name="system", step="intake",
                                event_type="action", message="Complaint received", created_at=created))
        return c, created

    def hist(c, steps, start):
        prev = None
        for i, (st, cyc, by, why) in enumerate(steps):
            db.add(StatusHistory(complaint_id=c.id, from_status=prev, to_status=st, cycle=cyc,
                                 changed_by=by, reason=why, created_at=start + timedelta(minutes=45 * i)))
            prev = st

    def log(c, at, agent, step, event, msg, cycle=1):
        db.add(AgentActivityLog(complaint_id=c.id, cycle=cycle, agent_name=agent, step=step,
                                event_type=event, message=msg, created_at=at))

    def result(c, at, cycle, stage, agent, summary, conf, payload):
        db.add(AgentResult(complaint_id=c.id, cycle=cycle, stage=stage, agent_name=agent, summary=summary,
                           confidence=conf, payload=payload, created_at=at))

    def assign(c, team, tech, cycle, status, at, prev=None, reason=None, notes=None, by="agent"):
        a = Assignment(complaint_id=c.id, cycle=cycle, team_id=T[team].id, technician_id=TECH[tech].id if tech else None,
                       department_id=T[team].department_id, status=status, assigned_by=by, reason=reason,
                       previous_assignment_id=prev.id if prev else None, assigned_at=at,
                       started_at=at + timedelta(hours=2) if status in ("in_progress", "completed", "failed") else None,
                       completed_at=at + timedelta(hours=5) if status in ("completed", "failed") else None,
                       resolution_notes=notes, created_at=at)
        db.add(a)
        db.flush()
        return a

    def verify(c, a, cycle, attempt, res, at, evidence, reason=None):
        db.add(Verification(complaint_id=c.id, assignment_id=a.id, cycle=cycle, attempt_number=attempt,
                            method="citizen_followup", result=res, confidence=0.92, evidence=evidence,
                            failure_reason=reason, verified_by="verifier_agent", created_at=at))

    def relate(c, other, rtype, score, reason, by="investigator"):
        db.add(ComplaintRelation(complaint_id=c.id, related_complaint_id=other.id, relation_type=rtype,
                                 similarity_score=score, reason=reason, detected_by=by))

    # ---------- 1. CLOSED streetlight (successful verification; later shows as RECURRING) ----------
    c1, t1 = mk("Streetlight on Street 7, Block 3 stopped working. The whole street is dark at night.",
                "GUL", "ELEC", "streetlight", "medium", "closed", "Street 7, Block 3, Gulshan-e-Iqbal",
                24.9210, 67.0925, "Hira Malik", "0311-1111111", days=6, sub="not_working")
    hist(c1, _path(8), t1)
    a = assign(c1, "Electrical Team Gulshan", "Imran Qureshi", 1, "completed", t1 + timedelta(hours=1),
               reason="Nearest available electrician in Gulshan", notes="Replaced faulty lamp and photocell")
    verify(c1, a, 1, 1, "passed", t1 + timedelta(days=2), "Citizen confirmed the light works")
    c1.resolved_at, c1.closed_at = t1 + timedelta(days=1, hours=6), t1 + timedelta(days=2)
    log(c1, t1 + timedelta(minutes=30), "decision_agent", "decision", "decision", "Priority MEDIUM, routed to Electrical")
    log(c1, t1 + timedelta(days=2), "verifier_agent", "verification", "decision", "Verification attempt #1: PASSED")

    # ---------- 2. IN-PROGRESS streetlight, HIGH priority (the 'master' complaint) ----------
    c2, t2 = mk("Streetlight outside Street 7 still off for 3 days. Children play here in the evening.",
                "GUL", "ELEC", "streetlight", "high", "in_progress", "House 5, Street 7, Block 3, Gulshan-e-Iqbal",
                24.9212, 67.0928, "Sana Tariq", "0312-2222222", days=3, sub="not_working")
    hist(c2, _path(4), t2)
    assign(c2, "Electrical Team Gulshan", "Bilal Ahmed", 1, "in_progress", t2 + timedelta(hours=2),
           reason="Same street was repaired 3 days earlier; assigning most experienced technician")
    result(c2, t2 + timedelta(minutes=5), 1, "understanding", "understanding_agent", "Streetlight outage for 3 days", 0.94,
           {"category": "streetlight", "subcategory": "not_working", "extracted": {"duration_days": 3}})
    result(c2, t2 + timedelta(minutes=20), 1, "decision", "decision_agent", "Safety risk + recurring fault -> HIGH", 0.9,
           {"priority": "high", "department_id": D["ELEC"].id})
    log(c2, t2 + timedelta(minutes=5), "understanding_agent", "understanding", "decision", "Classified as streetlight / not_working")
    log(c2, t2 + timedelta(minutes=12), "investigator", "investigation", "info", "Found RECURRING fault: same street fixed 3 days earlier")
    log(c2, t2 + timedelta(minutes=20), "decision_agent", "decision", "decision", "Priority HIGH: safety risk and recurring fault")
    log(c2, t2 + timedelta(hours=2), "dispatcher", "assignment", "action", "Assigned to Electrical Team Gulshan / Bilal Ahmed")
    relate(c2, c1, "recurring", 0.85, "Same street fixed 6 days ago; fault returned")

    # ---------- 3. DUPLICATE of #2 ----------
    c3, t3 = mk("Street light dead near Block 3 Street 7, please fix.", "GUL", "ELEC", "streetlight", "high",
                "duplicate", "Block 3, Street 7, Gulshan-e-Iqbal", 24.9211, 67.0927, "Omar Farooq", "0313-3333333",
                days=2, sub="not_working", dup_of=c2)
    hist(c3, [("submitted", 1, "citizen", None), ("processing", 1, "understanding_agent", None),
              ("duplicate", 1, "investigator", f"Duplicate of {c2.reference_no}")], t3)
    relate(c3, c2, "duplicate", 0.93, "Same street and category, reported 1 day apart")
    log(c3, t3 + timedelta(minutes=10), "investigator", "investigation", "decision",
        f"Confirmed duplicate of {c2.reference_no} (same street, same fault)")

    # ---------- 4. RELATED streetlight, MEDIUM, assigned ----------
    c4, t4 = mk("Streetlight on Street 9 keeps flickering at night.", "GUL", "ELEC", "streetlight", "medium",
                "assigned", "Street 9, Block 3, Gulshan-e-Iqbal", 24.9218, 67.0935, "Zainab Raza", "0314-4444444",
                days=2, sub="flickering")
    hist(c4, _path(3), t4)
    assign(c4, "Electrical Team Gulshan", "Imran Qureshi", 1, "assigned", t4 + timedelta(hours=1),
           reason="Lowest workload in Gulshan")
    relate(c4, c2, "related", 0.78, "Same block, same category, within 1 day")

    # ---------- 5. FAILED VERIFICATION -> REOPENED -> REASSIGNED (cycle 2) ----------
    c5, t5 = mk("Deep pothole on Main Road near Hyderi Market is damaging vehicles.", "NNZ", "ROADS", "pothole",
                "high", "in_progress", "Main Road near Hyderi Market, North Nazimabad", 24.9395, 67.0410,
                "Ali Hassan", "0315-5555555", days=5, cycle=2, reopen=1, sub="deep_pothole")
    hist(c5, _path(6) + [("verification_failed", 1, "verifier_agent", "Gravel patch washed away"),
                         ("reopened", 2, "verifier_agent", "Verification failed: Gravel patch washed away"),
                         ("processing", 2, "decision_agent", "Replanning"),
                         ("assigned", 2, "dispatcher", "Different team assigned"),
                         ("in_progress", 2, "technician", "Technician started work")], t5)
    a1 = assign(c5, "Roads Team North", "Hassan Javed", 1, "failed", t5 + timedelta(hours=1),
                reason="Closest roads team", notes="Filled with loose gravel")
    verify(c5, a1, 1, 1, "failed", t5 + timedelta(days=1), "Citizen sent photo: pothole is open again",
           "Pothole reopened after rain; gravel washed away")
    assign(c5, "Roads Team Korangi", "Tariq Hussain", 2, "in_progress", t5 + timedelta(days=1, hours=3), prev=a1,
           reason="Reassigned after failed verification; North team already tried once. Korangi has an asphalt crew.")
    result(c5, t5 + timedelta(minutes=20), 1, "decision", "decision_agent", "Vehicle damage risk -> HIGH", 0.88,
           {"priority": "high", "department_id": D["ROADS"].id})
    result(c5, t5 + timedelta(days=1, hours=1), 2, "replan", "decision_agent",
           "Previous team failed; choose a different team and use asphalt not gravel", 0.91,
           {"priority": "high", "department_id": D["ROADS"].id, "is_replan": True})
    log(c5, t5 + timedelta(hours=1), "dispatcher", "assignment", "action", "Assigned to Roads Team North / Hassan Javed")
    log(c5, t5 + timedelta(days=1), "verifier_agent", "verification", "decision",
        "Verification attempt #1: FAILED - pothole reopened after rain")
    log(c5, t5 + timedelta(days=1, minutes=5), "system", "reopen", "status_change", "Complaint reopened (cycle 2)", cycle=2)
    log(c5, t5 + timedelta(days=1, hours=1), "decision_agent", "replan", "decision",
        "Replanning: avoid Roads Team North, require asphalt repair", cycle=2)
    log(c5, t5 + timedelta(days=1, hours=3), "dispatcher", "assignment", "action",
        "Reassigned to Roads Team Korangi / Tariq Hussain", cycle=2)

    # ---------- 6. CRITICAL water leak, assigned ----------
    c6, t6 = mk("Main water pipe burst on Malir Halt road, water is flooding the street.", "MAL", "WATER",
                "water_leak", "critical", "assigned", "Malir Halt Road, Malir", 24.8935, 67.2010,
                "Farhan Sheikh", "0316-6666666", days=1, sub="pipe_burst")
    hist(c6, _path(3), t6)
    assign(c6, "Water Team Malir", "Javed Iqbal", 1, "assigned", t6 + timedelta(minutes=30),
           reason="CRITICAL: only available water crew in Malir")

    # ---------- 7. LOW priority garbage, closed ----------
    c7, t7 = mk("Garbage not collected from Empress Market lane for a week.", "SAD", "SAN", "garbage", "low",
                "closed", "Empress Market lane, Saddar", 24.8590, 67.0100, "Nida Aslam", "0317-7777777",
                days=7, sub="missed_collection")
    hist(c7, _path(8), t7)
    a = assign(c7, "Sanitation Team Saddar", "Nadeem Baig", 1, "completed", t7 + timedelta(hours=3),
               reason="Zone sanitation team", notes="Cleared backlog and scheduled daily pickup")
    verify(c7, a, 1, 1, "passed", t7 + timedelta(days=3), "Shopkeepers confirmed lane is clean")
    c7.resolved_at, c7.closed_at = t7 + timedelta(days=2), t7 + timedelta(days=3)

    # ---------- 8. CRITICAL sewage, still processing (not assigned yet) ----------
    c8, t8 = mk("Sewage overflowing near the Malir Cantt school gate. Children walk through it.", "MAL", "WATER",
                "sewage", "critical", "processing", "Near school gate, Malir Cantt", 24.8940, 67.2020,
                "Rubina Khan", "0318-8888888", hours=6, sub="overflow")
    hist(c8, _path(2), t8)
    relate(c8, c6, "related", 0.70, "Same area, both water-department incidents in last 24h")
    log(c8, t8 + timedelta(minutes=10), "decision_agent", "decision", "decision", "Priority CRITICAL: public health risk near school")

    # ---------- 9. LOW priority park bench, awaiting verification ----------
    c9, t9 = mk("Park bench broken near the Clifton Do Talwar playground.", "CLF", "PARKS", "park_maintenance",
                "low", "verification_pending", "Do Talwar playground, Clifton", 24.8120, 67.0310,
                "Maryam Qadir", "0319-9999999", days=2, sub="broken_bench")
    hist(c9, _path(6), t9)
    assign(c9, "Parks Team Clifton", "Mushtaq Ali", 1, "completed", t9 + timedelta(hours=2),
           reason="Zone parks team", notes="Replaced two wooden slats")

    # ---------- 10. HIGH priority, brand new (no agent has touched it) ----------
    mk("Power outage in the entire lane near Bohri Bazaar since morning.", "SAD", None, None, "high", "submitted",
       "Lane behind Bohri Bazaar, Saddar", 24.8600, 67.0120, "Kashif Mir", "0320-1010101", hours=1)

    # ---------- 11. DEMO TARGET: the broken streetlight (fresh, will FAIL first verification) ----------
    c11, t11 = mk("Streetlight outside my house hasn't worked for 3 days.", None, None, None, None, "submitted",
                  "House 12, Street 7, Block 3, Gulshan-e-Iqbal", 24.9213, 67.0926, "Ayesha Khan", "0333-3333333",
                  hours=0, sim="fail_first_verification")
    hist(c11, _path(1), t11)

    db.flush()
    return {
        "seeded": True,
        "departments": db.query(Department).count(),
        "zones": db.query(Zone).count(),
        "teams": db.query(Team).count(),
        "technicians": db.query(Technician).count(),
        "complaints": db.query(Complaint).count(),
        "demo_complaint": {"id": c11.id, "reference_no": c11.reference_no, "simulation_mode": c11.simulation_mode},
    }


if __name__ == "__main__":
    init_db()
    if "--reset" in sys.argv:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        print(seed(session))
        session.commit()
    finally:
        session.close()
