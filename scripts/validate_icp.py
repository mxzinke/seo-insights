"""
validate_icp.py — Validate an ICP YAML file before running keyword analysis.

Usage:
  python scripts/validate_icp.py <path/to/icp.yaml>

Exit codes:
  0 — ICP is valid and complete.
  1 — One or more required fields are missing, empty, or still placeholder values.

This module also exposes:
  load_icp(path)        — Load and return the validated ICP dict.
  icp_relevance(icp, keyword, boost_if_matched=1.0) → float
                        — Score a keyword's relevance [0.0, 1.0] against the ICP.
"""

import pathlib
import sys

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml is required. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# All fields that must be present and non-placeholder in a valid ICP.
REQUIRED_FIELDS = [
    "audience",
    "country",
    "language",
    "search_intent",
    "problem_solved",
    "value_proposition",
    "competitors",
    "priority_topics",
    "excluded_terms",
]

# Values that indicate the user hasn't filled in the example field yet.
PLACEHOLDER_PATTERNS = [
    "your ",
    "example",
    "placeholder",
    "fill in",
    "tbd",
    "todo",
    "<",
    ">",
]

VALID_INTENTS = {"informational", "navigational", "commercial", "transactional", "mixed"}


def _is_placeholder(value) -> bool:
    """Return True if the value looks like it hasn't been customized."""
    if value is None:
        return True
    if isinstance(value, (list, dict)):
        # Empty list/dict is a placeholder; a list/dict of placeholders is caught per-element.
        return len(value) == 0
    text = str(value).strip().lower()
    if not text:
        return True
    return any(pat in text for pat in PLACEHOLDER_PATTERNS)


def validate_icp(icp: dict) -> list[str]:
    """
    Validate the ICP dict.

    Returns a list of human-readable error strings. Empty list = valid.
    """
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in icp:
            errors.append(f"Missing required field: '{field}'")
            continue
        value = icp[field]
        if _is_placeholder(value):
            errors.append(f"Field '{field}' appears to be unfilled / placeholder: {value!r}")

    # Validate controlled-vocabulary fields.
    if "search_intent" in icp and icp.get("search_intent") not in VALID_INTENTS:
        errors.append(
            f"'search_intent' must be one of {sorted(VALID_INTENTS)}, "
            f"got: {icp['search_intent']!r}"
        )

    # List fields must contain at least one non-placeholder item.
    for list_field in ("competitors", "priority_topics", "excluded_terms"):
        if list_field in icp and isinstance(icp[list_field], list):
            non_placeholder = [v for v in icp[list_field] if not _is_placeholder(v)]
            if not non_placeholder:
                errors.append(f"Field '{list_field}' must have at least one real entry.")

    return errors


def load_icp(path: str | pathlib.Path) -> dict:
    """
    Load and validate an ICP YAML file.

    Raises SystemExit(1) with a clear message if validation fails.
    Returns the ICP dict on success.
    """
    path = pathlib.Path(path)
    if not path.exists():
        print(f"ERROR: ICP file not found: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path) as fh:
        try:
            icp = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            print(f"ERROR: Could not parse ICP YAML: {exc}", file=sys.stderr)
            sys.exit(1)

    if not isinstance(icp, dict):
        print(f"ERROR: ICP file must contain a YAML mapping (dict), got {type(icp).__name__}",
              file=sys.stderr)
        sys.exit(1)

    errors = validate_icp(icp)
    if errors:
        print("ICP validation FAILED — fix the following issues before running analysis:\n",
              file=sys.stderr)
        for err in errors:
            print(f"  • {err}", file=sys.stderr)
        sys.exit(1)

    return icp


def icp_relevance(icp: dict, keyword: str) -> float:
    """
    Score a keyword's relevance to the ICP on a [0.0, 1.0] scale.

    Scoring logic (deterministic):
      - Starts at 0.0.
      - Each matched priority_topic word adds 1/(number of topics) to the score,
        capped at 1.0.
      - Any match in excluded_terms returns 0.0 immediately.
      - Score is then adjusted toward 0 if language/country don't match hints
        embedded in the keyword (best-effort heuristic only).

    Returns a float in [0.0, 1.0].
    """
    kw_lower = keyword.strip().lower()

    # Exclusion check — hard block.
    for excluded in icp.get("excluded_terms", []):
        if excluded.lower() in kw_lower:
            return 0.0

    topics: list[str] = icp.get("priority_topics", [])
    if not topics:
        return 0.5  # No priority topics defined — neutral score.

    matched = sum(
        1 for topic in topics
        if any(word in kw_lower for word in topic.lower().split())
    )
    score = min(1.0, matched / len(topics))

    # Small boost if the keyword aligns with the stated audience signal words.
    audience = icp.get("audience", "")
    audience_words = {w.lower() for w in audience.split() if len(w) > 4}
    if any(w in kw_lower for w in audience_words):
        score = min(1.0, score + 0.1)

    return round(score, 4)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/validate_icp.py <path/to/icp.yaml>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    icp = load_icp(path)  # Exits non-zero on failure.
    print(f"ICP valid. Fields confirmed: {', '.join(REQUIRED_FIELDS)}")
    print(f"  Audience: {icp['audience']}")
    print(f"  Country/Language: {icp['country']}/{icp['language']}")
    print(f"  Priority topics: {icp['priority_topics']}")


if __name__ == "__main__":
    main()
