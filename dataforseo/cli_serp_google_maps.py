#!/usr/bin/env python3
"""
cli_serp_google_maps.py — DataForSEO SERP: Google Maps / Local Pack.

Fetches local business listings from Google Maps SERPs — including name,
address, rating, phone, and category. Essential for local SEO analysis.

Endpoint (live):  /serp/google/maps/live/advanced
Endpoint (async): /serp/google/maps/task_post + task_get/advanced

Usage:
  python dataforseo/cli_serp_google_maps.py --keyword "seo agentur berlin"
  python dataforseo/cli_serp_google_maps.py --demo
  python dataforseo/cli_serp_google_maps.py --help
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
        description="Fetch Google Maps local pack results via DataForSEO.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--keyword", "-k", help="Search keyword (e.g. 'seo agentur berlin').")
    p.add_argument(
        "--live",
        action="store_true",
        help="Use live (synchronous) endpoint.",
    )
    p.add_argument(
        "--depth",
        type=int,
        default=10,
        help="Number of results (default: 10).",
    )
    add_location_args(p)
    add_auth_args(p)
    add_output_args(p)
    add_demo_arg(p)
    return p


def load_demo() -> tuple[list[dict], float]:
    fixture = pathlib.Path(__file__).parent / "fixtures" / "serp_google_maps.json"
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
        if not args.keyword:
            die("--keyword is required (or use --demo)")

        from dataforseo.client import run_live, run_task, with_german_defaults  # noqa: E402

        payload = with_german_defaults({
            "keyword": args.keyword,
            "depth": args.depth,
            "location_code": args.location_code,
            "language_code": args.language_code,
        })

        creds = {}
        if args.login:
            creds["login"] = args.login
        if args.password:
            creds["password"] = args.password

        if args.live:
            results, cost = run_live("/serp/google/maps/live/advanced", [payload], **creds)
        else:
            results, cost = run_task(
                "/serp/google/maps/task_post",
                [payload],
                fetch_endpoint="/serp/google/maps",
                **creds,
            )

    if args.json:
        print_json(results)
    else:
        for serp in results:
            kw = serp.get("keyword", "")
            items = serp.get("items", [])
            print(f"Keyword: {kw!r} | Results: {len(items)}")
            print()

            rows = []
            for item in items:
                if item.get("type") != "maps_search":
                    continue
                rating = item.get("rating") or {}
                rows.append({
                    "rank": item.get("rank_group", ""),
                    "title": item.get("title", ""),
                    "rating": f"{rating.get('value', '')}/{rating.get('votes_count', '')}",
                    "address": item.get("address", ""),
                    "domain": item.get("domain", ""),
                })

            print_table(
                rows,
                columns=[
                    ("rank", "#", 3),
                    ("title", "Business", 35),
                    ("rating", "Rating/Reviews", 18),
                    ("address", "Address", 35),
                    ("domain", "Domain", 25),
                ],
                title="Google Maps Results",
            )

    print_cost(cost)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
