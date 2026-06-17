# Using SEO Insights in Claude Cowork

This guide shows how to install and run the **SEO Insights** plugin inside
**Claude Cowork** (Anthropic's agentic workspace). For Claude Code, see the
README instead — the analysis engine is identical; only the install and
"where Claude runs" differ.

> **In one line:** add this repo as a personal marketplace in Cowork, install
> the plugin, run `/seo-setup`, then `/seo-analyze`. Claude does the rest and hands you
> an interactive HTML report.

---

## Prerequisites

- **Claude Cowork** on a paid plan (the plugins/Customize features run in the
  **Claude Desktop app** — Cowork's customize session edits files on your
  machine, so it isn't available in the browser or mobile).
- **Python 3.10+** available on your machine (`python3 --version`). The plugin's
  analysis is done by deterministic Python scripts that Claude runs for you.
- A **Google account** that has the site verified in **Google Search Console**.
- *(Optional)* a **Google Ads Developer Token** for real search-volume data, and
  a **DataForSEO** key for organic keyword difficulty — both are optional; the
  plugin works without them (see README → free vs. paid layers).

> ### ⚠️ Network access (read this first)
> Cowork's code-execution sandbox blocks outbound traffic to non-allowlisted
> domains via an egress proxy. This plugin **must** reach Google's APIs
> (`oauth2.googleapis.com`, `accounts.google.com`, `www.googleapis.com`,
> `googleads.googleapis.com`). Before setup, an org admin must enable
> **Organization → Capabilities → Code execution → Allow network egress** and
> set it to **All domains**, then **restart Claude Desktop / start a fresh
> session**. (Due to current Cowork bugs the "Additional allowed domains" list is
> ignored unless the mode is "All domains".) `/seo-setup` covers this as Step 0.
> If you can't change org settings, run the analysis in **Claude Code** instead,
> which has no egress sandbox. A 403 `blocked-by-allowlist` error means this
> isn't configured.

---

## 1. Add this repo as a personal marketplace

1. In Cowork, open the **Cowork** tab, then open **Customize**.
2. Go to the **Plugins** tab.
3. Under **Personal plugins**, click **`+`** → **Add marketplace**.
4. Choose **Add from a repository** and enter:
   ```
   mxzinke/seo-insights
   ```
   (a GitHub `owner/repo` shorthand; a full git URL works too).

Cowork reads `.claude-plugin/marketplace.json` from the repo and registers the
marketplace. Personal plugins you add this way are saved locally on your
computer.

## 2. Install the plugin

In the same **Plugins** view, find **SEO Insights** and click **Install**.
This loads the skill, the `/seo-setup`, `/define-seo-audience`, `/seo-analyze`, and
`/seo-keywords-research` commands, the Haiku keyword-curator sub-agent, and a
session-start check.

## 3. Run the guided setup — `/seo-setup`

Type `/seo-setup`. Claude walks you through, step by step, and writes the config
files for you (you never hand-edit JSON):

- **Choosing a persistent workspace folder** on your Mac (e.g. `~/seo-insights`)
  where credentials and reports will live across sessions — this is Step 0.5 of
  the wizard and is essential in Cowork.
- Creating a Google Cloud OAuth client and authorizing Search Console access.
- *(Optional)* enabling the Google Ads API + Developer Token for search volume.
- *(Optional)* adding a DataForSEO key for organic keyword difficulty.

Credentials are written to `<workspace>/config/gsc.env` — a folder on your Mac
that survives Cowork session resets. They are never committed to any repository.

## 4. Define your audience — `/define-seo-audience`

Type `/define-seo-audience`. Claude interviews you with a few targeted questions to
pin down your Ideal Customer Profile (who, country/language, intent, problem,
value proposition, competitors). **The audience must be 100 % clear** — it's
what makes keyword relevance meaningful. The result is saved to your persistent
workspace at `<workspace>/config/icp.<domain>.yaml`.

## 5. Run the analysis — `/seo-analyze`

Type `/seo-analyze` (or just ask: *"run the weekly SEO analysis for example.com"*).
Claude:

1. Pulls Search Console data and runs all deterministic analyses
   (striking-distance, cannibalization, CTR outliers, content decay, on-page,
   Core Web Vitals, week-over-week).
2. Builds the **interactive HTML report** and presents the prioritized action
   plan in chat, leading with the highest-impact items.

Open the generated `report.html` in your browser for the full interactive
cockpit (sortable tables, charts, keyword opportunities).

## 6. Keyword research — `/seo-keywords-research`

Type `/seo-keywords-research`. Claude gathers candidate keywords (Search Console +
Google Ads ideas + autocomplete), then the **Haiku keyword-curator sub-agent**
judges which are genuinely relevant to *your* audience (with understanding — not
string matching) and classifies intent. Only relevant keywords appear in the
report, each with a short reason. All numbers (volume, competition, scores) come
from the scripts — never invented by the model (see `DETERMINISM.md`).

---

## Where results live & weekly comparison

Every run writes a dated folder inside your **persistent workspace** — the
folder you chose in `/seo-setup` Step 0.5 (e.g. `~/seo-insights`):

```
~/seo-insights/
  config/
    gsc.env                    ← your GSC credentials (one-time setup)
    icp.<domain>.yaml          ← your audience profile
  data/
    example.com/
      2026-06-17/
        report.html            ← the interactive report
        report_data.json       ← the underlying data
        queries.json …         ← raw Search Console pulls
```

The workspace folder is chosen **once** during `/seo-setup` and remembered via a
tiny pointer file at `~/.seo-insights/home`. Every future Cowork session — even
after Claude Desktop restarts — reads that pointer and writes to the same folder
automatically. You can also override the workspace location at any time by
setting the `SEO_INSIGHTS_HOME` environment variable.

Because each run is its own dated folder, **running the analysis again next week
automatically produces a week-over-week comparison** — keep the folders and
Claude will diff against the most recent prior run. This is the "store last
week's results" mechanism: just don't delete the workspace folder.

---

## Credentials & privacy

- `<workspace>/config/gsc.env` (Google + optional API keys) and
  `<workspace>/config/icp.*.yaml` are stored in your personal workspace folder
  on your Mac — they are **never** inside the plugin directory or any git
  repository, and never leave your machine.
- The plugin only talks to Google's APIs (and DataForSEO, if you opt in). No
  data is sent to any third-party file host.

## Troubleshooting

- **"Plugin/Customize not available"** → you're in the browser or mobile. Use
  the **Claude Desktop app**.
- **Session-start nudge to run `/seo-setup`** → `gsc.env` is missing or
  incomplete in your persistent workspace. Run `/seo-setup` (Step 0.5 will
  re-establish the workspace if needed).
- **Search Console auth fails (403)** → the access token expired; re-run the
  auth step in `/seo-setup` (or `python3 scripts/auth.py refresh`).
- **Volumes show "n/a"** → no Google Ads Developer Token configured. That's the
  free mode; add the token via `/seo-setup` for real volume data.
