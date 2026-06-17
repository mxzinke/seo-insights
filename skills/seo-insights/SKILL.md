---
name: seo-insights
description: >
  Run a deep, deterministic SEO analysis from Google Search Console data.
  Trigger this skill when the user asks to: analyze their SEO performance,
  audit Search Console data, find keyword opportunities, identify quick wins
  in GSC, generate an SEO report, check for keyword cannibalization, review
  CTR outliers, detect content decay, audit on-page issues, measure Core
  Web Vitals, or produce a prioritized SEO action plan. Also triggers on:
  "what should I work on for SEO", "which pages are losing traffic",
  "what keywords am I close to ranking for", "SEO week-over-week comparison",
  "Search Console analysis", "keyword research from GSC", "SEO insights",
  "improve my search rankings", "GSC data analysis", "organic traffic report".
---

# SEO Insights Skill

## Philosophy

Every number in the output is computed **deterministically in Python** from
raw data sources (Google Search Console, Google Ads API, rule-based
classifiers). No numbers are invented or estimated by an LLM. The LLM role
is narration only: reading `report_data.json` and presenting findings in
plain language. Never invent click counts, positions, volumes, scores, or
growth percentages — they must come from the JSON.

The output is a **prioritized action plan**, not a data dump. Lead with the
highest-priority recommendations and their GSC evidence. Bury raw tables in
the appendix.

See `DETERMINISM.md` for the formal guarantee and audit checklist.

> **Script location:** All Python scripts and shell scripts live at
> `${CLAUDE_PLUGIN_ROOT}/scripts/`. Config files are at
> `${CLAUDE_PLUGIN_ROOT}/config/`. Use `${CLAUDE_PLUGIN_ROOT}` as the base
> path when invoking any command below.

---

## STEP 0 — ICP Gate (mandatory, do not skip)

Before any keyword or content analysis, a valid Ideal Customer Profile (ICP)
must exist. The ICP defines who the site serves; without it, keyword scoring
and content recommendations are meaningless.

