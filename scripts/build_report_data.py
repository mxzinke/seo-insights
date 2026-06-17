"""
build_report_data.py — Orchestrate all analyses and emit a single report_data.json.

This is the main pipeline entry point. It:
  1. Loads data from data/<domain>/<rundate>/ (produced by fetch.py).
  2. Runs all analysis modules.
  3. Generates scored recommendations via recommend.py.
  4. Builds the chart data series.
  5. Emits data/<domain>/<rundate>/report_data.json.

Usage:
  python scripts/build_report_data.py --data-dir data/_demo/2026-06-16 [--icp config/icp.yaml] [--demo]

The --demo flag disables live HTTP calls in onpage_crawl and core_web_vitals.

Contract for report_data.json (consumed by the separate report.py template task):
  See module-level docstring or SKILL.md for the full schema.
"""

import argparse
import datetime
import json
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_icp import load_icp  # noqa: E402
from scripts.recommend import generate_recommendations  # noqa: E402
import scripts.analyze.striking_distance as mod_sd      # noqa: E402
import scripts.analyze.cannibalization as mod_can        # noqa: E402
import scripts.analyze.ctr_outliers as mod_ctr           # noqa: E402
import scripts.analyze.content_decay as mod_decay        # noqa: E402
import scripts.analyze.onpage_crawl as mod_onpage        # noqa: E402
import scripts.analyze.core_web_vitals as mod_cwv        # noqa: E402
import scripts.analyze.wow_compare as mod_wow            # noqa: E402
import scripts.keywords.research as mod_keywords         # noqa: E402


def load_json(path: pathlib.Path) -> list | dict | None:
    """Load a JSON file, returning None if missing."""
    if not path.exists():
        return None
    with open(path) as fh:
        return json.load(fh)


def build_summary_section(data_dir: pathlib.Path, wow_result: dict | None) -> dict:
    """Build the top-level summary section from the stored summary.json."""
    summary_raw = load_json(data_dir / "summary.json")
    if isinstance(summary_raw, list) and summary_raw:
        summary_raw = summary_raw[0]
    if not summary_raw:
        summary_raw = {}

    wow_deltas = None
    if wow_result and wow_result.get("wow"):
        w = wow_result["wow"]
        wow_deltas = {
            "clicks_delta_pct": w.get("clicks_delta_pct"),
            "impressions_delta_pct": w.get("impressions_delta_pct"),
            "ctr_delta": w.get("ctr_delta"),
            "position_delta": w.get("position_delta"),
        }

    return {
        "clicks": int(summary_raw.get("clicks", 0)),
        "impressions": int(summary_raw.get("impressions", 0)),
        "ctr": round(summary_raw.get("ctr", 0.0), 6),
        "position": round(summary_raw.get("position", 0.0), 2),
        "wow": wow_deltas,
    }


_COUNTRY_NAMES: dict[str, str] = {
    "usa": "United States",
    "gbr": "United Kingdom",
    "can": "Canada",
    "aus": "Australia",
    "ind": "India",
    "deu": "Germany",
    "nld": "Netherlands",
    "fra": "France",
    "sgp": "Singapore",
    "bra": "Brazil",
    "jpn": "Japan",
    "kor": "South Korea",
    "chn": "China",
    "esp": "Spain",
    "ita": "Italy",
    "pol": "Poland",
    "swe": "Sweden",
    "nor": "Norway",
    "dnk": "Denmark",
    "fin": "Finland",
    "che": "Switzerland",
    "aut": "Austria",
    "bel": "Belgium",
    "prt": "Portugal",
    "mex": "Mexico",
    "arg": "Argentina",
    "chl": "Chile",
    "col": "Colombia",
    "zaf": "South Africa",
    "nzl": "New Zealand",
    "idn": "Indonesia",
    "mys": "Malaysia",
    "tha": "Thailand",
    "phl": "Philippines",
    "vnm": "Vietnam",
    "pak": "Pakistan",
    "bgd": "Bangladesh",
    "tur": "Turkey",
    "sau": "Saudi Arabia",
    "are": "United Arab Emirates",
    "isr": "Israel",
    "egy": "Egypt",
    "nga": "Nigeria",
    "ken": "Kenya",
    "ukr": "Ukraine",
    "rus": "Russia",
    "cze": "Czech Republic",
    "hun": "Hungary",
    "rou": "Romania",
    "hrv": "Croatia",
}


