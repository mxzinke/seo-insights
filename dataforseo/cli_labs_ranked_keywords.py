#!/usr/bin/env python3
"""
cli_labs_ranked_keywords.py — DataForSEO Labs: All keywords a domain ranks for.

Returns every keyword for which a target domain has a Google organic ranking,
including position, URL, estimated traffic (ETV), search volume, and CPC.
Essential for competitor research and gap analysis.

Endpoint (live): /dataforseo_labs/google/ranked_keywords/live

Cost: $0.01/task + $0.0001/item (first 100 items: ~$0.02).

Usage:
  python dataforseo/cli_labs_ranked_keywords.py --target example.de
  python dataforseo/cli_labs_ranked_keywords.py --target competitor.de --limit 50
  python dataforseo/cli_labs_ranked_keywords.py --demo
  python dataforseo/cli_labs_ranked_keywords.py --help
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
        description="Fetch all keywords a domain ranks for via DataForSEO Labs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--target", "-t", help="Target domain (e.g. 'example.de').")
    p.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Number of ranked keywords to fetch (default: 100, max: 1000).",
    )
    p.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Pagination offset (default: 0).",
    )
    p.add_argument(
        "--min-position",
        type=int,
        default=None,
        metavar="N",
        help="Filter: only show rankings with position <= N (e.g. --min-position 20 for top 20).",
    )
    add_location_args(p)
    add_auth_args(p)
    add_output_args(p)
    add_demo_arg(p)
    return p


def load_demo() -> tuple[list[dict], float]:
    fixture = pathlib.Path(__file__).parent / "fixtures" / "labs_ranked_keywords.json"
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
        if not args.target:
            die("--target is required (or use --demo)")

        from dataforseo.client import run_live, with_german_defaults  # noqa: E402

        payload = with_german_defaults({
            "target": args.target,
            "limit": args.limit,
            "offset": args.offset,
            "location_code": args.location_code,
            "language_code": args.language_code,
        })

        creds = {}
        if args.login:
            creds["login"] = args.login
        if args.password:
            creds["password"] = args.password

        results, cost = run_live(
            "/dataforseo_labs/google/ranked_keywords/live", [payload], **creds
        )

    if args.json:
        print_json(results)
    else:
        for block in results:
            target = block.get("website", "")
            total = block.get("total_count", 0)
            items = block.get("items", [])

            print(f"Domain: {target!r} | Total ranked keywords: {total} | Showing: {len(items)}")
            print()

            rows = []
            for item in items:
                serp = (item.get("ranked_serp_element") or {}).get("serp_item") or {}
                kw_data = item.get("keyword_data") or {}
                kw_info = kw_data.get("keyword_info") or {}

                pos = serp.get("rank_group", "")
                if args.min_position is not None and pos and int(pos) > args.min_position:
                    continue

                rows.append({
                    "keyword": kw_data.get("keyword", ""),
                    "position": pos,
                    "url": serp.get("url", ""),
                    "volume": kw_info.get("search_volume", ""),
                    "etv": serp.get("etv", ""),
                    "cpc": kw_info.get("cpc", ""),
                })

            # Sort by position
            rows.sort(key=lambda r: r.get("position") or 9999)

            print_table(
                rows,
                columns=[
                    ("position", "Pos", 4),
                    ("keyword", "Keyword", 35),
                    ("volume", "Volume", 8),
                    ("etv", "ETV", 6),
                    ("cpc", "CPC", 6),
                    ("url", "URL", 50),
                ],
                title="Ranked Keywords",
            )
            print()
            print("ETV = Estimated Traffic Value (estimated monthly clicks from this keyword)")

    print_cost(cost)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
