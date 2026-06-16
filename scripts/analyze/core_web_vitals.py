"""
core_web_vitals.py — Core Web Vitals audit via PageSpeed Insights API.

Requires a PAGESPEED_API_KEY in the config (Google Cloud Console, any project).
If the key is absent, this module skips gracefully and returns None.

Metrics fetched (mobile strategy):
  - LCP  (Largest Contentful Paint) — good: <2.5s, needs improvement: <4s, poor: ≥4s
  - CLS  (Cumulative Layout Shift)  — good: <0.1, needs improvement: <0.25, poor: ≥0.25
  - INP  (Interaction to Next Paint) — good: <200ms, needs improvement: <500ms, poor: ≥500ms
  - Performance Score (0–100, composite Lighthouse score)

Finding fields per page:
  url              : page URL
  lcp_ms           : LCP in milliseconds (or None if not reported)
  lcp_category     : "GOOD", "NEEDS_IMPROVEMENT", "POOR", or "UNKNOWN"
  cls              : CLS score (or None)
  cls_category     : same categories
  inp_ms           : INP in milliseconds (or None)
  inp_category     : same categories
  performance_score: 0–100 Lighthouse score
  issues           : list of failing/poor metric names
  so_what          : one-line summary

Note: PageSpeed Insights returns field data (CrUX) when available and falls back
to lab data (Lighthouse). We prefer field data (displayed as "FAST", "AVERAGE", "SLOW"
in the API response as GOOD/NEEDS_IMPROVEMENT/POOR).
"""

import json
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

PSI_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
STRATEGY = "mobile"
DEFAULT_TOP_N = 20
REQUEST_DELAY = 2.0  # PageSpeed Insights has a quota; be polite.

# CWV thresholds (milliseconds for LCP/INP, raw score for CLS).
LCP_GOOD = 2500
LCP_POOR = 4000
CLS_GOOD = 0.1
CLS_POOR = 0.25
INP_GOOD = 200
INP_POOR = 500


def _categorize(value: float | None, good: float, poor: float) -> str:
    if value is None:
        return "UNKNOWN"
    if value <= good:
        return "GOOD"
    if value <= poor:
        return "NEEDS_IMPROVEMENT"
    return "POOR"