def build_explore(data_dir: pathlib.Path) -> dict:
    """Build the explore data object for interactive data exploration in the report."""
    from scripts.analyze import CTR_BENCHMARK, CTR_BENCHMARK_FALLBACK, expected_ctr as _expected_ctr  # noqa: PLC0415

    explore: dict = {}

    # ── Queries (top 250 by impressions) ────────────────────────────────────
    query_rows = load_json(data_dir / "queries.json") or []
    queries_sorted = sorted(query_rows, key=lambda r: r.get("impressions", 0), reverse=True)[:250]
    explore["queries"] = [
        {
            "query": r["keys"][0] if r.get("keys") else "",
            "clicks": int(r.get("clicks", 0)),
            "impressions": int(r.get("impressions", 0)),
            "ctr": round(r.get("ctr", 0.0) * 100, 2),   # percent, e.g. 6.49
            "position": round(r.get("position", 0.0), 1),
        }
        for r in queries_sorted
        if isinstance(r, dict) and r.get("keys")
    ]

    # ── Pages ────────────────────────────────────────────────────────────────
    page_rows = load_json(data_dir / "pages.json") or []
    pages_sorted = sorted(page_rows, key=lambda r: r.get("impressions", 0), reverse=True)
    explore["pages"] = [
        {
            "page": r["keys"][0] if r.get("keys") else "",
            "clicks": int(r.get("clicks", 0)),
            "impressions": int(r.get("impressions", 0)),
            "ctr": round(r.get("ctr", 0.0) * 100, 2),
            "position": round(r.get("position", 0.0), 1),
        }
        for r in pages_sorted
        if isinstance(r, dict) and r.get("keys")
    ]

    # ── Countries ────────────────────────────────────────────────────────────
    country_rows = load_json(data_dir / "country.json") or []
    country_sorted = sorted(country_rows, key=lambda r: r.get("impressions", 0), reverse=True)
    explore["countries"] = [
        {
            "country": _COUNTRY_NAMES.get(
                (r["keys"][0] if r.get("keys") else "").lower(),
                (r["keys"][0] if r.get("keys") else "").upper(),
            ),
            "country_code": (r["keys"][0] if r.get("keys") else "").lower(),
            "clicks": int(r.get("clicks", 0)),
            "impressions": int(r.get("impressions", 0)),
            "ctr": round(r.get("ctr", 0.0) * 100, 2),
            "position": round(r.get("position", 0.0), 1),
        }
        for r in country_sorted
        if isinstance(r, dict) and r.get("keys")
    ]

    # ── Devices ──────────────────────────────────────────────────────────────
    device_rows = load_json(data_dir / "device.json") or []
    explore["devices"] = [
        {
            "device": (r["keys"][0] if r.get("keys") else "").title(),
            "clicks": int(r.get("clicks", 0)),
            "impressions": int(r.get("impressions", 0)),
            "ctr": round(r.get("ctr", 0.0) * 100, 2),
            "position": round(r.get("position", 0.0), 1),
        }
        for r in sorted(device_rows, key=lambda r: r.get("impressions", 0), reverse=True)
        if isinstance(r, dict) and r.get("keys")
    ]

    # ── Timeseries ───────────────────────────────────────────────────────────
    date_rows = load_json(data_dir / "date.json") or []
    timeseries = []
    for r in date_rows:
        if isinstance(r, dict) and r.get("keys"):
            timeseries.append({
                "date": r["keys"][0],
                "clicks": int(r.get("clicks", 0)),
                "impressions": int(r.get("impressions", 0)),
                "ctr": round(r.get("ctr", 0.0) * 100, 2),
                "position": round(r.get("position", 0.0), 1),
            })
    timeseries.sort(key=lambda x: x["date"])
    explore["timeseries"] = timeseries

    # ── CTR vs Position scatter (queries with impressions >= 20) ─────────────
    scatter = []
    for r in query_rows:
        if not isinstance(r, dict) or not r.get("keys"):
            continue
        impressions = int(r.get("impressions", 0))
        if impressions < 20:
            continue
        pos = round(r.get("position", 0.0), 1)
        scatter.append({
            "query": r["keys"][0],
            "position": pos,
            "ctr": round(r.get("ctr", 0.0) * 100, 2),   # percent
            "impressions": impressions,
            "clicks": int(r.get("clicks", 0)),
        })
    scatter.sort(key=lambda x: x["impressions"], reverse=True)
    explore["ctr_vs_position"] = scatter

    # ── Benchmark curve ──────────────────────────────────────────────────────
    benchmark_curve = []
    for pos in range(1, 21):
        benchmark_curve.append({
            "position": pos,
            "expected_ctr": round(CTR_BENCHMARK.get(pos, CTR_BENCHMARK_FALLBACK) * 100, 2),
        })
    explore["benchmark_curve"] = benchmark_curve

    return explore


