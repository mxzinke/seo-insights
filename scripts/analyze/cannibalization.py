"""
cannibalization.py — Detect keyword cannibalization: one query served by 2+ pages.

When multiple pages compete for the same query, Google may rotate which one it ranks,
depressing overall click performance. The fix is either to merge/redirect the losers
into the canonical or to clearly differentiate their content.

Finding fields:
  query          : the cannibalizing search query
  pages          : list of competing pages, each with clicks/impressions/position
  canonical      : URL of the likely canonical (highest total clicks)
  cannibalizers  : other competing page URLs
  total_clicks   : sum of clicks across all competing pages
  total_impressions : sum of impressions across all competing pages
  so_what        : one-line summary of the cannibalization risk

Robustness: uses query_page.json which contains (query, page) pairs. Queries
with only one associated page are not flagged.
"""

import json
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Minimum impressions for a competing page to be considered "meaningful".
# Avoids flagging near-zero-traffic pages that happen to have appeared once.
MIN_PAGE_IMPRESSIONS = 20


def analyze(
    data_dir: pathlib.Path,
    *,
    min_page_impressions: int = MIN_PAGE_IMPRESSIONS,
) -> list[dict]:
    """
    Detect keyword cannibalization from query+page dimension data.

    Parameters
    ----------
    data_dir            : Directory containing query_page.json.
    min_page_impressions: A page must have at least this many impressions to count
                          as a meaningful competitor for a query.

    Returns
    -------
    List of cannibalization finding dicts, sorted by total_clicks desc.
    """
    qp_path = data_dir / "query_page.json"
    if not qp_path.exists():
        return []

    with open(qp_path) as fh:
        qp_rows: list[dict] = json.load(fh)

    # Aggregate per (query, page) pair.
    # Structure: {query: {page: {clicks, impressions, position}}}
    query_pages: dict[str, dict[str, dict]] = {}

    for row in qp_rows:
        if not isinstance(row, dict) or "keys" not in row:
            continue
        keys = row["keys"]
        if len(keys) < 2:
            continue
        query, page = keys[0], keys[1]
        impressions = int(row.get("impressions", 0))
        if impressions < min_page_impressions:
            continue
        entry = query_pages.setdefault(query, {})
        entry[page] = {
            "page": page,
            "clicks": int(row.get("clicks", 0)),
            "impressions": impressions,
            "position": round(row.get("position", 0.0), 1),
        }

    findings: list[dict] = []

    for query, pages in query_pages.items():
        if len(pages) < 2:
            continue  # Not cannibalization — only one page ranks.

        pages_list = sorted(pages.values(), key=lambda p: p["clicks"], reverse=True)
        canonical = pages_list[0]["page"]
        cannibalizers = [p["page"] for p in pages_list[1:]]
        total_clicks = sum(p["clicks"] for p in pages_list)
        total_impressions = sum(p["impressions"] for p in pages_list)

        findings.append({
            "query": query,
            "pages": pages_list,
            "canonical": canonical,
            "cannibalizers": cannibalizers,
            "total_clicks": total_clicks,
            "total_impressions": total_impressions,
            "so_what": (
                f'"{query}" is served by {len(pages_list)} competing pages '
                "(" + ", ".join(p["page"] for p in pages_list[:3])
                + ("..." if len(pages_list) > 3 else "") + "). "
                f"Likely canonical: {canonical}. Consolidate or differentiate to stop splitting authority."
            ),
        })

    findings.sort(key=lambda x: x["total_clicks"], reverse=True)
    return findings
