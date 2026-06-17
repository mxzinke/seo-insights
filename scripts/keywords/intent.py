"""
intent.py — Rule-based, deterministic search-intent classifier.

No LLM, no ML model — purely modifier-table look-ups in German and English.
Returns a label (transactional | commercial | informational | navigational | unknown)
plus which modifier matched, providing human-readable evidence.

Intent taxonomy
---------------
transactional  : user wants to buy / subscribe / install / order NOW
                 (kaufen, preis, bestellen, kosten, shop, buy, price, order, checkout)
commercial     : user compares options before buying
                 (beste, vergleich, top, alternative, review, vs, best, compare)
informational  : user wants to learn
                 (wie, was ist, anleitung, erklärt, how to, what is, guide, tutorial, tips)
navigational   : user wants to reach a specific brand / site
                 (brand terms supplied via icp.competitors, or "login" / "sign in" patterns)
unknown        : no modifier matched
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Modifier tables (order matters: first match wins within each tier)
# ---------------------------------------------------------------------------

# Transactional signals (DE + EN)
_TRANSACTIONAL: list[tuple[str, str]] = [
    (r"\b(kaufen|kauf)\b",             "kaufen"),
    (r"\b(bestellen|bestellung)\b",    "bestellen"),
    (r"\b(preis|preise|kosten|gebühr)", "preis/kosten"),
    (r"\b(shop|store|laden)\b",        "shop"),
    (r"\b(download|herunterladen)\b",  "download"),
    (r"\b(abonnement|abonnieren|abo)\b", "abonnieren"),
    (r"\b(anmelden|registrieren|sign up|signup|register)\b", "sign-up"),
    (r"\b(buy|purchase|order|checkout)\b", "buy"),
    (r"\b(price|pricing|cost|costs|fee|fees|plans?)\b", "price"),
    (r"\b(trial|free trial|demo)\b",   "trial"),
    (r"\b(discount|coupon|rabatt)\b",  "discount"),
]

# Commercial investigation (DE + EN)
_COMMERCIAL: list[tuple[str, str]] = [
    (r"\b(beste?n?|top)\b",            "beste/top"),
    (r"\bvergleich\b",                 "vergleich"),
    (r"\balternative[ns]?\b",          "alternative"),
    (r"\b(empfehlung|empfehlen)\b",    "empfehlung"),
    (r"\b(test|testen|review|reviews?)\b", "review/test"),
    (r"\b(ranking|rangliste)\b",       "ranking"),
    (r"\bvs\.?\b",                     "vs"),
    (r"\b(compare|comparison|vs)\b",   "compare"),
    (r"\b(best|top)\b",               "best/top"),
    (r"\b(recommended?|recommend)\b",  "recommended"),
    (r"\b(worth it|is .+ good)\b",     "worth-it"),
]

# Informational (DE + EN)
_INFORMATIONAL: list[tuple[str, str]] = [
    (r"\b(wie|how)\b",                 "wie/how"),
    (r"\b(was ist|what is|what are)\b", "was ist / what is"),
    (r"\b(warum|why)\b",               "warum/why"),
    (r"\b(wann|when)\b",               "wann/when"),
    (r"\b(wo|where)\b",                "wo/where"),
    (r"\b(anleitung|tutorial|guide)\b", "anleitung/guide"),
    (r"\b(erklär|erklärt|explained?)\b", "erklärung"),
    (r"\b(tipps?|tips?|tricks?)\b",    "tipps/tips"),
    (r"\b(beispiel|example)\b",        "beispiel/example"),
    (r"\b(checkliste?|checklist)\b",   "checklist"),
    (r"\b(einführung|introduction|intro)\b", "einführung"),
    (r"\b(überblick|overview)\b",      "overview"),
    (r"\b(verstehen|understand)\b",    "verstehen"),
    (r"\b(definition|bedeutung|meaning)\b", "definition"),
    (r"\b(lernen|learn|lern\w+)\b",    "lernen"),
    (r"\b(schritt für schritt|step by step)\b", "step-by-step"),
]

# Navigational — brand / login patterns (brand terms from ICP added at call time)
_NAVIGATIONAL_GENERIC: list[tuple[str, str]] = [
    (r"\b(login|log in|einloggen|anmelden)\b", "login"),
    (r"\b(sign in)\b",                         "sign-in"),
    (r"\b(homepage|startseite|website|official)\b", "homepage"),
    (r"\bwww\.",                                "url"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify(keyword: str, brand_terms: list[str] | None = None) -> dict:
    """
    Classify the search intent of *keyword* deterministically.

    Parameters
    ----------
    keyword     : The search query string to classify.
    brand_terms : Optional list of brand / competitor domain tokens.
                  When a keyword matches one of these, it's navigational.

    Returns
    -------
    dict with keys:
      intent   : str — one of transactional | commercial | informational |
                               navigational | unknown
      evidence : str — the modifier that matched, or "" if unknown
    """
    kw = keyword.strip().lower()

    # Navigational — brand check first (highest specificity)
    if brand_terms:
        for term in brand_terms:
            clean = term.lower().replace("https://", "").replace("http://", "").split("/")[0]
            # Match the bare domain name (e.g. "ahrefs" from "ahrefs.com")
            root = clean.split(".")[0]
            if root and len(root) > 2 and root in kw:
                return {"intent": "navigational", "evidence": f"brand:{root}"}

    for pattern, label in _NAVIGATIONAL_GENERIC:
        if re.search(pattern, kw):
            return {"intent": "navigational", "evidence": label}

    # Transactional — strongest commercial signal
    for pattern, label in _TRANSACTIONAL:
        if re.search(pattern, kw):
            return {"intent": "transactional", "evidence": label}

    # Commercial investigation
    for pattern, label in _COMMERCIAL:
        if re.search(pattern, kw):
            return {"intent": "commercial", "evidence": label}

    # Informational
    for pattern, label in _INFORMATIONAL:
        if re.search(pattern, kw):
            return {"intent": "informational", "evidence": label}

    return {"intent": "unknown", "evidence": ""}


def classify_batch(
    keywords: list[str],
    brand_terms: list[str] | None = None,
) -> dict[str, dict]:
    """
    Classify a list of keywords.

    Returns
    -------
    Dict mapping keyword → classify() result.
    """
    return {kw: classify(kw, brand_terms=brand_terms) for kw in keywords}
