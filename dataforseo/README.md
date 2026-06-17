# DataForSEO Integration — Opt-In Toolkit

> **This module is completely isolated from the default pipeline.**
> `run.sh`, `build_report_data.py`, and all `scripts/analyze/` modules are
> unmodified and will never import anything from `dataforseo/`.
> This toolkit only runs when you explicitly invoke a `cli_*.py` script
> **and** provide a DataForSEO API key.

---

## Why DataForSEO?

Our free Google-based pipeline (GSC + Google Ads) covers clicks, impressions,
CTR, and basic keyword volume — but has three critical blind spots:

| Gap | DataForSEO fills it with |
|-----|--------------------------|
| Organic keyword **difficulty** (0–100) | `cli_labs_keyword_difficulty.py` |
| API-level **search intent** classification | `cli_labs_search_intent.py` |
| **SERP scraping** (Google, Bing, Maps, AI Mode) | `cli_serp_*.py` |
| **Backlink** analysis | `cli_backlinks.py` |
| Deep **on-page crawl** (incl. JS rendering) | `cli_onpage.py` |

---

## Auth Setup

**Step 1:** Register at <https://app.dataforseo.com/register>

**Step 2:** Top up your account (**$50 minimum required** to activate API access).

**Step 3:** Your login is your registration email. Get your API password at  
<https://app.dataforseo.com/api-access>

**Step 4:** Create `dataforseo/.dataforseo.env` (already gitignored):

```bash
cp dataforseo/.dataforseo.env.example dataforseo/.dataforseo.env
# then edit the file and fill in your credentials
```

Or export as environment variables:

```bash
export DATAFORSEO_LOGIN=your@email.com
export DATAFORSEO_PASSWORD=your_api_password
```

The client tries env vars first, then the `.dataforseo.env` file. If neither
is found, it prints a clear error with setup instructions and does not crash
any other part of the pipeline.

---

## Quick Start (no API key needed)

Every CLI has a `--demo` flag that loads bundled fixture data:

```bash
python dataforseo/cli_serp_google_organic.py --demo
python dataforseo/cli_labs_keyword_difficulty.py --demo
python dataforseo/cli_labs_search_intent.py --demo
python dataforseo/cli_labs_keyword_ideas.py --demo
python dataforseo/cli_labs_ranked_keywords.py --demo
python dataforseo/cli_serp_google_maps.py --demo
python dataforseo/cli_serp_google_ai_mode.py --demo
python dataforseo/cli_serp_bing_organic.py --demo
python dataforseo/cli_keywords_search_volume.py --demo
python dataforseo/cli_backlinks.py --demo
python dataforseo/cli_onpage.py --demo
```

---

## Async vs. Live

DataForSEO offers two patterns (owner note: *"DataForSEO ist async API"*):

### Async (default for SERP/On-Page)
```
POST /v3/<endpoint>/task_post     → returns task ID(s)
GET  /v3/tasks_ready              → poll until your task ID appears
GET  /v3/<endpoint>/task_get/advanced/{id} → fetch results
```
- Cheaper (~$0.0006/query for SERP organic)
- Takes seconds to minutes
- Supports `postback_url` / `pingback_url` for webhook-style notification
  (add to your payload dict: `{"keyword": "...", "postback_url": "https://..."}`)

### Live (synchronous)
```
POST /v3/<endpoint>/live/advanced  → immediate response
```
- 2–3× more expensive
- Results in one HTTP call
- Use `--live` flag in the CLIs

The `client.py` provides:
- `run_live(endpoint, payload)` — for live endpoints
- `run_task(post_endpoint, payload, ...)` — full async lifecycle (post → poll → fetch)
- `task_post()`, `tasks_ready()`, `task_get()` — low-level async primitives

---

## German Defaults

All CLIs default to **Germany**: `location_code=2276`, `language_code="de"`.

Override per CLI:
```bash
python dataforseo/cli_serp_google_organic.py \
  --keyword "seo tools" \
  --location-code 2840 \   # USA
  --language-code en
```

Full location/language list: <https://docs.dataforseo.com/v3/appendix/language_list/>

---

## API Cost Table

