# Determinism Guarantee

## The Hard Principle

Every number in every report produced by SEO Insights originates in the
Python pipeline. The model (LLM) never computes, estimates, or invents
metrics. Its only role is to narrate findings that already exist in
`report_data.json`.

## What This Means in Practice

| Data type | Source | Never from LLM? |
|---|---|---|
| Clicks, impressions, CTR, position | Google Search Console API | YES |
| Week-over-week deltas | Python arithmetic on two GSC windows | YES |
| Striking-distance extra-click estimates | `impressions * (benchmark_ctr - actual_ctr)` | YES |
| CTR outlier gaps | `impressions * (expected_ctr - actual_ctr)` | YES |
| Search volume | Google Ads KeywordPlanIdeaService API | YES |
| Competition index (0–100) | Google Ads API field `competitionIndex` | YES |
| Opportunity score | Deterministic formula in `research.py` | YES |
| Autocomplete suggestions | Google Suggest API — text only, no volume | YES |
| Search intent | Rule-based modifier table in `intent.py` | YES |
| ICP relevance score | Token-matching algorithm in `validate_icp.py` | YES |
| Recommendation text figures | Pulled from evidence fields in JSON | YES |

## The Formula for Opportunity Score

Defined in `scripts/keywords/research.py` (`_opportunity_score`):

```
volume_score     = log10(max(search_volume, 10)) / log10(max_volume) * 40
                   (log-scaled; null volume → 10 pts baseline)

competition_score= (100 - competition_index) / 100 * 25
                   (null competition_index → 12.5 pts neutral)

gap_score        = 25          if our_current_position is None (content gap)
                 = max(0, (30 - position) / 30) * 20  if position <= 30
                 = 0           if position > 30

icp_score        = icp_relevance * 10
                   (from validate_icp.icp_relevance — token matching)

opportunity_score = min(volume_score + competition_score + gap_score + icp_score, 100)
```

All four inputs are pulled directly from API responses or computed from
them. No coefficient is chosen by the model; the formula is hardcoded in
Python and auditable in the source.

## Audit Checklist

To verify this guarantee is met:

1. **No hardcoded numbers in recommendation text that aren't in `evidence`.**
   Check `recommend.py`: every figure used in `action` or `detail` strings
   must reference a field from the evidence dict (e.g. `f.get("clicks")`,
   `f.get("opportunity_score")`).

2. **Keyword volumes come from API or fixture only.**
   In demo mode, `keyword_ideas_fixture.json` supplies the numbers.
   In production, `google_ads.py` fetches them from the Ads API.
   `research.py` never assigns a volume value without an API source.

3. **Intent classification is rule-based.**
   `intent.py` uses regex pattern tables — no model inference.

4. **GSC data is fetched, not constructed.**
   `fetch.py` calls the GSC Search Analytics API and writes raw JSON.
   The analysis modules read those files. No row is synthesized.

5. **demo.sh validates the pipeline deterministically.**
   The validation script asserts `opportunity_score` is numeric and that
   `source` is one of `gsc | ads | autocomplete`.
