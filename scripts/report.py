"""
report.py — Render a report_data.json into a self-contained HTML report.

Usage:
    python3 scripts/report.py <path-to-report_data.json> [--out <output.html>]

The template is resolved relative to this file's location at:
    ../templates/report.html

All CSS is inlined in a <style> block.  Chart.js is loaded from CDN.
Output is a single self-contained .html file.
"""

import argparse
import json
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_TEMPLATES = _ROOT / "templates"


def _fmt_pct(value: float | None, decimals: int = 1) -> str:
    """Format a float as a percentage string, e.g. 2.57 → '2.6%'."""
    if value is None:
        return "—"
    return f"{value * 100:.{decimals}f}%"


def _fmt_number(value: int | float | None, decimals: int = 0) -> str:
    """Format a number with thousands separator."""
    if value is None:
        return "—"
    if decimals == 0:
        return f"{int(value):,}"
    return f"{value:,.{decimals}f}"


def _fmt_delta_pct(value: float | None) -> str:
    """Format a percentage delta with sign, e.g. -10.9 → '-10.9%'."""
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def _fmt_delta_pos(value: float | None) -> str:
    """Format a position delta (lower is better, so negate sign convention)."""
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}"


def _headline_verdict(recommendations: list) -> str:
    """Generate the one-line headline verdict."""
    total = len(recommendations)
    quick_wins = sum(1 for r in recommendations if r.get("category") == "quick_win")
    ctr_opts = sum(1 for r in recommendations if r.get("category") == "ctr_optimization")
    combined_quick = quick_wins + ctr_opts
    if total == 0:
        return "No priority actions identified."
    parts = [f"{total} priority action{'s' if total != 1 else ''} identified"]
    if combined_quick:
        parts.append(f"{combined_quick} quick win{'s' if combined_quick != 1 else ''}")
    return " — ".join(parts)


def _short_page(url: str) -> str:
    """Shorten a URL to just the path component for display."""
    if not url or url == "unknown":
        return url
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path.rstrip("/") or "/"
        return path
    except Exception:
        return url


def _cwv_color(category: str) -> str:
    """Map a CWV category to a CSS class name."""
    mapping = {
        "GOOD": "good",
        "NEEDS_IMPROVEMENT": "warn",
        "POOR": "poor",
    }
    return mapping.get(category, "neutral")


