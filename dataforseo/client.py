"""
dataforseo/client.py — Shared DataForSEO REST client.

Auth: HTTP Basic (DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD).
Credentials are loaded from env vars or dataforseo/.dataforseo.env.
All calls are isolated in this module; nothing outside dataforseo/ imports it.

Patterns supported:
  run_live(endpoint, payload)       — synchronous POST to /live/ endpoints
  run_task(endpoint, payload, ...)  — async: post task → poll tasks_ready → fetch result

German defaults: location_code=2276, language_code="de" (overridable per-call).
Base URL: https://api.dataforseo.com/v3
"""

from __future__ import annotations

import base64
import json
import os
import pathlib
import time
import urllib.error
import urllib.request
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://api.dataforseo.com/v3"
DEFAULT_LOCATION_CODE = 2276   # Germany
DEFAULT_LANGUAGE_CODE = "de"

_ENV_FILE = pathlib.Path(__file__).parent / ".dataforseo.env"

# ---------------------------------------------------------------------------
# Credential loading
# ---------------------------------------------------------------------------


def _load_env_file(path: pathlib.Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE env file (lines starting with # are ignored)."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
    return result


def _get_credentials() -> tuple[str, str]:
    """
    Return (login, password) from env vars or .dataforseo.env file.

    Raises DataForSEOAuthError with a clear setup message if missing.
    """
    login = os.environ.get("DATAFORSEO_LOGIN", "")
    password = os.environ.get("DATAFORSEO_PASSWORD", "")

    if not login or not password:
        env_vars = _load_env_file(_ENV_FILE)
        login = login or env_vars.get("DATAFORSEO_LOGIN", "")
        password = password or env_vars.get("DATAFORSEO_PASSWORD", "")

    if not login or not password:
        raise DataForSEOAuthError(
            "DataForSEO credentials not found.\n\n"
            "Set them via environment variables:\n"
            "  export DATAFORSEO_LOGIN=your@email.com\n"
            "  export DATAFORSEO_PASSWORD=your_api_password\n\n"
            "Or create dataforseo/.dataforseo.env with:\n"
            "  DATAFORSEO_LOGIN=your@email.com\n"
            "  DATAFORSEO_PASSWORD=your_api_password\n\n"
            "Get your credentials at https://app.dataforseo.com/register\n"
            "Note: DataForSEO requires a $50 minimum account top-up."
        )

    return login, password


def _auth_header(login: str, password: str) -> str:
    token = base64.b64encode(f"{login}:{password}".encode()).decode()
    return f"Basic {token}"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DataForSEOError(Exception):
    """Base exception for DataForSEO client errors."""


class DataForSEOAuthError(DataForSEOError):
    """Raised when credentials are missing or invalid."""


class DataForSEOAPIError(DataForSEOError):
    """Raised when the API returns a non-20000 status code."""

    def __init__(self, status_code: int, message: str, cost: float = 0.0) -> None:
        self.status_code = status_code
        self.cost = cost
        super().__init__(f"DataForSEO API error {status_code}: {message}")


class DataForSEOTimeoutError(DataForSEOError):
    """Raised when async task polling exceeds timeout."""


# ---------------------------------------------------------------------------
# Low-level HTTP
# ---------------------------------------------------------------------------


def _post(url: str, payload: list[dict], login: str, password: str) -> dict:
    """POST JSON payload; return parsed response dict."""
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": _auth_header(login, password),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        raise DataForSEOAPIError(exc.code, f"HTTP {exc.code}: {body_text}") from exc
    except urllib.error.URLError as exc:
        raise DataForSEOError(f"Network error reaching DataForSEO: {exc.reason}") from exc


def _get(url: str, login: str, password: str) -> dict:
    """GET request; return parsed response dict."""
    req = urllib.request.Request(
        url,
        headers={"Authorization": _auth_header(login, password)},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        raise DataForSEOAPIError(exc.code, f"HTTP {exc.code}: {body_text}") from exc
    except urllib.error.URLError as exc:
        raise DataForSEOError(f"Network error reaching DataForSEO: {exc.reason}") from exc


# ---------------------------------------------------------------------------
# Response validation helpers
# ---------------------------------------------------------------------------


def _check_response(response: dict) -> None:
    """Raise DataForSEOAPIError if top-level status is not 20000."""
    code = response.get("status_code", 0)
    msg = response.get("status_message", "unknown error")
    if code != 20000:
        raise DataForSEOAPIError(code, msg)


def _extract_results(response: dict) -> list[dict]:
    """
    Return the list of task result items from a standard response envelope.

    Standard envelope:
      {
        "status_code": 20000,
        "cost": 0.0012,
        "tasks": [
          {
            "id": "...",
            "status_code": 20000,
            "result": [ {...}, ... ]
          }
        ]
      }

    Logs cost and checks per-task status codes.
    """
    _check_response(response)

    cost = response.get("cost", 0.0)
    tasks = response.get("tasks", [])
    all_results: list[dict] = []

    for task in tasks:
        task_code = task.get("status_code", 0)
        task_msg = task.get("status_message", "unknown")
        if task_code != 20000:
            raise DataForSEOAPIError(task_code, f"Task error: {task_msg}", cost=cost)
        result = task.get("result") or []
        all_results.extend(result)

    return all_results, cost


# ---------------------------------------------------------------------------
# Public API: run_live
# ---------------------------------------------------------------------------


def run_live(
    endpoint: str,
    payload: list[dict] | dict,
    *,
    login: str | None = None,
    password: str | None = None,
) -> tuple[list[dict], float]:
    """
    Execute a DataForSEO *live* (synchronous) request.

    endpoint: path under BASE_URL, e.g. "/serp/google/organic/live/advanced"
    payload:  list of task dicts (will be wrapped in a list if a single dict is given)

    Returns (results: list[dict], cost: float).

    Live endpoints are synchronous but cost ~2-3x more than standard async.
    """
    if login is None or password is None:
        login, password = _get_credentials()

    if isinstance(payload, dict):
        payload = [payload]

    url = BASE_URL.rstrip("/") + "/" + endpoint.lstrip("/")
    response = _post(url, payload, login, password)
    return _extract_results(response)


# ---------------------------------------------------------------------------
# Public API: run_task (async pattern)
# ---------------------------------------------------------------------------


def task_post(
    endpoint: str,
    payload: list[dict] | dict,
    *,
    login: str | None = None,
    password: str | None = None,
) -> list[str]:
    """
    Post one or more tasks to a DataForSEO async endpoint.

    endpoint: e.g. "/serp/google/organic/task_post"
    Returns list of task IDs.

    DataForSEO async flow (owner note: "DataForSEO ist async API"):
      1. POST to /task_post   → get task IDs
      2. GET  /tasks_ready    → poll until task IDs appear
      3. GET  /task_get/advanced/{id} → fetch result

    Optionally you may pass postback_url / pingback_url in each payload item
    for webhook-style notification instead of polling.
    """
    if login is None or password is None:
        login, password = _get_credentials()

    if isinstance(payload, dict):
        payload = [payload]

    url = BASE_URL.rstrip("/") + "/" + endpoint.lstrip("/")
    response = _post(url, payload, login, password)
    _check_response(response)

    task_ids = [t["id"] for t in response.get("tasks", []) if "id" in t]
    return task_ids


def tasks_ready(
    *,
    login: str | None = None,
    password: str | None = None,
) -> list[str]:
    """
    Poll the /tasks_ready endpoint and return the list of ready task IDs.

    DataForSEO keeps completed tasks available for 30 days.
    """
    if login is None or password is None:
        login, password = _get_credentials()

    url = BASE_URL + "/tasks_ready"
    response = _get(url, login, password)
    _check_response(response)

    ready_ids: list[str] = []
    for task in response.get("tasks", []):
        result = task.get("result") or []
        for item in result:
            tid = item.get("id")
            if tid:
                ready_ids.append(tid)
    return ready_ids


def task_get(
    task_id: str,
    fetch_path: str = "task_get/advanced",
    *,
    base_endpoint: str | None = None,
    login: str | None = None,
    password: str | None = None,
) -> tuple[list[dict], float]:
    """
    Fetch results for a completed task.

    task_id:      the ID returned by task_post
    fetch_path:   sub-path like "task_get/advanced" (DataForSEO standard)
    base_endpoint: optional top-level path (e.g. "/serp/google/organic")

    Returns (results: list[dict], cost: float).
    """
    if login is None or password is None:
        login, password = _get_credentials()

    if base_endpoint:
        url = BASE_URL.rstrip("/") + "/" + base_endpoint.strip("/") + "/" + fetch_path.strip("/") + "/" + task_id
    else:
        url = BASE_URL + "/task_get/advanced/" + task_id

    response = _get(url, login, password)
    return _extract_results(response)


def run_task(
    post_endpoint: str,
    payload: list[dict] | dict,
    *,
    fetch_endpoint: str | None = None,
    poll_interval: float = 5.0,
    timeout: float = 600.0,
    login: str | None = None,
    password: str | None = None,
) -> tuple[list[dict], float]:
    """
    Full async task lifecycle: post → poll tasks_ready → fetch result.

    post_endpoint:  e.g. "/serp/google/organic/task_post"
    payload:        task dict(s)
    fetch_endpoint: base path for task_get (e.g. "/serp/google/organic").
                    If None, uses generic /task_get/advanced/{id}.
    poll_interval:  seconds between tasks_ready polls (default 5s)
    timeout:        max seconds to wait (default 600s = 10 min)

    Returns (results: list[dict], total_cost: float).

    Note: For webhook-based notification instead of polling, add
    "postback_url" or "pingback_url" to your payload items and
    handle the callback yourself rather than calling run_task.
    """
    if login is None or password is None:
        login, password = _get_credentials()

    # Step 1: post task
    task_ids = set(task_post(post_endpoint, payload, login=login, password=password))
    if not task_ids:
        raise DataForSEOError("No task IDs returned from task_post.")

    # Step 2: poll tasks_ready
    deadline = time.monotonic() + timeout
    remaining_ids = set(task_ids)

    all_results: list[dict] = []
    total_cost = 0.0

    while remaining_ids:
        if time.monotonic() > deadline:
            raise DataForSEOTimeoutError(
                f"DataForSEO tasks {remaining_ids} not ready after {timeout}s."
            )
        ready = set(tasks_ready(login=login, password=password))
        to_fetch = remaining_ids & ready
        for tid in to_fetch:
            results, cost = task_get(
                tid,
                base_endpoint=fetch_endpoint,
                login=login,
                password=password,
            )
            all_results.extend(results)
            total_cost += cost
            remaining_ids.discard(tid)

        if remaining_ids:
            time.sleep(poll_interval)

    return all_results, total_cost


# ---------------------------------------------------------------------------
# Utility: merge German defaults into a payload dict
# ---------------------------------------------------------------------------


def with_german_defaults(params: dict[str, Any]) -> dict[str, Any]:
    """
    Return params with location_code and language_code set to German defaults
    if not already specified.
    """
    result = dict(params)
    result.setdefault("location_code", DEFAULT_LOCATION_CODE)
    result.setdefault("language_code", DEFAULT_LANGUAGE_CODE)
    return result
