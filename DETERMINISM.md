# Determinism Guarantee

## The Hard Principle

Every number in every report produced by SEO Insights originates in the
Python pipeline. The model (LLM) never computes, estimates, or invents
metrics. Its only role is to narrate findings that already exist in
`report_data.json`.

## What the AI Does and Does Not Do

**The AI (keyword-curator sub-agent) does exactly one thing:**
Judges whether a keyword candidate is genuinely relevant to the specific
target audience described in the ICP. It does this with understanding,
not string matching. It produces boolean relevance verdicts + short reasons.

**The AI never:**
- Computes, estimates, or modifies any number
- Sets volumes, scores, positions, or competition values
- Decides which sources to query or how to weight them

| Data type | Source | Ever from LLM? |
|---|---|---|
| Clicks, impressions, CTR, position | Google Search Console API | NO |
| Week-over-week deltas | Python arithmetic on two GSC windows | NO |
| Striking-distance extra-click estimates | `impressions * (benchmark_ctr - actual_ctr)` | NO |
| CTR outlier gaps | `impressions * (expected_ctr - actual_ctr)` | NO |
| Search volume | Google Ads KeywordPlanIdeaService API | NO |
| Competition index (0–100) | Google Ads API field `competitionIndex` | NO |
| Opportunity score | Deterministic formula in `research.py` | NO |
| Autocomplete suggestions | Google Suggest API — text only, no volume | NO |
| Search intent (primary) | Rule-based modifier table in `intent.py` | NO |
| Search intent (fallback) | AI curator fills in when rule-based returns "unknown" | YES (label only) |
| Recommendation text figures | Pulled from evidence fields in JSON | NO |
| **Keyword relevance judgment** | **AI curator sub-agent (`keyword-curator.md`)** | **YES (boolean + reason)** |

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

opportunity_score = min(volume_score + competition_score + gap_score, 100)
```

Note: ICP relevance is intentionally NOT a component of this formula.
Audience relevance is a judgment call best made by the AI curator (which
understands context), not by string-matching priority_topics tokens.
The only hard exclusion gate is `excluded_terms` (user's explicit opt-outs).

All three score inputs are pulled directly from API responses or computed
from them. No coefficient is chosen by the model; the formula is hardcoded
in Python and auditable in the source.

## AI Relevance Judgment Layer

The `keyword-curator` sub-agent (Haiku, read-only) receives the ICP + candidate
keywords and returns per-keyword verdicts `{relevant, reason, intent}`. These
are written to `<rundir>/keyword_relevance.json`.

`build_report_data.py` consumes this file:
- When present: keeps only `relevant: true` keywords; attaches `relevance_reason`
  to each; sets `keywords.relevance_reviewed = true`.
- When absent: passes all candidates through; sets `keywords.relevance_reviewed = false`
  and appends a note to `keywords.source_note`.

`recommend.py` does NOT emit keyword content recommendations when `relevance_reviewed`
is false, to avoid confidently recommending off-audience keywords.

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

3. **Intent classification is rule-based (primary).**
   `intent.py` uses regex pattern tables — no model inference.
   The AI curator may fill in intent only when the rule-based classifier
   returns "unknown" — and even then it outputs only a label string, never a number.

4. **GSC data is fetched, not constructed.**
   `fetch.py` calls the GSC Search Analytics API and writes raw JSON.
   The analysis modules read those files. No row is synthesized.

5. **demo.sh validates the pipeline deterministically.**
   The validation script asserts `opportunity_score` is numeric and that
   `source` is one of `gsc | ads | autocomplete`. It also verifies that
   the REVIEWED path sets `relevance_reviewed=True` and that no
   `relevant: false` keywords appear in `opportunities`.

6. **AI curator output is in keyword_relevance.json — isolated from numbers.**
   The curator's output schema contains only `keyword` (string), `relevant`
   (boolean), `reason` (string), and `intent` (enum string). It cannot
   produce or modify numeric fields. `build_report_data.py` never reads
   numeric values from `keyword_relevance.json`.
