#!/usr/bin/env python3
"""
cli_onpage.py — DataForSEO On-Page: crawl a website and audit on-page SEO.

Uses the async task pattern (DataForSEO crawls the site in the background,
typically 1-5 minutes for small sites). Returns page-level SEO data:
meta tags, headings, images, links, Core Web Vitals, and SEO checks.

This can augment the repo's existing on-page audit in scripts/analyze/onpage_crawl.py
with deeper data — BUT it runs independently and does NOT connect to that module.

Endpoints (async):
  POST /on_page/task_post
  GET  /on_page/tasks_ready
  GET  /on_page/pages  (page-level results)
  GET  /on_page/summary  (crawl summary)

Cost: $0.000125/page (base) + optional JS rendering / Lighthouse surcharges.

Usage:
  python dataforseo/cli_onpage.py --target example.de --max-pages 20
  python dataforseo/cli_onpage.py --demo
  python dataforseo/cli_onpage.py --help
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
        description="Crawl and audit a website via DataForSEO On-Page API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--target", "-t", help="Target domain (e.g. 'example.de').")
    p.add_argument(
        "--max-pages",
        type=int,
        default=10,
        dest="max_pages",
        help="Maximum pages to crawl (default: 10, max: 10000).",
    )
    p.add_argument(
        "--enable-javascript",
        action="store_true",
        dest="enable_javascript",
        help="Enable JavaScript rendering (increases cost and crawl time).",
    )
    p.add_argument(
        "--enable-lighthouse",
        action="store_true",
        dest="enable_lighthouse",
        help="Run Lighthouse audit per page (additional cost).",
    )
    p.add_argument(
        "--load-resources",
        action="store_true",
        dest="load_resources",
        help="Load all page resources (CSS, images) for more accurate rendering.",
    )
    p.add_argument(
        "--poll-interval",
        type=float,
        default=10.0,
        dest="poll_interval",
        help="Seconds between tasks_ready polls (default: 10 — on_page is slow).",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="Max seconds to wait for crawl to complete (default: 600).",
    )
    add_auth_args(p)
    add_output_args(p)
    add_demo_arg(p)
    return p


def load_demo() -> tuple[list[dict], float]:
    fixture = pathlib.Path(__file__).parent / "fixtures" / "onpage.json"
    data = json.loads(fixture.read_text())
    # On-Page demo returns the task_post response + page data from _demo_pages key
    pages = data.get("_demo_pages", [])
    cost = data.get("cost", 0.0)
    return pages, cost


def run(args: argparse.Namespace) -> None:
    if args.demo:
        pages, cost = load_demo()
        print("(demo mode — fixture data, no network call)\n", file=sys.stderr)
        print("NOTE: In live mode, on_page crawl is ASYNC and may take 1-5 minutes.\n", file=sys.stderr)

        if args.json:
            print_json(pages)
        else:
            print(f"Pages crawled: {len(pages)}")
            print()
            rows = []
            for page in pages:
                meta = page.get("meta") or {}
                content = page.get("content") or {}
                checks = page.get("checks") or {}
                issues = [k for k, v in checks.items() if v is False]
                rows.append({
                    "url": page.get("url", ""),
                    "status": page.get("status_code", ""),
                    "title": (meta.get("title") or "")[:40],
                    "words": content.get("plain_text_word_count", ""),
                    "issues": ", ".join(issues[:3]) if issues else "none",
                })

            print_table(
                rows,
                columns=[
                    ("status", "SC", 4),
                    ("url", "URL", 40),
                    ("title", "Title", 40),
                    ("words", "Words", 6),
                    ("issues", "Issues", 30),
                ],
                title="On-Page Crawl Results",
            )
        print_cost(cost)
        return

    if not args.target:
        die("--target is required (or use --demo)")

    from dataforseo.client import run_task  # noqa: E402

    creds = {}
    if args.login:
        creds["login"] = args.login
    if args.password:
        creds["password"] = args.password

    payload = {
        "target": args.target,
        "max_crawl_pages": args.max_pages,
        "enable_javascript": args.enable_javascript,
        "enable_browser_rendering": args.enable_javascript,
        "load_resources": args.load_resources,
        "enable_lighthouse": args.enable_lighthouse,
    }

    print(f"Posting on_page crawl task for {args.target!r} (max {args.max_pages} pages)...")
    print(f"Polling every {args.poll_interval}s, timeout {args.timeout}s.")
    print("On-page crawls typically complete in 1-5 minutes for small sites.\n")

    # On-Page uses a non-standard task_get path (/on_page/pages)
    # We post the task and then fetch pages separately
    from dataforseo.client import task_post, tasks_ready, task_get  # noqa: E402
    import time

    task_ids = task_post("/on_page/task_post", [payload], **creds)
    if not task_ids:
        die("No task IDs returned from on_page/task_post.")

    task_id = task_ids[0]
    print(f"Task posted: {task_id}")
    print("Waiting for crawl to complete...")

    deadline = time.monotonic() + args.timeout
    while True:
        if time.monotonic() > deadline:
            die(f"Timed out waiting for on_page task {task_id} after {args.timeout}s.")
        ready = tasks_ready(**creds)
        if task_id in ready:
            break
        time.sleep(args.poll_interval)

    print(f"Crawl complete! Fetching results...")

    # Fetch pages
    pages_url = f"{task_id}"
    results, cost = task_get(task_id, fetch_path="pages", base_endpoint="/on_page", **creds)

    if args.json:
        print_json(results)
    else:
        print(f"Pages: {len(results)}")
        rows = []
        for page in results:
            meta = page.get("meta") or {}
            content = page.get("content") or {}
            checks = page.get("checks") or {}
            issues = [k for k, v in checks.items() if v is False]
            rows.append({
                "url": page.get("url", ""),
                "status": page.get("status_code", ""),
                "title": (meta.get("title") or "")[:40],
                "words": content.get("plain_text_word_count", ""),
                "issues": ", ".join(issues[:3]) if issues else "none",
            })
        print_table(
            rows,
            columns=[
                ("status", "SC", 4),
                ("url", "URL", 40),
                ("title", "Title", 40),
                ("words", "Words", 6),
                ("issues", "Issues", 30),
            ],
            title="On-Page Crawl Results",
        )

    print_cost(cost)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
