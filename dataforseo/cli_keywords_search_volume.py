#!/usr/bin/env python3
"""
cli_keywords_search_volume.py — DataForSEO: Google Ads search volume, CPC, competition.

Fetches monthly search volume, cost-per-click, and competition data for
a list of keywords via the Google Ads API (DataForSEO acts as proxy).

Endpoint (live only): /keywords_data/google_ads/search_volume/live

Usage:
  python dataforseo/cli_keywords_search_volume.py --keywords "seo tools" "keyword recherche"
  python dataforseo/cli_keywords_search_volume.py --keywords-file kw.txt
  python dataforseo/cli_keywords_search_volume.py --demo
  python dataforseo/cli_keywords_search_volume.py --help
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dataforseo._common import (  # noqa: E402
    add_auth_args,
    add_demo_arg,
    add_location_args,
    add_output_args,
    die,
    print_cost,
    print_json,
    print_table,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Fetch Google Ads search volume + CPC data via DataForSEO.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument(
        "--keywords",
        "-k",
        nargs="+",
        metavar="KW",
        help="One or more keywords.",
    )
    g.add_argument(
        "--keywords-file",
        metavar="FILE",
        help="Path to a text file with one keyword per line.",
    )
    add_location_args(p)
    add_auth_args(p)
    add_output_args(p)
    add_demo_arg(p)
    return p


def load_demo() -> tuple[list[dict], float]:
    fixture = pathlib.Path(__file__).parent / "fixtures" / "keywords_search_volume.json"
    data = json.loads(fixture.read_text())
    tasks = data.get("tasks", [])
    results = []
    for t in tasks:
        results.extend(t.get("result", []))
    return results, data.get("cost", 0.0)


def run(args: argparse.Namespace) -> None:
    if args.demo:
        results, cost = load_demo()
        print("(demo mode — fixture data, no network call)\n", file=sys.stderr)
    else:
        keywords: list[str] = []
        if args.keywords:
            keywords = args.keywords
        elif args.keywords_file:
            path = pathlib.Path(args.keywords_file)
            if not path.exists():
                die(f"Keywords file not found: {path}")
            keywords = [l.strip() for l in path.read_text().splitlines() if l.strip()]
        else:
            die("Provide --keywords or --keywords-file (or use --demo)")

        if len(keywords) > 700:
            die("DataForSEO allows max 700 keywords per request.")

        from dataforseo.client import run_live, with_german_defaults  # noqa: E402

        payload = with_german_defaults({
            "keywords": keywords,
            "location_code": args.location_code,
            "language_code": args.language_code,
        })

        creds = {}
        if args.login:
            creds["login"] = args.login
        if args.password:
            creds["password"] = args.password

        results, cost = run_live(
            "/keywords_data/google_ads/search_volume/live", [payload], **creds
        )

    if args.json:
        print_json(results)
    else:
        for block in results:
            items = block.get("items", [])
            print(f"Keywords: {len(items)}")
            print()
            print_table(
                items,
                columns=[
                    ("keyword", "Keyword", 35),
                    ("search_volume", "Volume/mo", 10),
                    ("cpc", "CPC (€)", 9),
                    ("competition", "Competition", 12),
                    ("competition_index", "Comp.Index", 10),
                ],
                title="Google Ads Search Volume Data",
            )

    print_cost(cost)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
