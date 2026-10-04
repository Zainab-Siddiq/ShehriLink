"""
Agent 2 - Location.

The LLM (or regex fallback) only EXTRACTS the area text. The zone always comes
from the municipal area->zone table, so the model can never invent a zone.
If no known area is found the location is marked "unknown" - never invented.
"""
import re
from typing import Optional

from app.data.mock_database import get_repository
from app.graph.state import ComplaintState, log
from app.llm import run_structured
from app.models.schemas import LocationExtraction, LocationResult

AGENT = "Location Agent"
UNKNOWN = "unknown"

# Optional "Phase 3", "Block C", "Sector F-7", "Street 4" next to the area name.
_DETAIL = r"(?:phase|sector|block|street|gali|lane)\s*[-#]?\s*[a-z0-9][a-z0-9-]*"


def _find_area(text: str, areas: dict, aliases: dict) -> Optional[tuple]:
    """Return (canonical_area, matched_span_text) or None. Longest names first."""
    lowered = text.lower()
    candidates = [(a.lower(), a) for a in areas] + [(al, canon) for al, canon in aliases.items()]
    for key, canonical in sorted(candidates, key=lambda x: -len(x[0])):
        m = re.search(rf"(?:{_DETAIL}[,\s]+)?\b{re.escape(key)}\b(?:[,\s]+{_DETAIL})?", lowered)
        if m:
            span = text[m.start():m.end()].strip(" ,")
            return canonical, span
    return None


def extract_location_with_rules(state: ComplaintState, areas: dict, aliases: dict) -> LocationExtraction:
    # 1) the explicit location field is the best source, 2) then the description
    for source, conf in ((state.location or "", 0.92), (state.description, 0.85)):
        found = _find_area(source, areas, aliases) if source else None
        if found:
            area, span = found
            return LocationExtraction(area=area, location_text=span.title() if span.islower() else span,
                                      confidence=conf)
    # Not a known area: keep the citizen's text if there is one, but area stays unknown.
    if state.location and state.location.strip():
        return LocationExtraction(area=UNKNOWN, location_text=state.location.strip(), confidence=0.3)
    return LocationExtraction(area=UNKNOWN, location_text=UNKNOWN, confidence=0.0)


def location_node(state: ComplaintState) -> dict:
    repo = get_repository()
    areas, aliases = repo.get_areas(), repo.get_area_aliases()

    system = (
        "Extract the location of a municipal complaint.\n"
        f"Known areas: {', '.join(areas)}.\n"
        "Set `area` to one known area (exact spelling) or 'unknown' if none is mentioned. "
        "Set `location_text` to the most specific location phrase from the text "
        "(e.g. 'Hayatabad Phase 3'), or 'unknown'. NEVER invent a location."
    )
    user = f"Complaint: {state.description}\nLocation field: {state.location or 'not provided'}"
    extracted, errors = run_structured(AGENT, LocationExtraction, system, user)

    if extracted is not None:
        # Normalise the LLM's area to a canonical known area; otherwise unknown.
        lookup = {a.lower(): a for a in areas}
        lookup.update({k: v for k, v in aliases.items()})
        canonical = lookup.get(extracted.area.strip().lower())
        extracted = extracted.model_copy(update={"area": canonical or UNKNOWN})
        if extracted.area == UNKNOWN:
            extracted = extracted.model_copy(update={"confidence": min(extracted.confidence, 0.3)})
    else:
        extracted = extract_location_with_rules(state, areas, aliases)

    zone = areas.get(extracted.area, UNKNOWN)
    result = LocationResult(area=extracted.area, zone=zone, location_text=extracted.location_text,
                            confidence=extracted.confidence)
    known = result.area != UNKNOWN
    entry = log(AGENT, "Identified location", f"{result.area} ({result.zone})" if known else "unknown",
                status="success" if known else "info",
                message="Location identified" if known else "Location not found in complaint",
                details={"location_text": result.location_text, "confidence": result.confidence})
    return {"area": result.area, "zone": result.zone, "location_text": result.location_text,
            "location_confidence": result.confidence, "history": [entry], "errors": errors}
