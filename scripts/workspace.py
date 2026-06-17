"""
workspace.py — Resolve and manage the persistent SEO Insights workspace folder.

The workspace is a stable, user-owned directory on the local machine where
credentials, ICP files, and dated results are stored. It survives across
Claude Cowork / plugin-sandbox sessions because it lives outside the ephemeral
plugin cache directory.

Resolution order (first match wins):
  1. Environment variable: SEO_INSIGHTS_HOME
  2. Pointer file: ~/.seo-insights/home  (contains an absolute path)
  3. Default: ~/seo-insights

All returned paths are absolute and expanded (expanduser applied).

Typical layout:
  <home>/
    config/
      gsc.env           ← GSC credentials
      icp.<domain>.yaml ← Ideal Customer Profile(s)
    data/
      <domain>/
        <YYYY-MM-DD>/   ← dated run directories
"""

from __future__ import annotations

import os
import pathlib
import sys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_POINTER_FILE = pathlib.Path("~/.seo-insights/home").expanduser()
_DEFAULT_HOME = pathlib.Path("~/seo-insights").expanduser()


# ---------------------------------------------------------------------------
# Core resolution
# ---------------------------------------------------------------------------


def get_home() -> pathlib.Path:
    """
    Return the workspace home directory (absolute path, expanded).

    Resolution order:
      1. SEO_INSIGHTS_HOME env var
      2. ~/.seo-insights/home pointer file
      3. ~/seo-insights (default)
    """
    # 1. Environment variable takes highest priority.
    env_val = os.environ.get("SEO_INSIGHTS_HOME", "").strip()
    if env_val:
        return pathlib.Path(env_val).expanduser().resolve()

    # 2. Pointer file written by set_home().
    if _POINTER_FILE.exists():
        try:
            stored = _POINTER_FILE.read_text().strip()
            if stored:
                return pathlib.Path(stored).expanduser().resolve()
        except OSError:
            pass  # unreadable pointer → fall through to default

    # 3. Default.
    return _DEFAULT_HOME.resolve()


def set_home(path: str | pathlib.Path) -> pathlib.Path:
    """
    Set the workspace home to *path*, create required subdirectories, and
    persist the choice to ~/.seo-insights/home so future sessions reuse it.

    Returns the resolved, absolute home path.
    """
    home = pathlib.Path(path).expanduser().resolve()

    # Create required subdirectories.
    (home / "config").mkdir(parents=True, exist_ok=True)
    (home / "data").mkdir(parents=True, exist_ok=True)

    # Write the pointer file.
    _POINTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    _POINTER_FILE.write_text(str(home) + "\n")

    return home


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def config_path() -> pathlib.Path:
    """Return the path to the gsc.env credentials file."""
    return get_home() / "config" / "gsc.env"


def config_dir() -> pathlib.Path:
    """Return the config directory (home/config/).  ICP files live here too."""
    return get_home() / "config"


def data_root() -> pathlib.Path:
    """Return the data root directory (home/data/)."""
    return get_home() / "data"


# ---------------------------------------------------------------------------
# Tiny CLI
# ---------------------------------------------------------------------------


def _cmd_set(args: list[str]) -> None:
    if not args:
        print("Usage: workspace.py set <path>", file=sys.stderr)
        sys.exit(1)
    home = set_home(args[0])
    print(f"Workspace set to: {home}")
    print(f"  config/ : {home / 'config'}")
    print(f"  data/   : {home / 'data'}")
    print(f"  pointer : {_POINTER_FILE}")


def _cmd_show() -> None:
    home = get_home()
    cfg = config_path()
    # Determine resolution source for display.
    env_val = os.environ.get("SEO_INSIGHTS_HOME", "").strip()
    if env_val:
        source = "SEO_INSIGHTS_HOME env var"
    elif _POINTER_FILE.exists():
        source = f"pointer file ({_POINTER_FILE})"
    else:
        source = "default (~/seo-insights)"

    print(f"Workspace home : {home}")
    print(f"  resolved via : {source}")
    print(f"  config/gsc.env exists: {cfg.exists()}")
    print(f"  data/ exists         : {(home / 'data').exists()}")


def main() -> None:
    # Allow running as both `python3 scripts/workspace.py` and
    # `python3 -m scripts.workspace` — sys.path bootstrap handles both.
    argv = sys.argv[1:]
    if not argv:
        _cmd_show()
        return

    cmd, *rest = argv
    if cmd == "set":
        _cmd_set(rest)
    elif cmd == "show":
        _cmd_show()
    else:
        print(f"Unknown command: {cmd!r}  (use 'set <path>' or 'show')", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# sys.path bootstrap — lets this run as a standalone script from any cwd
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


if __name__ == "__main__":
    main()
