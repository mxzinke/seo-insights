"""
ctr_outliers.py — Flag queries whose CTR is far below what their ranking deserves.

When a query ranks in a good position but earns very few clicks, it usually means:
  - The title tag is unappealing, unclear, or doesn't match search intent.
  - The meta description is missing, generic, or truncated badly.
  - A competitor's snippet is dramatically more compelling.
  - There is a featured snippet or SERP feature taking all the clicks.

We flag queries where actual CTR < 0.5× the benchmark CTR for their position
(the "0.5× threshold") AND impressions >= minimum threshold.

Finding fields:
  query           : the search query
  position        : average position in the window
  impressions     : total impressions
  clicks          : total clicks
  actual_ctr      : clicks / impressions
  expected_ctr    : benchmark CTR for this position
  ctr_ratio       : actual_ctr / expected_ctr  (< 0.5 triggers the flag)
  best_page       : page URL with most clicks for this query
  so_what         : one-line plain-English description of the opportunity
"""

import json
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.analyze import expected_ctr  # noqa: E402

# Fraction of expected CTR below which we flag the query.
CTR_UNDERPERFORMANCE_THRESHOLD = 0.5

# Minimum impressions to have a statistically meaningful CTR signal.
DEFAULT_IMPRESSION_THRESHOLD = 50


def analyze(
    data_dir: pathlib.Path,
    *,
    impression_threshold: int = DEFAULT_IMPRESSION_THRESHOLD,
    ctr_threshold: float = CTR_UNDERPERFORMANCE_THRESHOLD,
) -> list[dict]:
    """
    Identify queries with significantly underperforming CTR.

    Parameters
    ----------
    data_dir            : Directory containing queries.json and query_page.json.
    impression_threshold: Minimum impressions to consider a query.
    ctr_threshold       : Flag when actual_ctr < ctr_threshold * expected_ctr.

    Returns
    -------
    List of finding dicts sorted by estimated click gap (largest opportunity first).
    """
    queries_path = data_dir / "queries.json"
    qp_path = data_dir / "query_page.json"

    if not queries_path.exists():
        return []

    with open(queries_path) as fh:
        query_rows: list[dict] = json.load(fh)

    # Best page per query from query+page data.
    best_page: dict[str, str] = {}
    if qp_path.exists():
        with open(qp_path) as fh:
            qp_rows: list[dict] = json.load(fh)
        for row in qp_rows:
            if not isinstance(row, dict) or "keys" not in row or len(row["keys"]) < 2:
                continue
            q, page = row["keys"][0], row["keys"][1]
            if q not in best_page or row.get("clicks", 0) > 0:
                best_page[q] = page

    findings: list[dict] = []

    for row in query_rows:
        if not isinstance(row, dict) or "keys" not in row:
            continue
        query = row["keys"][0]
        position = row.get("position", 0.0)
        impressions = int(row.get("impressions", 0))
        clicks = int(row.get("clicks", 0))

        if impressions < impression_threshold:
            continue
        if position <= 0:
            continue

        # Positions > 20 have negligible expected CTR — not actionable from on-page changes.
        if position > 20:
            continue

        actual_ctr = clicks / impressions
        exp_ctr = expected_ctr(position)
        ctr_ratio = actual_ctr / exp_ctr if exp_ctr > 0 else 0.0

        if ctr_ratio >= ctr_threshold:
            continue  # CTR is within acceptable range.

        # Estimate how many clicks are being lost vs the benchmark.
        click_gap = max(0, round(impressions * (exp_ctr - actual_ctr)))

        findings.append({
            "query": query,
            "position": round(position, 1),
            "impressions": impressions,
            "clicks": clicks,
            "actual_ctr": round(actual_ctr, 4),
            "expected_ctr": round(exp_ctr, 4),
            "ctr_ratio": round(ctr_ratio, 3),
            "click_gap": click_gap,
            "best_page": best_page.get(query, "unknown"),
            "so_what": (
                f'"{query}" ranks at position {position:.1f} but has only '
                f"{actual_ctr:.1%} CTR vs {exp_ctr:.1%} expected "
                f"(ratio {ctr_ratio:.2f}×). Rewriting the title/meta for "
                f"{best_page.get(query, 'this page')} could recover ~{click_gap} clicks/period."
            ),
        })

    # Sort by click gap (biggest opportunity first).
    findings.sort(key=lambda x: x["click_gap"], reverse=True)
    return findings
