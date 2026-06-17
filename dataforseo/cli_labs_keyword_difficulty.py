#!/usr/bin/env python3
"""
cli_labs_keyword_difficulty.py — DataForSEO Labs: Bulk Keyword Difficulty (0-100).

THE key gap-filler vs. free Google-based pipeline: organic keyword difficulty
as a score from 0 (easy) to 100 (very competitive). This endpoint tells you
how hard it is to rank organically for each keyword, which Google Search
Console and Ads APIs do NOT provide.

Endpoint (live): /dataforseo_labs/google/bulk_keyword_difficulty/live

Cost: $0.001/task + $0.0001/keyword (~$0.0013 for 5 keywords, $0.11 for 1000).

Usage:
  python dataforseo/cli_labs_keyword_difficulty.py --keywords "seo tools" "keyword recherche"
  python dataforseo/cli_labs_keyword_difficulty.py --demo
  python dataforseo/cli_labs_keyword_difficulty.py --help
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

_DIFFICULTY_LABELS = {
    range(0, 20): "Very Easy",
    range(20, 40): "Easy",
    range(40, 55): "Medium",
    range(55, 70): "Hard",
    range(70, 85): "Very Hard",
    range(85, 101): "Extremely Hard",
}


def difficulty_label(score: int) -> str:
    for r, label in _DIFFICULTY_LABELS.items():
        if score in r:
            return label
    return "Unknown"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Fetch bulk keyword difficulty scores (0-100) via DataForSEO Labs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument(
        "--keywords",
        "-k",
        nargs="+",
        metavar="KW",
        help="One or more keywords (max 1000 per request).",
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
    fixture = pathlib.Path(__file__).parent / "fixtures" / "labs_keyword_difficulty.json"
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

        if len(keywords) > 1000:
            die("DataForSEO allows max 1000 keywords per bulk_keyword_difficulty request.")

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
            "/dataforseo_labs/google/bulk_keyword_difficulty/live",
            [payload],
            **creds,
        )

    if args.json:
        print_json(results)
    else:
        for block in results:
            items = block.get("items", [])
            print(f"Keywords: {len(items)} | Location: {block.get('location_code')} | Lang: {block.get('language_code')}")
            print()

            # Enrich items with difficulty label for display
            rows = []
            for item in items:
                diff = item.get("keyword_difficulty", 0) or 0
                rows.append({
                    **item,
                    "difficulty_label": difficulty_label(int(diff)),
                })

            print_table(
                rows,
                columns=[
                    ("keyword", "Keyword", 35),
                    ("keyword_difficulty", "Difficulty", 10),
                    ("difficulty_label", "Level", 15),
                    ("search_volume", "Volume/mo", 10),
                    ("cpc", "CPC (€)", 9),
                    ("competition_level", "Competition", 12),
                ],
                title="Keyword Difficulty (0-100)",
            )

    print_cost(cost)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
