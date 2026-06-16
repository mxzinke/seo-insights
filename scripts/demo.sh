#!/usr/bin/env bash
# demo.sh — Run the full SEO Insights pipeline on synthetic fixture data.
#
# No live credentials required. Uses tests/fixtures/ as the data source.
# Writes output to data/_demo/<today>/report_data.json.
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

echo "============================================"
echo "  SEO Insights — Demo Pipeline"
echo "  Date: $TODAY"
echo "  Output: $REPORT_PATH"
echo "============================================"

# Step 1: Copy fixture data to the demo run directory.
echo ""
echo "[1/4] Copying fixture data to $DATA_DIR …"
python3 "$SCRIPT_DIR/fetch.py" --demo --days 90

# Step 2: Validate the ICP.
echo ""
echo "[2/4] Validating ICP …"
python3 "$SCRIPT_DIR/validate_icp.py" "$ICP_PATH"

# Step 3: Build the report_data.json (demo mode — no live HTTP calls).
echo ""
echo "[3/4] Running analysis and building report_data.json …"
python3 "$SCRIPT_DIR/build_report_data.py" \
  --data-dir "$DATA_DIR" \
  --icp "$ICP_PATH" \
  --demo

# Step 4: Render the HTML report.
echo ""
echo "[4/4] Rendering HTML report …"
REPORT_HTML="$DATA_DIR/report.html"
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
required_keys = {"meta", "icp", "summary", "recommendations", "analyses", "charts", "explore"}
missing = required_keys - set(data.keys())
if missing:
    print(f"MISSING: {missing}", file=sys.stderr)
    sys.exit(1)
print("YES")

print()
print("  Validation PASSED")
PYEOF