def build_charts(data_dir: pathlib.Path) -> dict:
    """Build chart-ready data series from the stored dimension files."""
    charts: dict = {}

    # Clicks by date (time series).
    date_rows = load_json(data_dir / "date.json") or []
    clicks_by_date = []
    for row in date_rows:
        if isinstance(row, dict) and row.get("keys"):
            clicks_by_date.append({
                "date": row["keys"][0],
                "clicks": int(row.get("clicks", 0)),
                "impressions": int(row.get("impressions", 0)),
            })
    clicks_by_date.sort(key=lambda x: x["date"])
    charts["clicks_by_date"] = clicks_by_date

    # Top pages by clicks.
    page_rows = load_json(data_dir / "pages.json") or []
    top_pages = []
    for row in sorted(page_rows, key=lambda r: r.get("clicks", 0), reverse=True)[:20]:
        if isinstance(row, dict) and row.get("keys"):
            top_pages.append({
                "page": row["keys"][0],
                "clicks": int(row.get("clicks", 0)),
                "impressions": int(row.get("impressions", 0)),
                "position": round(row.get("position", 0.0), 1),
            })
    charts["top_pages"] = top_pages

    # Position distribution bucketed into ranges.
    query_rows = load_json(data_dir / "queries.json") or []
    buckets = {"1-3": 0, "4-10": 0, "11-20": 0, "21-50": 0, "51+": 0}
    for row in query_rows:
        if not isinstance(row, dict):
            continue
        pos = row.get("position", 0)
        if pos <= 3:
            buckets["1-3"] += 1
        elif pos <= 10:
            buckets["4-10"] += 1
        elif pos <= 20:
            buckets["11-20"] += 1
        elif pos <= 50:
            buckets["21-50"] += 1
        else:
            buckets["51+"] += 1
    charts["position_distribution"] = [
        {"bucket": k, "count": v} for k, v in buckets.items()
    ]

    charts["recommendations_by_category"] = []  # Filled in after recs are built.
    return charts


