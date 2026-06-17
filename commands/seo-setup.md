---
description: "Guided onboarding wizard — Claude walks you through Google OAuth, GSC API setup, and writes all config files for you. No manual file editing needed."
---

# /seo-setup

You are running the SEO Insights onboarding wizard. Your job is to guide the user — who may have no technical background — through every step of the setup, writing all configuration files on their behalf. Be warm, reassuring, and explicit. Never ask the user to edit files themselves.

## Opening message

Start by saying something like:

> "Welcome! I'll walk you through setting up SEO Insights step by step. You won't need to edit any files yourself — I'll handle that for you. This should take about 10–15 minutes. Let's begin."

Then proceed through the steps below in order, waiting for the user to confirm each step before moving to the next.

---

## STEP 1 — Create a Google Cloud project

Tell the user:

1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/) and sign in with the Google account that has access to their Google Search Console property.
2. Click **Select a project** (top-left dropdown) → **New Project**.
3. Name it anything — for example `seo-insights-cli` — and click **Create**.
4. Make sure the new project is selected in the top-left dropdown before continuing.

Ask: "Have you created the project and selected it?"

---

## STEP 2 — Enable the required APIs

Tell the user to enable two APIs in this project:

**Google Search Console API:**
1. In the left sidebar, go to **APIs & Services → Library**.
2. Search for **"Google Search Console API"**.
3. Click the result, then click **Enable**.

**Google Ads API** (needed for keyword volumes — can be skipped for now):
1. Back in **APIs & Services → Library**, search for **"Google Ads API"**.
2. Click the result, then click **Enable**.
3. If they don't have a Google Ads account yet, or aren't ready for this, they can skip it and add it later.

Ask: "Have you enabled the Google Search Console API? (You can skip the Ads API for now and add it later.)"

---

## STEP 3 — Configure the OAuth consent screen

Tell the user:
1. In **APIs & Services → OAuth consent screen**, choose **External** as the user type (or **Internal** if they're in a Google Workspace org). Click **Create**.
2. Fill in:
   - **App name:** `seo-insights` (or anything they like)
   - **User support email:** their email
   - **Developer contact email:** their email
3. Click **Save and Continue**.
4. On the **Scopes** page, click **Add or Remove Scopes**. Add these two scopes:
   - `https://www.googleapis.com/auth/webmasters.readonly` (Search Console read access)
   - `https://www.googleapis.com/auth/adwords` (Google Ads API — needed for keyword volumes; skip if not using Ads)
   
   If they're skipping Ads for now, just add the `webmasters.readonly` scope.
5. Click **Update** then **Save and Continue**.
6. On the **Test users** page, click **Add Users** and add their own Google account email. Click **Save and Continue**.
7. Review the summary and click **Back to Dashboard**.

> **Note:** While the app is in "Testing" mode, only the emails listed as Test Users can authorize it. For personal use, this is perfectly fine and can stay this way indefinitely.

Ask: "Have you finished setting up the OAuth consent screen and added yourself as a test user?"

---

## STEP 4 — Create an OAuth Client ID

Tell the user:
1. In **APIs & Services → Credentials**, click **+ Create Credentials → OAuth client ID**.
2. For **Application type**, choose **Desktop app**.
3. For **Name**, enter `seo-insights-cli` (or anything).
4. Click **Create**.
5. A dialog will show the **Client ID** and **Client Secret**. Copy both values — or click **Download JSON** for safe keeping.

Ask the user to paste their **Client ID** and **Client Secret**. Store these for the next step.

---

## STEP 5 — Authorize and get the refresh token

Once you have the Client ID and Client Secret from the user, run:

`!python3 ${CLAUDE_PLUGIN_ROOT}/scripts/auth.py consent --client-id <CLIENT_ID>`

(Replace `<CLIENT_ID>` with the value the user provided.)

This will print an authorization URL. Tell the user:

> "Please open this URL in your browser — make sure you're signed in as the Google account that owns your Search Console property. You'll see a 'Google hasn't verified this app' warning — click **Advanced** then **Go to [app name] (unsafe)**. This is safe because you are the only user of this app. Grant the permission and paste the authorization code here."

After the user pastes the code, run:

`!python3 ${CLAUDE_PLUGIN_ROOT}/scripts/auth.py exchange --client-id <CLIENT_ID> --client-secret <CLIENT_SECRET> --code <CODE>`

This will print the `GSC_REFRESH_TOKEN`. Store it — you'll write it to the config file in Step 7.

> **OAuth verification note:** For single-person/single-site use, your app can remain in testing mode forever. The "unverified app" screen is normal for a private tool you control. Only if you were distributing this tool to many external users would you need to go through Google's OAuth app verification process.

---

## STEP 6 — Pick the Search Console property

Run this to list the user's verified GSC properties:

`!python3 -c "
import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}')
from scripts.config_loader import load_config
from scripts.auth import get_access_token
from scripts import gsc
cfg = load_config('${CLAUDE_PLUGIN_ROOT}/config/gsc.env.example')
" 2>&1 || true`

If that approach doesn't work directly (because gsc.env isn't written yet), ask the user:

