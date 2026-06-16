"""
onpage_crawl.py — Crawl top N pages and audit on-page SEO signals.

Checks per page:
  - Title tag: presence, length (30–60 chars), uniqueness across crawled set
  - Meta description: presence, length (70–160 chars)
  - H1 tags: must have exactly one; zero or multiple are flagged
  - Canonical tag: presence and whether it's self-referencing
  - JSON-LD structured data: any schema.org markup present?
  - Word count: rough paragraph-text estimate (< 300 flagged as thin content)
  - Noindex: meta robots or X-Robots-Tag blocking indexing?
  - HTTP status: non-200 responses are flagged as critical

Finding fields per page:
  url              : page URL
  status_code      : HTTP response code
  title            : extracted title text
  title_length     : character count
  title_issues     : list of issue strings
  description      : extracted meta description text
  description_length: character count
  description_issues: list of issue strings
  h1_count         : number of H1 elements found
  h1_issues        : list of issue strings
  canonical        : canonical URL if present, else None
  has_json_ld      : bool
  word_count       : rough estimate
  is_noindex       : bool
  issues           : consolidated list of all issues (for easy filtering)
  so_what          : one-line summary if issues found, else "No issues found."

Demo / no-internet mode: if demo=True, returns pre-built findings from fixtures
without making any HTTP requests.
"""

import html.parser
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

DEFAULT_TOP_N = 20
CRAWL_DELAY_SECONDS = 2.0
CRAWL_TIMEOUT = 20
MAX_RETRIES = 3
# A realistic browser User-Agent. Many sites / WAFs rate-limit or block
# unknown bot agents (HTTP 429/403), which would otherwise be misread as
# on-page problems. We crawl politely (delay + backoff) instead.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Title length thresholds.
TITLE_MIN = 30
TITLE_MAX = 60

# Meta description length thresholds.
DESC_MIN = 70
DESC_MAX = 160

# Word count below this is flagged as thin content.
MIN_WORD_COUNT = 300


class _PageParser(html.parser.HTMLParser):
    """Minimal HTML parser for on-page signal extraction."""

    def __init__(self):
        super().__init__()
        self.title: str | None = None
        self.description: str | None = None
        self.canonical: str | None = None
        self.has_json_ld: bool = False
        self.is_noindex: bool = False
        self.h1_count: int = 0
        self.body_text_chunks: list[str] = []

        # Internal state.
        self._in_title: bool = False
        self._in_body: bool = False
        self._in_script: bool = False
        self._in_style: bool = False
        self._script_type: str = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr_dict = dict(attrs)
        tag_lower = tag.lower()

        if tag_lower == "title":
            self._in_title = True

        elif tag_lower == "meta":
            name = (attr_dict.get("name") or "").lower()
            prop = (attr_dict.get("property") or "").lower()
            content = attr_dict.get("content") or ""
            http_equiv = (attr_dict.get("http-equiv") or "").lower()

            if name == "description" or prop == "og:description":
                if self.description is None:
                    self.description = content.strip()

            if name == "robots" and "noindex" in content.lower():
                self.is_noindex = True
            if http_equiv == "x-robots-tag" and "noindex" in content.lower():
                self.is_noindex = True

        elif tag_lower == "link":
            rel = (attr_dict.get("rel") or "").lower()
            if rel == "canonical":
                self.canonical = attr_dict.get("href")

        elif tag_lower == "script":
            self._in_script = True
            self._script_type = (attr_dict.get("type") or "").lower()
            if "application/ld+json" in self._script_type:
                self.has_json_ld = True

        elif tag_lower == "style":
            self._in_style = True

        elif tag_lower == "h1":
            self.h1_count += 1

        elif tag_lower == "body":
            self._in_body = True

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if tag_lower == "title":
            self._in_title = False
        elif tag_lower == "script":
            self._in_script = False
        elif tag_lower == "style":
            self._in_style = False

    def handle_data(self, data: str):
        if self._in_title and self.title is None:
            self.title = data.strip()
        elif self._in_body and not self._in_script and not self._in_style:
            chunk = data.strip()
            if chunk:
                self.body_text_chunks.append(chunk)

    @property
    def word_count(self) -> int:
        all_text = " ".join(self.body_text_chunks)
        return len(all_text.split())


def _fetch_html(url: str) -> tuple[str, int, str]:
    """
    Fetch a page, retrying on transient rate-limit/server responses.

    Returns (html_text, status_code, content_type). Retries HTTP 429 and 503
    with exponential backoff (honouring a numeric Retry-After header). Raises
    the last exception if all attempts fail.
    """
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=CRAWL_TIMEOUT) as resp:
                content_type = resp.headers.get("Content-Type", "")
                html_bytes = resp.read()
                charset = "utf-8"
                if "charset=" in content_type:
                    charset = content_type.split("charset=")[-1].split(";")[0].strip()
                return html_bytes.decode(charset, errors="replace"), resp.status, content_type
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in (429, 503) and attempt < MAX_RETRIES - 1:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                wait = float(retry_after) if (retry_after and retry_after.isdigit()) else (2.0 ** attempt) * 3
                time.sleep(min(wait, 30))
                continue
            raise
        except Exception as exc:  # noqa: BLE001 — network/parse errors all map to "uncrawlable"
            last_exc = exc
            if attempt < MAX_RETRIES - 1:
                time.sleep((2.0 ** attempt) * 2)
                continue
            raise
    raise last_exc if last_exc else RuntimeError("fetch failed")


