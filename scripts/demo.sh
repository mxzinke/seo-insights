#!/usr/bin/env bash
# demo.sh — Run the full SEO Insights pipeline on synthetic fixture data.
#
# No live credentials required. Uses tests/fixtures/ as the data source.
# Writes output to data/_demo/<today>/report_data.json.
#
# Tests both paths:
#   UNREVIEWED path: keyword_relevance.json absent → shows all candidates with pending note
#   REVIEWED path:  keyword_relevance.json present → shows AI-filtered keywords with reasons
#
# Usage:
#   bash scripts/demo.sh
#   # or from project root:
#   make demo

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TODAY=$(date +%Y-%m-%d)
DATA_DIR="$PROJECT_ROOT/data/_demo/$TODAY"
ICP_PATH="$PROJECT_ROOT/config/icp.example.yaml"
REPORT_PATH="$DATA_DIR/report_data.json"
RELEVANCE_FIXTURE="$PROJECT_ROOT/tests/fixtures/keyword_relevance.json"

echo "============================================"
echo "  SEO Insights — Demo Pipeline"
echo "  Date: $TODAY"
echo "  Output: $REPORT_PATH"
echo "============================================"

# Step 1: Copy fixture data to the demo run directory.
echo ""
echo "[1/5] Copying fixture data to $DATA_DIR …"
python3 "$SCRIPT_DIR/fetch.py" --demo --days 90

# Step 2: Validate the ICP.
echo ""
echo "[2/5] Validating ICP …"
python3 "$SCRIPT_DIR/validate_icp.py" "$ICP_PATH"

# Step 3: Build the report_data.json (demo mode — no live HTTP calls).
# Ensure keyword_relevance.json is absent so we exercise the UNREVIEWED path.
rm -f "$DATA_DIR/keyword_relevance.json"
echo ""
echo "[3/5] Running analysis (UNREVIEWED path — no keyword_relevance.json) …"
python3 "$SCRIPT_DIR/build_report_data.py" \
  --data-dir "$DATA_DIR" \
  --icp "$ICP_PATH" \
  --demo

# Step 4: Render the HTML report for the UNREVIEWED path.
echo ""
echo "[4/5] Rendering HTML report (UNREVIEWED path) …"
REPORT_HTML="$DATA_DIR/report.html"
python3 "$SCRIPT_DIR/report.py" "$REPORT_PATH" --out "$REPORT_HTML"

# Validate the UNREVIEWED path immediately.
python3 - <<'UNREVIEWED_CHECK'
import json, sys, pathlib

today = __import__('datetime').date.today().isoformat()
path = pathlib.Path(f"data/_demo/{today}/report_data.json")
with open(path) as f:
    data = json.load(f)

keywords = data.get("keywords", {})
assert keywords.get("relevance_reviewed") is False, \
    f"FAIL: UNREVIEWED path must have relevance_reviewed=False, got {keywords.get('relevance_reviewed')}"
assert "AI relevance review not yet applied" in keywords.get("source_note", ""), \
    f"FAIL: UNREVIEWED path must have pending note in source_note"
# In unreviewed path, recommend.py emits no keyword recommendations
kw_recs = [r for r in data.get("recommendations", []) if "kw_gap" in r.get("id", "") or "kw_opt" in r.get("id", "")]
assert len(kw_recs) == 0, \
    f"FAIL: UNREVIEWED path must not emit keyword recommendations, got: {[r['id'] for r in kw_recs]}"
print(f"  UNREVIEWED path checks:")
print(f"    relevance_reviewed=False: OK")
print(f"    pending note in source_note: OK")
print(f"    no keyword content recommendations: OK (got {len(kw_recs)})")
print(f"    candidates in opportunities: {len(keywords.get('opportunities', []))}")
UNREVIEWED_CHECK

echo ""
echo "  --- Now testing REVIEWED path (with keyword_relevance.json) ---"

# Copy the demo keyword_relevance.json fixture to the run dir.
if [ -f "$RELEVANCE_FIXTURE" ]; then
    cp "$RELEVANCE_FIXTURE" "$DATA_DIR/keyword_relevance.json"
    echo "  Copied keyword_relevance.json fixture to $DATA_DIR"
else
    echo "ERROR: Demo fixture not found: $RELEVANCE_FIXTURE" >&2
    exit 1
fi

# Re-run build_report_data with the relevance file present → REVIEWED path.
echo ""
echo "[5/5] Re-running analysis (REVIEWED path — keyword_relevance.json present) …"
python3 "$SCRIPT_DIR/build_report_data.py" \
  --data-dir "$DATA_DIR" \
  --icp "$ICP_PATH" \
  --demo

