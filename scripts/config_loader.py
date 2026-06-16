"""
config_loader.py — Resolve GSC credentials from env file or environment variables.

Resolution order (first match wins):
  1. CLI flag: --config <path>       (caller passes the path as an argument)
  2. Environment variable: SEO_INSIGHTS_CONFIG
  3. Default file: ./config/gsc.env  (relative to cwd at runtime)

The env file uses KEY=VALUE syntax (shell-style, no export, no quotes required).
Lines starting with # and blank lines are ignored.
"""

import os
import pathlib
import sys

# Required keys that must be present for any GSC operation.
REQUIRED_KEYS = ["GSC_CLIENT_ID", "GSC_CLIENT_SECRET", "GSC_REFRESH_TOKEN", "GSC_SITE_URL"]

# Optional keys — absence is acceptable; downstream code checks before use.
OPTIONAL_KEYS = ["PAGESPEED_API_KEY"]


def _parse_env_file(path: pathlib.Path) -> dict:
    """Parse a KEY=VALUE env file, ignoring comments and blank lines."""
    result = {}
    with open(path) as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                print(f"  [config] WARNING: line {lineno} in {path} has no '=' — skipped: {line!r}",
                      file=sys.stderr)
                continue
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def load_config(cli_config_path: str | None = None, *, require_all: bool = True) -> dict:
    """
    Load configuration from the resolved source.

    Parameters
    ----------
    cli_config_path : str | None
        Path explicitly supplied via --config CLI flag; takes highest priority.
    require_all : bool
        When True (default), raise ValueError if any REQUIRED_KEYS are missing.
        Set to False in demo/test mode where no real creds are needed.

    Returns
    -------
    dict with at minimum all REQUIRED_KEYS (unless require_all=False).
    """
    # Start with a copy of the current environment so OS-level vars work too.
    cfg: dict = {}

    # Determine file source.
    if cli_config_path:
        env_path = pathlib.Path(cli_config_path)
        source = f"--config flag ({env_path})"
    elif "SEO_INSIGHTS_CONFIG" in os.environ:
        env_path = pathlib.Path(os.environ["SEO_INSIGHTS_CONFIG"])
        source = f"SEO_INSIGHTS_CONFIG env var ({env_path})"
    else:
        env_path = pathlib.Path("config/gsc.env")
        source = f"default path ({env_path})"

    if env_path.exists():
        cfg.update(_parse_env_file(env_path))
    else:
        # Fall back to pure environment variables (useful in CI/Docker).
        for key in REQUIRED_KEYS + OPTIONAL_KEYS:
            if key in os.environ:
                cfg[key] = os.environ[key]
        if not cfg:
            # Env file missing and no env vars — only error if we actually need creds.
            if require_all:
                raise FileNotFoundError(
                    f"Config file not found at {env_path} (resolved via {source}) "
                    "and no GSC_* environment variables set. "
                    "Copy config/gsc.env.example to config/gsc.env and fill in your credentials."
                )

    if require_all:
        missing = [k for k in REQUIRED_KEYS if not cfg.get(k)]
        if missing:
            raise ValueError(
                f"Missing required config keys: {', '.join(missing)}\n"
                f"  Source: {source}\n"
                "  See config/gsc.env.example for the required format."
            )

    return cfg
