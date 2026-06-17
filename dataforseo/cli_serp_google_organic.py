#!/usr/bin/env python3
"""
cli_serp_google_organic.py — DataForSEO SERP: Google Organic results.

Fetches organic search results, SERP features, and People Also Ask boxes
from Google. Supports both live (synchronous) and async task patterns.

Endpoint (live):  /serp/google/organic/live/advanced
Endpoint (async): /serp/google/organic/task_post + task_get/advanced

Usage:
  python dataforseo/cli_serp_google_organic.py --keyword "seo tools"
  python dataforseo/cli_serp_google_organic.py --keyword "seo" --live
  python dataforseo/cli_serp_google_organic.py --keyword "seo" --ai-overview
  python dataforseo/cli_serp_google_organic.py --demo
  python dataforseo/cli_serp_google_organic.py --help
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
        description="Fetch Google organic SERP results via DataForSEO.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--keyword", "-k", help="Search keyword.")
    p.add_argument(
        "--live",
        action="store_true",
        help="Use live (synchronous) endpoint. Higher cost (~$0.002/query) but instant results.",
    )
    p.add_argument(
        "--ai-overview",
        action="store_true",
        dest="ai_overview",
        help="Set load_async_ai_overview=True to capture Google AI Overview in results.",
    )
    p.add_argument(
        "--depth",
        type=int,
        default=10,
        help="Number of results to fetch (default: 10, max: 700).",
    )
    p.add_argument(
        "--device",
        choices=["desktop", "mobile"],
        default="desktop",
        help="Device type (default: desktop).",
    )
    add_location_args(p)
    add_auth_args(p)
    add_output_args(p)
    add_demo_arg(p)
    return p


def load_demo() -> tuple[list[dict], float]:
    fixture = pathlib.Path(__file__).parent / "fixtures" / "serp_google_organic.json"
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
            "device": args.device,
        })
        if args.ai_overview:
            payload["load_async_ai_overview"] = True

        creds = {}
        if args.login:
            creds["login"] = args.login
        if args.password:
            creds["password"] = args.password
        payload.update({
            "location_code": args.location_code,
            "language_code": args.language_code,
        })

        if args.live:
            endpoint = "/serp/google/organic/live/advanced"
            results, cost = run_live(endpoint, [payload], **creds)
        else:
            results, cost = run_task(
                "/serp/google/organic/task_post",
                [payload],
                fetch_endpoint="/serp/google/organic",
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

            organic = [i for i in items if i.get("type") == "organic"]
            paa = [i for i in items if i.get("type") == "people_also_ask"]
            ai_items = [i for i in items if i.get("type") == "ai_overview"]

            if organic:
                print_table(
                    organic,
                    columns=[
                        ("rank_group", "Pos", 4),
                        ("domain", "Domain", 30),
                        ("title", "Title", 55),
                    ],
                    title="Organic Results",
                )

            if paa:
                print(f"\nPeople Also Ask: {len(paa)} block(s)")
                for block in paa:
                    for q in (block.get("items") or []):
                        print(f"  Q: {q.get('title', '')}")

            if ai_items:
                print("\nAI Overview detected")
                ai = ai_items[0].get("ai_overview", {})
                text = ai.get("text", "") if isinstance(ai, dict) else ""
                if text:
                    print(f"  {text[:200]}{'...' if len(text) > 200 else ''}")

    print_cost(cost)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