| API Family | Endpoint | Pattern | Cost per Call | Notes |
|---|---|---|---|---|
| SERP Google Organic | `/serp/google/organic` | async | **$0.0006**/query | Standard; +$0.0006 for AI Overview |
| SERP Google Organic | `/serp/google/organic/live/advanced` | live | **$0.002**/query | Priority async: $0.0012 |
| SERP Google Maps | `/serp/google/maps` | async/live | **$0.0006**/query | Local pack / business listings |
| SERP Google AI Mode | `/serp/google/ai_mode` | async/live | **$0.0012**/query | ~2× organic cost |
| SERP Bing Organic | `/serp/bing/organic` | async/live | **$0.0006**/query | Same as Google standard |
| Keywords Search Volume | `/keywords_data/google_ads/search_volume/live` | live | **$0.0004**/keyword | Volume, CPC, competition |
| Labs Keyword Difficulty | `/dataforseo_labs/google/bulk_keyword_difficulty/live` | live | **$0.001**/task + **$0.0001**/kw | Up to 1000 kw/task |
| Labs Search Intent | `/dataforseo_labs/google/search_intent/live` | live | **~$0.001**/task + **$0.0001**/kw | Similar to difficulty |
| Labs Keyword Ideas | `/dataforseo_labs/google/keyword_ideas/live` | live | **~$0.001**/task | Incl. difficulty + intent |
| Labs Ranked Keywords | `/dataforseo_labs/google/ranked_keywords/live` | live | **$0.01**/task + **$0.0001**/item | First 100 items ~$0.02 |
| Backlinks Summary | `/backlinks/summary/live` | live | **$0.02**/request | Requires $100/mo min plan |
| Backlinks Referring Domains | `/backlinks/referring_domains/live` | live | **$0.02**/req + **$0.00003**/row | Requires $100/mo min plan |
| On-Page Crawl | `/on_page/task_post` | async | **$0.000125**/page | +JS/Lighthouse surcharges |

**Account minimums:**
- General API access: **$50** minimum top-up to activate
- Backlinks API: **$100/month** minimum spend (separate requirement)
- Rate limits: **2000 calls/minute**, max **30 concurrent** tasks

**Example costs:**
- 100 SERP queries (organic, standard async): $0.06
- 1000 keyword difficulty scores: $0.11
- Backlink summary for one domain: $0.02
- Crawling 50 pages on-page: $0.00625

---

## API Families Detail

### 1. SERP Google Organic — `cli_serp_google_organic.py`

**Endpoint:** `/serp/google/organic`  
**Pattern:** async (default) or live (`--live`)  
**What it returns:** Organic results, SERP features (featured snippets, PAA, knowledge graph), People Also Ask questions, related searches, AI Overview text  
**Key params:**
- `keyword` — the search query
- `depth` — number of results (1–700)
- `device` — `desktop` | `mobile`
- `load_async_ai_overview` — `true` to capture Google AI Overview content
- `location_code` — 2276 (DE default)
- `language_code` — `de` (default)

**When to use:** Competitor SERP analysis, featured snippet opportunities, PAA content ideas, AI Overview presence check.

Docs: <https://docs.dataforseo.com/v3/serp/google/organic/overview/>

---

### 2. SERP Google Maps — `cli_serp_google_maps.py`

**Endpoint:** `/serp/google/maps`  
**Pattern:** async or live  
**What it returns:** Local pack business listings — name, address, phone, categories, rating + review count, claimed status  
**Key params:** `keyword`, `location_code`, `language_code`, `depth`  
**When to use:** Local SEO analysis, competitor local pack presence, Google Business Profile benchmarking.

Docs: <https://docs.dataforseo.com/v3/serp/google/maps/overview/>

---

### 3. SERP Google AI Mode — `cli_serp_google_ai_mode.py`

**Endpoint:** `/serp/google/ai_mode`  
**Pattern:** async or live  
**What it returns:** Google AI Mode SERP — the AI-first search experience. Returns AI-generated response text, cited sources, and organic results shown alongside AI content.  
**Cost:** ~2× standard organic  
**When to use:** Understanding AI Mode visibility, which domains get cited in AI responses, new content opportunities for AI-targeted queries.

