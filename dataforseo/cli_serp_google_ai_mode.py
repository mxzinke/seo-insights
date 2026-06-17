#!/usr/bin/env python3
"""
cli_serp_google_ai_mode.py — DataForSEO SERP: Google AI Mode results.

Fetches results from Google's AI Mode SERP (the AI-first search experience).
Returns AI-generated overview text and cited organic results.
Costs ~2x vs standard organic SERP.

Endpoint (live):  /serp/google/ai_mode/live/advanced
Endpoint (async): /serp/google/ai_mode/task_post + task_get/advanced

Usage:
  python dataforseo/cli_serp_google_ai_mode.py --keyword "wie verbessere ich mein seo"
  python dataforseo/cli_serp_google_ai_mode.py --demo
  python dataforseo/cli_serp_google_ai_mode.py --help
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
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Fetch Google AI Mode SERP results via DataForSEO.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--keyword", "-k", help="Search keyword.")
    p.add_argument(
        "--live",
        action="store_true",
        help="Use live (synchronous) endpoint.",
    )
    add_location_args(p)
    add_auth_args(p)
    add_output_args(p)
    add_demo_arg(p)
    return p


def load_demo() -> tuple[list[dict], float]:
    fixture = pathlib.Path(__file__).parent / "fixtures" / "serp_google_ai_mode.json"
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
            "location_code": args.location_code,
            "language_code": args.language_code,
        })

        creds = {}
        if args.login:
            creds["login"] = args.login
        if args.password:
            creds["password"] = args.password

        if args.live:
            results, cost = run_live("/serp/google/ai_mode/live/advanced", [payload], **creds)
        else:
            results, cost = run_task(
                "/serp/google/ai_mode/task_post",
                [payload],
                fetch_endpoint="/serp/google/ai_mode",
                **creds,
            )

    if args.json:
        print_json(results)
    else:
        for serp in results:
            kw = serp.get("keyword", "")
            items = serp.get("items", [])
            print(f"Keyword: {kw!r} | Items: {len(items)}")
            print()

            for item in items:
                itype = item.get("type", "")
                print(f"  Type: {itype}")

                ai_ov = item.get("ai_overview")
                if ai_ov and isinstance(ai_ov, dict):
                    text = ai_ov.get("text", "")
                    print(f"  AI Overview Text:")
                    print(f"    {text[:400]}{'...' if len(text) > 400 else ''}")
                    refs = ai_ov.get("references") or []
                    if refs:
                        print(f"  References ({len(refs)}):")
                        for r in refs[:5]:
                            print(f"    - {r.get('title', '')} ({r.get('url', '')})")

                organic_items = item.get("organic_items") or []
                if organic_items:
                    print(f"\n  Cited organic results ({len(organic_items)}):")
                    for oi in organic_items[:5]:
                        print(f"    #{oi.get('rank_group', '')} {oi.get('domain', '')} — {oi.get('title', '')}")

                print()

    print_cost(cost)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
