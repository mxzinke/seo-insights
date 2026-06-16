#!/usr/bin/env bash
# run.sh — One-command SEO Insights pipeline runner.
#
# Runs the full pipeline in sequence:
#   1. validate_icp   — ensures the audience definition is complete
#   2. fetch          — pulls current + prior GSC windows to data/<domain>/<date>/
#   3. build_report_data — runs all 7 analyses → report_data.json
#   4. report         — renders the self-contained HTML report
#
# Safe to run weekly: each run creates its own dated directory, enabling
# automatic week-over-week comparison on the next run.
#
# Usage:
#   bash scripts/run.sh --icp config/icp.mysite.yaml [options]
#
# Required:
#   --icp <path>         Path to an ICP YAML file (e.g. config/icp.mysite.yaml)
#
# Optional:
#   --days N             GSC window size in days (default: 90)
#   --config <path>      Path to gsc.env credentials file (default: config/gsc.env)
#   --pagespeed-key K    PageSpeed Insights API key for Core Web Vitals analysis
#   --demo               Use synthetic fixture data (no GSC credentials required)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# ── Defaults ────────────────────────────────────────────────────────────────
ICP_PATH=""
DAYS=90
CONFIG_PATH=""
PAGESPEED_KEY=""
DEMO=false

# ── Argument parsing ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --icp)
      ICP_PATH="$2"
      shift 2
      ;;
    --days)
      DAYS="$2"
      shift 2
      ;;
    --config)
      CONFIG_PATH="$2"
      shift 2
      ;;
    --pagespeed-key)
      PAGESPEED_KEY="$2"
      shift 2
      ;;
    --demo)
      DEMO=true
      shift
      ;;
    *)
      echo "ERROR: Unknown option: $1" >&2
      echo "Usage: bash scripts/run.sh --icp <path> [--days N] [--config <path>] [--pagespeed-key K] [--demo]" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$ICP_PATH" ]]; then
  echo "ERROR: --icp <path> is required." >&2
  echo "Usage: bash scripts/run.sh --icp config/icp.mysite.yaml [--days N] [--demo]" >&2
  exit 1
fi

TODAY=$(date +%Y-%m-%d)

# ── Banner ───────────────────────────────────────────────────────────────────
echo "============================================"
echo "  SEO Insights Pipeline"
echo "  Date:     $TODAY"
echo "  ICP:      $ICP_PATH"
echo "  Days:     $DAYS"
if $DEMO; then
  echo "  Mode:     DEMO (fixture data, no credentials)"
fi
echo "============================================"
echo ""

# ── Step 0: Validate ICP ────────────────────────────────────────────────────
echo "[1/4] Validating ICP: $ICP_PATH …"
python3 "$SCRIPT_DIR/validate_icp.py" "$ICP_PATH"
echo ""

# ── Step 1: Fetch GSC data ─────────────────────────────────────────────────
echo "[2/4] Fetching GSC data (window: last $DAYS days) …"
FETCH_ARGS=("--days" "$DAYS")
if $DEMO; then
  FETCH_ARGS+=("--demo")
fi
if [[ -n "$CONFIG_PATH" ]]; then
  FETCH_ARGS+=("--config" "$CONFIG_PATH")
fi
python3 "$SCRIPT_DIR/fetch.py" "${FETCH_ARGS[@]}"
echo ""

# ── Resolve the data directory written by fetch ──────────────────────────────
# fetch.py writes to data/<domain>/<today>/ for live runs, data/_demo/<today>/ for demo.
if $DEMO; then
  DATA_DIR="$PROJECT_ROOT/data/_demo/$TODAY"
else
  # Read GSC_SITE_URL from the config file to derive the domain directory name.
  RESOLVED_CONFIG="${CONFIG_PATH:-$PROJECT_ROOT/config/gsc.env}"
  if [[ ! -f "$RESOLVED_CONFIG" ]]; then
    echo "ERROR: Config file not found: $RESOLVED_CONFIG" >&2
    exit 1
  fi
  SITE_URL=$(grep -E '^GSC_SITE_URL=' "$RESOLVED_CONFIG" | head -1 | cut -d= -f2-)
  if [[ -z "$SITE_URL" ]]; then
    echo "ERROR: GSC_SITE_URL not found in $RESOLVED_CONFIG" >&2
    exit 1
  fi
  # Derive domain dir using the same logic as fetch.py: strip sc-domain:, strip https://.
  DOMAIN="${SITE_URL#sc-domain:}"
  DOMAIN="${DOMAIN#https://}"
  DOMAIN="${DOMAIN#http://}"
  DOMAIN="${DOMAIN%/}"
  DOMAIN="${DOMAIN//\//_}"
  DATA_DIR="$PROJECT_ROOT/data/$DOMAIN/$TODAY"
fi

if [[ ! -d "$DATA_DIR" ]]; then
  echo "ERROR: Expected data directory not found: $DATA_DIR" >&2
  echo "  (fetch.py may have failed or written to a different path)" >&2
  exit 1
fi

echo "[2/4] Data directory: $DATA_DIR"
echo ""

# ── Step 2: Build report_data.json ──────────────────────────────────────────
echo "[3/4] Running analyses and building report_data.json …"
BUILD_ARGS=("--data-dir" "$DATA_DIR" "--icp" "$ICP_PATH")
if $DEMO; then
  BUILD_ARGS+=("--demo")
fi
if [[ -n "$PAGESPEED_KEY" ]]; then
  BUILD_ARGS+=("--pagespeed-key" "$PAGESPEED_KEY")
fi
python3 "$SCRIPT_DIR/build_report_data.py" "${BUILD_ARGS[@]}"
echo ""

# ── Step 3: Render HTML report ───────────────────────────────────────────────
echo "[4/4] Rendering HTML report …"
REPORT_DATA="$DATA_DIR/report_data.json"
REPORT_HTML="$DATA_DIR/report.html"
python3 "$SCRIPT_DIR/report.py" "$REPORT_DATA" --out "$REPORT_HTML"
echo ""

# ── Done ─────────────────────────────────────────────────────────────────────
echo "============================================"
echo "  Pipeline complete!"
echo ""
echo "  Report:      $REPORT_HTML"
echo "  Report data: $REPORT_DATA"
echo ""
echo "  Open the report:"
echo "    open $REPORT_HTML          # macOS"
echo "    xdg-open $REPORT_HTML      # Linux"
echo ""
echo "  Tip: run this script again next week for automatic week-over-week"
echo "  comparison (each run creates data/<domain>/$(date +%Y-%m-%d)/)."
echo "============================================"
