#!/usr/bin/env bash
# check_setup.sh — SessionStart hook: checks whether GSC credentials are configured.
#
# Prints a friendly nudge if config/gsc.env is missing or incomplete.
# Always exits 0 so the session is never blocked.

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CONFIG_FILE="$PLUGIN_ROOT/config/gsc.env"

REQUIRED_KEYS=("GSC_CLIENT_ID" "GSC_CLIENT_SECRET" "GSC_REFRESH_TOKEN" "GSC_SITE_URL")

# If config file is missing — nudge and exit cleanly.
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "[seo-insights] GSC credentials not configured. Run /seo-insights:setup to get started."
  exit 0
fi

# Check each required key exists and is non-empty in the file.
missing=()
for key in "${REQUIRED_KEYS[@]}"; do
  value=$(grep -E "^${key}=" "$CONFIG_FILE" 2>/dev/null | head -1 | cut -d= -f2-)
  if [[ -z "$value" ]]; then
    missing+=("$key")
  fi
done

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "[seo-insights] GSC config incomplete (missing: ${missing[*]}). Run /seo-insights:setup to configure."
fi

# Always exit 0 — never block the session.
exit 0
