"""
research.py — Keyword research orchestrator.

Produces a unified keyword list by combining:
  1. GSC opportunities  (free, always runs, real data from our own GSC)
  2. Google Ads ideas   (requires credentials; skipped gracefully if absent)
  3. Autocomplete       (free, best-effort; silently skipped if blocked)

For each keyword the output includes:
  keyword           : str
  source            : "gsc" | "ads" | "autocomplete"
  search_volume     : int | null  (from Ads; null when Ads unavailable)
  competition       : "LOW" | "MEDIUM" | "HIGH" | "UNSPECIFIED" | null
  competition_index : int 0–100 | null
  trend             : list[int] | []  (12-month monthly volumes; [] when unavailable)
  intent            : str  (transactional | commercial | informational | navigational | unknown)
  intent_evidence   : str  (which modifier matched)
  our_current_position : float | null  (from GSC data; null if we don't rank)
  icp_relevance     : float 0–1  (from validate_icp.icp_relevance)
  opportunity_score : float  — see formula below
  recommended_action: str

Opportunity score formula
-------------------------
Scores are on a 0–100 scale computed deterministically from four inputs:

  volume_score     = log10(max(search_volume, 10)) / log10(max_volume) * 40
                     (log-scaled; capped at 40 pts; null volume → 10 pts baseline)

  competition_score= (100 - competition_index) / 100 * 25
                     (lower competition → more points; null → 12.5 pts neutral)

  gap_score        = 25 when we have no position (content gap)
                   = max(0, (30 - our_position) / 30) * 20 if we rank 1–30
                   = 0 when position > 30

  icp_score        = icp_relevance * 10
                     (ICP alignment; 0 if excluded term)

  opportunity_score = round(volume_score + competition_score + gap_score + icp_score, 2)

Reasoning:
  - Volume is the biggest lever (40 pts) but log-scaled so 100k isn't 100× a 1k keyword.
  - Competition (25 pts) rewards attainable gaps; LOW wins over HIGH.
  - Gap (25 pts) rewards content we haven't created yet, more than improving existing rank.
  - ICP (10 pts) ensures audience fit is a tiebreaker.

Usage
-----
  python3 scripts/keywords/research.py \
      --data-dir data/_demo/2026-06-16 \
      --icp config/icp.example.yaml \
      [--config config/gsc.env] \
      [--demo]
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_icp import load_icp, icp_relevance  # noqa: E402
from scripts.keywords import intent as intent_mod           # noqa: E402
from scripts.keywords import gsc_opportunities              # noqa: E402
from scripts.keywords import autocomplete as ac             # noqa: E402
from scripts.keywords import google_ads as ads_mod          # noqa: E402

# Max results from each source
MAX_GSC_OPPS   = 200
MAX_ADS_IDEAS  = 500
MAX_AUTOCOMPLETE_SEEDS = 10


# ---------------------------------------------------------------------------
# Opportunity score
# ---------------------------------------------------------------------------

def _opportunity_score(
    search_volume: int | None,
    competition_index: int | None,
    our_position: float | None,
    icp_rel: float,
    max_volume: int,
) -> float:
    """
    Compute a deterministic opportunity score on a 0–100 scale.

    Formula (documented in module docstring):
      volume_score     = log10(max(volume, 10)) / log10(max(max_volume, 10)) * 40
      competition_score= (100 - competition_index) / 100 * 25
      gap_score        = 25 (no rank) | (30 - pos) / 30 * 20 (pos 1-30) | 0 (pos > 30)
      icp_score        = icp_relevance * 10
    """
    # Volume component (40 pts)
    if search_volume is not None and search_volume > 0:
        denom = max(math.log10(max(max_volume, 10)), 1)
        volume_score = math.log10(max(search_volume, 10)) / denom * 40
    else:
        volume_score = 10.0  # baseline for keywords without volume data

    # Competition component (25 pts) — lower index = more opportunity
    if competition_index is not None:
        competition_score = (100 - competition_index) / 100 * 25
    else:
        competition_score = 12.5  # neutral

    # Gap component (25 pts)
    if our_position is None:
        gap_score = 25.0   # content gap — we don't rank at all
    elif our_position <= 30:
        gap_score = max(0.0, (30 - our_position) / 30) * 20
    else:
        gap_score = 0.0

    # ICP component (10 pts)
    icp_score = icp_rel * 10

    total = volume_score + competition_score + gap_score + icp_score
    return round(min(total, 100.0), 2)


def _recommended_action(
    opportunity_score: float,
    search_volume: int | None,
    our_position: float | None,
    competition: str | None,
    intent: str,
) -> str:
    """
    Rule-based recommended action string.  Deterministic — no LLM.
    """
    if our_position is None:
        if opportunity_score >= 60:
            return "content_gap"
        return "monitor"
    if our_position <= 10:
        if intent in ("transactional", "commercial"):
            return "optimize_conversion"
        return "optimize_ranking"
    if our_position <= 30:
        return "optimize_ranking"
    return "monitor"


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_research(
    data_dir: pathlib.Path,
    icp: dict,
    cfg: dict | None = None,
    demo: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Run the full keyword research pipeline and return the keywords dict.

    Parameters
    ----------
    data_dir : Run directory containing queries.json etc.
    icp      : Validated ICP dict.
    cfg      : Config dict (from config_loader); may be None in demo mode.
    demo     : If True, use fixture data instead of live APIs.
    verbose  : Print progress to stderr.

    Returns
    -------
    {
      "enabled": True,
      "source_note": str,
      "opportunities": [ ... ],  # sorted by opportunity_score desc
    }
    """
    cfg = cfg or {}
    brand_terms = icp.get("competitors", []) + [icp.get("audience", "")]
    country = icp.get("country", "DE")
    language = icp.get("language", "de")
    excluded_terms = [t.lower() for t in icp.get("excluded_terms", [])]
    priority_topics = icp.get("priority_topics", [])

    # ── 1. GSC opportunities (always runs — free) ────────────────────────────
    if verbose:
        print("[research] Running GSC opportunity analysis…", file=sys.stderr)
    gsc_opps = gsc_opportunities.analyze(data_dir)[:MAX_GSC_OPPS]

    # Build a lookup of our current GSC positions (keyword → position)
    gsc_position_map: dict[str, float] = {}
    queries_path = data_dir / "queries.json"
    if queries_path.exists():
        with open(queries_path) as fh:
            for row in json.load(fh):
                if isinstance(row, dict) and row.get("keys"):
                    gsc_position_map[row["keys"][0].lower()] = float(row.get("position", 0))

    # ── 2. Google Ads keyword ideas ──────────────────────────────────────────
    ads_note = "Google Ads volumes: OFF (not configured)"
    ads_ideas: list[dict] = []

    if demo:
        # Load fixture data
        fixture_path = (
            pathlib.Path(__file__).resolve().parent.parent.parent
            / "tests" / "fixtures" / "keyword_ideas_fixture.json"
        )
        if fixture_path.exists():
            with open(fixture_path) as fh:
                fixture = json.load(fh)
            ads_ideas = fixture.get("ideas", [])
            ads_note  = fixture.get("source_note", "Google Ads volumes: ON (demo fixture)")
            if verbose:
                print(f"[research] Loaded {len(ads_ideas)} Ads ideas from fixture", file=sys.stderr)
        else:
            ads_note = "Google Ads volumes: OFF (demo fixture not found)"
    else:
        # Live API call — seed with ICP priority topics
        seed_kws = priority_topics[:15]
        site_url = cfg.get("GSC_SITE_URL", "")
        # Convert sc-domain: prefix to bare domain for URL seed
        url_seed = site_url.replace("sc-domain:", "")
        if url_seed.startswith("http"):
            pass  # already a URL
        elif url_seed:
            url_seed = f"https://{url_seed}"

        ads_result = ads_mod.fetch_keyword_ideas_with_config(
            cfg,
            keywords=seed_kws,
            url=url_seed or None,
            country_code=country,
            language_code=language,
            max_results=MAX_ADS_IDEAS,
            verbose=verbose,
        )
        ads_note   = ads_result["source_note"]
        ads_ideas  = ads_result["ideas"]

    # ── 3. Autocomplete expansion ────────────────────────────────────────────
    autocomplete_results: list[dict] = []
    if demo:
        ac_fixture_path = (
            pathlib.Path(__file__).resolve().parent.parent.parent
            / "tests" / "fixtures" / "autocomplete_fixture.json"
        )
        if ac_fixture_path.exists():
            with open(ac_fixture_path) as fh:
                autocomplete_results = json.load(fh)
            if verbose:
                print(f"[research] Loaded {len(autocomplete_results)} autocomplete suggestions from fixture",
                      file=sys.stderr)
    else:
        existing_queries = list(gsc_position_map.keys())[:50]
        try:
            autocomplete_results = ac.expand(
                priority_topics=priority_topics,
                existing_queries=existing_queries,
                lang=language[:2],
                country=country.lower()[:2],
                max_seeds=MAX_AUTOCOMPLETE_SEEDS,
                verbose=verbose,
            )
        except Exception as exc:  # noqa: BLE001
            if verbose:
                print(f"[research] Autocomplete failed (non-fatal): {exc}", file=sys.stderr)

    # ── 4. Unified keyword list ──────────────────────────────────────────────
    # Build a max-volume reference for score normalization
    all_volumes = [
        idea["avg_monthly_searches"]
        for idea in ads_ideas
        if idea.get("avg_monthly_searches") is not None
    ]
    max_volume = max(all_volumes) if all_volumes else 1000

    # Build an ads lookup: keyword → idea dict
    ads_lookup: dict[str, dict] = {
        idea["text"].lower(): idea
        for idea in ads_ideas
        if idea.get("text")
    }

    # Deduplicate across sources: keyword_lower → best entry
    merged: dict[str, dict] = {}

    def _add_keyword(
        keyword: str,
        source: str,
        our_pos: float | None = None,
        extra: dict | None = None,
    ) -> None:
        kw_lower = keyword.strip().lower()

        # Exclusion gate
        for excl in excluded_terms:
            if excl in kw_lower:
                return

        # Classify intent
        intent_result = intent_mod.classify(keyword, brand_terms=brand_terms)

        # Look up Ads data
        ads_data = ads_lookup.get(kw_lower) or {}
        volume          = ads_data.get("avg_monthly_searches")
        competition     = ads_data.get("competition")
        comp_index      = ads_data.get("competition_index")
        trend           = [
            mv.get("monthly_searches")
            for mv in ads_data.get("monthly_search_volumes", [])
            if mv.get("monthly_searches") is not None
        ]

        # ICP relevance
        rel = icp_relevance(icp, keyword)
        if rel <= 0.0:
            return  # excluded by ICP

        # Resolve our current position
        if our_pos is None:
            our_pos = gsc_position_map.get(kw_lower)

        # Opportunity score
        score = _opportunity_score(
            search_volume=volume,
            competition_index=comp_index,
            our_position=our_pos,
            icp_rel=rel,
            max_volume=max_volume,
        )

        rec_action = _recommended_action(
            opportunity_score=score,
            search_volume=volume,
            our_position=our_pos,
            competition=competition,
            intent=intent_result["intent"],
        )

        entry = {
            "keyword": keyword.strip(),
            "source": source,
            "search_volume": volume,
            "competition": competition if competition and competition != "UNSPECIFIED" else None,
            "competition_index": comp_index,
            "trend": trend[-12:] if len(trend) > 12 else trend,  # last 12 months
            "intent": intent_result["intent"],
            "intent_evidence": intent_result["evidence"],
            "our_current_position": our_pos,
            "icp_relevance": rel,
            "opportunity_score": score,
            "recommended_action": rec_action,
        }

        # Dedup: keep the entry with the highest opportunity score, prefer richer data
        if kw_lower not in merged or score > merged[kw_lower]["opportunity_score"]:
            merged[kw_lower] = entry

    # Process GSC opportunities
    for opp in gsc_opps:
        _add_keyword(
            keyword=opp["keyword"],
            source="gsc",
            our_pos=opp["our_current_position"],
        )

    # Process Ads ideas
    for idea in ads_ideas:
        if idea.get("text"):
            _add_keyword(keyword=idea["text"], source="ads")

    # Process autocomplete
    for sug in autocomplete_results:
        if sug.get("keyword"):
            _add_keyword(keyword=sug["keyword"], source="autocomplete")

    # Sort by opportunity_score desc
    opportunities = sorted(merged.values(), key=lambda x: x["opportunity_score"], reverse=True)

    # Assemble source note
    sources_active = ["GSC (always on)"]
    if ads_ideas:
        sources_active.append("Google Ads keyword ideas")
    if autocomplete_results:
        sources_active.append("Google Autocomplete")
    source_note = (
        f"{ads_note}. "
        f"Active sources: {', '.join(sources_active)}."
    )

    return {
        "enabled": True,
        "source_note": source_note,
        "opportunities": opportunities,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run keyword research and write keywords.json."
    )
    parser.add_argument("--data-dir", required=True,
                        help="Path to the run data directory.")
    parser.add_argument("--icp", required=True,
                        help="Path to validated ICP YAML file.")
    parser.add_argument("--config", default=None,
                        help="Path to gsc.env (for Google Ads credentials).")
    parser.add_argument("--demo", action="store_true",
                        help="Use fixtures instead of live APIs.")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--out", default=None,
                        help="Output path (default: <data-dir>/keywords.json).")
    args = parser.parse_args()

    data_dir = pathlib.Path(args.data_dir).resolve()
    if not data_dir.exists():
        print(f"ERROR: data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    icp = load_icp(args.icp)

    cfg: dict = {}
    if not args.demo:
        try:
            from scripts.config_loader import load_config  # noqa: PLC0415
            cfg = load_config(args.config, require_all=False)
        except Exception as exc:
            print(f"[research] WARNING: could not load config: {exc}", file=sys.stderr)

    result = run_research(
        data_dir=data_dir,
        icp=icp,
        cfg=cfg,
        demo=args.demo,
        verbose=args.verbose,
    )

    out_path = pathlib.Path(args.out) if args.out else data_dir / "keywords.json"
    with open(out_path, "w") as fh:
        json.dump(result, fh, indent=2, default=str)

    print(f"[research] keywords.json written to: {out_path}")
    print(f"[research] Source note: {result['source_note']}")
    print(f"[research] {len(result['opportunities'])} keyword opportunities found.")
    if result["opportunities"]:
        top = result["opportunities"][0]
        print(f"[research] Top keyword: {top['keyword']!r} "
              f"(score={top['opportunity_score']}, intent={top['intent']})")


if __name__ == "__main__":
    main()