Docs: <https://docs.dataforseo.com/v3/serp/google/ai_mode/overview/>

---

### 4. SERP Bing Organic — `cli_serp_bing_organic.py`

**Endpoint:** `/serp/bing/organic`  
**Pattern:** async or live  
**What it returns:** Organic results from Bing SERP  
**Key params:** `keyword`, `depth`, `device`, `location_code`, `language_code`  
**When to use:** Cross-engine ranking comparison, audiences on Microsoft/Windows platforms, B2B SEO (Bing has higher B2B demographic share).

Docs: <https://docs.dataforseo.com/v3/serp/bing/organic/overview/>

---

### 5. Keywords Search Volume — `cli_keywords_search_volume.py`

**Endpoint:** `/keywords_data/google_ads/search_volume/live`  
**Pattern:** live only  
**What it returns:** Monthly search volume, CPC (low/high bid), competition level and index, 12-month trend data — from Google Ads API (DataForSEO as proxy)  
**Key params:** `keywords` (list, max 700), `location_code`, `language_code`  
**Cost:** $0.0004/keyword  
**When to use:** Validating keyword volumes before content production, CPC benchmarks for paid vs. organic decision, trend analysis.

Docs: <https://docs.dataforseo.com/v3/keywords_data/google_ads/search_volume/overview/>

---

### 6. Labs Keyword Difficulty — `cli_labs_keyword_difficulty.py`

**Endpoint:** `/dataforseo_labs/google/bulk_keyword_difficulty/live`  
**Pattern:** live  
**What it returns:** Organic keyword difficulty score (0–100) per keyword, plus volume, CPC, competition level  
**Key params:** `keywords` (list, max 1000), `location_code`, `language_code`  
**Cost:** $0.001/task + $0.0001/keyword  
**THE key gap-filler:** Neither GSC nor Google Ads provides organic difficulty. This is the single most important DataForSEO endpoint for prioritising content opportunities.

Score interpretation:
- 0–19: Very Easy — a new site can rank
- 20–39: Easy — some authority needed
- 40–54: Medium — established domain needed
- 55–69: Hard — strong domain + quality content
- 70–84: Very Hard — top-tier authority
- 85–100: Extremely Hard — industry leaders only

Docs: <https://docs.dataforseo.com/v3/dataforseo_labs/google/bulk_keyword_difficulty/overview/>

---

### 7. Labs Search Intent — `cli_labs_search_intent.py`

**Endpoint:** `/dataforseo_labs/google/search_intent/live`  
**Pattern:** live  
**What it returns:** Intent classification per keyword — `informational`, `navigational`, `commercial`, `transactional` — with probability scores and secondary intents  
**Key params:** `keywords` (list, max 1000), `location_code`, `language_code`  
**When to use:** Content planning (match intent to content type), prioritising commercial/transactional keywords for conversion pages, validating ICP-alignment.

Docs: <https://docs.dataforseo.com/v3/dataforseo_labs/google/search_intent/overview/>

---

### 8. Labs Keyword Ideas — `cli_labs_keyword_ideas.py`

**Endpoint:** `/dataforseo_labs/google/keyword_ideas/live`  
**Pattern:** live  
**What it returns:** Keyword ideas related to seed keywords, each enriched with difficulty score, search intent, volume, CPC, and competition — all in one call  
**Key params:** `keywords` (seed list), `limit`, `location_code`, `language_code`  
**When to use:** Content ideation sessions, finding low-difficulty variants of target keywords, building topical clusters.

Docs: <https://docs.dataforseo.com/v3/dataforseo_labs/google/keyword_ideas/overview/>

---

### 9. Labs Ranked Keywords — `cli_labs_ranked_keywords.py`

**Endpoint:** `/dataforseo_labs/google/ranked_keywords/live`  
**Pattern:** live  
**What it returns:** All Google organic rankings for a domain — keyword, position, ranking URL, estimated traffic value (ETV), volume, CPC  
**Key params:** `target` (domain), `limit` (max 1000), `offset`, `location_code`, `language_code`  
**Cost:** $0.01/task + $0.0001/item  
**When to use:** Competitor keyword gap analysis, discover all keywords you already rank for beyond what GSC shows (GSC caps at ~1000 queries), find pages losing rankings.

