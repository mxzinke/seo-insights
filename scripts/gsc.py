"""
gsc.py — Generalized Google Search Console API client.

Supports:
  - Dimensions: query, page, date, country, device (any combination)
  - Dimension filters (dimensionFilterGroups)
  - Date range and row offset pagination (up to 25,000 rows per property limit)
  - Listing all verified sites
  - Graceful error handling with informative messages

GSC API notes baked into this module:
  - GSC returns at most 25,000 rows per request; this module paginates automatically.
  - The sum of per-query rows never equals the property total due to anonymization.
    Always use the summary (no dimension) query for aggregate numbers.
  - Position: lower is better (1 = top result). A negative WoW delta = improvement.
  - Data has a ~2-day lag; callers should account for this in their date ranges.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

GSC_SEARCH_ANALYTICS_URL = (
    "https://www.googleapis.com/webmasters/v3/sites/{encoded_site}/searchAnalytics/query"
)
GSC_SITES_URL = "https://www.googleapis.com/webmasters/v3/sites"

# GSC hard cap per-page.
MAX_ROWS_PER_REQUEST = 25_000


def _make_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def _post(url: str, body: dict, access_token: str, timeout: int = 30) -> dict:
    """HTTP POST with JSON body; raises RuntimeError on non-2xx."""
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=_make_headers(access_token), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        raise RuntimeError(
            f"GSC API error {exc.code} {exc.reason} for {url}\n{body_text}"
        ) from exc


def _get(url: str, access_token: str, timeout: int = 15) -> dict:
    """HTTP GET; raises RuntimeError on non-2xx."""
    req = urllib.request.Request(url, headers=_make_headers(access_token), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        raise RuntimeError(
            f"GSC API GET error {exc.code} {exc.reason} for {url}\n{body_text}"
        ) from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_sites(access_token: str) -> list[dict]:
    """
    Return all verified sites for the authenticated account.

    Each entry has: siteUrl, permissionLevel.
    """
    payload = _get(GSC_SITES_URL, access_token)
    return payload.get("siteEntry", [])


def search_analytics(
    access_token: str,
    site_url: str,
    start_date: str,
    end_date: str,
    *,
    dimensions: list[str] | None = None,
    dimension_filter_groups: list[dict] | None = None,
    row_limit: int = MAX_ROWS_PER_REQUEST,
    data_state: str = "final",
) -> dict:
    """
    Execute a single (non-paginated) Search Analytics query.

    Parameters
    ----------
    access_token     : Bearer token from get_access_token().
    site_url         : e.g. "sc-domain:example.com" or "https://www.example.com/".
    start_date       : "YYYY-MM-DD" inclusive.
    end_date         : "YYYY-MM-DD" inclusive.
    dimensions       : List of dimension names. None or [] = aggregate summary row.
    dimension_filter_groups : GSC filter group dicts.
    row_limit        : Max rows to return (capped at 25,000 by GSC).
    data_state       : "final" (default) or "all" (includes fresh/unverified data).

    Returns
    -------
    Raw GSC API response dict: {"rows": [...], "responseAggregationType": "..."}
    """
    body: dict = {
        "startDate": start_date,
        "endDate": end_date,
        "rowLimit": min(row_limit, MAX_ROWS_PER_REQUEST),
        "dataState": data_state,
    }
    if dimensions:
        body["dimensions"] = dimensions
    if dimension_filter_groups:
        body["dimensionFilterGroups"] = dimension_filter_groups

    encoded = urllib.parse.quote(site_url, safe="")
    url = GSC_SEARCH_ANALYTICS_URL.format(encoded_site=encoded)
    return _post(url, body, access_token)


def search_analytics_all_rows(
    access_token: str,
    site_url: str,
    start_date: str,
    end_date: str,
    *,
    dimensions: list[str] | None = None,
    dimension_filter_groups: list[dict] | None = None,
    data_state: str = "final",
    verbose: bool = False,
) -> list[dict]:
    """
    Paginate through GSC results and return ALL rows for the given query.

    GSC returns at most 25,000 rows per page; this function issues multiple
    requests with increasing startRow offsets until fewer rows than the page
    size are returned (indicating the last page).

    Returns
    -------
    List of row dicts in GSC format:
      {"keys": [...], "clicks": int, "impressions": int, "ctr": float, "position": float}
    """
    all_rows: list[dict] = []
    start_row = 0

    while True:
        body: dict = {
            "startDate": start_date,
            "endDate": end_date,
            "rowLimit": MAX_ROWS_PER_REQUEST,
            "startRow": start_row,
            "dataState": data_state,
        }
        if dimensions:
            body["dimensions"] = dimensions
        if dimension_filter_groups:
            body["dimensionFilterGroups"] = dimension_filter_groups

        encoded = urllib.parse.quote(site_url, safe="")
        url = GSC_SEARCH_ANALYTICS_URL.format(encoded_site=encoded)
        resp = _post(url, body, access_token)

        rows = resp.get("rows", [])
        if verbose:
            print(f"  [gsc] fetched {len(rows)} rows (offset {start_row})", file=sys.stderr)

        all_rows.extend(rows)

        # If we got fewer rows than the page size, we've exhausted the result set.
        if len(rows) < MAX_ROWS_PER_REQUEST:
            break
        start_row += MAX_ROWS_PER_REQUEST

    return all_rows


def query_summary(
    access_token: str,
    site_url: str,
    start_date: str,
    end_date: str,
) -> dict:
    """
    Return aggregate property-level metrics (no dimensions).

    This is the ONLY correct way to get total clicks/impressions/CTR/position
    for a property — do NOT reconstruct these from per-query row sums (GSC
    anonymizes low-volume queries, so the sums will be lower than reality).

    Returns
    -------
    {"clicks": int, "impressions": int, "ctr": float, "position": float}
    or empty dict if GSC returned no rows.
    """
    resp = search_analytics(access_token, site_url, start_date, end_date)
    rows = resp.get("rows", [])
    if not rows:
        return {}
    # Summary query always returns exactly one row.
    row = rows[0]
    return {
        "clicks": int(row.get("clicks", 0)),
        "impressions": int(row.get("impressions", 0)),
        "ctr": round(row.get("ctr", 0.0), 6),
        "position": round(row.get("position", 0.0), 2),
    }
