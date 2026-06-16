"""
auth.py — OAuth 2.0 helper for Google Search Console.

Three operations:
  consent   Print the URL the user must visit to grant offline access.
  exchange  Exchange an authorization code for a refresh token and print it.
  refresh   Use a stored refresh token to obtain a short-lived access token.

Usage:
  python scripts/auth.py consent  --client-id <id> --client-secret <secret>
  python scripts/auth.py exchange --client-id <id> --client-secret <secret> --code <code>
  python scripts/auth.py refresh  [--config <path>]
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request

# The only OAuth scope required for Search Console read access.
GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"

# Google's token and auth endpoints.
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Loopback redirect — required for offline desktop / CLI flows.
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"


def build_consent_url(client_id: str) -> str:
    """Return the URL the site owner must visit to grant consent."""
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": GSC_SCOPE,
        "access_type": "offline",
        "prompt": "consent",  # force refresh_token to be issued even if previously granted
    }
    return GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params)


def exchange_code(client_id: str, client_secret: str, code: str) -> dict:
    """Exchange a one-time authorization code for access + refresh tokens."""
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request(GOOGLE_TOKEN_URL, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
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
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read())
    if "access_token" not in payload:
        raise RuntimeError(f"Token refresh failed: {payload}")
    return payload["access_token"]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def cmd_consent(args):
    url = build_consent_url(args.client_id)
    print("Visit this URL in a browser signed in as the Search Console owner:\n")
    print(url)
    print("\nAfter granting access, paste the authorization code here and run:")
    print(f"  python scripts/auth.py exchange --client-id {args.client_id} "
          f"--client-secret <secret> --code <code>")


def cmd_exchange(args):
    tokens = exchange_code(args.client_id, args.client_secret, args.code)
    if "refresh_token" not in tokens:
        print("ERROR: no refresh_token in response — did you use prompt=consent?", file=sys.stderr)
        print(json.dumps(tokens, indent=2), file=sys.stderr)
        sys.exit(1)
    print("Tokens received. Add these to your config/gsc.env:\n")
    print(f"GSC_REFRESH_TOKEN={tokens['refresh_token']}")
    print(f"# (access_token expires in {tokens.get('expires_in', '?')}s — do not store it)")


def cmd_refresh(args):
    from scripts.config_loader import load_config  # noqa: PLC0415 — local import only for CLI
    cfg = load_config(args.config)
    token = get_access_token(cfg["GSC_CLIENT_ID"], cfg["GSC_CLIENT_SECRET"], cfg["GSC_REFRESH_TOKEN"])
    print(f"access_token={token}")


def main():
    parser = argparse.ArgumentParser(description="Google OAuth2 helper for Search Console.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_consent = sub.add_parser("consent", help="Print the OAuth consent URL.")
    p_consent.add_argument("--client-id", required=True)
    p_consent.set_defaults(func=cmd_consent)

    p_exchange = sub.add_parser("exchange", help="Exchange auth code for refresh token.")
    p_exchange.add_argument("--client-id", required=True)
    p_exchange.add_argument("--client-secret", required=True)
    p_exchange.add_argument("--code", required=True)
    p_exchange.set_defaults(func=cmd_exchange)

    p_refresh = sub.add_parser("refresh", help="Get a fresh access token using stored refresh token.")
    p_refresh.add_argument("--config", default=None, help="Path to gsc.env file.")
    p_refresh.set_defaults(func=cmd_refresh)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
