#!/usr/bin/env python3
"""
cli_backlinks.py — DataForSEO Backlinks: summary + referring domains.

Fetches backlink data for a domain:
  - Summary: total backlinks, referring domains, domain rank, dofollow ratio
  - Referring domains: per-domain breakdown with rank and link count

Endpoints (live):
  /backlinks/summary/live
  /backlinks/referring_domains/live

IMPORTANT: Backlinks API requires a $100/month minimum spend (separate from
the standard $50 account top-up). Check your plan before using.

Cost: $0.02/request + $0.00003/row for referring_domains.

Usage:
  python dataforseo/cli_backlinks.py --target example.de
  python dataforseo/cli_backlinks.py --target example.de --referring-domains --limit 50
  python dataforseo/cli_backlinks.py --demo
  python dataforseo/cli_backlinks.py --help
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
    add_output_args,
    die,
    print_cost,
    print_json,
    print_table,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Fetch backlink summary and referring domains via DataForSEO.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--target", "-t", help="Target domain (e.g. 'example.de').")
    p.add_argument(
        "--referring-domains",
        action="store_true",
        dest="referring_domains",
        help="Also fetch per-domain referring domain breakdown.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max referring domains to return (default: 20).",
    )
    p.add_argument(
        "--include-subdomains",
        action="store_true",
        dest="include_subdomains",
        help="Include subdomains of the target (default: false).",
    )
    add_auth_args(p)
    add_output_args(p)
    add_demo_arg(p)
    return p


def load_demo() -> tuple[list[dict], float]:
    fixture = pathlib.Path(__file__).parent / "fixtures" / "backlinks.json"
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
        print("NOTE: Backlinks API requires $100/month minimum spend.\n", file=sys.stderr)
    else:
        if not args.target:
            die("--target is required (or use --demo)")

        from dataforseo.client import run_live  # noqa: E402

        creds = {}
        if args.login:
            creds["login"] = args.login
        if args.password:
            creds["password"] = args.password

        all_results: list[dict] = []
        total_cost = 0.0

        # Summary call
        summary_payload = [{"target": args.target, "include_subdomains": args.include_subdomains}]
        res, c = run_live("/backlinks/summary/live", summary_payload, **creds)
        all_results.extend(res)
        total_cost += c

        # Referring domains call
        if args.referring_domains:
            rd_payload = [{"target": args.target, "limit": args.limit, "include_subdomains": args.include_subdomains}]
            res, c = run_live("/backlinks/referring_domains/live", rd_payload, **creds)
            all_results.extend(res)
            total_cost += c

        results = all_results
        cost = total_cost

    if args.json:
        print_json(results)
    else:
        for block in results:
            btype = block.get("type", "")

            if btype == "summary":
                target = block.get("target", "")
                print(f"Backlink Summary: {target}")
                print(f"  Domain Rank:        {block.get('rank', 'n/a')}")
                print(f"  Total Backlinks:    {block.get('backlinks', 0):,}")
                print(f"  New Backlinks:      {block.get('new_backlinks', 0):,}")
                print(f"  Lost Backlinks:     {block.get('lost_backlinks', 0):,}")
                print(f"  Referring Domains:  {block.get('referring_domains', 0):,}")
                print(f"  Referring IPs:      {block.get('referring_ips', 0):,}")
                print(f"  Dofollow Links:     {block.get('dofollow_links', 0):,}")
                print(f"  Broken Backlinks:   {block.get('broken_backlinks', 0):,}")
                print(f"  Indexed Pages:      {block.get('indexed_pages', 0):,}")
                print()

            elif "items" in block:
                # Referring domains result
                items = block.get("items", [])
                total = block.get("total_count", len(items))
                print(f"Referring Domains: {total:,} total | Showing {len(items)}")
                print()
                print_table(
                    items,
                    columns=[
                        ("domain", "Domain", 35),
                        ("rank", "Rank", 6),
                        ("backlinks", "Links", 6),
                        ("backlinks_spam_score", "Spam", 5),
                        ("dofollow", "DoFollow", 9),
                        ("first_seen", "First Seen", 14),
                    ],
                    title="Referring Domains",
                )

    print_cost(cost)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
