"""
autocomplete.py — Google Autocomplete / Suggest expansion.

Endpoint: GET https://suggestqueries.google.com/complete/search
Params  : client=chrome, hl=<lang>, gl=<country>, q=<seed>

This is a best-effort idea expander ONLY. It returns suggestion strings
with NO volume data — volume must come from the Google Ads API or GSC.

Design principles
-----------------
- Polite: small delay between requests, realistic User-Agent.
- Retry with exponential backoff (up to 3 attempts).
- Graceful degradation: if Google blocks or returns non-200, return []
  and continue — never crash the pipeline.
- Cap: at most `max_seeds` seeds expanded per call.
- No crash guarantee: all exceptions are caught and logged to stderr.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterator

SUGGEST_URL = "https://suggestqueries.google.com/complete/search"

# Realistic browser UA to avoid immediate bot detection
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_DEFAULT_DELAY   = 0.8   # seconds between requests
_MAX_RETRIES     = 3
_BACKOFF_BASE    = 2.0   # exponential backoff multiplier


def _fetch_suggestions(
    seed: str,
    lang: str = "de",
    country: str = "de",
    timeout: int = 8,
    verbose: bool = False,
) -> list[str]:
    """
    Fetch autocomplete suggestions for a single seed query.

    Returns
    -------
    List of suggestion strings, possibly empty on error.
    """
    params = urllib.parse.urlencode({
        "client": "chrome",
        "hl": lang,
        "gl": country.lower(),
        "q": seed,
    })
    url = f"{SUGGEST_URL}?{params}"

    for attempt in range(1, _MAX_RETRIES + 1):
        req = urllib.request.Request(
            url,
            headers={"User-Agent": _USER_AGENT},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    if verbose:
                        print(f"  [autocomplete] HTTP {resp.status} for seed={seed!r}", file=sys.stderr)
                    return []
                raw = resp.read().decode("utf-8", errors="replace")
                # Chrome client returns: [seed, [suggestion1, suggestion2, ...], ...]
                data = json.loads(raw)
                if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
                    return [s for s in data[1] if isinstance(s, str)]
                return []
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503):
                # Rate limited — back off
                wait = _BACKOFF_BASE ** attempt
                if verbose:
                    print(f"  [autocomplete] rate-limited (HTTP {exc.code}), "
                          f"waiting {wait:.1f}s (attempt {attempt}/{_MAX_RETRIES})", file=sys.stderr)
                time.sleep(wait)
            else:
                if verbose:
                    print(f"  [autocomplete] HTTP {exc.code} for seed={seed!r} — skipping", file=sys.stderr)
                return []
        except Exception as exc:  # noqa: BLE001 — intentional broad catch
            if verbose:
                print(f"  [autocomplete] error for seed={seed!r}: {exc} — skipping", file=sys.stderr)
            return []

    if verbose:
        print(f"  [autocomplete] giving up on seed={seed!r} after {_MAX_RETRIES} attempts", file=sys.stderr)
    return []


def _build_seeds(
    priority_topics: list[str],
    existing_queries: list[str],
    max_seeds: int = 10,
) -> list[str]:
    """
    Derive a capped list of seed queries to expand.

    Strategy: take priority topics first, then top existing GSC queries as seeds.
    """
    seeds: list[str] = []
    seen: set[str] = set()

    for topic in priority_topics:
        t = topic.strip()
        if t and t not in seen:
            seeds.append(t)
            seen.add(t)
        if len(seeds) >= max_seeds:
            break

    for q in existing_queries:
        q = q.strip()
        if q and q not in seen:
            seeds.append(q)
            seen.add(q)
        if len(seeds) >= max_seeds:
            break

    return seeds[:max_seeds]


def expand(
    *,
    priority_topics: list[str],
    existing_queries: list[str] | None = None,
    lang: str = "de",
    country: str = "de",
    max_seeds: int = 10,
    delay: float = _DEFAULT_DELAY,
    verbose: bool = False,
) -> list[dict]:
    """
    Expand seed keywords via Google Autocomplete.

    Parameters
    ----------
    priority_topics   : ICP priority topics used as primary seeds.
    existing_queries  : Additional GSC queries to use as seeds.
    lang              : Language code for the suggest endpoint (e.g. "de", "en").
    country           : Country code (e.g. "de", "us").
    max_seeds         : Maximum number of seeds to expand.
    delay             : Seconds to wait between requests.
    verbose           : Log progress to stderr.

    Returns
    -------
    List of dicts: { keyword: str, source: "autocomplete", seed: str }
    Volumes are NOT included — this is idea-expansion only.
    """
    seeds = _build_seeds(
        priority_topics=priority_topics,
        existing_queries=existing_queries or [],
        max_seeds=max_seeds,
    )

    if not seeds:
        return []

    seen_suggestions: set[str] = set(s.lower() for s in seeds)
    results: list[dict] = []

    for i, seed in enumerate(seeds):
        if verbose:
            print(f"  [autocomplete] expanding seed {i+1}/{len(seeds)}: {seed!r}", file=sys.stderr)

        suggestions = _fetch_suggestions(seed=seed, lang=lang, country=country, verbose=verbose)

        for sug in suggestions:
            sug_lower = sug.lower().strip()
            if sug_lower and sug_lower not in seen_suggestions:
                seen_suggestions.add(sug_lower)
                results.append({
                    "keyword": sug.strip(),
                    "source": "autocomplete",
                    "seed": seed,
                })

        # Polite delay — skip after last seed
        if i < len(seeds) - 1:
            time.sleep(delay)

    if verbose:
        print(f"  [autocomplete] {len(results)} unique suggestions from {len(seeds)} seeds", file=sys.stderr)

    return results