def prepare_template_context(data: dict) -> dict:
    """Build the full Jinja2 context from report_data."""
    meta = data.get("meta", {})
    summary = data.get("summary", {})
    recommendations = data.get("recommendations", [])
    analyses = data.get("analyses", {})
    charts = data.get("charts", {})
    icp = data.get("icp") or {}

    wow = summary.get("wow") or {}

    # Compute headline
    headline = _headline_verdict(recommendations)

    # Category display names and order
    category_meta = {
        "quick_win":        {"label": "Quick Win",         "icon": "⚡", "order": 0},
        "ctr_optimization": {"label": "CTR Optimization",  "icon": "↑",  "order": 1},
        "on_page":          {"label": "On-Page",           "icon": "📝", "order": 2},
        "cannibalization":  {"label": "Cannibalization",   "icon": "⚔",  "order": 3},
        "decay_recovery":   {"label": "Decay Recovery",    "icon": "📉", "order": 4},
        "technical_seo":    {"label": "Technical SEO",     "icon": "⚙",  "order": 5},
        "content_gap":      {"label": "Content Gap",       "icon": "🔍", "order": 6},
    }

    # Impact labels
    impact_labels = {1: "Low", 2: "Low", 3: "Medium", 4: "High", 5: "High"}
    effort_labels = {1: "Easy", 2: "Easy", 3: "Medium", 4: "Hard", 5: "Hard"}
    impact_class = {1: "low", 2: "low", 3: "medium", 4: "high", 5: "high"}
    effort_class = {1: "easy", 2: "easy", 3: "medium", 4: "hard", 5: "hard"}

    # Annotate recommendations with display metadata
    annotated_recs = []
    for i, rec in enumerate(recommendations):
        cat = rec.get("category", "other")
        imp = rec.get("impact", 1)
        eff = rec.get("effort", 1)
        annotated_recs.append({
            **rec,
            "rank": i + 1,
            "category_label": category_meta.get(cat, {}).get("label", cat),
            "category_icon":  category_meta.get(cat, {}).get("icon", ""),
            "impact_label":   impact_labels.get(imp, str(imp)),
            "impact_class":   impact_class.get(imp, "medium"),
            "effort_label":   effort_labels.get(eff, str(eff)),
            "effort_class":   effort_class.get(eff, "medium"),
            "is_quick":       cat in ("quick_win", "ctr_optimization"),
        })

    # Position delta: positive means position worsened (went up numerically = bad).
    # We want to show green when position improved (went down numerically).
    position_delta = wow.get("position_delta")
    pos_delta_class = ""
    if position_delta is not None:
        # positive position_delta = position worsened = red
        pos_delta_class = "delta-neg" if position_delta > 0 else ("delta-pos" if position_delta < 0 else "")

    # Format summary WoW
    clicks_delta_pct = wow.get("clicks_delta_pct")
    impressions_delta_pct = wow.get("impressions_delta_pct")
    ctr_delta = wow.get("ctr_delta")

    # Charts: serialize as JSON strings for embedding in JS
    clicks_by_date = charts.get("clicks_by_date", [])
    top_pages = charts.get("top_pages", [])[:10]
    position_dist = charts.get("position_distribution", [])
    recs_by_cat = charts.get("recommendations_by_category", [])

    # WoW detail for top pages
    top_page_deltas = (analyses.get("wow") or {}).get("top_page_deltas", [])

    # Process onpage for appendix
    onpage_rows = []
    for row in (analyses.get("onpage") or []):
        issues = row.get("issues", [])
        onpage_rows.append({
            "url": row.get("url", ""),
            "short_url": _short_page(row.get("url", "")),
            "title": row.get("title") or "—",
            "word_count": row.get("word_count", 0),
            "issues": issues,
            "issue_count": len(issues),
            "status": "ok" if not issues else "warn",
        })

    # Process CWV for appendix
    cwv_rows = []
    for row in (analyses.get("core_web_vitals") or []):
        cwv_rows.append({
            "url": row.get("url", ""),
            "short_url": _short_page(row.get("url", "")),
            "score": row.get("performance_score", "—"),
            "lcp_ms": row.get("lcp_ms", "—"),
            "lcp_cat": row.get("lcp_category", "—"),
            "lcp_class": _cwv_color(row.get("lcp_category", "")),
            "cls": row.get("cls", "—"),
            "cls_cat": row.get("cls_category", "—"),
            "cls_class": _cwv_color(row.get("cls_category", "")),
            "inp_ms": row.get("inp_ms", "—"),
            "inp_cat": row.get("inp_category", "—"),
            "inp_class": _cwv_color(row.get("inp_category", "")),
            "issues": row.get("issues", []),
            "score_class": "good" if row.get("performance_score", 0) >= 90 else (
                "warn" if row.get("performance_score", 0) >= 50 else "poor"
            ),
        })

    # Process striking distance for appendix
    sd_rows = []
    for row in (analyses.get("striking_distance") or []):
        sd_rows.append({
            "query": row.get("query", ""),
            "position": row.get("position", 0),
            "impressions": _fmt_number(row.get("impressions")),
            "clicks": _fmt_number(row.get("clicks")),
            "extra_clicks": _fmt_number(row.get("estimated_extra_clicks")),
            "best_page": _short_page(row.get("best_page", "unknown")),
        })

    # Process cannibalization for appendix
    can_rows = []
    for row in (analyses.get("cannibalization") or []):
        can_rows.append({
            "query": row.get("query", ""),
            "canonical": _short_page(row.get("canonical", "")),
            "pages": [
                {
                    "page": _short_page(p.get("page", "")),
                    "clicks": _fmt_number(p.get("clicks")),
                    "position": p.get("position", 0),
                }
                for p in row.get("pages", [])
            ],
            "total_clicks": _fmt_number(row.get("total_clicks")),
        })

    # Process CTR outliers for appendix
    ctr_rows = []
    for row in (analyses.get("ctr_outliers") or []):
        ctr_rows.append({
            "query": row.get("query", ""),
            "position": row.get("position", 0),
            "impressions": _fmt_number(row.get("impressions")),
            "actual_ctr": _fmt_pct(row.get("actual_ctr")),
            "expected_ctr": _fmt_pct(row.get("expected_ctr")),
            "click_gap": _fmt_number(row.get("click_gap")),
            "best_page": _short_page(row.get("best_page", "unknown")),
        })

    # Process content decay for appendix
    decay_rows = []
    for row in (analyses.get("content_decay") or []):
        decay_rows.append({
            "url": row.get("url", "(all pages)"),
            "short_url": _short_page(row.get("url", "")),
            "type": row.get("type", ""),
            "clicks_decline_pct": row.get("clicks_decline_pct", 0),
            "impressions_decline_pct": row.get("impressions_decline_pct", 0),
            "current_clicks": _fmt_number(row.get("current_clicks") or row.get("second_half_clicks")),
            "prior_clicks": _fmt_number(row.get("prior_clicks") or row.get("first_half_clicks")),
        })

    # Domain display
    domain = meta.get("domain", "")
    site_url = meta.get("site_url", "")
    if site_url.startswith("sc-domain:"):
        display_domain = site_url[len("sc-domain:"):]
    else:
        display_domain = domain or site_url

    return {
        "meta": meta,
        "display_domain": display_domain,
        "icp": icp,
        "headline": headline,
        "summary": summary,
        "recommendations": annotated_recs,
        "total_recs": len(recommendations),
        "quick_wins_count": sum(1 for r in recommendations if r.get("category") in ("quick_win", "ctr_optimization")),

        # WoW summary display
        "clicks": _fmt_number(summary.get("clicks")),
        "impressions": _fmt_number(summary.get("impressions")),
        "ctr": _fmt_pct(summary.get("ctr")),
        "position": f"{summary.get('position', 0):.1f}",

        "clicks_delta": _fmt_delta_pct(clicks_delta_pct),
        "clicks_delta_class": "delta-pos" if (clicks_delta_pct or 0) > 0 else ("delta-neg" if (clicks_delta_pct or 0) < 0 else ""),
        "impressions_delta": _fmt_delta_pct(impressions_delta_pct),
        "impressions_delta_class": "delta-pos" if (impressions_delta_pct or 0) > 0 else ("delta-neg" if (impressions_delta_pct or 0) < 0 else ""),
        "ctr_delta": f"{(ctr_delta or 0)*100:+.2f}pp",
        "ctr_delta_class": "delta-pos" if (ctr_delta or 0) > 0 else ("delta-neg" if (ctr_delta or 0) < 0 else ""),
        "position_delta": _fmt_delta_pos(position_delta),
        "position_delta_class": pos_delta_class,

        # Charts (JSON for JS)
        "clicks_by_date_json": json.dumps(clicks_by_date),
        "top_pages_json": json.dumps(top_pages),
        "position_dist_json": json.dumps(position_dist),
        "recs_by_cat_json": json.dumps(recs_by_cat),

        # Appendix data
        "top_page_deltas": top_page_deltas,
        "onpage_rows": onpage_rows,
        "cwv_rows": cwv_rows,
        "sd_rows": sd_rows,
        "can_rows": can_rows,
        "ctr_rows": ctr_rows,
        "decay_rows": decay_rows,

        # Helpers
        "category_meta": {
            "quick_win":        {"label": "Quick Win",         "css": "cat-quick-win"},
            "ctr_optimization": {"label": "CTR Optimization",  "css": "cat-ctr"},
            "on_page":          {"label": "On-Page",           "css": "cat-onpage"},
            "cannibalization":  {"label": "Cannibalization",   "css": "cat-cannibalization"},
            "decay_recovery":   {"label": "Decay Recovery",    "css": "cat-decay"},
            "technical_seo":    {"label": "Technical SEO",     "css": "cat-technical"},
            "content_gap":      {"label": "Content Gap",       "css": "cat-content-gap"},
        },
    }