def build_report_data(
    data_dir: pathlib.Path,
    icp_path: pathlib.Path | None = None,
    api_key: str | None = None,
    demo: bool = False,
    cfg: dict | None = None,
) -> dict:
    """
    Run all analyses and assemble the complete report_data dict.

    Parameters
    ----------
    data_dir  : Path to the run directory (contains summary.json, queries.json, etc.)
    icp_path  : Optional path to a validated ICP YAML file.
    api_key   : Optional PageSpeed Insights API key.
    demo      : If True, skip live HTTP requests in onpage/CWV and keyword APIs.
    cfg       : Config dict for optional Google Ads credentials.
    """
    print(f"[build] Data directory: {data_dir}")

    # Load meta.json for window info.
    meta_raw = load_json(data_dir / "meta.json") or {}
    window = meta_raw.get("window", {})
    prior_window = meta_raw.get("prior_window")
    domain = meta_raw.get("domain", data_dir.parent.name)
    site_url = meta_raw.get("site_url", "unknown")

    # Load and validate ICP (optional).
    icp: dict = {}
    if icp_path and icp_path.exists():
        print(f"[build] Loading ICP: {icp_path}")
        icp = load_icp(icp_path)
    elif icp_path:
        print(f"[build] WARNING: ICP file not found at {icp_path} — proceeding without ICP filter.",
              file=sys.stderr)

    # --- Run all analyses ---

    print("[build] Running: striking distance …")
    sd = mod_sd.analyze(data_dir)

    print("[build] Running: cannibalization …")
    can = mod_can.analyze(data_dir)

    print("[build] Running: CTR outliers …")
    ctr = mod_ctr.analyze(data_dir)

    print("[build] Running: content decay …")
    decay = mod_decay.analyze(data_dir)

    print("[build] Running: on-page crawl …")
    onpage = mod_onpage.analyze(data_dir, demo=demo)

    print("[build] Running: Core Web Vitals …")
    cwv = mod_cwv.analyze(data_dir, api_key=api_key, demo=demo)

    print("[build] Running: WoW comparison …")
    wow = mod_wow.analyze(data_dir)

    # --- Keyword research (runs after GSC analyses so position data is available) ---
    print("[build] Running: keyword research …")
    keywords_result = {"enabled": False, "source_note": "Keyword research: ICP required", "opportunities": []}
    if icp:
        try:
            keywords_result = mod_keywords.run_research(
                data_dir=data_dir,
                icp=icp,
                cfg=cfg or {},
                demo=demo,
                verbose=False,
            )
            print(f"[build] Keyword research: {len(keywords_result.get('opportunities', []))} opportunities.")
        except Exception as exc:
            print(f"[build] WARNING: keyword research failed (non-fatal): {exc}", file=sys.stderr)
            keywords_result = {
                "enabled": False,
                "source_note": f"Keyword research failed: {exc}",
                "opportunities": [],
            }
    else:
        print("[build] Skipping keyword research (no ICP configured).")

    analyses = {
        "striking_distance": sd,
        "cannibalization": can,
        "ctr_outliers": ctr,
        "content_decay": decay,
        "onpage": onpage,
        "core_web_vitals": cwv,
        "wow": wow,
    }

    print(f"[build] Findings: sd={len(sd)}, can={len(can)}, ctr={len(ctr)}, "
          f"decay={len(decay)}, onpage={len(onpage)}, "
          f"cwv={'skipped' if cwv is None else len(cwv)}, "
          f"wow=has_prior={wow.get('has_prior', False)}")

    # --- Generate recommendations ---
    print("[build] Generating recommendations …")
    recommendations = generate_recommendations(analyses, icp, keywords_result)
    print(f"[build] {len(recommendations)} recommendations generated.")

    # --- Build summary, charts, and explore data ---
    summary = build_summary_section(data_dir, wow)
    charts = build_charts(data_dir)

    print("[build] Building explore data …")
    explore = build_explore(data_dir)

    # Add recommendation category distribution to charts.
    cat_counts: dict[str, int] = {}
    for rec in recommendations:
        cat = rec.get("category", "other")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    charts["recommendations_by_category"] = [
        {"category": k, "count": v}
        for k, v in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    # --- Assemble final report_data dict ---
    report_data = {
        "meta": {
            "domain": domain,
            "site_url": site_url,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "window": {
                "start": window.get("start", ""),
                "end": window.get("end", ""),
                "days": window.get("days", 90),
            },
            "prior_window": prior_window,
        },
        "icp": icp if icp else None,
        "summary": summary,
        "recommendations": recommendations,
        "analyses": analyses,
        "charts": charts,
        "explore": explore,
        "keywords": keywords_result,
    }

    return report_data


def main():
    parser = argparse.ArgumentParser(
        description="Build report_data.json from a fetched GSC data directory."
    )
    parser.add_argument("--data-dir", required=True,
                        help="Path to the run data directory (e.g. data/_demo/2026-06-16).")
    parser.add_argument("--icp", default=None,
                        help="Path to a validated ICP YAML file.")
    parser.add_argument("--pagespeed-key", default=None,
                        help="PageSpeed Insights API key (overrides config).")
    parser.add_argument("--demo", action="store_true",
                        help="Skip live HTTP calls (on-page crawl and CWV use fixtures).")
    parser.add_argument("--output", default=None,
                        help="Output path for report_data.json (default: <data-dir>/report_data.json).")
    args = parser.parse_args()

    data_dir = pathlib.Path(args.data_dir).resolve()
    if not data_dir.exists():
        print(f"ERROR: data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    icp_path = pathlib.Path(args.icp) if args.icp else None

    # Try to load API key from config if not given on CLI.
    api_key = args.pagespeed_key
    cfg: dict = {}
    if not args.demo:
        try:
            from scripts.config_loader import load_config  # noqa: PLC0415
            cfg = load_config(require_all=False)
            api_key = api_key or cfg.get("PAGESPEED_API_KEY") or None
        except Exception:
            pass

    report_data = build_report_data(
        data_dir=data_dir,
        icp_path=icp_path,
        api_key=api_key,
        demo=args.demo,
        cfg=cfg,
    )

    out_path = pathlib.Path(args.output) if args.output else data_dir / "report_data.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w") as fh:
        json.dump(report_data, fh, indent=2, default=str)

    print(f"[build] report_data.json written to: {out_path}")
    print(f"[build] Recommendations: {len(report_data['recommendations'])}")
    if report_data["recommendations"]:
        top = report_data["recommendations"][0]
        print(f"[build] Top recommendation: [{top['category']}] {top['title']}")


if __name__ == "__main__":
    main()
