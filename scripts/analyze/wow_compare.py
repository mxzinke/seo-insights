"""
wow_compare.py — Compare current metrics vs the most recent prior stored run.

"WoW" is used loosely here: it means period-over-period comparison between the
current analysis window and the immediately preceding equal-length window.

Metrics compared:
  - Property-level: clicks, impressions, CTR, average position
  - Top pages: clicks and position delta for each shared URL
  - Top queries: clicks and position delta for each shared query

Important conventions:
  - Position: LOWER IS BETTER. A negative position_delta means IMPROVEMENT.
  - CTR: stored as a ratio (0.0–1.0), displayed as percentage in reports.
  - Position swings of <=3 are treated as noise and not flagged individually.

Output structure (single dict, not a list):
  {
    "has_prior"          : bool,
    "current_summary"    : {clicks, impressions, ctr, position},
    "prior_summary"      : {clicks, impressions, ctr, position} | None,
    "wow": {
      "clicks_delta"         : int,
      "clicks_delta_pct"     : float,
      "impressions_delta"    : int,
      "impressions_delta_pct": float,
      "ctr_delta"            : float,   # absolute change in CTR ratio
      "position_delta"       : float,   # negative = improvement
    } | None,
    "top_page_deltas"    : [ {url, current_clicks, prior_clicks, clicks_delta_pct,
                               current_position, prior_position, position_delta} ],
    "top_query_deltas"   : [ same shape with query instead of url ],
    "baseline_note"      : str | None,   # set when has_prior = False
    "so_what"            : str,
  }
"""

import json
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Position changes within this band are treated as noise.
POSITION_NOISE_THRESHOLD = 3.0

# Top N pages and queries to include in deltas list.
TOP_N = 10


def _pct_delta(old_val: float, new_val: float) -> float:
    """Return % change from old to new. Positive = growth, negative = decline."""
    if old_val == 0:
        return 0.0
    return round((new_val - old_val) / old_val * 100, 1)


def _load_rows(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path) as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else []


def _load_summary(path: pathlib.Path) -> dict | None:
    """Load summary.json — either a list with one element or a dict."""
    if not path.exists():
        return None
    with open(path) as fh:
        data = json.load(fh)
    if isinstance(data, list) and data:
        return data[0]
    if isinstance(data, dict):
        return data
    return None


