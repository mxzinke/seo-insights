"""
_net.py — thin urllib wrapper with a friendly error for sandboxed environments.

Some hosts (notably the Claude Cowork code-execution sandbox) route outbound
traffic through an egress allowlist proxy that returns HTTP 403 with an
`X-Proxy-Error: blocked-by-allowlist` header for any domain not on the list.
Google's API domains are not allowlisted by default, so calls fail with an
opaque 403. This wrapper detects that case and raises a clear, actionable
message instead.
"""

import urllib.error
import urllib.request

# Domains this tool must reach for live data.
REQUIRED_DOMAINS = [
    "oauth2.googleapis.com",
    "accounts.google.com",
    "www.googleapis.com",
    "googleads.googleapis.com",
]

_ALLOWLIST_HINT = (
    "Network blocked by the sandbox egress allowlist (HTTP 403 "
    "'blocked-by-allowlist'). SEO Insights must reach Google's APIs: "
    + ", ".join(REQUIRED_DOMAINS)
    + ". Fixes: (1) run this in Claude Code (local CLI, no egress sandbox), or "
    "(2) have an org admin allow these domains under Organization > Capabilities "
    "> Code execution > Allow network egress (note: the additional-domains list "
    "currently only takes effect in 'All domains' mode)."
)


def _is_allowlist_block(exc: urllib.error.HTTPError) -> bool:
    if exc.code != 403:
        return False
    proxy_err = ""
    try:
        proxy_err = (exc.headers.get("X-Proxy-Error") or "") if exc.headers else ""
    except Exception:  # noqa: BLE001
        proxy_err = ""
    if "blocked-by-allowlist" in proxy_err.lower():
        return True
    # Fall back to inspecting the reason/body for the same marker.
    reason = (getattr(exc, "reason", "") or "")
    return "blocked-by-allowlist" in str(reason).lower()


def urlopen(req, timeout: int = 30):
    """urllib.request.urlopen with a clearer error on sandbox allowlist blocks."""
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if _is_allowlist_block(exc):
            raise RuntimeError(_ALLOWLIST_HINT) from exc
        raise
