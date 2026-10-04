"""
Agent 4 - Priority.

Priority is decided by EXPLICIT RULES (below), not by LLM imagination:
  1. The rule engine always computes a baseline priority + reason.
  2. In LLM mode the model sees the same guidelines and may adjust the baseline
     by at most ONE level. The result is clamped, so the LLM can never jump
     from LOW to CRITICAL.
"""
import re
from typing import Optional, Tuple

from app.graph.state import ComplaintState, log
from app.llm import run_structured
from app.models.schemas import PRIORITY_LEVELS, PriorityResult

AGENT = "Priority Agent"

GUIDELINES = """\
Priority guidelines (follow strictly):
- CRITICAL: a major water/sewer/drainage emergency (burst, flood, overflow) affecting MANY citizens,
  or a safety hazard where people were already injured/at immediate risk of death.
- HIGH: safety hazards (open manhole, exposed/live/fallen wires, sinkhole, collapse, fallen tree, flooding,
  sewage overflow) OR any service problem next to vulnerable places (school, hospital, clinic, children).
- MEDIUM: ordinary service disruption (streetlight not working, no water supply, blocked drain,
  uncollected garbage, damaged road, power outage) with no safety hazard.
- LOW: cosmetic / non-urgent (decorative lights, park benches, graffiti, faded paint, general enquiries).
"""

BASE_BY_CATEGORY = {
    "streetlight": "MEDIUM", "road": "MEDIUM", "water": "MEDIUM", "drainage": "MEDIUM",
    "garbage": "MEDIUM", "sanitation": "MEDIUM", "sewerage": "MEDIUM", "electricity": "MEDIUM",
    "parks": "LOW", "other": "LOW",
}

HAZARD = re.compile(
    r"open(?:ed)?\s+manholes?|manholes?\s+(?:is\s+|are\s+)?(?:open|uncovered)|uncovered\s+manholes?|"
    r"(?:missing|broken|stolen)\s+manhole\s+cover|manhole\s+cover\s+(?:is\s+)?(?:missing|broken|stolen)|"
    r"(?:exposed|live|hanging|sparking|fallen|loose)\s+(?:electric(?:al)?\s+)?(?:wires?|cables?)|"
    r"sparking|short\s+circuit|electrocut\w*|sinkhole|collaps\w+|gas\s+leak|fallen\s+(?:tree|pole)|"
    r"sewage\s+(?:is\s+)?overflow\w*|overflowing\s+sewage|sewer\s+overflow|flood\w*|burst\s+(?:water\s+)?pipe")
INJURY = re.compile(r"injur\w+|hurt|died|death|dead\s+body|electrocut\w*|fell\s+(?:in|into)|drown\w*|accident")
SENSITIVE = re.compile(r"\b(school|hospital|clinic|madrasa|madrassa|kindergarten|nursery|daycare|children|child|kids|elderly)\b")
EMERGENCY = re.compile(r"burst|flood\w*|overflow\w*|gushing|main\s+(?:line|pipe)|emergency|contaminat\w*")
MASS = re.compile(r"entire|whole|hundreds|dozens|many|several|residents|colony|neighbou?rhood|mohalla|locality|"
                  r"streets|main\s+road|market|all\s+(?:the\s+)?(?:houses|homes)")
COSMETIC = re.compile(r"decorative|ornamental|cosmetic|paint|graffiti|faded|bench(?:es)?|grass|lawn|trim|flowers?|"
                      r"fountain|signboard|aesthetic")
WATER_SEWER = {"water", "sewerage", "drainage"}


def _up(level: str, steps: int = 1, cap: str = "CRITICAL") -> str:
    i = min(PRIORITY_LEVELS.index(level) + steps, PRIORITY_LEVELS.index(cap))
    return PRIORITY_LEVELS[max(i, 0)]


def assess_priority_rules(category: str, subcategory: str, text: str) -> Tuple[str, str]:
    """Deterministic rule engine -> (priority, reason)."""
    t = text.lower()
    category = category or "other"
    hazard = HAZARD.search(t)
    sensitive = SENSITIVE.search(t)

    # 1) CRITICAL: emergency affecting many (water/sewer/drainage) or hazard with injury
    if category in WATER_SEWER and EMERGENCY.search(t) and MASS.search(t):
        return "CRITICAL", (f"Emergency ({EMERGENCY.search(t).group(0)}) in the {category} network "
                            f"affecting many citizens ({MASS.search(t).group(0)}).")
    if hazard and INJURY.search(t):
        return "CRITICAL", f"Safety hazard ({hazard.group(0)}) with reported injury or immediate danger to people."

    # 2) HIGH: safety hazard (+ sensitive location wording)
    if hazard:
        near = f" near a {sensitive.group(1)}" if sensitive else ""
        return "HIGH", f"{hazard.group(0).capitalize()}{near} presents a significant safety risk."

    # 3) cosmetic / non-urgent
    base = BASE_BY_CATEGORY.get(category, "MEDIUM")
    if COSMETIC.search(t):
        return "LOW", f"Cosmetic or non-urgent issue ({COSMETIC.search(t).group(0)}) with no safety impact."

    # 4) default by category, +1 level (max HIGH) near vulnerable places
    if sensitive:
        raised = _up(base, 1, cap="HIGH")
        return raised, (f"{category.capitalize()} issue near a {sensitive.group(1)}: raised from {base} "
                        f"because vulnerable people are affected.")
    return base, f"Routine {category} service issue with no safety hazard or large-scale impact detected."


def priority_node(state: ComplaintState) -> dict:
    text = f"{state.description} {state.location or ''}"
    baseline, base_reason = assess_priority_rules(state.category or "other", state.subcategory or "", text)
    final, reason = baseline, base_reason

    system = ("You assign a priority to a municipal complaint.\n" + GUIDELINES +
              f"\nA rule engine already computed the baseline priority: {baseline} ({base_reason}). "
              "Keep it unless the text clearly justifies exactly one level up or down. Explain briefly.")
    user = (f"Category: {state.category} / {state.subcategory}\nLocation: {state.location_text}\n"
            f"Complaint: {state.description}")
    llm_result, errors = run_structured(AGENT, PriorityResult, system, user)
    if llm_result is not None:
        i = PRIORITY_LEVELS.index(baseline)
        lo, hi = max(0, i - 1), min(len(PRIORITY_LEVELS) - 1, i + 1)
        j = min(max(PRIORITY_LEVELS.index(llm_result.priority), lo), hi)   # clamp to +-1 level
        final = PRIORITY_LEVELS[j]
        reason = llm_result.reason
        if final != llm_result.priority:
            reason += f" (Adjusted to {final} by policy guardrails; rule baseline was {baseline}.)"

    entry = log(AGENT, "Assigned priority", final, message="Priority determined",
                details={"reason": reason, "rule_baseline": baseline})
    return {"priority": final, "priority_reason": reason, "history": [entry], "errors": errors}