def _fetch_psi(url: str, api_key: str) -> dict | None:
    """Call PageSpeed Insights API. Returns parsed JSON or None on error."""
    params = urllib.parse.urlencode({
        "url": url,
        "key": api_key,
        "strategy": STRATEGY,
        "category": "performance",
    })
    req = urllib.request.Request(f"{PSI_URL}?{params}", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        print(f"  [cwv] PSI error {exc.code} for {url}: {body[:200]}", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"  [cwv] PSI fetch error for {url}: {exc}", file=sys.stderr)
        return None


def _extract_metrics(psi_data: dict) -> dict:
    """Extract CWV metrics from a PSI API response."""
    # Field data (CrUX) is in loadingExperience or originLoadingExperience.
    le = psi_data.get("loadingExperience", {})
    metrics = le.get("metrics", {})

    def _crux_value(key: str) -> float | None:
        """Get the p75 value from a CrUX metric dict."""
        m = metrics.get(key, {})
        # API returns distributions; the summary percentile is in "percentile".
        return m.get("percentile")

    lcp_ms = _crux_value("LARGEST_CONTENTFUL_PAINT_MS")
    cls = _crux_value("CUMULATIVE_LAYOUT_SHIFT_SCORE")
    inp_ms = _crux_value("INTERACTION_TO_NEXT_PAINT")

    # CLS is returned as integer * 100 in some API versions; normalize.
    if cls is not None and cls > 1:
        cls = cls / 100

    # Lighthouse performance score (lab data).
    perf_score = None
    cats = psi_data.get("lighthouseResult", {}).get("categories", {})
    perf = cats.get("performance", {})
    if "score" in perf and perf["score"] is not None:
        perf_score = round(perf["score"] * 100)

    # Also try lab data for LCP/CLS/INP if CrUX not available.
    audits = psi_data.get("lighthouseResult", {}).get("audits", {})
    if lcp_ms is None:
        lcp_audit = audits.get("largest-contentful-paint", {})
        lcp_numeric = lcp_audit.get("numericValue")
        if lcp_numeric is not None:
            lcp_ms = lcp_numeric
    if cls is None:
        cls_audit = audits.get("cumulative-layout-shift", {})
        cls_numeric = cls_audit.get("numericValue")
        if cls_numeric is not None:
            cls = cls_numeric
    if inp_ms is None:
        inp_audit = audits.get("interaction-to-next-paint", {})
        inp_numeric = inp_audit.get("numericValue")
        if inp_numeric is not None:
            inp_ms = inp_numeric

    lcp_cat = _categorize(lcp_ms, LCP_GOOD, LCP_POOR)
    cls_cat = _categorize(cls, CLS_GOOD, CLS_POOR)
    inp_cat = _categorize(inp_ms, INP_GOOD, INP_POOR)

    issues = []
    for metric, cat in [("LCP", lcp_cat), ("CLS", cls_cat), ("INP", inp_cat)]:
        if cat in ("POOR", "NEEDS_IMPROVEMENT"):
            issues.append(f"{metric}: {cat}")

    return {
        "lcp_ms": round(lcp_ms) if lcp_ms is not None else None,
        "lcp_category": lcp_cat,
        "cls": round(cls, 3) if cls is not None else None,
        "cls_category": cls_cat,
        "inp_ms": round(inp_ms) if inp_ms is not None else None,
        "inp_category": inp_cat,
        "performance_score": perf_score,
        "issues": issues,
    }


def analyze(
    data_dir: pathlib.Path,
    *,
    api_key: str | None = None,
    top_n: int = DEFAULT_TOP_N,
    demo: bool = False,
) -> list[dict] | None:
    """
    Fetch Core Web Vitals for top N pages via PageSpeed Insights.

    Returns None if no API key is configured (caller should note this gracefully).
    Returns a list of per-page CWV finding dicts otherwise.

    Parameters
    ----------
    data_dir : Directory containing pages.json.
    api_key  : PageSpeed Insights API key (from PAGESPEED_API_KEY config).
    top_n    : Number of top pages to check.
    demo     : If True, load fixtures instead of making HTTP requests.
    """
    if demo:
        fixture_path = _ROOT / "tests" / "fixtures" / "cwv_results.json"
        if fixture_path.exists():
            with open(fixture_path) as fh:
                return json.load(fh)
        return []

    if not api_key:
        print("  [cwv] No PAGESPEED_API_KEY configured — skipping Core Web Vitals audit.",
              file=sys.stderr)
        return None

    pages_path = data_dir / "pages.json"
    if not pages_path.exists():
        return []

    with open(pages_path) as fh:
        pages_rows: list[dict] = json.load(fh)

    valid_rows = [r for r in pages_rows if isinstance(r, dict) and r.get("keys")]
    valid_rows.sort(key=lambda r: r.get("clicks", 0), reverse=True)
    top_urls = [r["keys"][0] for r in valid_rows[:top_n]]

    findings: list[dict] = []
    for i, url in enumerate(top_urls):
        if i > 0:
            time.sleep(REQUEST_DELAY)
        print(f"  [cwv] Checking {url} …", file=sys.stderr)
        psi_data = _fetch_psi(url, api_key)
        if psi_data is None:
            findings.append({
                "url": url,
                "issues": ["PSI API error — could not fetch data"],
                "so_what": f"{url}: PageSpeed Insights API returned an error.",
            })
            continue
        metrics = _extract_metrics(psi_data)
        metrics["url"] = url
        metrics["so_what"] = (
            f"{url}: performance score {metrics['performance_score']}, "
            f"LCP {metrics['lcp_ms']}ms ({metrics['lcp_category']}), "
            f"CLS {metrics['cls']} ({metrics['cls_category']}), "
            f"INP {metrics['inp_ms']}ms ({metrics['inp_category']})."
            + (f" Issues: {'; '.join(metrics['issues'])}." if metrics["issues"] else " All CWV passing.")
        )
        findings.append(metrics)

    return findings
