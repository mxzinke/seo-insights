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

## STEP 0 — Allow network access (Claude Cowork only)

**Skip this step in Claude Code** (the local CLI has full network access).

If the user is running in **Claude Cowork**, its code-execution sandbox blocks
outbound traffic to all non-allowlisted domains through an egress proxy. SEO
Insights must reach Google's API domains (`oauth2.googleapis.com`,
`accounts.google.com`, `www.googleapis.com`, `googleads.googleapis.com`), so
these must be allowed first — otherwise every step below fails with an HTTP 403
`blocked-by-allowlist` error.

Tell the user:

1. Open **Claude → Settings/Admin → Organization → Capabilities → Code execution → Allow network egress** (an organization admin may be required).
2. Set the egress mode to **All domains**. *(Important: due to current Cowork bugs, the "Additional allowed domains" list is ignored unless the mode is "All domains" — adding only the Google domains often does not take effect.)*
3. **Restart Claude Desktop and start a fresh Cowork session** — egress changes only apply to new sessions.

Ask: "Are you in Cowork or Claude Code? If Cowork, have you enabled network egress (All domains) and restarted?" Only continue once confirmed (or if they're in Claude Code). If a later step fails with a 403 `blocked-by-allowlist` error, return here.

---

## STEP 0.5 — Choose your persistent workspace folder

**This step is critical for Claude Cowork users** and good practice for Claude
Code users too.

Explain to the user:

> "SEO Insights stores your credentials and analysis results in a folder on
> your Mac (or local machine). In Claude Cowork, the plugin runs inside a
> sandbox that is discarded after each chat session — so if we write files
> there, they are lost the next time you open Claude. We need a stable folder
> **outside** the sandbox, somewhere on your regular filesystem (e.g. in your
> home directory), so your credentials and weekly reports persist across every
> future session."

Ask:

> "Where would you like to store your SEO Insights workspace? I recommend
> `~/seo-insights` (a folder called `seo-insights` in your home directory).
> You can also enter any other absolute path. Press Enter to accept the default
> or type a custom path."

Once the user confirms a path (use `~/seo-insights` if they just press Enter),
run:

```
!python3 ${CLAUDE_PLUGIN_ROOT}/scripts/workspace.py set <path>
```

For example, for the default:

```
!python3 ${CLAUDE_PLUGIN_ROOT}/scripts/workspace.py set ~/seo-insights
```

This command:
- Creates the folder and its `config/` and `data/` subdirectories on the user's machine.
- Writes the absolute path to `~/.seo-insights/home` — a tiny pointer file that every future session reads to find the workspace, even when the plugin sandbox resets.

Tell the user:

> "Your workspace is now set up. All credentials and analysis results will be
> stored there. Every future chat session — including after Cowork restarts —
> will automatically find this folder via the pointer file `~/.seo-insights/home`.
> You can also override it at any time by setting the `SEO_INSIGHTS_HOME`
> environment variable."

Verify the workspace was created:

```
!python3 ${CLAUDE_PLUGIN_ROOT}/scripts/workspace.py show
```

Confirm the output shows the expected path and that `config/gsc.env exists: False`
(it doesn't exist yet — we'll create it in Step 7).

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
4. On the **Scopes** page, click **Add or Remove Scopes**. Add **both** scopes:
   - `https://www.googleapis.com/auth/webmasters.readonly` (Search Console read access)
   - `https://www.googleapis.com/auth/adwords` (Google Ads API — keyword volumes)

   Adding both now is recommended so the token is valid for Ads later without
   re-authorizing. (The `adwords` scope only appears in the picker if the Google
   Ads API was enabled in Step 2.) **If the user has no Google Ads account at
   all**, they can add only `webmasters.readonly` here — in that case you MUST
   run the Step 5 authorization with the `--gsc-only` flag so the requested
   scopes match what the consent screen allows (otherwise Google rejects it).
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

This uses Google's **localhost (loopback) redirect** flow. (Google disabled the
old "out-of-band" copy-paste flow in 2022 — a Desktop-app OAuth client like the
one created in Step 4 must use a localhost redirect, which this handles.)

**Preferred — automatic (no copy-paste):** run

`!python3 ${CLAUDE_PLUGIN_ROOT}/scripts/auth.py login --client-id <CLIENT_ID> --client-secret <CLIENT_SECRET> --open`

(If the user added only the Search Console scope in Step 3 — no Google Ads — append `--gsc-only` to this command.)

This opens a consent URL and starts a tiny local listener that captures the
authorization code automatically. Tell the user:

> "A browser tab will open. Sign in as the Google account that owns your Search Console property. You'll see a 'Google hasn't verified this app' warning — click **Advanced** then **Go to … (unsafe)**; this is safe because you are the only user of your own app. Grant the permission. The tab will say 'authorization received' — you're done, come back here."

The command then prints the `GSC_REFRESH_TOKEN`. Store it for Step 7.

**Fallback — manual (if the automatic listener can't capture, e.g. the browser is on another machine):** run

`!python3 ${CLAUDE_PLUGIN_ROOT}/scripts/auth.py consent --client-id <CLIENT_ID>`

Tell the user to open the printed URL, grant access; the browser will then try to
load `http://localhost/?code=…` and show a "can't reach this page" error — **that
is expected**. Ask them to copy the value of the `code=` parameter from the
address bar. Then run:

`!python3 ${CLAUDE_PLUGIN_ROOT}/scripts/auth.py exchange --client-id <CLIENT_ID> --client-secret <CLIENT_SECRET> --code <CODE>`

This prints the `GSC_REFRESH_TOKEN`. Store it for Step 7.

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

## STEP 7 — Write credentials to the persistent workspace

Now write the config file to the persistent workspace (established in Step 0.5).

First, resolve the workspace config path:

```
!python3 -c "import sys; sys.path.insert(0,'${CLAUDE_PLUGIN_ROOT}'); from scripts.workspace import config_path; print(config_path())"
```

This prints the full path, e.g. `/Users/you/seo-insights/config/gsc.env`.

Write the credentials to that path with the values collected:

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

Use the Write tool to create this file at the resolved workspace config path (NOT inside the plugin directory). Tell the user:

> "I've written your credentials to your persistent workspace at `<resolved path>/config/gsc.env`. This file lives in your home directory, not inside the plugin cache — so it will survive Cowork session restarts. It is never committed to any repository."

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

If they provide Ads credentials, update the workspace `gsc.env` (at the path printed by `workspace.py show`) with the values. Also remind them that the OAuth refresh token must include the `adwords` scope — if they only authorized the GSC scope earlier, they'll need to re-run the consent/exchange flow.

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
> 1. Run `/define-seo-audience` so I can learn about your target customers — this makes keyword scoring much more accurate.
> 2. Then run `/seo-analyze` to run the full analysis and get your prioritized SEO action plan."

If the token refresh fails, walk the user through re-running Steps 4–5 to get a fresh authorization code and refresh token.

---

## Error handling

- If the user doesn't have a Google Cloud account yet, direct them to [https://console.cloud.google.com/](https://console.cloud.google.com/) to create one for free.
- If the user skips the Google Ads steps, configure the free tier only and confirm it still works.
- If validation fails, diagnose and offer to re-run the affected step.
- Never abandon the user mid-wizard — always offer a path forward.
