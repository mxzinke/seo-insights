---
description: "Run the full SEO analysis pipeline — validates config, fetches GSC data, runs all analyses, and presents a prioritized action plan with the HTML report path."
---

# /seo-insights:analyze

You are running the full SEO Insights analysis pipeline. Follow these steps in order. Do not skip any gate — each check exists to prevent confusing errors.

---

## STEP 1 — Check prerequisites

### 1a. Check GSC credentials

Check whether `${CLAUDE_PLUGIN_ROOT}/config/gsc.env` exists and contains the four required keys:

`!bash ${CLAUDE_PLUGIN_ROOT}/scripts/check_setup.sh`

If credentials are missing or incomplete, stop and tell the user:

> "Your Google Search Console credentials aren't configured yet. Please run `/seo-insights:setup` first — I'll walk you through the whole process."

Do not proceed until credentials are confirmed.

### 1b. Check for a valid ICP

Look for ICP files in `${CLAUDE_PLUGIN_ROOT}/config/`:

`!ls ${CLAUDE_PLUGIN_ROOT}/config/icp.*.yaml 2>/dev/null || echo "NO_ICP_FILES"`

If no ICP files exist (output is `NO_ICP_FILES`), stop and tell the user:

> "No audience profile found. Please run `/seo-insights:define-audience` first — I'll interview you about your target audience, which makes the keyword scoring and content recommendations much more useful."

If one or more ICP files exist, and there is only one, use it. If there are multiple, ask the user which site they want to analyze.

Then validate the chosen ICP:

`!python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_icp.py ${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml`

If validation fails, point the user to `/seo-insights:define-audience` to fix it.

---

## STEP 2 — Run the pipeline

Once both prerequisites are confirmed, tell the user:

> "Everything looks good — starting the analysis now. This will fetch data from Google Search Console, run all the analysis modules, and generate your report. This usually takes 30–90 seconds."

Run:

`!bash ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh --icp ${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml`

(Replace `<domain>` with the actual domain from the ICP filename.)

If the pipeline exits with an error, read the error output carefully and explain what went wrong in plain language. Common issues:
- **Auth failure:** Suggest re-running `/seo-insights:setup` Step 9 to test the refresh token.
- **Network timeout:** Suggest retrying; GSC API is occasionally slow.
- **ICP error:** Point to `/seo-insights:define-audience`.

---

## STEP 3 — Read and present the action plan

After the pipeline completes, the report data is at:
`${CLAUDE_PLUGIN_ROOT}/data/<domain>/<today>/report_data.json`

Read it and present findings in this order.

### 3a. Headline KPIs

State the analysis period, then:
- **Total clicks** and **total impressions** for the period
- **Overall CTR** and **average position**
- If `summary.wow` is present: week-over-week deltas for clicks, impressions, and position — highlight whether things are improving or declining

Never invent or estimate these numbers. Quote them exactly from `summary` in the JSON.

### 3b. Top Priority Actions

Present the top 10 recommendations from `recommendations` (already sorted by priority descending).

For each recommendation:

```
[#rank] [Category] — Title
  Evidence: <evidence field>
  Action: <action field>
  Impact: <impact>/5  |  Effort: <effort>/5
```

Group by category for readability. Lead with `quick_win` and `ctr_optimization` items — they require the least effort for the most gain.

Quote numbers exactly from the JSON. For example: "The query 'example keyword' has 1,234 impressions at position 5.3 — optimizing this page's title and meta description could move it into top-3."

### 3c. Keyword opportunities summary

If `keywords.enabled` is true in the JSON, briefly summarize:
- How many keyword opportunities were found
- Whether AI relevance review was applied (`keywords.relevance_reviewed`)
- The top 3 by `opportunity_score` (keyword, intent, score, volume if available), with `relevance_reason` if present
- Note whether Ads data was used (from `keywords.source_note`)

If `relevance_reviewed` is false, note: "AI relevance review hasn't run yet — run `/seo-insights:keyword-research` for a fully audience-filtered list."

Tell the user they can run `/seo-insights:keyword-research` for a full keyword-focused breakdown with AI audience-relevance judgment.

### 3d. Report path

End with:

> "Your full interactive report is at:
> `<path to report.html>`
>
> Open it in your browser for charts, sortable tables, and the full analysis breakdown.
>
> **Tip:** Run this analysis again next week — the pipeline will automatically compare against this week's data for a week-over-week trend view."

---

## Important: numbers come from the pipeline

All metrics (clicks, impressions, positions, scores, volumes) come from the Python pipeline — they are deterministic and traceable to GSC raw data. Never paraphrase or round numbers differently from the JSON. Never estimate or invent metrics the pipeline didn't compute.
