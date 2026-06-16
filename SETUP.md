# Setup Guide

This guide walks you through everything you need to get seo-insights running
against your real Google Search Console data. Estimated time: 10–15 minutes.

---

## Step 1 — Install dependencies

```bash
pip install -r requirements.txt
```

Requires Python 3.10 or later.

---

## Step 2 — Create a Google Cloud project and enable the GSC API

1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/).
2. Click **Select a project → New Project**. Name it anything (e.g. `seo-insights-cli`).
3. In the left sidebar go to **APIs & Services → Library**.
4. Search for **"Google Search Console API"** and click **Enable**.

---

## Step 3 — Create an OAuth 2.0 Client ID

1. In **APIs & Services → Credentials**, click **+ Create Credentials → OAuth client ID**.
2. If prompted, configure the **OAuth consent screen** first:
   - User type: **External** (or Internal if you're in a Google Workspace org).
   - Fill in App name (e.g. `seo-insights`), your email for support and developer contact.
   - Scopes: click **Add or remove scopes**, add `https://www.googleapis.com/auth/webmasters.readonly`.
   - Test users: add your own Google account email (required while the app is in testing mode).
   - Save and continue.
3. Back in **Create OAuth client ID**:
   - Application type: **Desktop app**.
   - Name: `seo-insights-cli` (or any name).
   - Click **Create**.
4. Download or copy the **Client ID** and **Client Secret** — you will need them below.

> **OAuth verification note:** For personal use (you are the only user, one
> site), the app can remain in **testing mode** indefinitely. You will see a
> "Google hasn't verified this app" warning when authorizing — click
> **Advanced → Go to [app name] (unsafe)** to proceed. This is expected and
> safe for a private tool you control. If you later want to share this tool
> with many external users, you would need to submit the app for Google's
> OAuth verification process.

---

## Step 4 — Authorize and get your refresh token

Run the consent command to get the authorization URL:

```bash
python3 scripts/auth.py consent --client-id <YOUR_CLIENT_ID>
```

This prints a URL. Open it in a browser **signed in as the Google account
that owns the Search Console property**. Grant the requested permission
("View your Search Console data"). Google will show you a one-time
authorization code.

Exchange the code for a refresh token:

```bash
python3 scripts/auth.py exchange \
  --client-id <YOUR_CLIENT_ID> \
  --client-secret <YOUR_CLIENT_SECRET> \
  --code <AUTHORIZATION_CODE>
```

This prints your `GSC_REFRESH_TOKEN`. Copy it — you need it in the next step.

---

## Step 5 — Fill in config/gsc.env

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

### GSC_SITE_URL — domain property vs. URL-prefix property

Google Search Console supports two property types:

| Format | When to use |
|---|---|
| `sc-domain:example.com` | **Domain property** — covers `example.com` and all subdomains (`www.`, `blog.`, etc.) over both `http` and `https`. Recommended. |
| `https://www.example.com/` | **URL-prefix property** — covers only that exact prefix. Must include the trailing slash. |

Check your property type in [Google Search Console](https://search.google.com/search-console)
under **Property Selector** — the icon next to the property name indicates
the type (globe = domain, link = URL-prefix).

> `config/gsc.env` is listed in `.gitignore` and will never be committed.

---

## Step 6 — (Optional) PageSpeed Insights API key

For Core Web Vitals analysis (LCP, CLS, INP), this tool uses the
[PageSpeed Insights API](https://developers.google.com/speed/docs/insights/v5/get-started).

**Without a key:** CWV analysis is skipped gracefully — all other analyses
still run and the report is produced without CWV data.

**With a key:** Add it to `config/gsc.env`:

```env
PAGESPEED_API_KEY=AIzaSy...
```

To get a key:

1. In Google Cloud Console → **APIs & Services → Library**, search for
   **"PageSpeed Insights API"** and enable it.
2. Go to **Credentials → + Create Credentials → API key**.
3. (Optional but recommended) Restrict the key to the PageSpeed Insights API.

You can also pass the key at runtime without storing it:

```bash
bash scripts/run.sh --icp config/icp.mysite.yaml --pagespeed-key AIzaSy...
```

---

## Step 7 — Fill in your ICP

The Ideal Customer Profile (ICP) ensures keyword scoring reflects your
actual target audience — without it, analysis is generic and less useful.

```bash
cp config/icp.example.yaml config/icp.mysite.yaml
# edit config/icp.mysite.yaml — all fields are required
python3 scripts/validate_icp.py config/icp.mysite.yaml
```

Be specific about your audience (role, company type, company size). Vague
ICPs like "small businesses" produce weaker keyword scores than specific ones
like "DevOps engineers at Series A–C startups".

> ICP files matching `config/icp.*.yaml` are listed in `.gitignore` and will
> never be committed — they can contain confidential competitive intelligence.

---

## Step 8 — Run the pipeline

```bash
bash scripts/run.sh --icp config/icp.mysite.yaml
```

The script validates the ICP, fetches GSC data, runs all analyses, and
renders the HTML report. It prints the report path on completion.

**First run tip:** Use `--days 28` for a faster first run; switch to
`--days 90` (the default) for the regular weekly cadence.

---

## Verifying auth without a full run

To verify your credentials are working without fetching all data:

```bash
python3 scripts/auth.py refresh
```

A successful output looks like: `access_token=ya29.a0...`

---

## Troubleshooting

| Error | Fix |
|---|---|
| `Config file not found` | Check `config/gsc.env` exists and has all 4 required keys. |
| `Token refresh failed` | Re-run `auth.py exchange` to get a fresh refresh token. |
| `403 / insufficient permissions` | Confirm the Google account authorized owns (or has full access to) the Search Console property. |
| `ICP validation FAILED` | Open your `config/icp.*.yaml` and fill in all fields — no placeholder values allowed. |
| `ModuleNotFoundError: No module named 'yaml'` | Run `pip install -r requirements.txt`. |
