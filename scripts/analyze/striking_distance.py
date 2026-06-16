"""
striking_distance.py — Identify "quick win" keywords just outside the top rankings.

Definition: queries at average position 5–15 with >= impression_threshold impressions.
These are close enough to the top that a modest content improvement can meaningfully
lift clicks. Estimated extra clicks are computed from the standard CTR benchmark curve.

Finding fields:
  query           : the search query
  best_page       : URL of the page with the most clicks for this query
  position        : average position across the window
  impressions     : total impressions
  clicks          : total clicks
  current_ctr     : actual CTR (clicks / impressions)
  expected_ctr_p3 : benchmark CTR if ranked at position 3
  estimated_extra_clicks : impressions * (expected_ctr_p3 - current_ctr), rounded
  so_what         : one-line plain-English summary of the opportunity
"""

import json
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.analyze import CTR_BENCHMARK, expected_ctr  # noqa: E402

# Position window that defines "striking distance".
POSITION_MIN = 5.0
POSITION_MAX = 15.0

# Target position for estimating click uplift — position 3 is achievable with
# good on-page optimization without requiring massive authority gains.
TARGET_POSITION = 3


def analyze(
    data_dir: pathlib.Path,
    *,
    impression_threshold: int = 50,
) -> list[dict]:
    """
    Identify queries in striking distance and estimate click uplift.

    Parameters
    ----------
    data_dir            : Directory containing queries.json and query_page.json.
    impression_threshold: Minimum impressions to include a query (filters noise).

    Returns
    -------
    List of finding dicts, sorted by estimated_extra_clicks descending.
    """
    queries_path = data_dir / "queries.json"
    qp_path = data_dir / "query_page.json"

    if not queries_path.exists():
        return []

    with open(queries_path) as fh:
        query_rows: list[dict] = json.load(fh)

    # Build a query → best page mapping from query_page data (optional).
    best_page: dict[str, str] = {}
    if qp_path.exists():
        with open(qp_path) as fh:
            qp_rows: list[dict] = json.load(fh)
        # For each query, find the page with the most clicks.
        page_clicks: dict[str, dict[str, float]] = {}
        for row in qp_rows:
            if not isinstance(row, dict) or "keys" not in row:
                continue
            keys = row["keys"]
            if len(keys) < 2:
                continue
            q, page = keys[0], keys[1]
            clicks = row.get("clicks", 0)
            if q not in page_clicks or clicks > page_clicks[q].get("clicks", -1):
                page_clicks[q] = {"page": page, "clicks": clicks}
        best_page = {q: v["page"] for q, v in page_clicks.items()}

    findings: list[dict] = []
    target_ctr = CTR_BENCHMARK[TARGET_POSITION]

    for row in query_rows:
        if not isinstance(row, dict) or "keys" not in row:
            continue
        query = row["keys"][0]
        position = row.get("position", 0.0)
        impressions = int(row.get("impressions", 0))
        clicks = int(row.get("clicks", 0))

        if not (POSITION_MIN <= position <= POSITION_MAX):
            continue
        if impressions < impression_threshold:
            continue

        current_ctr = clicks / impressions if impressions > 0 else 0.0
        estimated_extra = max(0, round(impressions * (target_ctr - current_ctr)))

        findings.append({
            "query": query,
            "best_page": best_page.get(query, "unknown"),
            "position": round(position, 1),
            "impressions": impressions,
            "clicks": clicks,
            "current_ctr": round(current_ctr, 4),
            "expected_ctr_p3": target_ctr,
            "estimated_extra_clicks": estimated_extra,
            "so_what": (
                f'"{query}" ranks at position {position:.1f} — '
                f"optimizing content could add ~{estimated_extra} clicks/period "
                f"(from {current_ctr:.1%} to ~{target_ctr:.1%} CTR)."
            ),
        })

    # Sort by estimated click gain (highest first).
    findings.sort(key=lambda x: x["estimated_extra_clicks"], reverse=True)
    return findings
