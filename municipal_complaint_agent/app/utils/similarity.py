"""
Tiny, dependency-free text similarity (no vector DB needed).

Idea: normalise both texts the same way, then compare word counts with cosine
similarity. Normalisation makes different wordings look alike:
  "broken", "damaged", "has not worked", "stopped working"  -> "fault"
  "street light", "streetlamp"                              -> "streetlight"
  plus lower-casing, stop-word removal and light stemming.
"""
import math
import re
from collections import Counter
from typing import Optional, Set

STOPWORDS = {
    "a", "an", "the", "my", "our", "your", "their", "his", "her", "its", "i", "we", "it", "this", "that",
    "is", "are", "was", "were", "be", "been", "has", "have", "had", "do", "does", "did",
    "in", "on", "at", "of", "to", "for", "from", "by", "with", "near", "outside", "inside", "front",
    "around", "next", "behind", "since", "there", "here", "and", "or", "but", "very", "so", "please",
    "house", "home", "street", "day", "days", "week", "weeks", "three", "two", "one", "yesterday",
    "morning", "several", "again", "also", "just", "still", "area", "side",
}

# regex phrase -> replacement token (applied before tokenising)
PHRASES = [
    (r"\bstreet\s*-?\s*(?:light|lamp)s?\b", " streetlight "),
    (r"\bstreetlamps?\b", " streetlight "),
    (r"\blamp\s*posts?\b", " streetlight "),
    (r"\b(?:not|never)\s+(?:been\s+)?(?:working|worked|work|functioning|functional|functions)\b", " fault "),
    (r"\b(?:stopped|stops)\s+working\b", " fault "),
    (r"\bout\s+of\s+(?:order|service)\b", " fault "),
    (r"\bno\s+longer\s+working\b", " fault "),
    (r"\bno\s+light\b", " fault "),
]

SYNONYMS = {
    "broken": "fault", "damaged": "fault", "faulty": "fault", "defective": "fault", "dead": "fault",
    "flickering": "fault", "dark": "fault", "off": "fault",
    "trash": "garbage", "rubbish": "garbage", "waste": "garbage", "kachra": "garbage",
    "sewage": "sewer", "sewerage": "sewer",
    "gutter": "drain", "drainage": "drain", "nala": "drain", "nullah": "drain",
    "holes": "pothole", "hole": "pothole",
    "leakage": "leak", "leaking": "leak", "leaks": "leak",
}


def _stem(word: str) -> str:
    if any(ch.isdigit() for ch in word):
        return word
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> list:
    t = (text or "").lower().replace("n't", " not").replace("’", "'")
    for pattern, repl in PHRASES:
        t = re.sub(pattern, repl, t)
    out = []
    for w in re.findall(r"[a-z0-9]+", t):
        w = SYNONYMS.get(w, w)
        if w in STOPWORDS:
            continue
        out.append(_stem(w))
    return out


def text_similarity(a: str, b: str) -> float:
    """Cosine similarity of normalised word counts, 0.0 - 1.0."""
    ca, cb = Counter(tokenize(a)), Counter(tokenize(b))
    if not ca or not cb:
        return 0.0
    dot = sum(ca[w] * cb[w] for w in ca if w in cb)
    norm = math.sqrt(sum(v * v for v in ca.values())) * math.sqrt(sum(v * v for v in cb.values()))
    return dot / norm if norm else 0.0


# ------------------------------------------------------------------ locations
_GENERIC = {"phase", "sector", "block", "street", "gali", "lane", "road"}
_LOC_STOP = {"near", "the", "in", "at", "of", "outside", "inside", "my", "house", "home", "street", "road"}


def location_tokens(text: Optional[str]) -> Set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in _LOC_STOP}


def _known(area: Optional[str]) -> bool:
    return bool(area) and area.strip().lower() != "unknown"


def location_similarity(area_a, text_a, area_b, text_b) -> Optional[float]:
    """
    0.0 = different areas, 1.0 = same place.
    None = cannot compare (one of the areas is unknown).
    Same area but a different phase/block/street scores lower than an exact match.
    """
    if not (_known(area_a) and _known(area_b)):
        return None
    if area_a.strip().lower() != area_b.strip().lower():
        return 0.0
    ta, tb = location_tokens(text_a), location_tokens(text_b)
    if not ta or not tb:
        return 0.6
    # Different phase / block / street number in the same area = a different place.
    area_tokens = location_tokens(area_a)
    specific_a = ta - area_tokens - _GENERIC
    specific_b = tb - area_tokens - _GENERIC
    if specific_a and specific_b and not (specific_a & specific_b):
        return 0.2
    jaccard = len(ta & tb) / len(ta | tb)
    return max(0.5, jaccard)
