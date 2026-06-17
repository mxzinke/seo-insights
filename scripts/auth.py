"""
auth.py — OAuth 2.0 helper for Google Search Console (+ optional Google Ads).

Uses Google's loopback (localhost) redirect flow — the supported method for
installed/desktop apps. Google disabled the old out-of-band (OOB) copy-paste
flow in 2022, so newly created OAuth clients must use a localhost redirect.

Operations:
  login     One-shot: open consent in the browser, capture the code on a local
            loopback server automatically, exchange it, and print the refresh
            token. No copy-paste. (Recommended.)
  consent   Print the consent URL for manual flow (localhost redirect). After
            granting access the browser lands on a "can't reach localhost" page
            — copy the `code` value from the address bar.
  exchange  Exchange a manually copied authorization code for a refresh token.
  refresh   Use a stored refresh token to obtain a short-lived access token.

Usage:
  python scripts/auth.py login    --client-id <id> --client-secret <secret> [--open]
  python scripts/auth.py consent  --client-id <id>
  python scripts/auth.py exchange --client-id <id> --client-secret <secret> --code <code> [--redirect-uri <uri>]
  python scripts/auth.py refresh  [--config <path>]
"""

import argparse
import contextlib
import http.server
import json
import pathlib
import socket
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser

# Bootstrap: add repo root to sys.path so direct invocation works.
# e.g. `python3 scripts/auth.py refresh` as well as `python3 -m scripts.auth`
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._net import urlopen as _urlopen  # noqa: E402 — friendly 403 handling

# OAuth scopes. Search Console read access is always requested; the Google Ads
# scope is included so the same refresh token also works for keyword volume.
GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
ADS_SCOPE = "https://www.googleapis.com/auth/adwords"
DEFAULT_SCOPES = f"{GSC_SCOPE} {ADS_SCOPE}"

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Loopback redirect host. For "Desktop app" OAuth clients, Google permits any
# loopback redirect (http://localhost and http://127.0.0.1) on any port.
LOOPBACK_HOST = "localhost"
# Bare-host redirect used by the manual consent/exchange flow (no running server).
MANUAL_REDIRECT_URI = f"http://{LOOPBACK_HOST}"


def build_consent_url(client_id: str, redirect_uri: str, scopes: str = DEFAULT_SCOPES) -> str:
    """Return the URL the site owner must visit to grant offline access."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scopes,
        "access_type": "offline",
        "prompt": "consent",  # force a refresh_token even if previously granted
    }
    return GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params)


def exchange_code(client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict:
    """Exchange a one-time authorization code for access + refresh tokens.

    redirect_uri MUST match the one used to obtain the code.
    """
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request(GOOGLE_TOKEN_URL, data=data, method="POST")
    with _urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Exchange a refresh token for a short-lived access token (1 hour TTL)."""
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(GOOGLE_TOKEN_URL, data=data, method="POST")
    with _urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read())
    if "access_token" not in payload:
        raise RuntimeError(f"Token refresh failed: {payload}")
    return payload["access_token"]


# ---------------------------------------------------------------------------
# Loopback auto-capture (login)
# ---------------------------------------------------------------------------

def _free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind((LOOPBACK_HOST, 0))
        return s.getsockname()[1]


def _capture_code(port: int, timeout: int = 300) -> str | None:
    """Run a one-request loopback server and return the captured auth code."""
    captured: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            code = params.get("code", [None])[0]
            err = params.get("error", [None])[0]
            if code:
                captured["code"] = code
            elif err:
                captured["error"] = err
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            msg = (
                "<h2>SEO Insights - authorization received.</h2>"
                "<p>You can close this tab and return to the app.</p>"
                if code else
                f"<h2>Authorization failed.</h2><p>{err or 'No code returned.'}</p>"
            )
            self.wfile.write(msg.encode())

        def log_message(self, *args):  # silence default logging
            pass

    server = http.server.HTTPServer((LOOPBACK_HOST, port), Handler)
    server.timeout = timeout
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    thread.join(timeout=timeout)
    with contextlib.suppress(Exception):
        server.server_close()
    if "error" in captured:
        raise RuntimeError(f"Authorization error from Google: {captured['error']}")
    return captured.get("code")


