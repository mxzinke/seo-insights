"""
content_decay.py — Detect content that is losing traffic over time.

Two decay signals are computed:

  1. Intra-window split: the date-dimension data is split into first half vs
     second half of the analysis window. Pages/queries where the second half
     has >= decay_threshold% fewer clicks/impressions than the first half are flagged.

  2. WoW (week-over-week / period-over-period): if a prior run exists in
     data/<domain>/prior/, compare current aggregated pages against prior.
     Pages with >= decay_threshold% decline in both clicks AND impressions are flagged.

Finding fields (type: "split" or "prior"):
  type            : "split" or "prior"
  subject         : "page" or "query" being analyzed
  url             : page URL or query string
  first_half_clicks  / prior_clicks  : reference period clicks
  second_half_clicks / current_clicks : comparison period clicks
  first_half_impressions / prior_impressions
  second_half_impressions / current_impressions
  clicks_decline_pct  : % decline in clicks (positive = decline)
  impressions_decline_pct : % decline in impressions
  so_what         : one-line plain-English description of the decay signal
"""

import json
import pathlib
import sys
import datetime

_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Minimum % decline to flag — avoids noise from tiny fluctuations.
DEFAULT_DECAY_THRESHOLD_PCT = 20.0

# Minimum impressions in the first half to have a meaningful signal.
MIN_IMPRESSIONS_FIRST_HALF = 30


def _split_date_rows(date_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split date-dimension rows into first and second halves chronologically."""
    if not date_rows:
        return [], []
    # Sort by date key.
    sorted_rows = sorted(date_rows, key=lambda r: r["keys"][0] if r.get("keys") else "")
    mid = len(sorted_rows) // 2
    return sorted_rows[:mid], sorted_rows[mid:]


def _sum_metrics(rows: list[dict]) -> dict:
    """Sum clicks and impressions across a list of date rows."""
    return {
        "clicks": sum(int(r.get("clicks", 0)) for r in rows),
        "impressions": sum(int(r.get("impressions", 0)) for r in rows),
    }


def _decline_pct(old_val: float, new_val: float) -> float:
    """Return positive % if new < old (a decline). Negative if new > old (growth)."""
    if old_val <= 0:
        return 0.0
    return round((old_val - new_val) / old_val * 100, 1)


def analyze(
    data_dir: pathlib.Path,
    *,
    decay_threshold_pct: float = DEFAULT_DECAY_THRESHOLD_PCT,
) -> list[dict]:
    """
    Detect content decay using intra-window split and prior-run comparison.

    Parameters
    ----------
    data_dir            : Directory containing date.json, pages.json, and optionally
                          a sibling 'prior/' directory.
    decay_threshold_pct : Flag when click or impression decline >= this % (default 20).

    Returns
    -------
    List of decay finding dicts sorted by clicks_decline_pct descending.
    """
    findings: list[dict] = []

    # --- Signal 1: Intra-window split on date-dimension data ---
    date_path = data_dir / "date.json"
    if date_path.exists():
        with open(date_path) as fh:
            date_rows: list[dict] = json.load(fh)

        valid_rows = [r for r in date_rows if isinstance(r, dict) and r.get("keys")]
        first_half, second_half = _split_date_rows(valid_rows)

        if first_half and second_half:
            first = _sum_metrics(first_half)
            second = _sum_metrics(second_half)

            clicks_decline = _decline_pct(first["clicks"], second["clicks"])
            impressions_decline = _decline_pct(first["impressions"], second["impressions"])

            if (
                first["impressions"] >= MIN_IMPRESSIONS_FIRST_HALF
                and (clicks_decline >= decay_threshold_pct or impressions_decline >= decay_threshold_pct)
            ):
                findings.append({
                    "type": "split",
                    "subject": "property",
                    "url": "(all pages)",
                    "first_half_clicks": first["clicks"],
                    "second_half_clicks": second["clicks"],
                    "first_half_impressions": first["impressions"],
                    "second_half_impressions": second["impressions"],
                    "clicks_decline_pct": clicks_decline,
                    "impressions_decline_pct": impressions_decline,
                    "so_what": (
                        f"Overall property traffic is declining within the analysis window: "
                        f"clicks down {clicks_decline:.1f}% and impressions down "
                        f"{impressions_decline:.1f}% in the second half vs first half."
                    ),
                })

    # --- Signal 2: Prior-run comparison on pages ---
    pages_path = data_dir / "pages.json"
    prior_pages_path = data_dir / "prior" / "pages.json"

    if pages_path.exists() and prior_pages_path.exists():
        with open(pages_path) as fh:
            current_pages: list[dict] = json.load(fh)
        with open(prior_pages_path) as fh:
            prior_pages: list[dict] = json.load(fh)

        # Index prior pages by URL.
        prior_index: dict[str, dict] = {}
        for row in prior_pages:
            if isinstance(row, dict) and row.get("keys"):
                url = row["keys"][0]
                prior_index[url] = row

        for row in current_pages:
            if not isinstance(row, dict) or not row.get("keys"):
                continue
            url = row["keys"][0]
            prior = prior_index.get(url)
            if not prior:
                continue  # New page, not decay.

            curr_clicks = int(row.get("clicks", 0))
            curr_impressions = int(row.get("impressions", 0))
            prior_clicks = int(prior.get("clicks", 0))
            prior_impressions = int(prior.get("impressions", 0))

            if prior_impressions < MIN_IMPRESSIONS_FIRST_HALF:
                continue

            clicks_decline = _decline_pct(prior_clicks, curr_clicks)
            impressions_decline = _decline_pct(prior_impressions, curr_impressions)

            if (
                clicks_decline >= decay_threshold_pct
                and impressions_decline >= decay_threshold_pct
            ):
                findings.append({
                    "type": "prior",
                    "subject": "page",
                    "url": url,
                    "prior_clicks": prior_clicks,
                    "current_clicks": curr_clicks,
                    "prior_impressions": prior_impressions,
                    "current_impressions": curr_impressions,
                    "clicks_decline_pct": clicks_decline,
                    "impressions_decline_pct": impressions_decline,
                    "so_what": (
                        f"{url} has lost {clicks_decline:.1f}% of its clicks "
                        f"and {impressions_decline:.1f}% of impressions vs the prior period. "
                        "Review for content freshness, lost backlinks, or ranking drops."
                    ),
                })

    findings.sort(key=lambda x: x["clicks_decline_pct"], reverse=True)
    return findings
