"""
fetch.py — Pull a full GSC dataset for a configured site and store it locally.

For each run we store:
  data/<domain>/<YYYY-MM-DD>/
    summary.json           — aggregate property metrics (no dimension)
    queries.json           — top queries (dimension: query)
    pages.json             — top pages (dimension: page)
    query_page.json        — query+page pairs (dimensions: query, page)
    date.json              — daily trend (dimension: date)
    country.json           — by country (dimension: country)
    device.json            — by device (dimension: device)

The "prior window" mirrors this structure for the preceding equal-length period,
stored under the same run-date directory so wow_compare.py can locate it.

Date windows:
  --days N      : current window = last N days (default 90), accounting for ~2-day GSC lag.
  --start / --end : explicit date range overrides.

Usage:
  python scripts/fetch.py [--config <path>] [--days 90] [--demo]

  --demo        : Skip live API calls; copy fixtures into data/_demo/<today>/ instead.
"""

import argparse
import json
import os
import pathlib
import sys
import datetime
import shutil

# Add project root to sys.path so scripts can import sibling modules.
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.config_loader import load_config  # noqa: E402
from scripts.auth import get_access_token      # noqa: E402
import scripts.gsc as gsc                      # noqa: E402

# GSC reports data with ~2 day lag; we pull up to yesterday - 2 by default.
GSC_LAG_DAYS = 2

FIXTURE_DIR = _ROOT / "tests" / "fixtures"


def date_range(days: int) -> tuple[str, str]:
    """Return (start, end) YYYY-MM-DD for the last `days` days, accounting for GSC lag."""
    today = datetime.date.today()
    end = today - datetime.timedelta(days=GSC_LAG_DAYS)
    start = end - datetime.timedelta(days=days - 1)
    return str(start), str(end)


def prior_date_range(start: str, end: str) -> tuple[str, str]:
    """Return the equal-length window immediately preceding the given range."""
    s = datetime.date.fromisoformat(start)
    e = datetime.date.fromisoformat(end)
    n_days = (e - s).days + 1
    prior_end = s - datetime.timedelta(days=1)
    prior_start = prior_end - datetime.timedelta(days=n_days - 1)
    return str(prior_start), str(prior_end)


def domain_from_site_url(site_url: str) -> str:
    """Derive a safe directory name from the GSC site URL."""
    url = site_url.replace("sc-domain:", "").rstrip("/")
    # Strip protocol.
    for prefix in ("https://", "http://"):
        if url.startswith(prefix):
            url = url[len(prefix):]
    # Replace path separators with underscores for filesystem safety.
    return url.replace("/", "_")


def fetch_all(access_token: str, site_url: str, start: str, end: str, verbose: bool = False) -> dict:
    """
    Pull all dimension datasets for a given date window.

    Returns a dict keyed by dataset name, each value being the raw GSC response
    (rows list) or an error string.
    """
    datasets = {}

    def _fetch(name: str, dimensions: list[str] | None, **kwargs):
        if verbose:
            dims = dimensions or ["(summary)"]
            print(f"  [fetch] {name}: dimensions={dims} {start} → {end}", file=sys.stderr)
        try:
            if dimensions:
                rows = gsc.search_analytics_all_rows(
                    access_token, site_url, start, end,
                    dimensions=dimensions, verbose=verbose, **kwargs
                )
            else:
                # Summary: single aggregate row, no pagination needed.
                rows = [gsc.query_summary(access_token, site_url, start, end)]
            datasets[name] = rows
            if verbose:
                print(f"    → {len(rows)} rows", file=sys.stderr)
        except Exception as exc:
            print(f"  [fetch] ERROR fetching {name}: {exc}", file=sys.stderr)
            datasets[name] = {"error": str(exc)}

    _fetch("summary", None)
    _fetch("queries", ["query"])
    _fetch("pages", ["page"])
    _fetch("query_page", ["query", "page"])
    _fetch("date", ["date"])
    _fetch("country", ["country"])
    _fetch("device", ["device"])

    return datasets


