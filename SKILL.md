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
  "what keywords am I close to ranking for", "SEO week-over-week comparison".
---

# SEO Insights Skill

## Philosophy

Every number in the output is computed **deterministically in Python** from
raw Google Search Console data. No numbers are invented or estimated by an
LLM. The LLM role is narration only: reading `report_data.json` and
presenting findings in plain language. Never invent click counts, positions,
CTR values, or growth percentages — they must come from the JSON.

The output is a **prioritized action plan**, not a data dump. Lead with the
highest-priority recommendations and their GSC evidence. Bury raw tables in
the appendix.

---

## STEP 0 — ICP Gate (mandatory, do not skip)

Before any keyword or content analysis, a valid Ideal Customer Profile (ICP)
must exist. The ICP defines who the site serves; without it, keyword scoring
and content recommendations are meaningless.

**Check:** Does `config/icp.<domain>.yaml` exist and pass validation?

```bash
python3 scripts/validate_icp.py config/icp.<domain>.yaml
```

If the file is missing or validation fails, **interview the user** to fill it
in. Use `config/icp.example.yaml` as the template. Ask specifically:

1. Who is the target audience? (role, company type, size)
2. Primary country and language?
3. Primary search intent (informational / commercial / transactional / mixed)?
4. What problem does the site solve (one sentence)?
5. What is the value proposition vs. competitors?
6. Who are the 2–5 main competitors (domains)?
7. What are the 5–10 core topic pillars?
8. What terms should be excluded (noise queries unrelated to the audience)?

Save the answers to `config/icp.<domain>.yaml`. Run `validate_icp.py` again.
Do not proceed to Step 1 until validation exits 0.

---

## STEP 1 — Ensure Authentication

Check that `config/gsc.env` exists and contains valid credentials:

```
GSC_CLIENT_ID=...
GSC_CLIENT_SECRET=...
GSC_REFRESH_TOKEN=...
GSC_SITE_URL=sc-domain:example.com
```

If the refresh token has expired or `config/gsc.env` is missing, direct the
user to `SETUP.md` for the OAuth setup flow, then run:

```bash
python3 scripts/auth.py refresh
```

A successful refresh prints a short-lived `access_token=...` (no output from
this command means auth is OK; an error means the token is stale).

---

## STEP 2 — Run the Pipeline

Run the one-command pipeline. This is safe to run repeatedly; each run
creates a new dated directory (`data/<domain>/<YYYY-MM-DD>/`).

```bash
bash scripts/run.sh --icp config/icp.<domain>.yaml [--days 90] [--pagespeed-key <key>]
```

For demo mode (no credentials required):

```bash
bash scripts/run.sh --icp config/icp.example.yaml --demo
```

The script will print the path to the finished `report.html` on success.

What the pipeline does, in order:

1. **validate_icp** — confirms the ICP is complete (gate re-run for safety).
2. **fetch** — pulls the current 90-day window + the equal-length prior
   window from GSC into `data/<domain>/<date>/` and `data/<domain>/<date>/prior/`.
3. **build_report_data** — runs 7 analysis modules and emits `report_data.json`:
   - Striking-distance quick wins (positions 4–20, high impressions)
   - Keyword cannibalization (multiple pages competing for same query)
   - CTR outliers (actual CTR vs. position-curve expected CTR)
   - Content decay (pages/site losing clicks over the window)
   - On-page crawl (missing titles, thin content, meta issues)
   - Core Web Vitals (LCP / CLS / INP via PageSpeed Insights API)
   - Week-over-week comparison (current window vs. prior window)
4. **report** — renders `report.html` (self-contained, offline-readable).

---

## STEP 3 — Read and Present the Action Plan

Read `report_data.json`:

```python
import json
data = json.load(open("data/<domain>/<date>/report_data.json"))
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
  bash scripts/run.sh --icp config/icp.<domain>.yaml
```

---

## Quick Reference

| Task | Command |
|---|---|
| Full pipeline (real data) | `bash scripts/run.sh --icp config/icp.<domain>.yaml` |
| Full pipeline (demo) | `bash scripts/run.sh --icp config/icp.example.yaml --demo` |
| Validate ICP only | `python3 scripts/validate_icp.py config/icp.<domain>.yaml` |
| Fetch data only | `python3 scripts/fetch.py --days 90` |
| Build report_data only | `python3 scripts/build_report_data.py --data-dir data/<domain>/<date>` |
| Render HTML only | `python3 scripts/report.py data/<domain>/<date>/report_data.json` |
| OAuth consent URL | `python3 scripts/auth.py consent --client-id <id>` |
| Exchange auth code | `python3 scripts/auth.py exchange --client-id <id> --client-secret <s> --code <c>` |
| Refresh access token | `python3 scripts/auth.py refresh` |
| Run demo pipeline | `bash scripts/demo.sh` |