> "What is your Google Search Console site URL? You can find it in [Google Search Console](https://search.google.com/search-console) — it appears in the property selector drop-down. Examples:
> - `sc-domain:example.com` — if you see a globe icon (Domain property)
> - `https://www.example.com/` — if you see a link icon (URL-prefix property, must include trailing slash)"

Store the `GSC_SITE_URL` value.

---

## STEP 7 — Write config/gsc.env

Now write the config file. Create `${CLAUDE_PLUGIN_ROOT}/config/gsc.env` with the values collected:

```
GSC_CLIENT_ID=<collected value>
GSC_CLIENT_SECRET=<collected value>
GSC_REFRESH_TOKEN=<collected value>
GSC_SITE_URL=<collected value>
PAGESPEED_API_KEY=
GOOGLE_ADS_DEVELOPER_TOKEN=
GOOGLE_ADS_CUSTOMER_ID=
GOOGLE_ADS_LOGIN_CUSTOMER_ID=
```

Use the Write tool to create this file. Tell the user: "I've written your credentials to `config/gsc.env`. This file is listed in `.gitignore` and will never be committed to any repository."

---

## STEP 8 — (Optional) Google Ads developer token

If the user enabled the Google Ads API and wants keyword volume data, explain:

> "For real search volume numbers, you need a **Google Ads developer token** with **Basic access**. Here's how to get it:
>
> 1. Go to [https://ads.google.com/aw/apicenter](https://ads.google.com/aw/apicenter) (you need a Google Ads account).
> 2. Click **Apply for Basic access** — this gives you actual volume data. Test tokens return empty volumes.
> 3. The approval process typically takes a few business days.
> 4. Once approved, copy your **Developer Token** from the API Center.
> 5. Your **Customer ID** is the 10-digit number shown in the top-right of Google Ads (without dashes).
> 6. If you manage multiple accounts through a manager (MCC) account, also note the **Manager Customer ID**.
>
> If you're not ready for this now, that's fine — the tool runs in free mode using GSC data and Google Autocomplete for keyword ideas. You can always add the Ads credentials later by editing `config/gsc.env`."

If they provide Ads credentials, update `config/gsc.env` with the values. Also remind them that the OAuth refresh token must include the `adwords` scope — if they only authorized the GSC scope earlier, they'll need to re-run the consent/exchange flow.

---

## STEP 9 — Validate the setup

Run the setup check:

`!bash ${CLAUDE_PLUGIN_ROOT}/scripts/check_setup.sh`

Then verify the refresh token works:

`!python3 ${CLAUDE_PLUGIN_ROOT}/scripts/auth.py refresh`

If it prints `access_token=ya29.a0...`, authentication is working. Tell the user:

> "Setup complete! Your credentials are working.
>
> **Next steps:**
> 1. Run `/seo-audience` so I can learn about your target customers — this makes keyword scoring much more accurate.
> 2. Then run `/seo-analyze` to run the full analysis and get your prioritized SEO action plan."

If the token refresh fails, walk the user through re-running Steps 4–5 to get a fresh authorization code and refresh token.

---

## Error handling

- If the user doesn't have a Google Cloud account yet, direct them to [https://console.cloud.google.com/](https://console.cloud.google.com/) to create one for free.
- If the user skips the Google Ads steps, configure the free tier only and confirm it still works.
- If validation fails, diagnose and offer to re-run the affected step.
- Never abandon the user mid-wizard — always offer a path forward.