def cmd_login(args):
    port = _free_port()
    redirect_uri = f"http://{LOOPBACK_HOST}:{port}"
    url = build_consent_url(args.client_id, redirect_uri)
    print("Open this URL in a browser signed in as the Search Console owner:\n")
    print(url + "\n")
    print(f"Waiting for the Google redirect on {redirect_uri} ... (up to 5 min)")
    if args.open:
        with contextlib.suppress(Exception):
            webbrowser.open(url)

    code = _capture_code(port)
    if not code:
        print(
            "\nTimed out waiting for the redirect. Use the manual flow instead:\n"
            "  python scripts/auth.py consent --client-id <id>\n"
            "  python scripts/auth.py exchange --client-id <id> --client-secret <secret> --code <code>",
            file=sys.stderr,
        )
        sys.exit(1)

    tokens = exchange_code(args.client_id, args.client_secret, code, redirect_uri)
    _emit_refresh_token(tokens)


# ---------------------------------------------------------------------------
# Manual flow (consent / exchange)
# ---------------------------------------------------------------------------

def cmd_consent(args):
    url = build_consent_url(args.client_id, MANUAL_REDIRECT_URI)
    print("Visit this URL in a browser signed in as the Search Console owner:\n")
    print(url)
    print(
        "\nAfter granting access the browser will try to open "
        f"'{MANUAL_REDIRECT_URI}/?code=...' and show a 'can't reach this page' error - "
        "that is expected. Copy the value of the `code` parameter from the address bar, then run:\n"
        f"  python scripts/auth.py exchange --client-id {args.client_id} "
        "--client-secret <secret> --code <code>"
    )


def cmd_exchange(args):
    redirect_uri = args.redirect_uri or MANUAL_REDIRECT_URI
    tokens = exchange_code(args.client_id, args.client_secret, args.code, redirect_uri)
    _emit_refresh_token(tokens)


def _emit_refresh_token(tokens: dict):
    if "refresh_token" not in tokens:
        print("ERROR: no refresh_token in response - did you use prompt=consent?", file=sys.stderr)
        print(json.dumps(tokens, indent=2), file=sys.stderr)
        sys.exit(1)
    print("\nSuccess. Add this line to your config/gsc.env:\n")
    print(f"GSC_REFRESH_TOKEN={tokens['refresh_token']}")
    print(f"\n# (access_token expires in {tokens.get('expires_in', '?')}s - do not store it)")


def cmd_refresh(args):
    from scripts.config_loader import load_config  # noqa: PLC0415 — local import only for CLI
    cfg = load_config(args.config)
    token = get_access_token(cfg["GSC_CLIENT_ID"], cfg["GSC_CLIENT_SECRET"], cfg["GSC_REFRESH_TOKEN"])
    print(f"access_token={token}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Google OAuth2 helper for Search Console.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_login = sub.add_parser("login", help="One-shot loopback auth (recommended, no copy-paste).")
    p_login.add_argument("--client-id", required=True)
    p_login.add_argument("--client-secret", required=True)
    p_login.add_argument("--open", action="store_true", help="Also try to open the browser automatically.")
    p_login.set_defaults(func=cmd_login)

    p_consent = sub.add_parser("consent", help="Print the OAuth consent URL (manual localhost flow).")
    p_consent.add_argument("--client-id", required=True)
    p_consent.set_defaults(func=cmd_consent)

    p_exchange = sub.add_parser("exchange", help="Exchange a manually copied auth code for a refresh token.")
    p_exchange.add_argument("--client-id", required=True)
    p_exchange.add_argument("--client-secret", required=True)
    p_exchange.add_argument("--code", required=True)
    p_exchange.add_argument("--redirect-uri", default=None,
                            help=f"Redirect URI used at consent (default {MANUAL_REDIRECT_URI}).")
    p_exchange.set_defaults(func=cmd_exchange)

    p_refresh = sub.add_parser("refresh", help="Get a fresh access token using stored refresh token.")
    p_refresh.add_argument("--config", default=None, help="Path to gsc.env file.")
    p_refresh.set_defaults(func=cmd_refresh)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