# Render the final report (REVIEWED path).
python3 "$SCRIPT_DIR/report.py" "$REPORT_PATH" --out "$REPORT_HTML"

echo ""
echo "============================================"
echo "  Demo complete!"
echo "  report_data.json: $REPORT_PATH"
echo "  report.html:      $REPORT_HTML"
echo ""

# Quick validation: check the JSON is well-formed and has non-empty recommendations.
python3 - <<'PYEOF'
import json, sys, pathlib

today = __import__('datetime').date.today().isoformat()
path = pathlib.Path(f"data/_demo/{today}/report_data.json")
if not path.exists():
    print("ERROR: report_data.json not found!", file=sys.stderr)
    sys.exit(1)

with open(path) as f:
    data = json.load(f)

recs = data.get("recommendations", [])
analyses = data.get("analyses", {})
charts = data.get("charts", {})
explore = data.get("explore", {})

print(f"  JSON valid: YES")
print(f"  Meta domain: {data['meta']['domain']}")
print(f"  Summary clicks: {data['summary']['clicks']}")
print(f"  Recommendations: {len(recs)}")
print(f"  Analyses produced: {', '.join(k for k, v in analyses.items() if v)}")
print(f"  Chart series: {', '.join(k for k in charts)}")
print(f"  Explore keys: {', '.join(k for k in explore)}")
print()

if not recs:
    print("ERROR: No recommendations generated — pipeline may have failed.", file=sys.stderr)
    sys.exit(1)

print("  Top 5 recommendations (by priority):")
for i, rec in enumerate(recs[:5], 1):
    print(f"    {i}. [{rec['category']}] {rec['title'][:70]}")
    print(f"       Impact={rec['impact']} Effort={rec['effort']} Priority={rec['priority']:.2f}")
    print(f"       Action: {rec['action'][:100]}...")

print()
print("  All contract keys present:", end=" ")
required_keys = {"meta", "icp", "summary", "recommendations", "analyses", "charts", "explore", "keywords"}
missing = required_keys - set(data.keys())
if missing:
    print(f"MISSING: {missing}", file=sys.stderr)
    sys.exit(1)
print("YES")

# Validate keyword research section (REVIEWED path)
keywords = data.get("keywords", {})
kw_opps = keywords.get("opportunities", [])
print(f"  Keywords section enabled: {keywords.get('enabled', False)}")
print(f"  Keyword opportunities: {len(kw_opps)}")
print(f"  Source note: {keywords.get('source_note', 'N/A')[:80]}")
print(f"  relevance_reviewed: {keywords.get('relevance_reviewed', False)}")

# Check REVIEWED path assertions
assert keywords.get("relevance_reviewed") is True, \
    f"FAIL: relevance_reviewed must be True in REVIEWED path, got: {keywords.get('relevance_reviewed')}"
print("  REVIEWED path check: relevance_reviewed=True OK")

# All remaining opportunities must have relevance: true (or None for unjudged ones)
off_audience = [k for k in kw_opps if k.get("relevance") is False]
assert len(off_audience) == 0, \
    f"FAIL: off-audience keywords leaked into opportunities: {[k['keyword'] for k in off_audience]}"
print(f"  No off-audience keywords in opportunities: OK")

# Check that relevance_reason is present on reviewed keywords
reviewed_with_reason = [k for k in kw_opps if k.get("relevance") is True and k.get("relevance_reason")]
print(f"  Keywords with AI relevance_reason: {len(reviewed_with_reason)}")

if kw_opps:
    top_kw = kw_opps[0]
    print(f"  Top keyword: {top_kw.get('keyword')!r}")
    print(f"    Intent: {top_kw.get('intent')}")
    print(f"    Score: {top_kw.get('opportunity_score')}")
    print(f"    Source: {top_kw.get('source')}")
    print(f"    Relevance: {top_kw.get('relevance')}")
    print(f"    Reason: {top_kw.get('relevance_reason')}")
    # Determinism check: opportunity_score must be a number from the pipeline
    assert isinstance(top_kw.get('opportunity_score'), (int, float)), \
        "FAIL: opportunity_score must be a number"
    assert top_kw.get('source') in ('gsc', 'ads', 'autocomplete'), \
        f"FAIL: unexpected source: {top_kw.get('source')}"
    print("  Determinism check: opportunity_score is numeric from pipeline: OK")

if not kw_opps:
    print("WARNING: No keyword opportunities after relevance filtering", file=sys.stderr)

print()
print("  Validation PASSED")
PYEOF
