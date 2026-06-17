"""
config_loader.py — Resolve GSC credentials from env file or environment variables.

Resolution order (first match wins):
  1. CLI flag: --config <path>       (caller passes the path as an argument)
  2. Environment variable: SEO_INSIGHTS_CONFIG
  3. Persistent workspace: workspace.config_path()
     (SEO_INSIGHTS_HOME env var → ~/.seo-insights/home pointer → ~/seo-insights)
  4. Legacy fallback: ./config/gsc.env  (relative to cwd — for in-repo dev checkouts)

The env file uses KEY=VALUE syntax (shell-style, no export, no quotes required).
Lines starting with # and blank lines are ignored.
"""

import os
import pathlib
import sys

# Add project root to sys.path so this module can import siblings when run
# directly (e.g. python3 scripts/config_loader.py).
_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.workspace import config_path as _workspace_config_path  # noqa: E402

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
        candidates = [env_path]
    elif "SEO_INSIGHTS_CONFIG" in os.environ:
        env_path = pathlib.Path(os.environ["SEO_INSIGHTS_CONFIG"])
        source = f"SEO_INSIGHTS_CONFIG env var ({env_path})"
        candidates = [env_path]
    else:
        # Persistent workspace path (survives across Cowork sessions).
        workspace_cfg = _workspace_config_path()
        # Legacy in-repo path (for developer checkouts — final fallback).
        legacy_cfg = pathlib.Path("config/gsc.env")
        # Try workspace first, then legacy.
        env_path = workspace_cfg if workspace_cfg.exists() else legacy_cfg
        source = (
            f"workspace ({workspace_cfg})"
            if workspace_cfg.exists()
            else f"legacy path ({legacy_cfg})"
        )
        candidates = [workspace_cfg, legacy_cfg]

    # Try to load from the first existing candidate.
    loaded = False
    for candidate in candidates:
        if candidate.exists():
            cfg.update(_parse_env_file(candidate))
            loaded = True
            break

    if not loaded:
        # Fall back to pure environment variables (useful in CI/Docker).
        for key in REQUIRED_KEYS + OPTIONAL_KEYS:
            if key in os.environ:
                cfg[key] = os.environ[key]
        if not cfg:
            # Env file missing and no env vars — only error if we actually need creds.
            if require_all:
                workspace_cfg = _workspace_config_path()
                raise FileNotFoundError(
                    f"Config file not found. Looked for credentials at:\n"
                    f"  {workspace_cfg}  (persistent workspace — run /seo-setup to create it)\n"
                    f"  ./config/gsc.env  (legacy in-repo fallback)\n"
                    f"No GSC_* environment variables set either.\n"
                    f"Run /seo-setup to configure your workspace, or set SEO_INSIGHTS_HOME "
                    f"to point at an existing workspace."
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
