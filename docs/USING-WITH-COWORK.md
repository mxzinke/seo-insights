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
This loads the skill, the `/seo-setup`, `/seo-audience`, `/seo-analyze`, and
`/seo-keywords` commands, the Haiku keyword-curator sub-agent, and a
session-start check.

## 3. Run the guided setup — `/seo-setup`

Type `/seo-setup`. Claude walks you through, step by step, and writes the config
files for you (you never hand-edit JSON):

- Creating a Google Cloud OAuth client and authorizing Search Console access.
- *(Optional)* enabling the Google Ads API + Developer Token for search volume.
- *(Optional)* adding a DataForSEO key for organic keyword difficulty.

Credentials are written to a local, git-ignored `config/gsc.env` on your
machine and never leave it.

## 4. Define your audience — `/seo-audience`

Type `/seo-audience`. Claude interviews you with a few targeted questions to
pin down your Ideal Customer Profile (who, country/language, intent, problem,
value proposition, competitors). **The audience must be 100 % clear** — it's
what makes keyword relevance meaningful. The result is saved as
`config/icp.<domain>.yaml`.

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

## 6. Keyword research — `/seo-keywords`

Type `/seo-keywords`. Claude gathers candidate keywords (Search Console +
Google Ads ideas + autocomplete), then the **Haiku keyword-curator sub-agent**
judges which are genuinely relevant to *your* audience (with understanding — not
string matching) and classifies intent. Only relevant keywords appear in the
report, each with a short reason. All numbers (volume, competition, scores) come
from the scripts — never invented by the model (see `DETERMINISM.md`).

---

## Where results live & weekly comparison

Every run writes a dated folder under `data/<domain>/<YYYY-MM-DD>/` in the
plugin's working directory on your machine:

```
data/example.com/2026-06-17/
  report.html          ← the interactive report
  report_data.json     ← the underlying data
  queries.json …       ← raw Search Console pulls
```

Because each run is its own dated folder, **running the analysis again next week
automatically produces a week-over-week comparison** — keep the folders and
Claude will diff against the most recent prior run. This is the "store last
week's results" mechanism: just don't delete the folders.

---

## Credentials & privacy

- `config/gsc.env` (Google + optional API keys) and `config/icp.*.yaml` are
  **git-ignored** and stay on your machine.
- The plugin only talks to Google's APIs (and DataForSEO, if you opt in). No
  data is sent to any third-party file host.

## Troubleshooting

- **"Plugin/Customize not available"** → you're in the browser or mobile. Use
  the **Claude Desktop app**.
- **Session-start nudge to run `/seo-setup`** → `config/gsc.env` is missing or
  incomplete. Run `/seo-setup`.
- **Search Console auth fails (403)** → the access token expired; re-run the
  auth step in `/seo-setup` (or `python3 scripts/auth.py refresh`).
- **Volumes show "n/a"** → no Google Ads Developer Token configured. That's the
  free mode; add the token via `/seo-setup` for real volume data.