Docs: <https://docs.dataforseo.com/v3/dataforseo_labs/google/ranked_keywords/overview/>

---

### 10. Backlinks — `cli_backlinks.py`

**Endpoint:** `/backlinks/summary/live` + `/backlinks/referring_domains/live`  
**Pattern:** live  
**What it returns:**
- Summary: domain rank, total backlinks, referring domains, IPs, dofollow ratio, broken links
- Referring domains: per-domain breakdown with rank, link count, spam score

**Key params:** `target` (domain), `include_subdomains`, `limit`  
**Cost:** $0.02/request + $0.00003/row for referring domains  
**IMPORTANT:** Requires $100/month minimum spend on the Backlinks plan (separate from standard $50 account top-up).  
**When to use:** Link building opportunity identification, competitor backlink profile analysis, anchor text audits, toxic link identification.

Docs: <https://docs.dataforseo.com/v3/backlinks/overview/>

---

### 11. On-Page — `cli_onpage.py`

**Endpoint:** `/on_page/task_post` (async)  
**Pattern:** async only (crawl takes 1–5 minutes)  
**What it returns:** Page-by-page SEO audit — meta tags, headings, word count, internal/external links, images with/without alt, Core Web Vitals (if JS enabled), SEO checks (canonical, robots, sitemap, SSL, duplicate meta)  
**Key params:** `target` (domain), `max_crawl_pages`, `enable_javascript`, `enable_lighthouse`, `load_resources`  
**Cost:** $0.000125/page base; JS rendering + Lighthouse add extra cost  
**Note:** This can deepen our existing `scripts/analyze/onpage_crawl.py` — but operates fully independently. It does NOT connect to or import from the main pipeline.  
**When to use:** Deep technical SEO audit, JS-rendered site crawling, Lighthouse performance scoring at scale.

Docs: <https://docs.dataforseo.com/v3/on_page/overview/>

---

## File Structure

```
dataforseo/
├── __init__.py                      # package marker (not imported by main pipeline)
├── client.py                        # shared REST client: auth, run_live, run_task
├── _common.py                       # shared CLI helpers (argparse, table printing)
├── cli_serp_google_organic.py       # Google organic SERP + AI Overview
├── cli_serp_google_maps.py          # Google Maps / local pack
├── cli_serp_google_ai_mode.py       # Google AI Mode results
├── cli_serp_bing_organic.py         # Bing organic SERP
├── cli_keywords_search_volume.py    # Google Ads search volume + CPC
├── cli_labs_keyword_difficulty.py   # Bulk keyword difficulty (0-100)
├── cli_labs_search_intent.py        # Search intent classification
├── cli_labs_keyword_ideas.py        # Keyword ideas with difficulty + intent
├── cli_labs_ranked_keywords.py      # All keywords a domain ranks for
├── cli_backlinks.py                 # Backlink summary + referring domains
├── cli_onpage.py                    # On-page crawl (async)
├── .dataforseo.env.example          # Credential template (copy to .dataforseo.env)
├── README.md                        # This file
└── fixtures/
    ├── serp_google_organic.json     # Demo fixture for --demo
    ├── serp_google_maps.json
    ├── serp_google_ai_mode.json
    ├── serp_bing_organic.json
    ├── keywords_search_volume.json
    ├── labs_keyword_difficulty.json
    ├── labs_search_intent.json
    ├── labs_keyword_ideas.json
    ├── labs_ranked_keywords.json
    ├── backlinks.json
    └── onpage.json
```

---

## Dependencies

No additional packages required beyond Python 3.9+ stdlib (`urllib`, `json`, `argparse`).
`requests` is not used — all HTTP is done via `urllib.request`.

---

## Reference

- API docs: <https://docs.dataforseo.com/>
- Pricing: <https://dataforseo.com/pricing>
- Status page: <https://dataforseo.com/api-status>
- Rate limits: 2000 calls/min, 30 concurrent tasks
- Task storage: completed tasks stored for 30 days