def render(report_data_path: pathlib.Path, out_path: pathlib.Path) -> None:
    """Load JSON, render template, write HTML."""
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
    except ImportError:
        print("ERROR: jinja2 is required. Install with: pip install jinja2", file=sys.stderr)
        sys.exit(1)

    with open(report_data_path) as fh:
        data = json.load(fh)

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )

    # Register custom filters
    env.filters["fmt_pct"] = _fmt_pct
    env.filters["fmt_number"] = _fmt_number
    env.filters["fmt_delta_pct"] = _fmt_delta_pct
    env.filters["short_page"] = _short_page
    env.filters["cwv_color"] = _cwv_color

    template = env.get_template("report.html")
    ctx = prepare_template_context(data)
    html = template.render(**ctx)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"[report] Written: {out_path}")
    print(f"[report] Recommendations: {ctx['total_recs']}")
    print(f"[report] Domain: {ctx['display_domain']}")


def main():
    parser = argparse.ArgumentParser(
        description="Render a report_data.json into a self-contained HTML report."
    )
    parser.add_argument("report_data", help="Path to report_data.json")
    parser.add_argument("--out", default=None,
                        help="Output path (default: report.html next to the input JSON)")
    args = parser.parse_args()

    report_data_path = pathlib.Path(args.report_data).resolve()
    if not report_data_path.exists():
        print(f"ERROR: file not found: {report_data_path}", file=sys.stderr)
        sys.exit(1)

    if args.out:
        out_path = pathlib.Path(args.out).resolve()
    else:
        out_path = report_data_path.parent / "report.html"

    render(report_data_path, out_path)


if __name__ == "__main__":
    main()