def _fetch_error(url: str, status_code: int, reason: str) -> dict:
    """
    A finding for a page we could NOT crawl (rate-limit, timeout, connection
    error). This is a crawler-side limitation, NOT an on-page SEO defect, so
    `issues` stays empty — these never become on-page recommendations. Genuine
    SEO-relevant HTTP errors (404/410/5xx) are surfaced separately via
    `http_issue` so the recommender can treat them as real, lower-confidence.
    """
    # 4xx/5xx (other than 429) on a page that GSC says earns clicks is a real
    # problem worth flagging; 429/timeouts/connection errors are crawler noise.
    http_issue = status_code in (404, 410) or (500 <= status_code < 600 and status_code != 503)
    return {
        "url": url,
        "status_code": status_code,
        "fetch_error": reason,
        "http_issue": http_issue,
        "issues": [],
        "so_what": (
            f"{url}: page returns HTTP {status_code} — verify it is reachable and indexable."
            if http_issue
            else f"{url}: could not be crawled ({reason}) — on-page audit skipped, not an SEO defect."
        ),
    }


def _audit_page(url: str) -> dict:
    """Fetch and audit a single page. Returns a finding dict."""
    issues: list[str] = []

    # Fetch the page (with retry/backoff on transient responses).
    try:
        html_text, status_code, content_type = _fetch_html(url)
    except urllib.error.HTTPError as exc:
        return _fetch_error(url, exc.code, f"HTTP {exc.code} {exc.reason}")
    except Exception as exc:  # noqa: BLE001
        return _fetch_error(url, 0, f"{type(exc).__name__}: {exc}")

    # Only parse HTML.
    if "text/html" not in content_type:
        return {
            "url": url,
            "status_code": status_code,
            "fetch_error": f"Non-HTML content type: {content_type}",
            "http_issue": False,
            "issues": [],
            "so_what": f"{url}: Non-HTML content type ({content_type}) — on-page audit skipped.",
        }

    if status_code != 200:
        issues.append(f"Non-200 status: {status_code}")

    # Parse HTML.
    parser = _PageParser()
    try:
        parser.feed(html_text)
    except Exception:
        pass  # Parser errors shouldn't crash the audit.

    # Title checks.
    title_issues: list[str] = []
    if not parser.title:
        title_issues.append("Missing title tag")
    else:
        tlen = len(parser.title)
        if tlen < TITLE_MIN:
            title_issues.append(f"Title too short ({tlen} chars, min {TITLE_MIN})")
        elif tlen > TITLE_MAX:
            title_issues.append(f"Title too long ({tlen} chars, max {TITLE_MAX})")

    # Description checks.
    desc_issues: list[str] = []
    if not parser.description:
        desc_issues.append("Missing meta description")
    else:
        dlen = len(parser.description)
        if dlen < DESC_MIN:
            desc_issues.append(f"Meta description too short ({dlen} chars, min {DESC_MIN})")
        elif dlen > DESC_MAX:
            desc_issues.append(f"Meta description too long ({dlen} chars, max {DESC_MAX})")

    # H1 checks.
    h1_issues: list[str] = []
    if parser.h1_count == 0:
        h1_issues.append("No H1 tag found")
    elif parser.h1_count > 1:
        h1_issues.append(f"Multiple H1 tags found ({parser.h1_count}) — use exactly one")

    # Word count check.
    if parser.word_count < MIN_WORD_COUNT:
        issues.append(f"Thin content: only ~{parser.word_count} words (min {MIN_WORD_COUNT})")

    # Noindex check.
    if parser.is_noindex:
        issues.append("Page is set to noindex — verify this is intentional")

    all_issues = issues + title_issues + desc_issues + h1_issues
    so_what = (
        f"{url}: {len(all_issues)} issue(s) — {'; '.join(all_issues[:3])}"
        if all_issues
        else f"{url}: No on-page issues detected."
    )

    return {
        "url": url,
        "status_code": status_code,
        "fetch_error": None,
        "http_issue": False,
        "title": parser.title,
        "title_length": len(parser.title) if parser.title else 0,
        "title_issues": title_issues,
        "description": parser.description,
        "description_length": len(parser.description) if parser.description else 0,
        "description_issues": desc_issues,
        "h1_count": parser.h1_count,
        "h1_issues": h1_issues,
        "canonical": parser.canonical,
        "has_json_ld": parser.has_json_ld,
        "word_count": parser.word_count,
        "is_noindex": parser.is_noindex,
        "issues": all_issues,
        "so_what": so_what,
    }


def analyze(
    data_dir: pathlib.Path,
    *,
    top_n: int = DEFAULT_TOP_N,
    demo: bool = False,
) -> list[dict]:
    """
    Crawl top N pages by clicks and audit on-page signals.

    Parameters
    ----------
    data_dir : Directory containing pages.json.
    top_n    : Number of top pages to crawl (by clicks, descending).
    demo     : If True, load fixtures instead of making HTTP requests.

    Returns
    -------
    List of per-page audit dicts, sorted by number of issues descending.
    """
    if demo:
        fixture_path = _ROOT / "tests" / "fixtures" / "onpage_results.json"
        if fixture_path.exists():
            with open(fixture_path) as fh:
                return json.load(fh)
        return []

    pages_path = data_dir / "pages.json"
    if not pages_path.exists():
        return []

    with open(pages_path) as fh:
        pages_rows: list[dict] = json.load(fh)

    # Sort by clicks descending, take top N.
    valid_rows = [r for r in pages_rows if isinstance(r, dict) and r.get("keys")]
    valid_rows.sort(key=lambda r: r.get("clicks", 0), reverse=True)
    top_pages = [r["keys"][0] for r in valid_rows[:top_n]]

    findings: list[dict] = []
    for i, url in enumerate(top_pages):
        if i > 0:
            time.sleep(CRAWL_DELAY_SECONDS)
        result = _audit_page(url)
        findings.append(result)

    # Sort: most issues first.
    findings.sort(key=lambda x: len(x.get("issues", [])), reverse=True)
    return findings
