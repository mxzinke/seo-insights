"""
gsc_opportunities.py — Surface keyword opportunities from existing GSC data.

Fully free and deterministic: reads queries.json from the GSC data directory
and identifies queries where we have meaningful demand but are not capturing
it efficiently.

Two opportunity types
---------------------
1. "position_gap"  : queries ranking at position 8–30 with >= 50 impressions.
   We already appear in search results but too low to get meaningful clicks.
   These are real keywords we know people search for — just need to rank better.

2. "low_ctr"       : queries ranking at position 1–7 where actual CTR is
   substantially below the position benchmark (ratio < 0.5).
   Title / meta description is underperforming.

This complements striking_distance.py (which focuses on positions 5–15) but
frames the output as *keyword opportunities* with a combined opportunity score,
making it suitable for the keyword research table.
"""

from __future__ import annotations

import json
import pathlib

from scripts.analyze import CTR_BENCHMARK, CTR_BENCHMARK_FALLBACK, expected_ctr

# Thresholds
POSITION_MIN_GAP = 8.0       # queries below this are not "gap" candidates
POSITION_MAX_GAP = 30.0      # queries above this are unlikely to rank soon
IMPRESSION_MIN   = 50        # minimum impressions to be statistically useful
CTR_RATIO_WARN   = 0.50      # actual/expected CTR below this = low-CTR opportunity


def analyze(data_dir: pathlib.Path) -> list[dict]:
    """
    Return GSC-derived keyword opportunities from queries.json.

    Parameters
    ----------
    data_dir : Directory containing queries.json (and optionally query_page.json).

    Returns
    -------
    List of opportunity dicts with keys:
      keyword, source, our_current_position, impressions, clicks,
      actual_ctr, expected_ctr, opportunity_type
    """
    queries_path = data_dir / "queries.json"
    if not queries_path.exists():
        return []

    with open(queries_path) as fh:
        rows: list[dict] = json.load(fh)

    # Build query → best page mapping
    best_page: dict[str, str] = {}
    qp_path = data_dir / "query_page.json"
    if qp_path.exists():
        with open(qp_path) as fh:
            qp_rows = json.load(fh)
        page_clicks: dict[str, dict] = {}
        for row in qp_rows:
            if not isinstance(row, dict) or "keys" not in row or len(row["keys"]) < 2:
                continue
            q, page = row["keys"][0], row["keys"][1]
            clicks = row.get("clicks", 0)
            if q not in page_clicks or clicks > page_clicks[q].get("clicks", -1):
                page_clicks[q] = {"page": page, "clicks": clicks}
        best_page = {q: v["page"] for q, v in page_clicks.items()}

    opportunities: list[dict] = []

    for row in rows:
        if not isinstance(row, dict) or not row.get("keys"):
            continue

        keyword = row["keys"][0]
        position = float(row.get("position", 0))
        impressions = int(row.get("impressions", 0))
        clicks = int(row.get("clicks", 0))
        ctr = row.get("ctr", 0.0)

        if impressions < IMPRESSION_MIN:
            continue

        pos_int = round(position)
        exp_ctr = CTR_BENCHMARK.get(pos_int, CTR_BENCHMARK_FALLBACK)

        if POSITION_MIN_GAP <= position <= POSITION_MAX_GAP:
            # Type 1: position gap
            opportunities.append({
                "keyword": keyword,
                "source": "gsc",
                "our_current_position": round(position, 1),
                "impressions": impressions,
                "clicks": clicks,
                "actual_ctr": round(ctr, 6),
                "expected_ctr": round(exp_ctr, 6),
                "opportunity_type": "position_gap",
                "best_page": best_page.get(keyword),
            })

        elif position < POSITION_MIN_GAP and exp_ctr > 0:
            # Type 2: low CTR for the position
            ratio = ctr / exp_ctr if exp_ctr > 0 else 1.0
            if ratio < CTR_RATIO_WARN:
                opportunities.append({
                    "keyword": keyword,
                    "source": "gsc",
                    "our_current_position": round(position, 1),
                    "impressions": impressions,
                    "clicks": clicks,
                    "actual_ctr": round(ctr, 6),
                    "expected_ctr": round(exp_ctr, 6),
                    "opportunity_type": "low_ctr",
                    "best_page": best_page.get(keyword),
                })

    # Sort by impressions desc (most visible opportunity first)
    opportunities.sort(key=lambda x: x["impressions"], reverse=True)
    return opportunities
