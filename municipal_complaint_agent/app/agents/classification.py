"""
Agent 1 - Classification.

LLM mode : structured output (ClassificationResult).
Mock mode: keyword scoring (also the automatic fallback if the LLM fails).
"""
import re
from typing import Dict, List, Tuple

from app.graph.state import ComplaintState, log
from app.llm import run_structured
from app.models.schemas import CATEGORIES, ClassificationResult

AGENT = "Classification Agent"

# (regex, weight). Specific phrases weigh more than general words.
CATEGORY_KEYWORDS: Dict[str, List[Tuple[str, int]]] = {
    "streetlight": [(r"street\s*-?\s*(?:light|lamp)s?", 3), (r"streetlamps?", 3), (r"lamp\s*posts?", 3),
                    (r"light\s+pole", 2), (r"street\s+(?:is\s+)?dark", 2)],
    "sewerage": [(r"manholes?", 3), (r"sewage", 3), (r"sewer(?:age)?", 3), (r"septic", 2)],
    "drainage": [(r"drain(?:age|s)?\b", 3), (r"gutters?", 3), (r"nalas?|nullahs?", 3),
                 (r"rain\s*water", 2), (r"water\s*-?\s*logging|waterlogged", 3), (r"blocked\s+drain", 3)],
    "garbage": [(r"garbage", 3), (r"trash", 3), (r"rubbish", 3), (r"dustbins?|dumpsters?", 3),
                (r"kachra", 3), (r"waste", 2), (r"litter", 2)],
    "sanitation": [(r"sanitation", 3), (r"public\s+toilets?|toilets?", 2), (r"sweep(?:ing|er|ers)?|swept", 3),
                   (r"mosquito|fumigation|dengue", 3), (r"stray\s+(?:dogs?|animals?)", 2),
                   (r"dirty\s+(?:street|area|road)", 2), (r"cleanliness|unclean", 2)],
    "parks": [(r"\bparks?\b", 3), (r"gardens?", 2), (r"playground", 3), (r"benches", 2),
              (r"jogging\s+track", 3), (r"fountain", 2), (r"lawn|grass", 2), (r"swings?", 2)],
    "road": [(r"potholes?", 3), (r"road", 2), (r"asphalt|pavement|footpath|sidewalk", 2),
             (r"speed\s*breakers?", 3), (r"traffic\s+sign|road\s+marking", 2), (r"cracks?\b", 1), (r"damaged\s+road", 3)],
    "water": [(r"water\s+supply", 3), (r"no\s+water", 3), (r"\btaps?\b", 2), (r"water\s+pipe|pipeline|water\s+line", 3),
              (r"water\s+pressure", 3), (r"dirty\s+water|contaminated\s+water|muddy\s+water", 3),
              (r"water\s+tanker", 3), (r"tube\s*well", 3), (r"\bwater\b", 1), (r"leak(?:age|ing|s)?", 1)],
    "electricity": [(r"electricity", 3), (r"power\s+(?:outage|cut|failure)|load\s*shedding", 3),
                    (r"transformer", 3), (r"electric(?:al)?\s+(?:pole|wire|wires|cable)", 3),
                    (r"\bwires?\b|\bcables?\b", 1), (r"voltage", 2), (r"\bpower\b", 1), (r"electric", 1)],
}

# subcategory -> keywords. The FIRST entry of every category is the default.
SUBCATEGORIES: Dict[str, Dict[str, str]] = {
    "streetlight": {"streetlight_not_working": r".", "streetlight_flickering": r"flicker|blink",
                    "streetlight_damaged_pole": r"pole.*(?:damag|bent|lean|fallen)|(?:damag|bent|lean|fallen).*pole"},
    "road": {"road_damage": r".", "road_pothole": r"pothole|\bholes?\b", "road_sign_marking": r"sign|marking",
             "road_footpath": r"footpath|sidewalk|pavement"},
    "water": {"water_supply_issue": r".", "water_leakage": r"leak|burst", "water_contamination": r"dirty|contaminat|muddy|smell"},
    "drainage": {"drain_blocked": r".", "waterlogging": r"water\s*-?\s*logg|flood|rain"},
    "garbage": {"garbage_not_collected": r".", "garbage_dumping": r"dump|burn"},
    "sanitation": {"sanitation_general": r".", "street_sweeping": r"sweep|swept", "pest_control": r"mosquito|fumigation|dengue|stray",
                   "public_toilet": r"toilet"},
    "parks": {"park_maintenance": r".", "park_equipment_damaged": r"swing|bench|broken|damag", "park_lighting": r"light"},
    "sewerage": {"sewer_overflow": r".", "open_manhole": r"manhole", "sewer_blockage": r"block|choke"},
    "electricity": {"electricity_outage": r".", "electrical_hazard": r"spark|exposed|hanging|live|fallen",
                    "transformer_issue": r"transformer"},
    "other": {"other_general": r"."},
}


def classify_with_rules(description: str) -> ClassificationResult:
    text = description.lower()
    scores = {}
    for category, patterns in CATEGORY_KEYWORDS.items():
        scores[category] = sum(w for pat, w in patterns if re.search(pat, text))
    best = max(scores, key=lambda c: scores[c])         # ties: first in dict order wins
    if scores[best] == 0:
        return ClassificationResult(category="other", subcategory="other_general", confidence=0.4)
    sub = list(SUBCATEGORIES[best])[0]                  # default
    for name, pattern in list(SUBCATEGORIES[best].items())[1:]:
        if re.search(pattern, text):
            sub = name
            break
    confidence = min(0.97, 0.65 + 0.1 * scores[best])
    return ClassificationResult(category=best, subcategory=sub, confidence=round(confidence, 2))


def _llm_prompt() -> str:
    subs = "\n".join(f"  - {c}: {', '.join(s)}" for c, s in SUBCATEGORIES.items())
    return (
        "You classify citizen complaints for a municipal corporation.\n"
        f"Allowed categories: {', '.join(CATEGORIES)}.\n"
        "Pick exactly ONE category. Use 'other' only if nothing fits.\n"
        "Preferred subcategories (snake_case):\n" + subs + "\n"
        "Note: open/broken manholes and sewage belong to 'sewerage'. "
        "Street lights belong to 'streetlight' (not 'electricity').\n"
        "confidence is between 0 and 1."
    )


def classification_node(state: ComplaintState) -> dict:
    result, errors = run_structured(AGENT, ClassificationResult, _llm_prompt(),
                                    f"Complaint: {state.description}")
    if result is not None:
        # Guard: keep subcategory tidy and consistent with the category.
        allowed = list(SUBCATEGORIES.get(result.category, {"other_general": ""}))
        sub = result.subcategory.strip().lower().replace(" ", "_")
        result = result.model_copy(update={"subcategory": sub if sub else allowed[0]})
    else:
        result = classify_with_rules(state.description)

    entry = log(AGENT, "Classified complaint", result.category, message="Classification completed",
                details={"subcategory": result.subcategory, "confidence": result.confidence})
    return {
        "category": result.category,
        "subcategory": result.subcategory,
        "classification_confidence": result.confidence,
        "history": [entry],
        "errors": errors,
    }
