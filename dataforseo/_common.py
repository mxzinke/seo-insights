"""
dataforseo/_common.py — Shared CLI argument helpers and output utilities.

Used by all dataforseo/cli_*.py scripts. Not imported outside dataforseo/.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


# ---------------------------------------------------------------------------
# Shared argparse arguments
# ---------------------------------------------------------------------------


def add_auth_args(parser: argparse.ArgumentParser) -> None:
    """Add --login and --password options (override env vars)."""
    parser.add_argument(
        "--login",
        default=None,
        help="DataForSEO login (email). Overrides DATAFORSEO_LOGIN env var.",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="DataForSEO API password. Overrides DATAFORSEO_PASSWORD env var.",
    )


def add_location_args(parser: argparse.ArgumentParser) -> None:
    """Add --location-code and --language-code with German defaults."""
    parser.add_argument(
        "--location-code",
        type=int,
        default=2276,
        metavar="CODE",
        help="DataForSEO location code (default: 2276 = Germany).",
    )
    parser.add_argument(
        "--language-code",
        default="de",
        metavar="LANG",
        help="DataForSEO language code (default: de).",
    )


def add_output_args(parser: argparse.ArgumentParser) -> None:
    """Add --json flag to force raw JSON output."""
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of a formatted table.",
    )


def add_demo_arg(parser: argparse.ArgumentParser) -> None:
    """Add --demo flag to load fixture data without network/key."""
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Load bundled fixture data (no API key or network required).",
    )


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def print_cost(cost: float) -> None:
    print(f"\n[cost] ${cost:.6f} USD", file=sys.stderr)


def print_table(
    rows: list[dict],
    columns: list[tuple[str, str, int]],
    title: str = "",
) -> None:
    """
    Print a compact ASCII table.

    columns: list of (key, header, width) tuples.
    """
    if title:
        print(f"\n{title}")
        print("=" * sum(w + 2 for _, _, w in columns))

    header = "  ".join(h.ljust(w) for _, h, w in columns)
    sep = "  ".join("-" * w for _, _, w in columns)
    print(header)
    print(sep)

    for row in rows:
        parts = []
        for key, _, width in columns:
            val = row.get(key, "")
            if val is None:
                val = ""
            val = str(val)
            if len(val) > width:
                val = val[: width - 1] + "…"
            parts.append(val.ljust(width))
        print("  ".join(parts))


def die(msg: str, code: int = 1) -> None:
    """Print an error to stderr and exit."""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)
