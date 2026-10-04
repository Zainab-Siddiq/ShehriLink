"""
Agent 3 - History / Duplicate detection.

Compares the new complaint with OPEN complaints of the same category using:
  * text similarity (normalised cosine, see utils/similarity.py), and
  * location similarity (same area? same phase/block/street?)
combined into one score. Clear matches are accepted by rules alone. In the
"unsure" band, an LLM (if configured) makes the final call.
"""
from typing import Optional

from app.data.mock_database import get_repository
from app.graph.state import ComplaintState, log
from app.llm import run_structured
from app.models.schemas import DuplicateJudgement, DuplicateResult
from app.utils.similarity import location_similarity, text_similarity

AGENT = "History/Duplicate Agent"

DUPLICATE_THRESHOLD = 0.60     # score >= this -> duplicate (location known)
TEXT_ONLY_THRESHOLD = 0.75     # stricter when we cannot compare locations
UNSURE_THRESHOLD = 0.40        # between UNSURE and DUPLICATE -> ask the LLM (if available)


def _score(state: ComplaintState, candidate: dict) -> tuple:
    """Return (combined_score, text_sim, loc_sim)."""
    t = text_similarity(state.description, candidate["description"])
    loc = location_similarity(state.area, state.location_text,
                              candidate.get("area"), candidate.get("location_text"))
    combined = t if loc is None else 0.5 * t + 0.5 * loc
    return combined, t, loc


def check_duplicate(state: ComplaintState, errors: Optional[list] = None) -> tuple:
    """Returns (DuplicateResult, best_score)."""
    repo = get_repository()
    category = state.category if state.category != "other" else None
    candidates = [c for c in repo.get_open_complaints(category)
                  if str(c["complaint_id"]) != str(state.complaint_id)]

    best, best_score, best_loc = None, 0.0, None
    for c in candidates:
        combined, _, loc = _score(state, c)
        if combined > best_score:
            best, best_score, best_loc = c, combined, loc

    if best is None:
        return DuplicateResult(duplicate=False, reason="No similar open complaints found."), 0.0

    threshold = TEXT_ONLY_THRESHOLD if best_loc is None else DUPLICATE_THRESHOLD
    if best_score >= threshold:
        return DuplicateResult(
            duplicate=True, related_complaint_id=str(best["complaint_id"]),
            reason=f"Same issue and nearby location as complaint #{best['complaint_id']} "
                   f"(similarity {best_score:.2f})."), best_score

    if best_score >= UNSURE_THRESHOLD:
        system = ("You decide whether two municipal complaints describe the SAME issue at the SAME place "
                  "(duplicate) or just a related/different issue. Be strict about location.")
        user = (f"NEW: {state.description} (location: {state.location_text})\n"
                f"EXISTING #{best['complaint_id']}: {best['description']} (location: {best.get('location_text')})")
        judgement, errs = run_structured(AGENT, DuplicateJudgement, system, user)
        if errors is not None:
            errors.extend(errs)
        if judgement is not None and judgement.duplicate:
            return DuplicateResult(duplicate=True, related_complaint_id=str(best["complaint_id"]),
                                   reason=judgement.reason), best_score

    return DuplicateResult(
        duplicate=False,
        reason=f"No close match (best similarity {best_score:.2f} with complaint #{best['complaint_id']})."
    ), best_score


def history_node(state: ComplaintState) -> dict:
    errors: list = []
    result, score = check_duplicate(state, errors)
    entry = log(AGENT, "Checked for duplicates",
                f"duplicate of #{result.related_complaint_id}" if result.duplicate else "no duplicate",
                message="Duplicate check completed",
                details={"duplicate": result.duplicate, "related_complaint_id": result.related_complaint_id,
                         "similarity": round(score, 2), "reason": result.reason})
    return {"duplicate": result.duplicate, "related_complaint_id": result.related_complaint_id,
            "duplicate_reason": result.reason, "history": [entry], "errors": errors}