**Check:** Does `${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml` exist and pass validation?

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_icp.py ${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml
```

If the file is missing or validation fails, **interview the user** to fill it
in. Use `${CLAUDE_PLUGIN_ROOT}/config/icp.example.yaml` as the template. Ask specifically:

1. Who is the target audience? (role, company type, size)
2. Primary country and language?
3. Primary search intent (informational / commercial / transactional / mixed)?
4. What problem does the site solve (one sentence)?
5. What is the value proposition vs. competitors?
6. Who are the 2–5 main competitors (domains)?
7. What are the 5–10 core topic pillars?
8. What terms should be excluded (noise queries unrelated to the audience)?

Save the answers to `${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml`. Run `validate_icp.py` again.
Do not proceed to Step 1 until validation exits 0.

---

## STEP 1 — Ensure Authentication

Check that `${CLAUDE_PLUGIN_ROOT}/config/gsc.env` exists and contains valid credentials:

```
GSC_CLIENT_ID=...
GSC_CLIENT_SECRET=...
GSC_REFRESH_TOKEN=...
GSC_SITE_URL=sc-domain:example.com
```

If the refresh token has expired or `config/gsc.env` is missing, direct the
user to `${CLAUDE_PLUGIN_ROOT}/SETUP.md` for the OAuth setup flow, then run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/auth.py refresh
```

A successful refresh prints a short-lived `access_token=...` (no output from
this command means auth is OK; an error means the token is stale).

---

## STEP 2 — Run the Pipeline

Run the one-command pipeline. This is safe to run repeatedly; each run
creates a new dated directory (`${CLAUDE_PLUGIN_ROOT}/data/<domain>/<YYYY-MM-DD>/`).

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh --icp ${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml [--days 90] [--pagespeed-key <key>]
```

For demo mode (no credentials required):

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh --icp ${CLAUDE_PLUGIN_ROOT}/config/icp.example.yaml --demo
```

The script will print the path to the finished `report.html` on success.

What the pipeline does, in order:

1. **validate_icp** — confirms the ICP is complete (gate re-run for safety).
2. **fetch** — pulls the current 90-day window + the equal-length prior
   window from GSC into `data/<domain>/<date>/` and `data/<domain>/<date>/prior/`.
3. **build_report_data** — runs all analysis modules and emits `report_data.json`:
   - Striking-distance quick wins (positions 4–20, high impressions)
   - Keyword cannibalization (multiple pages competing for same query)
   - CTR outliers (actual CTR vs. position-curve expected CTR)
   - Content decay (pages/site losing clicks over the window)
   - On-page crawl (missing titles, thin content, meta issues)
   - Core Web Vitals (LCP / CLS / INP via PageSpeed Insights API)
   - Week-over-week comparison (current window vs. prior window)
   - **Keyword research** (see Step 2b below) — integrated into `report_data.json` as `keywords`.
4. **report** — renders `report.html` with a "Keyword Opportunities" section.

---

## STEP 2b — Keyword Research (requires valid ICP; no extra credentials needed for free layer)

Keyword research runs in **two phases**. This is the one place where the AI makes a judgment call — everything else is fully deterministic Python.

### Phase 1 — Deterministic pipeline (always runs)

`build_report_data.py` calls `research.py` to produce all candidates + all numbers:

**Three data sources, in order of richness:**

| Source | Credentials needed | Data provided |
|---|---|---|
| GSC opportunities | GSC only (always runs) | keywords we already rank for badly or with low CTR |
| Google Ads API | `GOOGLE_ADS_DEVELOPER_TOKEN` + `GOOGLE_ADS_CUSTOMER_ID` | avg monthly volume, competition index (0–100), 12-month trend |
| Google Autocomplete | none (best-effort) | keyword idea expansion — text only, no volume |

**Configuring Google Ads (optional):**

Add these keys to `config/gsc.env`:
```
GOOGLE_ADS_DEVELOPER_TOKEN=<your token>
GOOGLE_ADS_CUSTOMER_ID=<account id>
GOOGLE_ADS_LOGIN_CUSTOMER_ID=<manager id, if applicable>
```

The OAuth refresh token must also have `https://www.googleapis.com/auth/adwords` scope.
If absent, the pipeline runs in free mode (GSC + autocomplete) and marks volumes as
unavailable in the report.

**Opportunity score (deterministic, no LLM):**

```
opportunity_score = volume_score (40 pts)
                  + competition_score (25 pts)
                  + gap_score (25 pts)
```

All inputs come from API data or the rule-based classifier. See `DETERMINISM.md`.

The only hard exclusion gate is `excluded_terms` from the ICP (user's explicit opt-outs).
`priority_topics` are used only to seed keyword discovery — they are NOT used to
string-match-filter candidates. That filtering would miss context ("karte" in German
means both "map" and "card") and is done by the AI curator instead.

Each candidate in `keywords.json` has `relevance: null` and `relevance_reason: null`
until the AI curator pass runs.

### Phase 2 — AI relevance judgment (keyword-curator sub-agent)

**This is the only place the AI makes a content judgment in this plugin.**

When the user runs `/seo-keywords-research`, Claude:
1. Reads the ICP + candidate keywords from `keywords.json`
2. Delegates to the `keyword-curator` sub-agent (Haiku, read-only)
3. The curator returns per-keyword verdicts: `{relevant, reason, intent}`
4. Claude writes the verdicts to `<rundir>/keyword_relevance.json`
5. `build_report_data.py` re-runs to apply the filter

The curator judges relevance **with understanding**: a keyword can share words with the
site's topics but still be off-audience (e.g. a pokemon card query for a professional
map tool, even though "karte"/"ki" overlap). The curator never touches any number.

**Graceful fallback:**

When `keyword_relevance.json` is absent, `build_report_data.py` includes all candidates
and sets `keywords.relevance_reviewed = false`. The report shows a pending note.
`recommend.py` does NOT emit keyword content recommendations in the unreviewed state
(to avoid recommending off-audience keywords as confident actions).

**Demo mode:**

```bash
bash scripts/demo.sh   # exercises both UNREVIEWED and REVIEWED paths
```

The `keywords` key in `report_data.json` contains:
- `enabled` : bool
- `source_note` : which sources were active; includes pending note when unreviewed
- `relevance_reviewed` : bool — true only when keyword_relevance.json was applied
- `opportunities` : list sorted by `opportunity_score` desc
  - When reviewed: only `relevant: true` keywords; each has `relevance_reason`
  - When unreviewed: all candidates; `relevance: null`, `relevance_reason: null`

The HTML report shows a sortable/filterable **Keyword Opportunities** table
in its own section (accessible from the sticky nav under "Keywords"):
- When reviewed: AI `relevance_reason` appears as subtext on each keyword row
- When unreviewed: amber info note says "AI relevance review pending"

---

## STEP 3 — Read and Present the Action Plan

Read `report_data.json`:

```python
import json
data = json.load(open("${CLAUDE_PLUGIN_ROOT}/data/<domain>/<date>/report_data.json"))
recs = data["recommendations"]   # already sorted by priority (descending)
summary = data["summary"]        # clicks, impressions, ctr, position, wow deltas
```

Present findings to the user in this order:

### 1. Headline KPIs (from `summary`)

State the period, total clicks, impressions, overall CTR and average
position. If `summary.wow` is present, call out the week-over-week deltas
(+/- clicks, impressions, position) — highlight whether traffic is growing
or declining.

### 2. Top Priority Actions (from `recommendations[:10]`)

For each recommendation (sorted by `priority` desc):

```
[#rank] [category_label] — Title
  Evidence: <evidence field>
  Action: <action field>
  Impact: <impact>/5  |  Effort: <effort>/5
```

Group by category for readability. Lead with `quick_win` and
`ctr_optimization` items — they require the least effort for the most gain.

**Never paraphrase numbers.** Quote them exactly from the JSON.
For example: "The query 'example keyword' has 1,234 impressions at position
5.3 — moving it to top-3 could yield ~89 extra clicks per month."

### 3. Attach the HTML Report

Share the path to `report.html` so the user can open it in a browser for
the full interactive report (charts, appendix tables for all analyses).

---

## STEP 4 — Week-over-Week Note

Remind the user that the dated `data/<domain>/<date>/` directory is kept
locally. The next weekly run will automatically use the current window as
the "prior" baseline for WoW comparison, enabling trend tracking without
any additional configuration.

```
Next run (next week):
  bash ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh --icp ${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml
```

---

## Quick Reference

| Task | Command |
|---|---|
| Full pipeline (real data) | `bash ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh --icp ${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml` |
| Full pipeline (demo) | `bash ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh --icp ${CLAUDE_PLUGIN_ROOT}/config/icp.example.yaml --demo` |
| Validate ICP only | `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_icp.py ${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml` |
| Fetch data only | `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch.py --days 90` |
| Build report_data only | `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/build_report_data.py --data-dir ${CLAUDE_PLUGIN_ROOT}/data/<domain>/<date> --icp ${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml` |
| Keyword research only | `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/keywords/research.py --data-dir ${CLAUDE_PLUGIN_ROOT}/data/<domain>/<date> --icp ${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml --demo` |
| Render HTML only | `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/report.py ${CLAUDE_PLUGIN_ROOT}/data/<domain>/<date>/report_data.json` |
| OAuth consent URL | `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/auth.py consent --client-id <id>` |
| Exchange auth code | `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/auth.py exchange --client-id <id> --client-secret <s> --code <c>` |
| Refresh access token | `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/auth.py refresh` |
| Run demo pipeline | `bash ${CLAUDE_PLUGIN_ROOT}/scripts/demo.sh` |