def save_datasets(datasets: dict, out_dir: pathlib.Path) -> None:
    """Write each dataset to its own JSON file under out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, data in datasets.items():
        path = out_dir / f"{name}.json"
        with open(path, "w") as fh:
            json.dump(data, fh, indent=2)


def run_demo(run_date: str, days: int) -> pathlib.Path:
    """
    Copy fixture files into data/_demo/<run_date>/ so the demo pipeline works
    without any live GSC credentials.
    """
    out_dir = _ROOT / "data" / "_demo" / run_date
    out_dir.mkdir(parents=True, exist_ok=True)

    fixture_names = ["summary", "queries", "pages", "query_page", "date", "country", "device"]
    for name in fixture_names:
        src = FIXTURE_DIR / "current" / f"{name}.json"
        dst = out_dir / f"{name}.json"
        if src.exists():
            shutil.copy2(src, dst)
        else:
            print(f"  [demo] WARNING: fixture {src} not found — skipping", file=sys.stderr)

    # Also copy "prior" fixtures into a prior/ subdirectory of the run dir
    # so that wow_compare.py can find them at data_dir/prior/.
    prior_out = out_dir / "prior"
    prior_out.mkdir(parents=True, exist_ok=True)
    for name in fixture_names:
        src = FIXTURE_DIR / "prior" / f"{name}.json"
        dst = prior_out / f"{name}.json"
        if src.exists():
            shutil.copy2(src, dst)

    # Write a meta.json so downstream scripts know the window.
    end_date = datetime.date.today() - datetime.timedelta(days=GSC_LAG_DAYS)
    start_date = end_date - datetime.timedelta(days=days - 1)
    prior_start, prior_end = prior_date_range(str(start_date), str(end_date))
    meta = {
        "domain": "_demo",
        "site_url": "sc-domain:demo.example.com",
        "run_date": run_date,
        "window": {"start": str(start_date), "end": str(end_date), "days": days},
        "prior_window": {"start": prior_start, "end": prior_end},
        "mode": "demo",
    }
    with open(out_dir / "meta.json", "w") as fh:
        json.dump(meta, fh, indent=2)

    return out_dir


def main():
    parser = argparse.ArgumentParser(description="Fetch GSC data for a site and store locally.")
    parser.add_argument("--config", default=None, help="Path to gsc.env credentials file.")
    parser.add_argument("--days", type=int, default=90, help="Window size in days (default 90).")
    parser.add_argument("--start", default=None, help="Explicit start date YYYY-MM-DD.")
    parser.add_argument("--end", default=None, help="Explicit end date YYYY-MM-DD.")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--demo", action="store_true",
                        help="Use fixture files instead of live GSC (no credentials needed).")
    args = parser.parse_args()

    run_date = str(datetime.date.today())

    if args.demo:
        out_dir = run_demo(run_date, args.days)
        print(f"[fetch] Demo data written to: {out_dir}")
        return

    # Live path: load config and authenticate.
    cfg = load_config(args.config)
    token = get_access_token(cfg["GSC_CLIENT_ID"], cfg["GSC_CLIENT_SECRET"], cfg["GSC_REFRESH_TOKEN"])
    site_url = cfg["GSC_SITE_URL"]
    domain = domain_from_site_url(site_url)

    if args.start and args.end:
        start, end = args.start, args.end
    else:
        start, end = date_range(args.days)

    prior_start, prior_end = prior_date_range(start, end)

    print(f"[fetch] Site: {site_url}")
    print(f"[fetch] Current window: {start} → {end}")
    print(f"[fetch] Prior window:   {prior_start} → {prior_end}")

    out_dir = _ROOT / "data" / domain / run_date
    print(f"[fetch] Output: {out_dir}")

    # Fetch and save current window.
    print("[fetch] Fetching current window …")
    current = fetch_all(token, site_url, start, end, verbose=args.verbose)
    save_datasets(current, out_dir)

    # Fetch and save prior window for WoW comparison.
    prior_dir = out_dir / "prior"
    print("[fetch] Fetching prior window …")
    prior = fetch_all(token, site_url, prior_start, prior_end, verbose=args.verbose)
    save_datasets(prior, prior_dir)

    # Write a meta.json for downstream scripts.
    meta = {
        "domain": domain,
        "site_url": site_url,
        "run_date": run_date,
        "window": {"start": start, "end": end, "days": args.days},
        "prior_window": {"start": prior_start, "end": prior_end},
        "mode": "live",
    }
    with open(out_dir / "meta.json", "w") as fh:
        json.dump(meta, fh, indent=2)

    print("[fetch] Done.")


if __name__ == "__main__":
    main()
