"""
recommend.py — Translate analysis findings into scored, prioritized recommendations.

Each recommendation is an action the site owner can take. Recommendations are:
  - Specific and imperative ("rewrite the title of /pricing to include X")
  - Scored by impact (1–5) and effort (1–5)
  - Prioritized by impact/effort ratio (higher = do first)
  - Backed by traceable evidence rows from the analysis data
  - Filtered through the ICP to ensure keyword opportunities are relevant

Recommendation object schema:
  {
    "id"        : str (stable, e.g. "sd_001")
    "title"     : str (short, < 80 chars)
    "category"  : str (one of CATEGORIES)
    "action"    : str (imperative, specific, actionable)
    "impact"    : int 1–5
    "effort"    : int 1–5
    "priority"  : float = impact / effort
    "evidence"  : list of evidence dicts from the analysis
    "detail"    : str (markdown, 2–4 sentences explaining why)
  }

Categories:
  quick_win, content_gap, technical_seo, on_page, cannibalization,
  ctr_optimization, decay_recovery
"""

import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_icp import icp_relevance  # noqa: E402

CATEGORIES = {
    "quick_win",
    "content_gap",
    "technical_seo",
    "on_page",
    "cannibalization",
    "ctr_optimization",
    "decay_recovery",
    "keyword_opportunity",
}

# ICP relevance score below which keyword-centric recommendations are skipped.
ICP_RELEVANCE_MIN = 0.0  # Allow all by default; excluded_terms still block.


def _rec(
    rec_id: str,
    title: str,
    category: str,
    action: str,
    impact: int,
    effort: int,
    evidence: list,
    detail: str,
) -> dict:
    """Build a recommendation dict with computed priority."""
    assert 1 <= impact <= 5, f"impact out of range: {impact}"
    assert 1 <= effort <= 5, f"effort out of range: {effort}"
    return {
        "id": rec_id,
        "title": title,
        "category": category,
        "action": action,
        "impact": impact,
        "effort": effort,
        "priority": round(impact / effort, 3),
        "evidence": evidence,
        "detail": detail,
    }


# ---------------------------------------------------------------------------
# Per-analysis recommendation generators
# ---------------------------------------------------------------------------

