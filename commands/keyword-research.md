---
description: "Run or refresh the keyword research module and present the top keyword opportunities ranked by opportunity score, intent, volume, and competition."
---

# /seo-insights:keyword-research

You are running the keyword research module in isolation. This gives a focused view of keyword opportunities without re-running the full analysis pipeline.

---

## STEP 1 — Check prerequisites

### 1a. Check GSC credentials

`!bash ${CLAUDE_PLUGIN_ROOT}/scripts/check_setup.sh`

If credentials are missing, stop and direct the user to `/seo-insights:setup`.

### 1b. Find and validate the ICP

`!ls ${CLAUDE_PLUGIN_ROOT}/config/icp.*.yaml 2>/dev/null || echo "NO_ICP_FILES"`

If no ICP files exist, stop and tell the user:

> "Keyword scoring requires an audience profile. Please run `/seo-insights:define-audience` first so I know who you're targeting — this makes the opportunities far more relevant."

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

## STEP 2 — Run keyword research

Run the keyword research module against the most recent data directory:

`!python3 ${CLAUDE_PLUGIN_ROOT}/scripts/keywords/research.py --data-dir ${CLAUDE_PLUGIN_ROOT}/data/<domain>/<date> --icp ${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml`

(Replace `<domain>` and `<date>` with actual values.)

If you want to run in demo mode (no credentials needed, uses fixture data):

`!python3 ${CLAUDE_PLUGIN_ROOT}/scripts/keywords/research.py --data-dir ${CLAUDE_PLUGIN_ROOT}/data/<domain>/<date> --icp ${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml --demo`

---

## STEP 3 — Read and present keyword opportunities

Read `${CLAUDE_PLUGIN_ROOT}/data/<domain>/<date>/report_data.json` and look at the `keywords` section.

### Mode note

First tell the user which mode is active (from `keywords.source_note`):

- **Free mode** (GSC + Google Autocomplete): Keyword ideas come from your existing GSC queries and autocomplete expansion. Volume data shows as "unavailable" — great for direction, not precise volume.
- **Ads-enabled mode**: Full search volume, competition index, and 12-month trend data from the Google Ads API. Volumes are average monthly searches for the selected country/language.

To enable Ads mode, the user needs a Google Ads developer token with Basic access. See `/seo-insights:setup` Step 8, or read `${CLAUDE_PLUGIN_ROOT}/SETUP.md` for instructions.

### Top opportunities table

Present the top 20 opportunities from `keywords.opportunities` (sorted by `opportunity_score` descending).

Format as a clear table or list:

```
Rank | Keyword | Intent | Volume | Competition | Our Position | Score
1    | [keyword] | [intent] | [vol or "—"] | [Low/Med/High or "—"] | [pos or "not ranking"] | [score]/100
```

For each entry use the exact values from the JSON. Never invent or estimate volumes or scores.

Column explanations to give the user:
- **Intent:** `informational` (wants to learn), `commercial` (comparing options), `transactional` (ready to act), `navigational` (looking for a specific page)
- **Volume:** Average monthly searches (from Google Ads API when enabled; `—` in free mode)
- **Competition:** How many advertisers bid on this keyword — `Low`, `Medium`, `High` (Ads-enabled only)
- **Our Position:** Current average ranking in Google Search (from GSC). "not ranking" means the keyword was discovered but we have no GSC impression data yet.
- **Score:** Opportunity score 0–100, computed deterministically from volume, competition, ranking gap, and ICP relevance. Higher is better.

### Highlight top picks

After the table, highlight 3–5 standout opportunities with a sentence each explaining why they're worth prioritizing. Focus on:
- High score + high volume + low/medium competition
- Good ICP relevance (topic matches priority_topics)
- Keywords where the site ranks 5–20 (striking distance — small improvement = big click gains)

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
