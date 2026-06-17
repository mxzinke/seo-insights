---
description: "Run or refresh the keyword research module, apply AI audience-relevance judgment via the keyword-curator sub-agent, and present the top AI-filtered keyword opportunities ranked by opportunity score, intent, volume, and competition."
---

# /seo-keywords

You are running the keyword research module in isolation. This gives a focused view of keyword opportunities without re-running the full analysis pipeline.

**Two-phase design:**
1. **Deterministic pipeline** — Python scripts produce all candidates + all numbers (scores, volumes, positions). No AI judgment in this phase.
2. **AI relevance pass** — the `keyword-curator` sub-agent judges which candidates are genuinely relevant to the ICP audience (with understanding, not string matching). Numbers are never touched in this phase.

---

## STEP 1 — Check prerequisites

### 1a. Check GSC credentials

`!bash ${CLAUDE_PLUGIN_ROOT}/scripts/check_setup.sh`

If credentials are missing, stop and direct the user to `/seo-setup`.

### 1b. Find and validate the ICP

`!ls ${CLAUDE_PLUGIN_ROOT}/config/icp.*.yaml 2>/dev/null || echo "NO_ICP_FILES"`

If no ICP files exist, stop and tell the user:

> "Keyword scoring requires an audience profile. Please run `/seo-audience` first so I know who you're targeting — this makes the opportunities far more relevant."

If multiple ICPs exist, ask which site to use. Then validate:

`!python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_icp.py ${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml`

### 1c. Find existing data

Check whether there is already a data directory from a recent run:

`!ls ${CLAUDE_PLUGIN_ROOT}/data/<domain>/ 2>/dev/null | sort | tail -5 || echo "NO_DATA"`

If data exists, use the most recent dated directory. If no data exists, tell the user:

> "No GSC data found yet. I'll run a quick fetch first to get your Search Console data."

Then fetch data:

`!python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch.py --days 90`

---

## STEP 2 — Run keyword research (deterministic phase)

Run the keyword research module against the most recent data directory:

`!python3 ${CLAUDE_PLUGIN_ROOT}/scripts/keywords/research.py --data-dir ${CLAUDE_PLUGIN_ROOT}/data/<domain>/<date> --icp ${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml`

(Replace `<domain>` and `<date>` with actual values.)

This produces `keywords.json` in the run directory. Each candidate has:
- All numbers computed deterministically: `opportunity_score`, `search_volume`, `competition_index`, `our_current_position`
- `relevance: null` and `relevance_reason: null` — unjudged until the AI pass runs
- Hard exclusions: any term matching `excluded_terms` in the ICP is blocked before scoring

---

## STEP 3 — AI relevance pass (keyword-curator sub-agent)

Read `${CLAUDE_PLUGIN_ROOT}/data/<domain>/<date>/keywords.json` to get the candidate list.

Also read the ICP at `${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml`.

Now delegate the relevance + intent judgment to the `keyword-curator` sub-agent. Send it:

```json
{
  "icp": {
    "audience": "<from ICP>",
    "problem_solved": "<from ICP>",
    "value_proposition": "<from ICP>",
    "country": "<from ICP>",
    "language": "<from ICP>",
    "search_intent": "<from ICP>",
    "priority_topics": ["<from ICP>"]
  },
  "keywords": [
    {"keyword": "<candidate 1>"},
    {"keyword": "<candidate 2>"},
    ...
  ]
}
```

The sub-agent returns a JSON array with `{keyword, relevant, reason, intent}` per keyword. It does NOT touch any numbers.

Write the verdict array to `${CLAUDE_PLUGIN_ROOT}/data/<domain>/<date>/keyword_relevance.json`.

Important: the curator judges relevance with understanding, not string matching. A keyword can share words with the site's topics but still be off-audience (e.g. "pokemon karte mit ki erstellen" for a professional map tool — "karte" and "ki" overlap but the searcher wants pokemon cards, not maps).

---

## STEP 4 — Rebuild report with AI verdicts

