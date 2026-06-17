# Setup Guide

There are two ways to set up SEO Insights: the AI-guided path (recommended for most users) and the manual path (for advanced users who prefer to configure things themselves).

---

## Path A — AI-guided setup (recommended)

If you have the SEO Insights plugin installed in Claude Code, the assistant can configure everything for you.

**Start here:**

1. Open Claude Code with the `seo-insights` plugin active.
2. Run the command:
   ```
   /seo-setup
   ```
3. The assistant will walk you through every step — creating the Google Cloud project, enabling the APIs, setting up OAuth, and writing your config files. You do not need to edit any files yourself.

After setup is complete, run:
```
/define-seo-audience
```
The assistant will interview you about your target audience and write your ICP config file. Then:
```
/seo-analyze
```
This fetches your GSC data, runs the full analysis, and presents a prioritized SEO action plan.

That's it. The AI handles the technical details.

---

## Path B — Manual setup (advanced users)

Follow these steps if you prefer to configure the tool yourself, or if you are not using the plugin interface.

**Estimated time: 10–15 minutes**

### Step 1 — Install dependencies

```bash
pip install -r requirements.txt
```

Requires Python 3.10 or later.

---

### Step 2 — Create a Google Cloud project and enable the APIs

1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/).
2. Click **Select a project → New Project**. Name it anything (e.g. `seo-insights-cli`).
3. In the left sidebar go to **APIs & Services → Library**.
4. Search for **"Google Search Console API"** and click **Enable**.
5. (Optional, for keyword volumes) Search for **"Google Ads API"** and click **Enable**.

---

### Step 3 — Configure the OAuth consent screen

1. In **APIs & Services → OAuth consent screen**, choose **External** user type. Click **Create**.
2. Fill in:
   - **App name:** `seo-insights` (or anything)
   - **User support email** and **Developer contact email:** your email
3. On the **Scopes** screen, add:
   - `https://www.googleapis.com/auth/webmasters.readonly` (required)
   - `https://www.googleapis.com/auth/adwords` (optional, for Ads API)
4. Under **Test users**, add your own Google account email.
5. Save and return to the dashboard.

> **OAuth verification note:** For personal use where you are the only user and only tracking your own site, the app can remain in **testing mode** indefinitely. When you authorize, you'll see a "Google hasn't verified this app" warning — click **Advanced → Go to [app name] (unsafe)** to proceed. This is expected and safe for a private tool you control.
>
> If you later want to distribute this tool to many external users, you would need to submit the OAuth app for Google's verification process. For single-site personal use, no verification is required.

---

### Step 4 — Create an OAuth Client ID

1. In **APIs & Services → Credentials**, click **+ Create Credentials → OAuth client ID**.
2. Application type: **Desktop app**.
3. Name: `seo-insights-cli`.
4. Click **Create**. Copy the **Client ID** and **Client Secret**.

---

### Step 5 — Authorize and get your refresh token

Run the consent command to get the authorization URL:

```bash
python3 scripts/auth.py consent --client-id <YOUR_CLIENT_ID>
```

Open the URL in a browser signed in as the Google account that owns the Search Console property. Grant permission. Google shows you a one-time authorization code.

Exchange the code for a refresh token:

```bash
python3 scripts/auth.py exchange \
  --client-id <YOUR_CLIENT_ID> \
  --client-secret <YOUR_CLIENT_SECRET> \
  --code <AUTHORIZATION_CODE>
```

This prints your `GSC_REFRESH_TOKEN`. Copy it.

---

### Step 6 — Write config/gsc.env

```bash
cp config/gsc.env.example config/gsc.env
```

Edit `config/gsc.env` with your values:

```env
GSC_CLIENT_ID=your-client-id.apps.googleusercontent.com
GSC_CLIENT_SECRET=your-client-secret
GSC_REFRESH_TOKEN=your-refresh-token
GSC_SITE_URL=sc-domain:example.com
```

#### GSC_SITE_URL format

Google Search Console supports two property types:

| Format | When to use |
|---|---|
| `sc-domain:example.com` | **Domain property** — covers all subdomains and both http/https. Recommended. |
| `https://www.example.com/` | **URL-prefix property** — exact prefix only. Must include trailing slash. |

