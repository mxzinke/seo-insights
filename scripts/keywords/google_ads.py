"""
google_ads.py — Keyword idea generation via Google Ads KeywordPlanIdeaService.

Uses raw REST (urllib only — no google-ads SDK dependency).

API specification
-----------------
Endpoint : POST https://googleads.googleapis.com/v23/customers/{customerId}:generateKeywordIdeas
Auth     : Bearer <access_token>  +  developer-token  +  (optional) login-customer-id
Body     : JSON — see _build_body() below.
Response : { results: [ { text, keywordIdeaMetrics: { avgMonthlySearches,
              competition, competitionIndex, lowTopOfPageBidMicros,
              highTopOfPageBidMicros, monthlySearchVolumes[] } } ],
             nextPageToken? }

Geographic / language constants
--------------------------------
language  : languageConstants/1000 = en, languageConstants/1001 = de
geo       : geoTargetConstants/2276 = Germany (DE), 2840 = US, 2826 = UK

ICP country/language mapping
-----------------------------
DE → geo 2276, lang 1001
US → geo 2840, lang 1000
GB → geo 2826, lang 1000
AT → geo 2040, lang 1001
CH → geo 2756, lang 1001
(unmapped → fallback DE/de)

Graceful degradation
--------------------
If GOOGLE_ADS_DEVELOPER_TOKEN or GOOGLE_ADS_CUSTOMER_ID are absent from
config, returns an empty result dict and sets `available=False`.
Callers should check `result["available"]` before using volume data.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADS_API_BASE = "https://googleads.googleapis.com/v23"
KEYWORD_IDEAS_PATH = "customers/{customer_id}:generateKeywordIdeas"

# Country → geoTargetConstants ID
_GEO_MAP: dict[str, str] = {
    "DE": "geoTargetConstants/2276",
    "AT": "geoTargetConstants/2040",
    "CH": "geoTargetConstants/2756",
    "US": "geoTargetConstants/2840",
    "GB": "geoTargetConstants/2826",
    "UK": "geoTargetConstants/2826",
    "CA": "geoTargetConstants/2124",
    "AU": "geoTargetConstants/2036",
    "NL": "geoTargetConstants/2528",
    "FR": "geoTargetConstants/2250",
}

# Language → languageConstants ID
_LANG_MAP: dict[str, str] = {
    "de": "languageConstants/1001",
    "en": "languageConstants/1000",
    "fr": "languageConstants/1002",
    "nl": "languageConstants/1010",
}

_DEFAULT_GEO  = "geoTargetConstants/2276"   # Germany
_DEFAULT_LANG = "languageConstants/1001"    # German


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_geo(country_code: str) -> str:
    return _GEO_MAP.get(country_code.upper(), _DEFAULT_GEO)


def _resolve_lang(lang_code: str) -> str:
    return _LANG_MAP.get(lang_code.lower()[:2], _DEFAULT_LANG)


def _build_headers(access_token: str, developer_token: str,
                   login_customer_id: str | None) -> dict:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "developer-token": developer_token,
        "Content-Type": "application/json",
    }
    if login_customer_id:
        # Must be digits only (no hyphens)
        headers["login-customer-id"] = login_customer_id.replace("-", "")
    return headers


def _build_body(
    keywords: list[str],
    url: str | None,
    geo_constant: str,
    lang_constant: str,
    page_token: str | None = None,
) -> dict:
    """
    Build the generateKeywordIdeas request body.

    Seed strategy:
      - keywords + url  → KeywordAndUrlSeed
      - keywords only   → KeywordSeed
      - url only        → UrlSeed
      - nothing         → SiteSeed (not useful here, caller should provide something)
    """
    body: dict[str, Any] = {
        "language": lang_constant,
        "geoTargetConstants": [geo_constant],
        "keywordPlanNetwork": "GOOGLE_SEARCH",
        "includeAdultKeywords": False,
    }

    if page_token:
        body["pageToken"] = page_token

    kw_list = [k.strip() for k in keywords if k.strip()]

    if kw_list and url:
        body["keywordAndUrlSeed"] = {"url": url, "keywords": kw_list}
    elif kw_list:
        body["keywordSeed"] = {"keywords": kw_list}
    elif url:
        body["urlSeed"] = {"url": url}
    else:
        body["keywordSeed"] = {"keywords": []}

    return body


def _post(url: str, body: dict, headers: dict, timeout: int = 30) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        raise RuntimeError(
            f"Google Ads API error {exc.code} {exc.reason}:\n{body_text}"
        ) from exc


def _parse_result(raw_result: dict) -> dict:
    """
    Parse a single result entry from the Google Ads API response.

    Returns a normalized dict:
      text, avg_monthly_searches, competition (LOW|MEDIUM|HIGH|UNSPECIFIED),
      competition_index (0-100), low_cpc_micros, high_cpc_micros,
      monthly_search_volumes (list of {year, month, monthly_searches})
    """
    metrics = raw_result.get("keywordIdeaMetrics") or {}

    # avgMonthlySearches is returned as a string in the API
    avg = metrics.get("avgMonthlySearches")
    try:
        avg_int: int | None = int(avg) if avg is not None else None
    except (ValueError, TypeError):
        avg_int = None

    comp_index = metrics.get("competitionIndex")
    try:
        comp_index_int: int | None = int(comp_index) if comp_index is not None else None
    except (ValueError, TypeError):
        comp_index_int = None

    monthly_vols = []
    for mv in metrics.get("monthlySearchVolumes", []):
        monthly_searches = mv.get("monthlySearches")
        try:
            ms_int = int(monthly_searches) if monthly_searches is not None else None
        except (ValueError, TypeError):
            ms_int = None
        monthly_vols.append({
            "year": mv.get("year"),
            "month": mv.get("month"),
            "monthly_searches": ms_int,
        })

    return {
        "text": raw_result.get("text", ""),
        "avg_monthly_searches": avg_int,
        "competition": metrics.get("competition", "UNSPECIFIED"),
        "competition_index": comp_index_int,
        "low_cpc_micros": metrics.get("lowTopOfPageBidMicros"),
        "high_cpc_micros": metrics.get("highTopOfPageBidMicros"),
        "monthly_search_volumes": monthly_vols,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_keyword_ideas(
    *,
    access_token: str,
    developer_token: str,
    customer_id: str,
    login_customer_id: str | None = None,
    keywords: list[str] | None = None,
    url: str | None = None,
    country_code: str = "DE",
    language_code: str = "de",
    max_results: int = 500,
    verbose: bool = False,
) -> list[dict]:
    """
    Call Google Ads KeywordPlanIdeaService and return normalized keyword ideas.

    Parameters
    ----------
    access_token      : OAuth access token (must have adwords scope).
    developer_token   : Google Ads developer token.
    customer_id       : Google Ads customer ID (digits, with or without hyphens).
    login_customer_id : Manager account ID (optional).
    keywords          : Seed keywords.
    url               : Seed URL / domain.
    country_code      : ISO-3166-1 alpha-2 country code (default "DE").
    language_code     : BCP-47 language code (default "de").
    max_results       : Maximum number of ideas to return (API paginates at 1000).
    verbose           : Print progress to stderr.

    Returns
    -------
    List of parsed keyword idea dicts (see _parse_result).
    Empty list if no ideas returned.
    """
    geo  = _resolve_geo(country_code)
    lang = _resolve_lang(language_code)
    cid  = customer_id.replace("-", "")
    endpoint = f"{ADS_API_BASE}/{KEYWORD_IDEAS_PATH.format(customer_id=cid)}"
    headers  = _build_headers(access_token, developer_token, login_customer_id)

    results: list[dict] = []
    page_token: str | None = None

    while True:
        body = _build_body(
            keywords=keywords or [],
            url=url,
            geo_constant=geo,
            lang_constant=lang,
            page_token=page_token,
        )
        if verbose:
            print(f"  [ads] POST {endpoint} (page_token={page_token!r})", file=sys.stderr)

        resp = _post(endpoint, body, headers)
        page_results = resp.get("results", [])
        for r in page_results:
            results.append(_parse_result(r))

        if verbose:
            print(f"  [ads] {len(page_results)} ideas returned (total so far: {len(results)})",
                  file=sys.stderr)

        page_token = resp.get("nextPageToken")
        if not page_token or len(results) >= max_results:
            break

        # Polite delay between pages
        time.sleep(0.5)

    return results[:max_results]


def fetch_keyword_ideas_with_config(
    cfg: dict,
    *,
    keywords: list[str] | None = None,
    url: str | None = None,
    country_code: str = "DE",
    language_code: str = "de",
    max_results: int = 500,
    verbose: bool = False,
) -> dict:
    """
    High-level wrapper: resolve credentials from config dict, call the API.

    Required config keys
    --------------------
    GOOGLE_ADS_DEVELOPER_TOKEN
    GOOGLE_ADS_CUSTOMER_ID
    GSC_CLIENT_ID, GSC_CLIENT_SECRET, GSC_REFRESH_TOKEN  (for OAuth refresh)

    Optional config keys
    --------------------
    GOOGLE_ADS_LOGIN_CUSTOMER_ID

    Returns
    -------
    {
      "available": bool,
      "source_note": str,
      "ideas": list[dict],      # empty when available=False
    }
    """
    developer_token = cfg.get("GOOGLE_ADS_DEVELOPER_TOKEN", "").strip()
    customer_id     = cfg.get("GOOGLE_ADS_CUSTOMER_ID", "").strip()
    login_cid       = cfg.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").strip() or None

    if not developer_token or not customer_id:
        return {
            "available": False,
            "source_note": (
                "Google Ads volumes: OFF "
                "(GOOGLE_ADS_DEVELOPER_TOKEN or GOOGLE_ADS_CUSTOMER_ID not configured)"
            ),
            "ideas": [],
        }

    # Refresh the access token using the same flow as auth.py
    try:
        from scripts.auth import get_access_token  # noqa: PLC0415
        access_token = get_access_token(
            cfg["GSC_CLIENT_ID"],
            cfg["GSC_CLIENT_SECRET"],
            cfg["GSC_REFRESH_TOKEN"],
        )
    except Exception as exc:
        return {
            "available": False,
            "source_note": f"Google Ads volumes: OFF (token refresh failed: {exc})",
            "ideas": [],
        }

    try:
        ideas = generate_keyword_ideas(
            access_token=access_token,
            developer_token=developer_token,
            customer_id=customer_id,
            login_customer_id=login_cid,
            keywords=keywords,
            url=url,
            country_code=country_code,
            language_code=language_code,
            max_results=max_results,
            verbose=verbose,
        )
        return {
            "available": True,
            "source_note": "Google Ads volumes: ON",
            "ideas": ideas,
        }
    except Exception as exc:
        if verbose:
            print(f"  [ads] ERROR: {exc}", file=sys.stderr)
        return {
            "available": False,
            "source_note": f"Google Ads volumes: OFF (API error: {exc})",
            "ideas": [],
        }
