#!/usr/bin/env bash
# check_setup.sh — SessionStart hook: checks whether GSC credentials are configured.
#
# Checks the persistent workspace location (not the ephemeral plugin directory)
# so the nudge correctly reflects missing credentials even in Cowork sessions.
#
# Always exits 0 so the session is never blocked.

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# Resolve the config file path from the persistent workspace.
# Falls back gracefully if Python or workspace.py is unavailable.
CONFIG_FILE=$(python3 "${PLUGIN_ROOT}/scripts/workspace.py" show 2>/dev/null \
  | grep '^Workspace home' | awk '{print $NF"/config/gsc.env"}')

# If workspace.py couldn't resolve anything, fall back to legacy in-plugin path.
if [[ -z "$CONFIG_FILE" ]]; then
  CONFIG_FILE="$PLUGIN_ROOT/config/gsc.env"
fi

REQUIRED_KEYS=("GSC_CLIENT_ID" "GSC_CLIENT_SECRET" "GSC_REFRESH_TOKEN" "GSC_SITE_URL")

# If config file is missing — nudge and exit cleanly.
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "[seo-insights] GSC credentials not configured."
  echo "  Expected: $CONFIG_FILE"
  echo "  Run /seo-setup to create your persistent workspace and configure credentials."
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
  echo "[seo-insights] GSC config incomplete (missing: ${missing[*]})."
  echo "  Config: $CONFIG_FILE"
  echo "  Run /seo-setup to configure."
fi

# Always exit 0 — never block the session.
exit 0
