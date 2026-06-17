#!/usr/bin/env python3
"""
cli_serp_bing_organic.py — DataForSEO SERP: Bing Organic results.

Fetches organic search results from Bing. Useful for competitive analysis
beyond Google and for audiences on Microsoft platforms.

Endpoint (live):  /serp/bing/organic/live/advanced
Endpoint (async): /serp/bing/organic/task_post + task_get/advanced

Usage:
  python dataforseo/cli_serp_bing_organic.py --keyword "seo tools kostenlos"
  python dataforseo/cli_serp_bing_organic.py --demo
  python dataforseo/cli_serp_bing_organic.py --help
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
        description="Fetch Bing organic SERP results via DataForSEO.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--keyword", "-k", help="Search keyword.")
    p.add_argument(
        "--live",
        action="store_true",
        help="Use live (synchronous) endpoint.",
    )
    p.add_argument(
        "--depth",
        type=int,
        default=10,
        help="Number of results (default: 10, max: 700).",
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
    fixture = pathlib.Path(__file__).parent / "fixtures" / "serp_bing_organic.json"
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
            "location_code": args.location_code,
            "language_code": args.language_code,
        })

        creds = {}
        if args.login:
            creds["login"] = args.login
        if args.password:
            creds["password"] = args.password

        if args.live:
            results, cost = run_live("/serp/bing/organic/live/advanced", [payload], **creds)
        else:
            results, cost = run_task(
                "/serp/bing/organic/task_post",
                [payload],
                fetch_endpoint="/serp/bing/organic",
                **creds,
            )

    if args.json:
        print_json(results)
    else:
        for serp in results:
            kw = serp.get("keyword", "")
            items = serp.get("items", [])
            organic = [i for i in items if i.get("type") == "organic"]
            print(f"Keyword: {kw!r} | Organic: {len(organic)} / Total items: {len(items)}")
            print()
            print_table(
                organic,
                columns=[
                    ("rank_group", "Pos", 4),
                    ("domain", "Domain", 30),
                    ("title", "Title", 55),
                ],
                title="Bing Organic Results",
            )

    print_cost(cost)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