def _from_striking_distance(findings: list[dict], icp: dict) -> list[dict]:
    """Quick wins: optimize content just outside the top positions."""
    recs = []
    for i, f in enumerate(findings[:10]):  # Cap at 10 per category.
        query = f.get("query", "")
        if icp and icp_relevance(icp, query) <= 0.0:
            continue  # Blocked by excluded_terms.

        best_page = f.get("best_page", "unknown")
        extra = f.get("estimated_extra_clicks", 0)
        position = f.get("position", 0)

        recs.append(_rec(
            rec_id=f"sd_{i+1:03d}",
            title=f'Optimize "{query}" from position {position} to top 3',
            category="quick_win",
            action=(
                f'Improve the title, H1, and internal links for {best_page} '
                f'to better target "{query}" — currently at position {position}, '
                f"moving to top 3 could add ~{extra} clicks per period."
            ),
            impact=min(5, max(1, 3 + (extra // 25))),  # Scale impact by click potential.
            effort=2,
            evidence=[f],
            detail=(
                f'"{query}" ranks at position {position} with {f.get("impressions", 0)} impressions. '
                f"At position 3, the benchmark CTR ({f.get('expected_ctr_p3', 0):.1%}) "
                f"would yield ~{extra} extra clicks vs the current {f.get('clicks', 0)}. "
                f"Focus on: include the exact query phrase in the H1, strengthen the opening paragraph, "
                f"and add 2–3 internal links from topically relevant pages."
            ),
        ))
    return recs


def _from_cannibalization(findings: list[dict], icp: dict) -> list[dict]:
    """Cannibalization: merge or differentiate competing pages."""
    recs = []
    for i, f in enumerate(findings[:8]):
        query = f.get("query", "")
        canonical = f.get("canonical", "unknown")
        cannibalizers = f.get("cannibalizers", [])
        n_pages = len(f.get("pages", []))

        recs.append(_rec(
            rec_id=f"can_{i+1:03d}",
            title=f'Fix cannibalization: "{query}" served by {n_pages} pages',
            category="cannibalization",
            action=(
                f'Consolidate "{query}" onto {canonical}. '
                f"301-redirect or noindex {', '.join(cannibalizers[:2])} "
                f"{'(and others) ' if len(cannibalizers) > 2 else ''}"
                f"to eliminate ranking split."
            ),
            impact=3,
            effort=2,
            evidence=[f],
            detail=(
                f'{n_pages} pages compete for "{query}", splitting authority and confusing crawlers. '
                f"The likely canonical (highest clicks) is {canonical}. "
                f"Either 301-redirect the weaker pages into it, clearly differentiate their content "
                f"to target distinct intent variants, or add canonical tags pointing to {canonical}."
            ),
        ))
    return recs


def _from_ctr_outliers(findings: list[dict], icp: dict) -> list[dict]:
    """CTR optimization: rewrite titles and meta descriptions."""
    recs = []
    for i, f in enumerate(findings[:10]):
        query = f.get("query", "")
        if icp and icp_relevance(icp, query) <= 0.0:
            continue

        best_page = f.get("best_page", "unknown")
        gap = f.get("click_gap", 0)
        actual = f.get("actual_ctr", 0)
        expected = f.get("expected_ctr", 0)
        position = f.get("position", 0)

        recs.append(_rec(
            rec_id=f"ctr_{i+1:03d}",
            title=f'Rewrite title/meta for "{query}" (CTR {actual:.1%} vs {expected:.1%} expected)',
            category="ctr_optimization",
            action=(
                f"Rewrite the <title> and meta description of {best_page} "
                f'to be more compelling for the query "{query}". '
                f"Include a clear value proposition, the query phrase, and a call to action. "
                f"Goal: lift CTR toward {expected:.1%} to recover ~{gap} clicks/period."
            ),
            impact=min(5, max(2, 2 + (gap // 30))),
            effort=1,
            evidence=[f],
            detail=(
                f'"{query}" at position {position} earns only {actual:.1%} CTR '
                f"vs the {expected:.1%} benchmark ({f.get('ctr_ratio', 0):.2f}× ratio). "
                f"This strongly suggests the snippet is unappealing. "
                f"Test: (1) add a number or year to the title, (2) make the meta description answer "
                f"the query intent directly, (3) A/B test with Search Console Impressions as signal."
            ),
        ))
    return recs


def _from_content_decay(findings: list[dict], icp: dict) -> list[dict]:
    """Decay recovery: refresh or rebuild declining content."""
    recs = []
    for i, f in enumerate(findings[:8]):
        url = f.get("url", f.get("subject", "unknown"))
        clicks_decline = f.get("clicks_decline_pct", 0)
        decay_type = f.get("type", "split")

        recs.append(_rec(
            rec_id=f"dec_{i+1:03d}",
            title=f"Recover declining traffic on {url[:60]}",
            category="decay_recovery",
            action=(
                f"Audit and refresh {url}: update statistics, add new sections covering "
                f"emerging subtopics, strengthen internal links, and check for lost backlinks. "
                f"Clicks down {clicks_decline:.0f}% in the {'analysis window' if decay_type == 'split' else 'prior period'}."
            ),
            impact=3,
            effort=3,
            evidence=[f],
            detail=(
                f"{url} shows a {clicks_decline:.1f}% click decline "
                f"({'intra-window split' if decay_type == 'split' else 'period-over-period comparison'}). "
                "Common causes: content became stale (update facts/dates), competing pages freshly published, "
                "lost featured snippet, or algorithm update targeting thin content. "
                "Start with a content audit: word count, outbound link freshness, on-page signals."
            ),
        ))
    return recs


def _from_onpage(findings: list[dict], icp: dict) -> list[dict]:
    """On-page SEO fixes: title, meta, H1, schema, canonical."""
    recs = []
    uncrawlable = [f for f in findings if f.get("fetch_error") and not f.get("http_issue")]
    http_broken = [f for f in findings if f.get("http_issue")]

    # Genuine HTTP errors (404/410/5xx) on pages GSC tracks ARE real issues.
    for i, f in enumerate(http_broken):
        url = f.get("url", "unknown")
        recs.append(_rec(
            rec_id=f"http_{i+1:03d}",
            title=f"Broken page: {url[:50]} returns HTTP {f.get('status_code')}",
            category="technical_seo",
            action=f"Restore or redirect {url} — it returns HTTP {f.get('status_code')} but is tracked in Search Console.",
            impact=4,
            effort=2,
            evidence=[{k: v for k, v in f.items() if k != "so_what"}],
            detail=(
                f"{url} returns HTTP {f.get('status_code')}. A page Google has indexed that now "
                "errors loses its rankings and wastes crawl budget. Fix the page or 301-redirect it "
                "to the most relevant live URL."
            ),
        ))

    # Real on-page SEO defects (title/meta/H1/thin content/noindex).
    issue_findings = [f for f in findings if f.get("issues") and not f.get("fetch_error")]
    for i, f in enumerate(issue_findings):
        issues = f["issues"]
        url = f.get("url", "unknown")

        is_critical = any(
            kw in " ".join(issues).lower()
            for kw in ["missing title", "noindex", "non-200"]
        )
        impact = 4 if is_critical else 2

        recs.append(_rec(
            rec_id=f"op_{i+1:03d}",
            title=f"Fix {len(issues)} on-page issue(s) on {url[:50]}",
            category="on_page",
            action=(
                f"Fix on {url}: {'; '.join(issues[:3])}"
                + (f" (and {len(issues) - 3} more)" if len(issues) > 3 else "") + "."
            ),
            impact=impact,
            effort=1,
            evidence=[{k: v for k, v in f.items() if k != "so_what"}],
            detail=(
                f"Crawl of {url} found {len(issues)} issue(s): {', '.join(issues)}. "
                "Each issue reduces GSC ranking signals or user engagement. "
                "Title and meta description issues directly affect CTR in search results. "
                "Fix missing H1 and thin content issues to signal topical depth to crawlers."
            ),
        ))
        if i >= 15:
            break

    # Pages we could not crawl are a DATA-COLLECTION gap, not an SEO defect.
    # Surface them as a single low-priority note so the user knows coverage was
    # incomplete — never as per-page "fix this page" recommendations.
    if uncrawlable:
        sample = ", ".join(f.get("url", "?") for f in uncrawlable[:5])
        recs.append(_rec(
            rec_id="op_uncrawlable",
            title=f"{len(uncrawlable)} page(s) could not be crawled for the on-page audit",
            category="technical_seo",
            action=(
                f"Re-run the on-page audit for {len(uncrawlable)} page(s) that were rate-limited or "
                f"unreachable during this run (e.g. {sample}). Consider allow-listing the crawler "
                "or lowering crawl concurrency. This is a coverage gap, not a confirmed SEO issue."
            ),
            impact=1,
            effort=1,
            evidence=[{"url": f.get("url"), "reason": f.get("fetch_error")} for f in uncrawlable],
            detail=(
                "These pages returned rate-limit (HTTP 429), timeout, or connection errors and could "
                "not be analysed. This reflects crawl conditions, not page quality — do not treat as "
                "an on-page defect. Re-run during off-peak hours or allow-list the User-Agent."
            ),
        ))
    return recs


def _from_keywords(keywords_result: dict, icp: dict) -> list[dict]:
    """
    Keyword opportunity recommendations from keyword research results.

    Only surfaces strong signals:
      - content_gap: high opportunity_score + no current rank (position is null)
      - optimize_ranking: high opportunity_score + we rank 8–20
    ICP relevance gate: icp_relevance must be > 0.
    """
    if not keywords_result or not keywords_result.get("enabled"):
        return []

    opportunities = keywords_result.get("opportunities", [])
    recs = []
    content_gap_count = 0
    optimize_count = 0

    for kw in opportunities:
        if content_gap_count >= 5 and optimize_count >= 5:
            break

        keyword = kw.get("keyword", "")
        score = kw.get("opportunity_score", 0)
        icp_rel = kw.get("icp_relevance", 0.0)
        position = kw.get("our_current_position")
        action = kw.get("recommended_action", "monitor")
        volume = kw.get("search_volume")  # may be None (free layer)
        intent = kw.get("intent", "unknown")
        competition = kw.get("competition")
        comp_index = kw.get("competition_index")

        # ICP gate
        if icp_rel <= 0.0:
            continue

        # Only surface strong opportunities
        if score < 40:
            continue

        # Build evidence dict — all figures come from the keyword research pipeline
        evidence = {
            "keyword": keyword,
            "opportunity_score": score,
            "icp_relevance": icp_rel,
            "intent": intent,
            "our_current_position": position,
            "search_volume": volume,
            "competition": competition,
            "competition_index": comp_index,
        }

        if action == "content_gap" and content_gap_count < 5:
            content_gap_count += 1
            vol_note = f"{volume:,} avg monthly searches" if volume else "volume unavailable (free mode)"
            comp_note = (
                f"competition: {competition} ({comp_index}/100)"
                if competition and comp_index is not None
                else "competition data unavailable"
            )
            recs.append(_rec(
                rec_id=f"kw_gap_{content_gap_count:03d}",
                title=f'Content gap: create content targeting "{keyword}"',
                category="content_gap",
                action=(
                    f'Create a dedicated page or article targeting "{keyword}" '
                    f"({vol_note}, {comp_note}). "
                    f"Intent: {intent}. We currently have no ranking for this keyword."
                ),
                impact=min(5, max(2, round(score / 20))),
                effort=3,
                evidence=[evidence],
                detail=(
                    f'"{keyword}" has an opportunity score of {score:.0f}/100 '
                    f"with {vol_note} and {comp_note}. "
                    f"We have zero presence for this keyword — creating relevant content "
                    f"aligned with {intent} intent could capture this demand. "
                    f"ICP relevance: {icp_rel:.2f}. "
                    f"Source: keyword research pipeline (no numbers invented by model)."
                ),
            ))
        elif action in ("optimize_ranking", "optimize_conversion") and optimize_count < 5:
            if position is None or position < 8 or position > 30:
                continue
            optimize_count += 1
            vol_note = f"{volume:,} avg monthly searches" if volume else "volume unavailable"
            recs.append(_rec(
                rec_id=f"kw_opt_{optimize_count:03d}",
                title=f'Improve ranking for "{keyword}" (pos {position:.1f})',
                category="keyword_opportunity",
                action=(
                    f'Strengthen content targeting "{keyword}": '
                    f"update the page at position {position:.1f}, add internal links, "
                    f"expand semantic coverage ({vol_note})."
                ),
                impact=min(5, max(2, round(score / 20))),
                effort=2,
                evidence=[evidence],
                detail=(
                    f'"{keyword}" ranks at position {position:.1f} with {vol_note}. '
                    f"Opportunity score: {score:.0f}/100. "
                    f"Improving this ranking toward the top 3 could meaningfully increase "
                    f"clicks given the search volume. ICP relevance: {icp_rel:.2f}. "
                    f"Source: keyword research pipeline (all figures from Python pipeline)."
                ),
            ))

    return recs


def _from_cwv(findings: list[dict] | None, icp: dict) -> list[dict]:
    """Core Web Vitals: performance fixes for failing pages."""
    if not findings:
        return []
    recs = []
    for i, f in enumerate(findings):
        issues = f.get("issues", [])
        if not issues:
            continue
        url = f.get("url", "unknown")
        score = f.get("performance_score", "?")

        recs.append(_rec(
            rec_id=f"cwv_{i+1:03d}",
            title=f"Fix Core Web Vitals on {url[:50]} (score: {score})",
            category="technical_seo",
            action=(
                f"Improve Core Web Vitals for {url}: {'; '.join(issues)}. "
                f"Performance score: {score}/100. "
                "Prioritize LCP and INP — these are Google ranking signals."
            ),
            impact=3,
            effort=4,
            evidence=[f],
            detail=(
                f"{url} fails CWV thresholds: {', '.join(issues)}. "
                f"Lighthouse performance score: {score}/100. "
                "LCP fix: ensure hero image is preloaded and server response time < 200ms. "
                "CLS fix: set explicit width/height on images and avoid injecting content above the fold. "
                "INP fix: defer non-critical JavaScript and break up long tasks."
            ),
        ))
    return recs


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_recommendations(
    analyses: dict,
    icp: dict | None = None,
    keywords_result: dict | None = None,
) -> list[dict]:
    """
    Produce a sorted list of recommendations from all analysis outputs.

    Parameters
    ----------
    analyses         : Dict with keys matching the analysis module names:
                       striking_distance, cannibalization, ctr_outliers, content_decay,
                       onpage, core_web_vitals, wow.
    icp              : Validated ICP dict (or None to skip ICP filtering).
    keywords_result  : Output from keywords.research.run_research() (optional).

    Returns
    -------
    List of recommendation dicts sorted by priority descending.
    """
    all_recs: list[dict] = []
    icp = icp or {}

    all_recs.extend(_from_striking_distance(analyses.get("striking_distance", []), icp))
    all_recs.extend(_from_cannibalization(analyses.get("cannibalization", []), icp))
    all_recs.extend(_from_ctr_outliers(analyses.get("ctr_outliers", []), icp))
    all_recs.extend(_from_content_decay(analyses.get("content_decay", []), icp))
    all_recs.extend(_from_onpage(analyses.get("onpage", []), icp))
    all_recs.extend(_from_cwv(analyses.get("core_web_vitals"), icp))
    all_recs.extend(_from_keywords(keywords_result or {}, icp))

    # Sort by priority desc, then impact desc, then absolute click opportunity
    # desc — so among equally efficient actions, the biggest real win surfaces
    # first (e.g. a 40-click quick win outranks a niche tweak of the same ratio).
    all_recs.sort(
        key=lambda r: (r["priority"], r["impact"], _opportunity(r)),
        reverse=True,
    )

    return all_recs


def _opportunity(rec: dict) -> int:
    """Absolute click opportunity behind a recommendation, for tiebreaking."""
    best = 0
    for ev in rec.get("evidence", []):
        if not isinstance(ev, dict):
            continue
        for key in ("estimated_extra_clicks", "click_gap", "clicks"):
            val = ev.get(key)
            if isinstance(val, (int, float)):
                best = max(best, int(val))
    return best