Re-run `build_report_data.py` so it picks up `keyword_relevance.json` and applies the AI filter:

`!python3 ${CLAUDE_PLUGIN_ROOT}/scripts/build_report_data.py --data-dir ${CLAUDE_PLUGIN_ROOT}/data/<domain>/<date> --icp ${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml`

Then re-render the report:

`!python3 ${CLAUDE_PLUGIN_ROOT}/scripts/report.py ${CLAUDE_PLUGIN_ROOT}/data/<domain>/<date>/report_data.json`

The rebuilt report will have `keywords.relevance_reviewed = true` and only show AI-approved opportunities.

---

## STEP 5 — Read and present keyword opportunities

Read `${CLAUDE_PLUGIN_ROOT}/data/<domain>/<date>/report_data.json` and look at the `keywords` section.

### Mode note

First tell the user which mode is active (from `keywords.source_note`):

- **Free mode** (GSC + Google Autocomplete): Keyword ideas come from your existing GSC queries and autocomplete expansion. Volume data shows as "unavailable" — great for direction, not precise volume.
- **Ads-enabled mode**: Full search volume, competition index, and 12-month trend data from the Google Ads API. Volumes are average monthly searches for the selected country/language.

Also confirm that `keywords.relevance_reviewed` is `true` (it should be after STEP 4).

### Top opportunities table

Present the top 20 opportunities from `keywords.opportunities` (sorted by `opportunity_score` descending). These have already been filtered to `relevant: true` by the AI curator.

Format as a clear table:

```
Rank | Keyword | Intent | Volume | Competition | Our Position | Score | Relevance note
1    | [keyword] | [intent] | [vol or "—"] | [Low/Med/High or "—"] | [pos or "not ranking"] | [score]/100 | [relevance_reason]
```

For each entry use the exact values from the JSON. Never invent or estimate volumes or scores.

Column explanations to give the user:
- **Intent:** `informational` (wants to learn), `commercial` (comparing options), `transactional` (ready to act), `navigational` (looking for a specific page). Rule-based classifier; AI intent used when rule-based returned "unknown".
- **Volume:** Average monthly searches (from Google Ads API when enabled; `—` in free mode)
- **Competition:** How many advertisers bid on this keyword — `Low`, `Medium`, `High` (Ads-enabled only)
- **Our Position:** Current average ranking in Google Search (from GSC). "not ranking" means the keyword was discovered but we have no GSC impression data yet.
- **Score:** Opportunity score 0–100, computed deterministically from volume, competition, and ranking gap. Higher is better. (ICP string-matching is NOT used in this score — audience relevance is judged by the AI curator.)
- **Relevance note:** The AI curator's one-sentence reason for including this keyword.

### Highlight top picks

After the table, highlight 3–5 standout opportunities with a sentence each explaining why they're worth prioritizing. Focus on:
- High score + high volume + low/medium competition
- Keywords where the site ranks 5–20 (striking distance — small improvement = big click gains)
- Include the AI curator's relevance reason to explain why each pick fits the audience

### Discovery tips

End with:

> "Want to find even more keyword ideas? Try these free Google tools:
> - **Google Keyword Planner** (inside Google Ads) for volume data and related ideas
> - **Google Trends** for spotting rising/seasonal terms before competitors do
>
> Ask me 'show me how to use Keyword Planner' or 'how do I find trending topics in Google Trends' and I'll walk you through it step by step."

(These tools are covered in detail in the keyword discovery guide — you can read it at `${CLAUDE_PLUGIN_ROOT}/skills/seo-insights/references/keyword-discovery-guide.md` if you want full context before explaining.)

---

## Important

All keyword scores, volumes, and positions come from the Python pipeline — they are deterministic computations from GSC and API data. Never invent, round differently, or estimate any metric that isn't present in the JSON.

The AI curator (keyword-curator sub-agent) only judges RELEVANCE and INTENT — it never produces or modifies any numeric value. The `opportunity_score` in the JSON is always from the Python pipeline.
