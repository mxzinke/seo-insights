#!/usr/bin/env python3
"""
cli_labs_search_intent.py — DataForSEO Labs: Search Intent classification.

Classifies keywords by search intent (informational, navigational, commercial,
transactional) with probability scores. Fills the gap our free pipeline covers
heuristically — DataForSEO provides API-level intent classification.

Endpoint (live): /dataforseo_labs/google/search_intent/live

Usage:
  python dataforseo/cli_labs_search_intent.py --keywords "seo tools kostenlos" "was ist seo"
  python dataforseo/cli_labs_search_intent.py --demo
  python dataforseo/cli_labs_search_intent.py --help
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

_INTENT_EMOJI = {
    "informational": "[I]",
    "navigational": "[N]",
    "commercial": "[C]",
    "transactional": "[T]",
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Classify search intent for keywords via DataForSEO Labs.",
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
    fixture = pathlib.Path(__file__).parent / "fixtures" / "labs_search_intent.json"
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
            "/dataforseo_labs/google/search_intent/live", [payload], **creds
        )

    if args.json:
        print_json(results)
    else:
        for block in results:
            items = block.get("items", [])
            print(f"Keywords: {len(items)}")
            print()

            rows = []
            for item in items:
                intent_data = item.get("keyword_intent") or {}
                label = intent_data.get("label", "")
                prob = intent_data.get("probability", 0.0)
                secondary = item.get("secondary_keyword_intents") or []
                secondary_str = ", ".join(
                    f"{_INTENT_EMOJI.get(s.get('label',''), s.get('label',''))} {s.get('probability', 0):.0%}"
                    for s in secondary[:2]
                )
                rows.append({
                    "keyword": item.get("keyword", ""),
                    "intent": f"{_INTENT_EMOJI.get(label, label)} {label}",
                    "probability": f"{prob:.0%}",
                    "secondary": secondary_str,
                })

            print_table(
                rows,
                columns=[
                    ("keyword", "Keyword", 35),
                    ("intent", "Primary Intent", 22),
                    ("probability", "Confidence", 10),
                    ("secondary", "Secondary Intents", 35),
                ],
                title="Search Intent Classification",
            )
            print()
            print("Intent key: [I]=Informational [N]=Navigational [C]=Commercial [T]=Transactional")

    print_cost(cost)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
