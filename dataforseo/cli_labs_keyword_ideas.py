#!/usr/bin/env python3
"""
cli_labs_keyword_ideas.py — DataForSEO Labs: Keyword Ideas with difficulty + intent.

Generates keyword ideas related to seed keywords, with integrated difficulty
scores (0-100), search intent, search volume, and CPC. This combines multiple
data points in one call — ideal for content ideation.

Endpoint (live): /dataforseo_labs/google/keyword_ideas/live

Usage:
  python dataforseo/cli_labs_keyword_ideas.py --keywords "seo tools"
  python dataforseo/cli_labs_keyword_ideas.py --keywords "seo" --limit 20
  python dataforseo/cli_labs_keyword_ideas.py --demo
  python dataforseo/cli_labs_keyword_ideas.py --help
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
        description="Generate keyword ideas with difficulty + intent via DataForSEO Labs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--keywords",
        "-k",
        nargs="+",
        metavar="KW",
        required=False,
        help="Seed keyword(s) to generate ideas for.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of ideas to return (default: 50).",
    )
    p.add_argument(
        "--max-difficulty",
        type=int,
        default=None,
        metavar="N",
        help="Filter: only show keywords with difficulty <= N.",
    )
    p.add_argument(
        "--min-volume",
        type=int,
        default=None,
        metavar="N",
        help="Filter: only show keywords with search volume >= N.",
    )
    add_location_args(p)
    add_auth_args(p)
    add_output_args(p)
    add_demo_arg(p)
    return p


def load_demo() -> tuple[list[dict], float]:
    fixture = pathlib.Path(__file__).parent / "fixtures" / "labs_keyword_ideas.json"
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
        if not args.keywords:
            die("--keywords is required (or use --demo)")

        from dataforseo.client import run_live, with_german_defaults  # noqa: E402

        payload = with_german_defaults({
            "keywords": args.keywords,
            "limit": args.limit,
            "location_code": args.location_code,
            "language_code": args.language_code,
        })

        creds = {}
        if args.login:
            creds["login"] = args.login
        if args.password:
            creds["password"] = args.password

        results, cost = run_live(
            "/dataforseo_labs/google/keyword_ideas/live", [payload], **creds
        )

    if args.json:
        print_json(results)
    else:
        for block in results:
            items = block.get("items", [])

            # Flatten and apply filters
            rows = []
            for item in items:
                kw_info = item.get("keyword_info") or {}
                kw_props = item.get("keyword_properties") or {}
                intent_info = item.get("search_intent_info") or {}

                diff = kw_props.get("keyword_difficulty")
                vol = kw_info.get("search_volume")
                intent = intent_info.get("main_intent", "")

                if args.max_difficulty is not None and diff is not None and diff > args.max_difficulty:
                    continue
                if args.min_volume is not None and vol is not None and vol < args.min_volume:
                    continue

                rows.append({
                    "keyword": item.get("keyword", ""),
                    "volume": vol,
                    "difficulty": diff,
                    "intent": intent,
                    "cpc": kw_info.get("cpc"),
                    "competition": kw_info.get("competition_level", ""),
                })

            # Sort by volume desc
            rows.sort(key=lambda r: r.get("volume") or 0, reverse=True)

            print(f"Keyword ideas: {len(rows)} (after filters)")
            print()
            print_table(
                rows,
                columns=[
                    ("keyword", "Keyword", 40),
                    ("volume", "Volume/mo", 10),
                    ("difficulty", "KD", 5),
                    ("intent", "Intent", 15),
                    ("cpc", "CPC (€)", 9),
                    ("competition", "Competition", 12),
                ],
                title="Keyword Ideas",
            )

    print_cost(cost)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