def analyze(data_dir: pathlib.Path) -> dict:
    """
    Compare current run metrics to prior run.

    Looks for prior data in data_dir / "prior/".

    Returns the WoW comparison dict described in the module docstring.
    """
    prior_dir = data_dir / "prior"
    has_prior = prior_dir.exists()

    # Load current summary.
    current_summary_raw = _load_summary(data_dir / "summary.json")
    current_summary = None
    if current_summary_raw:
        current_summary = {
            "clicks": int(current_summary_raw.get("clicks", 0)),
            "impressions": int(current_summary_raw.get("impressions", 0)),
            "ctr": round(current_summary_raw.get("ctr", 0.0), 6),
            "position": round(current_summary_raw.get("position", 0.0), 2),
        }

    if not has_prior:
        return {
            "has_prior": False,
            "current_summary": current_summary,
            "prior_summary": None,
            "wow": None,
            "top_page_deltas": [],
            "top_query_deltas": [],
            "baseline_note": (
                "No prior run found. This is the baseline. Run again next period to see deltas."
            ),
            "so_what": "First run — no prior period to compare against. Baseline established.",
        }

    # Load prior summary.
    prior_summary_raw = _load_summary(prior_dir / "summary.json")
    prior_summary = None
    if prior_summary_raw:
        prior_summary = {
            "clicks": int(prior_summary_raw.get("clicks", 0)),
            "impressions": int(prior_summary_raw.get("impressions", 0)),
            "ctr": round(prior_summary_raw.get("ctr", 0.0), 6),
            "position": round(prior_summary_raw.get("position", 0.0), 2),
        }

    wow = None
    if current_summary and prior_summary:
        wow = {
            "clicks_delta": current_summary["clicks"] - prior_summary["clicks"],
            "clicks_delta_pct": _pct_delta(prior_summary["clicks"], current_summary["clicks"]),
            "impressions_delta": current_summary["impressions"] - prior_summary["impressions"],
            "impressions_delta_pct": _pct_delta(prior_summary["impressions"], current_summary["impressions"]),
            "ctr_delta": round(current_summary["ctr"] - prior_summary["ctr"], 6),
            # Negative position delta = improvement (lower position number = higher ranking).
            "position_delta": round(current_summary["position"] - prior_summary["position"], 2),
        }

    # Page-level deltas.
    current_pages = _load_rows(data_dir / "pages.json")
    prior_pages = _load_rows(prior_dir / "pages.json")

    prior_page_index: dict[str, dict] = {}
    for row in prior_pages:
        if row.get("keys"):
            prior_page_index[row["keys"][0]] = row

    page_deltas = []
    for row in sorted(current_pages, key=lambda r: r.get("clicks", 0), reverse=True)[:TOP_N]:
        if not row.get("keys"):
            continue
        url = row["keys"][0]
        prior = prior_page_index.get(url)
        if not prior:
            continue
        page_deltas.append({
            "url": url,
            "current_clicks": int(row.get("clicks", 0)),
            "prior_clicks": int(prior.get("clicks", 0)),
            "clicks_delta_pct": _pct_delta(prior.get("clicks", 0), row.get("clicks", 0)),
            "current_position": round(row.get("position", 0.0), 1),
            "prior_position": round(prior.get("position", 0.0), 1),
            "position_delta": round(row.get("position", 0.0) - prior.get("position", 0.0), 1),
        })

    # Query-level deltas.
    current_queries = _load_rows(data_dir / "queries.json")
    prior_queries = _load_rows(prior_dir / "queries.json")

    prior_query_index: dict[str, dict] = {}
    for row in prior_queries:
        if row.get("keys"):
            prior_query_index[row["keys"][0]] = row

    query_deltas = []
    for row in sorted(current_queries, key=lambda r: r.get("clicks", 0), reverse=True)[:TOP_N]:
        if not row.get("keys"):
            continue
        query = row["keys"][0]
        prior = prior_query_index.get(query)
        if not prior:
            continue
        query_deltas.append({
            "query": query,
            "current_clicks": int(row.get("clicks", 0)),
            "prior_clicks": int(prior.get("clicks", 0)),
            "clicks_delta_pct": _pct_delta(prior.get("clicks", 0), row.get("clicks", 0)),
            "current_position": round(row.get("position", 0.0), 1),
            "prior_position": round(prior.get("position", 0.0), 1),
            "position_delta": round(row.get("position", 0.0) - prior.get("position", 0.0), 1),
        })

    # Compose a plain-English summary.
    if wow:
        direction = "up" if wow["clicks_delta"] >= 0 else "down"
        pos_change = "improved" if wow["position_delta"] < 0 else "declined"
        so_what = (
            f"Period-over-period: clicks {direction} {abs(wow['clicks_delta_pct']):.1f}%, "
            f"impressions {'+' if wow['impressions_delta_pct'] >= 0 else ''}"
            f"{wow['impressions_delta_pct']:.1f}%, "
            f"avg position {pos_change} by {abs(wow['position_delta']):.1f} "
            f"({'lower is better' if wow['position_delta'] < 0 else 'higher is worse'})."
        )
    else:
        so_what = "Insufficient data to compute period comparison."

    return {
        "has_prior": True,
        "current_summary": current_summary,
        "prior_summary": prior_summary,
        "wow": wow,
        "top_page_deltas": page_deltas,
        "top_query_deltas": query_deltas,
        "baseline_note": None,
        "so_what": so_what,
    }
