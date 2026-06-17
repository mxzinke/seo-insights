# Keyword Discovery Guide: Free Google Tools

A practical how-to for finding keyword ideas manually using Google's own free tools, before feeding the best candidates into this plugin's analysis.

---

## 1. Google Keyword Planner

**What it is:** Google's official keyword research tool, built into Google Ads. It shows real search volume data from Google's index. You need a free Google Ads account to access it — you do not need to run any ads.

**Official help:** https://support.google.com/google-ads/answer/7337243

### How to access

1. Go to [https://ads.google.com/](https://ads.google.com/) and sign in.
2. In the top navigation, click **Tools** (wrench icon) → **Planning** → **Keyword Planner**.
3. You'll see two options: **Discover new keywords** and **Get search volume and forecasts**. For topic exploration, choose **Discover new keywords**.

### Two starting modes

**Start with keywords:**
- Enter 1–10 seed terms that describe your topic. Example: "SEO analysis", "search console", "keyword research".
- Click **Get results**. Google returns a list of related keyword ideas with volume data.

**Start with a website:**
- Enter your own URL or a competitor's URL. Google suggests keywords based on the page content.
- Useful for finding what topics competitors rank for that you might be missing.

### Understanding the columns

| Column | What it means |
|---|---|
| **Avg. monthly searches** | Average number of Google searches per month over the last 12 months. This is a range (e.g. 1K–10K) unless you have an active campaign with spend. |
| **Competition** | How many advertisers bid on this keyword — **Low**, **Medium**, or **High**. High competition = topic is commercially valuable but costly for ads. For SEO purposes, high competition often means high intent and revenue potential, but harder to rank for. |
| **Top of page bid (low/high)** | What advertisers pay per click. High bids signal commercial or transactional intent — people are willing to pay to reach these searchers. |

### Refining by location and language

- At the top of the results, click the location/language bar to restrict results.
- For Germany in German: set **Location** to "Germany" and **Language** to "German (Deutsch)".
- This filters volume data to German-language searches from Germany — critical if your site targets the German market.

### Tips

- Use the **Refine keywords** sidebar (right side) to filter by intent signal, brand/non-brand, topic, etc.
- Download results as CSV for offline sorting.
- Keyword Planner rounds volume to ranges (10, 100, 1K, 10K, etc.) unless your Google Ads account has billing set up. The ranges are still useful for relative comparison.

---

## 2. Google Trends

**What it is:** A free, no-login tool that shows the relative search popularity of a term over time, by region, and compared to other terms. It does not show absolute volumes — it shows a 0–100 index where 100 = peak popularity.

**Official documentation:** https://developers.google.com/search/docs/monitor-debug/trends-start

**Access:** [https://trends.google.com/](https://trends.google.com/) — no account needed.

### Basic usage

1. Enter a search term in the search bar.
2. Set the **Country** filter to your target market (e.g. Germany).
3. Set the **Time range**: 12 months is a good default. Use "2004–present" for long-term trend direction.
4. Set the **Search type**: "Web Search" is standard. "Google Shopping" or "YouTube Search" are useful for e-commerce/video topics.

### Reading the chart

The chart shows relative interest over time (0–100). Look for:
- **Upward trend:** The topic is growing — good time to invest in content.
- **Downward trend:** The topic is declining — consider whether it's worth the effort.
- **Seasonal pattern:** Spikes at the same time each year signal seasonal demand. Plan content to publish 4–8 weeks before the expected spike.
- **Flat:** Stable demand — reliable topic, less urgency.

### Related queries — the most powerful feature

Scroll down to **Related queries**. This shows what else people search for alongside your term.

There are two views — always check both:

- **Top:** The most-searched related queries overall. Good for finding high-volume adjacent topics.
- **Rising:** Queries that have grown the most recently (shown as % growth, or "Breakout" for >5000% growth). These are emerging topics competitors may not have covered yet. **This is where you find early-mover opportunities.**

To use: toggle from "Top" to "Rising" in the Related queries panel. Click any term to explore it further.

### Comparing terms

Enter up to 5 terms in the search bar (click "+ Compare"). Useful for:
- Deciding between two keyword variants (e.g. "SEO tool" vs "SEO software")
- Understanding which topic has stronger or faster-growing demand

### Regional interest

Below the main chart, the **Interest by subregion** map shows which regions or states search most for your term. Useful for geo-targeted content strategies.

### Tips

- Trends is best for **direction and seasonality** — combine with Keyword Planner for actual volume.
- "Breakout" in Rising queries means the term grew more than 5,000% — treat with some caution (could be a one-off event), but often signals a genuine new trend.
- Use Google Trends before creating a content calendar: plan your cornerstone articles around topics with growing or stable demand.

---

## 3. Combined workflow

The most effective approach combines both tools:

### Step 1 — Direction and emerging topics (Google Trends)
1. Enter your core topic(s) in Google Trends, filtered to your target country.
2. Check the trend line: growing, stable, or declining?
3. Switch to **Rising** in Related queries. Note any breakout or fast-growing adjacent terms — these are your early-mover opportunities.
4. Compare 2–3 variants to see which framing has stronger momentum.

**Output:** A shortlist of topics with confirmed growth direction.

### Step 2 — Volume and competition (Google Keyword Planner)
1. Take your shortlisted topics from Trends and enter them as seeds in Keyword Planner.
2. Filter to your target country and language.
3. Sort by **Avg. monthly searches** descending to find the highest-volume variants.
4. Note the **Competition** column: Low or Medium is generally more approachable for SEO.
5. Note the **Top of page bid**: high bids confirm commercial/transactional intent.

**Output:** Keywords with volume and competition data, ready for prioritization.

### Step 3 — Feed into this tool
1. Add the best topics to your ICP's `priority_topics` field by running `/define-seo-audience` (or updating the YAML directly if you're comfortable).
2. Run `/seo-keywords-research` to cross-reference with your GSC data — this shows which of these topics you already (partially) rank for, and where the biggest opportunity gaps are.

---

## Quick reference

| Goal | Tool | Where |
|---|---|---|
| Find search volume for specific terms | Keyword Planner → "Discover new keywords" | ads.google.com → Tools → Keyword Planner |
| Spot emerging / rising topics | Google Trends → Related queries → Rising | trends.google.com |
| Check if a topic is seasonal | Google Trends → Time range: 2 years | trends.google.com |
| Compare two keyword variants | Google Trends → "+ Compare" | trends.google.com |
| Find what a competitor ranks for | Keyword Planner → "Start with a website" | ads.google.com → Tools → Keyword Planner |
| Get volume for German market | Keyword Planner → Location: Germany, Language: German | ads.google.com → Tools → Keyword Planner |

---

## Limitations to know

- **Keyword Planner** volume ranges are broad (1K–10K) unless you have active ad spend. The ranges are good enough for relative comparison and prioritization.
- **Google Trends** shows relative interest, not absolute volume. A term at "50" has roughly half the interest of the same term at "100" — but the absolute number of searches could be anywhere from 100 to 10 million.
- Both tools reflect Google Search behavior in the selected region/language. Behavior on other search engines (Bing, etc.) may differ, but Google holds the majority share in most markets.