Check your property type in [Google Search Console](https://search.google.com/search-console) — the globe icon = domain property, link icon = URL-prefix property.

> `config/gsc.env` is listed in `.gitignore` and will never be committed.

---

### Step 7 — (Optional) Google Ads developer token

For real search volume data in keyword research, you need a Google Ads developer token with **Basic access**:

1. Go to [https://ads.google.com/aw/apicenter](https://ads.google.com/aw/apicenter).
2. Click **Apply for Basic access**. Test tokens return no volume data; Basic access is required for real numbers.
3. Approval takes a few business days.
4. Once approved, note your **Developer Token**, **Customer ID** (the 10-digit number in the top-right of Google Ads), and **Manager Customer ID** if you use a manager (MCC) account.

Add to `config/gsc.env`:

```env
GOOGLE_ADS_DEVELOPER_TOKEN=<your token>
GOOGLE_ADS_CUSTOMER_ID=<digits only, no dashes>
GOOGLE_ADS_LOGIN_CUSTOMER_ID=<manager id, or leave blank>
```

The OAuth refresh token must also include the `adwords` scope. If you created it with only the GSC scope, re-run Step 5 after updating the consent screen scopes.

**Without Ads credentials:** The tool runs in free mode using GSC data and Google Autocomplete for keyword ideas. Volumes show as unavailable. All other analyses (striking distance, CTR outliers, content decay, etc.) work normally.

---

### Step 8 — (Optional) PageSpeed Insights API key

For Core Web Vitals analysis (LCP, CLS, INP):

1. In Google Cloud → **APIs & Services → Library**, enable **"PageSpeed Insights API"**.
2. In **Credentials → + Create Credentials → API key**, create a key.
3. Add to `config/gsc.env`: `PAGESPEED_API_KEY=AIzaSy...`

Without this key, CWV analysis is skipped gracefully and all other analyses still run.

---

### Step 9 — Define your audience (ICP)

The Ideal Customer Profile (ICP) is what makes keyword scoring and recommendations relevant to your actual target audience.

```bash
cp config/icp.example.yaml config/icp.mysite.yaml
# edit config/icp.mysite.yaml — fill in all fields
python3 scripts/validate_icp.py config/icp.mysite.yaml
```

See `config/icp.example.yaml` for the schema and field descriptions. Be specific about role, company type, and size — vague ICPs produce weaker scoring.

> ICP files matching `config/icp.*.yaml` are listed in `.gitignore` and will never be committed.

---

### Step 10 — Run the pipeline

```bash
bash scripts/run.sh --icp config/icp.mysite.yaml
```

The script validates the ICP, fetches GSC data, runs all analyses, and renders the HTML report. It prints the report path on completion.

**First run tip:** Use `--days 28` for a faster initial run; switch to `--days 90` (the default) for the regular weekly cadence.

---

### Verify auth without a full run

```bash
python3 scripts/auth.py refresh
```

Success: `access_token=ya29.a0...`

---

### Troubleshooting

| Error | Fix |
|---|---|
| `Config file not found` | Check `config/gsc.env` exists and has all 4 required keys. |
| `Token refresh failed` | Re-run `auth.py exchange` to get a fresh refresh token. |
| `403 / insufficient permissions` | Confirm the Google account that authorized owns (or has full access to) the Search Console property. |
| `ICP validation FAILED` | Open `config/icp.*.yaml` and fill in all fields — no placeholder values allowed. |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt`. |
| No volume data in keyword research | Ads developer token is missing or is a Test token. See Step 7. |

---

## Advanced add-ons

### DataForSEO integration

DataForSEO provides additional keyword data sources (SERP data, backlink metrics, competitor analysis). This is an optional advanced add-on with its own setup process.

See `dataforseo/README.md` for installation and configuration instructions.

---

## Demo mode (no credentials required)

To see the tool in action without any setup:

```bash
bash scripts/demo.sh
```

This runs the full pipeline on synthetic fixture data and produces a demo report at `data/_demo/<today>/report.html`.
