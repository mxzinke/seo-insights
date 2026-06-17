---
description: "ICP interview — Claude asks probing questions to define your target audience, then writes config/icp.<domain>.yaml and validates it."
---

# /seo-insights:define-audience

You are conducting a structured Ideal Customer Profile (ICP) interview. Your goal is to deeply understand the user's target audience so that keyword scoring, content recommendations, and SEO prioritization are sharply focused on the right readers.

The user may not know the terminology — guide them with concrete examples. Ask questions conversationally, a few at a time. Do NOT fire all questions at once. Push back gently if answers are vague. Only move on when you have sharp, specific answers.

When the interview is complete, you will write `${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml` and validate it automatically.

---

## How to conduct the interview

Start with a warm opener:

> "Let's nail down who your website is actually for. The more specific we get, the better the keyword recommendations will be. I'll ask you a series of questions — just answer naturally, and I'll ask follow-ups until we have a crisp picture. Ready?"

Then work through the following topics in roughly this order, adapting as the conversation flows. Do not accept vague answers — probe until you have specifics.

---

### Topic 1 — The audience

Ask who the site is for. Push for specifics:

- What is their job title or role? (e.g. "Head of Marketing" vs "marketing person")
- What kind of company do they work at? Industry, business model (B2B/B2C), size?
- What stage is the company at? Early-stage startup, growth-stage, enterprise, SMB?
- Are there multiple audience segments? If so, which is primary?

**Do not accept:** "small businesses", "entrepreneurs", "anyone who needs SEO", "companies". Push for specifics like: "B2B SaaS growth teams at Series A–C companies with 10–100 employees".

**Example follow-up:** "You said 'small businesses' — can you be more specific? What industry? How many employees? Do they have a dedicated marketing person or is it the founder doing everything?"

---

### Topic 2 — Country and language

Ask:
- Which country is the primary market? (just the most important one)
- What language do they search in?

If the site is multilingual or multi-region, ask which is primary for this analysis.

---

### Topic 3 — The problem and search intent

Ask:
- What problem does your site/product solve — in one sentence?
- When someone searches Google and finds your site, what were they trying to figure out or do?
- Do they mostly want to learn something (informational), compare options (commercial), buy/sign up (transactional), or find a specific page (navigational)?

**ICP YAML field:** `search_intent` must be one of: `informational`, `navigational`, `commercial`, `transactional`, `mixed`.

---

### Topic 4 — Value proposition

Ask:
- Why should someone choose your product/site over alternatives?
- What makes it different from competitors?

Push for one strong, specific sentence. Avoid vague marketing language like "we're the best" — ask for the concrete differentiator.

---

### Topic 5 — Competitors

Ask:
- Who are your 2–5 main competitors? (domain names preferred, e.g. `ahrefs.com`)
- Are there indirect competitors (tools, blogs, categories of search result) that compete for the same audience?

At least 2 real competitor domains are needed.

---

### Topic 6 — Core topic pillars

Ask:
- If you had to pick 5–10 keyword themes or topic clusters that define what your site should rank for, what would they be?
- What are the big topics your audience cares about most?
- What do you most want to show up for in Google?

These become `priority_topics` — short keyword themes like "seo analysis", "keyword research", "content optimization". They influence how opportunities are scored. Help the user think of concrete examples if they're stuck.

If the user wants guidance finding topics, mention: "If you want help brainstorming keyword ideas from Google's own tools, I can walk you through that — just ask me about keyword discovery."

---

### Topic 7 — Excluded terms (noise filter)

Ask:
- Are there any types of searches you definitely do NOT want to attract? (e.g. consumer queries when you're B2B, unrelated tools, competitor brand names, topics outside your niche)
- Are there any terms that sound relevant but actually bring the wrong audience?

Examples: "youtube seo", "free tools", "instagram", "tiktok", "seo for beginners" (if targeting professionals).

At least 1–3 excluded terms are needed.

---

## Writing the ICP file

Once you have sharp, specific answers to all topics above, determine the domain. Ask the user if they haven't already mentioned it:

> "What is the domain name of the site we're analyzing? (e.g. `example.com`)"

Then write `${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml` using the Write tool. Match the schema in `${CLAUDE_PLUGIN_ROOT}/config/icp.example.yaml` exactly:

```yaml
audience: "<specific role, company type, size>"
country: "<two-letter ISO code, e.g. DE>"
language: "<BCP-47 code, e.g. de>"
search_intent: "<one of: informational | navigational | commercial | transactional | mixed>"
problem_solved: "<one sentence>"
value_proposition: "<one sentence>"
competitors:
  - <domain1>
  - <domain2>
priority_topics:
  - <topic 1>
  - <topic 2>
excluded_terms:
  - <term 1>
  - <term 2>
```

All fields are required. Do not leave placeholder values.

---

## Validation

After writing the file, validate it:

`!python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_icp.py ${CLAUDE_PLUGIN_ROOT}/config/icp.<domain>.yaml`

If validation passes, show the user a summary of the ICP and say:

> "Your audience profile is saved and valid. Here's what I captured:
>
> - **Audience:** [value]
> - **Market:** [country] / [language]
> - **Core topics:** [list]
> - **Excluded noise:** [list]
>
> You're ready to run the analysis! Use `/seo-insights:analyze` to get your prioritized SEO action plan."

If validation fails, read the error messages and fix the specific field(s) that failed — do not ask the user to edit the file themselves. Re-run validation after fixing.

---

## Quality bar

The ICP is not done until it is sharp enough that a content writer could use it to decide whether a given article idea is on-target. If the answers are still vague after two rounds of follow-ups on a topic, point that out explicitly and give the user a concrete example of what a specific answer looks like.

> ICP files matching `config/icp.*.yaml` are listed in `.gitignore` and will never be committed — they can contain confidential competitive intelligence.
