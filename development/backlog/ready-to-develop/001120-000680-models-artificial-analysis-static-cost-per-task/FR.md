# FR 000680 — Models: static Artificial Analysis cost-per-task table between pricing and Terminal-Bench

**Owner-requested Ready Feature Request, 2026-11-11.** Permanent ID **000680**, Ready priority **001120**, following FR000679 (001110). **Authoring only:** publish this FR and increment `development/backlog/identity-state.json` highWatermark from 679 to 680; no product code, JSON runtime asset, tests, release/version files or other backlog changes now.

## Product decision and desired order

On Cost Guard Web → Models, preserve the existing **GitHub Reference Pricing** table and its existing default sort/valuation entirely. Change the lower page to exactly:

1. **GitHub Reference Pricing** — unchanged content/behavior.
2. **Cost per Task – Artificial Analysis** — new, static, independently owned benchmark table, visually and interactively matching the current Harbor table as closely as the metric semantics allow.
3. **Cost per Task – Terminal-Bench** — the existing Terminal-Bench 4.0 / Harbor Hub benchmark table, moved *below* Artificial Analysis. Keep all its source retrieval, 24h cache, Refresh benchmark action, default **Solved descending** sorting, filters, cost math and independent failure handling. Rename its heading only; its parenthesized source attribution remains **(Terminal-Bench 4.0 · Harbor Hub · View source)**.

Remove the final **More Coding Benchmarks** link-only section introduced in FR000657, since its official Artificial Analysis link moves to the new table heading. Use consistent unboxed section spacing, toolbar/table typography, responsive horizontal scrolling, accessibility and Classic/Web themes.

New heading: **Cost per Task – Artificial Analysis** with matching **(Artificial Analysis · View source)** linking only to https://artificialanalysis.ai/agents/coding-agents/ (new tab, noopener/noreferrer).

## New static table contract

- Five compact sortable columns: **Publisher | Model | Effort | Relative Task Cost | Coding Index**. This deliberately differs from Harbor's last column **Solved**: the Artificial Analysis *Coding Agent Index v2.0* is a weighted composite of FrontierCode v1.1, Terminal-Bench 4.0 and SWE-Atlas-QnA-AA, **not an observed overall solved percentage**. Display scores on a 0–100 index scale **without a fabricated % suffix**, with concise hover/focus help. Do not label it Solved or merge it with Harbor's solved values.
- Default order **Coding Index descending**, matching Harbor's *performance-first* sort; numeric sorting for costs/scores, deterministic tie-breaks, existing sortable accessible header behavior. Preserve separate sort/filter state for all three tables.
- Retain the Harbor table's familiar compact **Effort levels** multi-select and **Latest versions only** filter; retain an equivalent model-visibility filter, but **do not match/filter new Artificial Analysis rows against GitHub Copilot pricing by default**. Newly released / unpriced-in-Copilot models are the main benefit. If offering *Only Copilot-priced models*, make it optional and off by default; do not invent matches. The AA snapshot contains only source-published effort configurations: never synthesize High/Max/Medium for a model that has not been evaluated at that effort.
- Show **Last updated: YYYY-MM-DD** from the embedded JSON's `updated_at` field (configured Swedish-style numeric date; no implied live fetching). **NO Refresh benchmark button** on Artificial Analysis, no browser/source fetch, no network access, no auto-polling or TTL/cache. Git history is sufficient; no new in-product snapshot version history or archives. Each future manually reviewed update overwrites the same JSON file and sets the new `updated_at`.
- Keep original API currency **USD per attempted benchmark task** in the JSON. Derive **Relative Task Cost = row.cost_per_task_usd / minimum strictly positive finite cost across ALL eligible comparable rows of this one snapshot** in Python/server display preparation (or equivalent shared view-preparation layer), not from pre-rounded text, filter selection or currently visible rows. Display one decimal (`1.0x`), sort raw numeric. Show original USD/Task in targeted value help; missing/zero/nonfinite cost is **N/A**, never the denominator. Do not convert to CCost, Credits, subscription bills or estimated cost per solved task.
- Preserve agent identity via `coding_client` and display it in the model's contextual tooltip (plus any fallback/version notes when source-proven). Identity is **publisher + model + coding client + effort**, not merely model name; avoid deduplicating different clients/efforts. No fuzzy source/model joins or invention of missing metadata.
- The static AA table must remain operational when Harbor / GitHub price-source requests fail and vice versa. Reuse only relevant rendering styles and sort/filter logic; do not alter `src/application/benchmark.py`'s Harbor-specific GitHub catalog matching or its live fetch path.

## One overwriteable JSON file: proposed contract and initial review subset

At implementation, use e.g. `src/data/artificial-analysis-coding-agent-index.json` (one repository-shipped JSON asset; **not** the runtime Harbor cache). Read/validate it as static data and return a prepared view to the Web. `updated_at` represents **when a human-reviewed dataset was refreshed**, not when Artificial Analysis ran each benchmark. `methodology` is a plain descriptive label, **not a separate release/snapshot versioning subsystem**.

**Owner-level data-use decision (not an implementation work item):** This is a small, manually curated set of public benchmark facts, not a copy of the full Artificial Analysis leaderboard. The owner and assistant reviewed the site's current Terms of Use (notably §§2.2(d), 3.3(b)): automated scraping is prohibited and the terms do **not** expressly permit republishing a dataset. A locally running UI does not remove the distribution question when Cost Guard and its JSON are published or downloadable. Individual numeric facts have a different copyright position from a database as a whole; the applicable contractual/database-right scope for this particular excerpt remains uncertain. **Do not assign the implementer a licensing investigation, permission request, legal interpretation or approval workflow.** The owner retains the responsibility for any release/publication decision outside this FR. Implement the requested static-table architecture and curated data presentation without additional licensing workflow or a blocked development task; do not expand this into systematic harvesting or a full leaderboard mirror. Cite and link Artificial Analysis in the UI; no scraping, unofficial API endpoints, or assertions that the data is licensed.

This research sample deliberately prioritizes current relevant coding models plus every actually published **GPT-6.1 Terra** effort in the coding-agent benchmark, without fabricating unmeasured Carbon/Sol efforts. Official source pages used to check model, agent, effort, index and USD/task:
- https://artificialanalysis.ai/agents/coding-agents/comparisons/claude-code-vs-codex
- https://artificialanalysis.ai/agents/coding-agents/comparisons/antigravity-cli-vs-antigravity-sdk
- https://artificialanalysis.ai/agents/coding-agents/comparisons/codex-vs-opencode
- https://artificialanalysis.ai/agents/coding-agents/comparisons/codex-vs-grok-build
- https://artificialanalysis.ai/agents/coding-agents/comparisons/codex-vs-kimi-code-cli

```json
{
  "updated_at": "2026-11-11",
  "source": "Artificial Analysis",
  "source_url": "https://artificialanalysis.ai/agents/coding-agents/",
  "methodology": "Coding Agent Index v2.0",
  "currency": "USD",
  "rows": [
    {
      "publisher": "Anthropic",
      "model": "Claude Opus 5.5",
      "coding_client": "Claude Code",
      "effort": "max",
      "cost_per_task_usd": 11.42,
      "coding_index": 62
    },
    {
      "publisher": "Google",
      "model": "Gemini 4 Carbon",
      "coding_client": "Antigravity CLI",
      "effort": "high",
      "cost_per_task_usd": 7.74,
      "coding_index": 59
    },
    {
      "publisher": "Anthropic",
      "model": "Claude Sonnet 5.5",
      "coding_client": "Claude Code",
      "effort": "max",
      "cost_per_task_usd": 13.3,
      "coding_index": 59
    },
    {
      "publisher": "Anthropic",
      "model": "Claude Fable 5.1",
      "coding_client": "Claude Code",
      "effort": "max",
      "cost_per_task_usd": 11.53,
      "coding_index": 58
    },
    {
      "publisher": "OpenAI",
      "model": "GPT-6 Astra",
      "coding_client": "Codex",
      "effort": "max",
      "cost_per_task_usd": 7.04,
      "coding_index": 55
    },
    {
      "publisher": "OpenAI",
      "model": "GPT-6.1 Sol",
      "coding_client": "Codex",
      "effort": "max",
      "cost_per_task_usd": 1.5,
      "coding_index": 54
    },
    {
      "publisher": "Google",
      "model": "Gemini 4 Argon",
      "coding_client": "Antigravity CLI",
      "effort": "high",
      "cost_per_task_usd": 11.73,
      "coding_index": 53
    },
    {
      "publisher": "Z AI",
      "model": "GLM-5.3",
      "coding_client": "OpenCode",
      "effort": "max",
      "cost_per_task_usd": 5.23,
      "coding_index": 49
    },
    {
      "publisher": "OpenAI",
      "model": "GPT-6.1 Terra",
      "coding_client": "Codex",
      "effort": "xhigh",
      "cost_per_task_usd": 0.69,
      "coding_index": 48
    },
    {
      "publisher": "OpenAI",
      "model": "GPT-6.1 Terra",
      "coding_client": "Codex",
      "effort": "max",
      "cost_per_task_usd": 1.24,
      "coding_index": 48
    },
    {
      "publisher": "DeepSeek",
      "model": "DeepSeek V4.1 Flash",
      "coding_client": "Codex",
      "effort": "max",
      "cost_per_task_usd": 0.39,
      "coding_index": 47
    },
    {
      "publisher": "xAI",
      "model": "Grok 4.7",
      "coding_client": "Grok Build",
      "effort": "xhigh",
      "cost_per_task_usd": 9.48,
      "coding_index": 47
    },
    {
      "publisher": "OpenAI",
      "model": "GPT-6.1 Terra",
      "coding_client": "Codex",
      "effort": "high",
      "cost_per_task_usd": 0.54,
      "coding_index": 46
    },
    {
      "publisher": "OpenAI",
      "model": "GPT-6.1 Terra",
      "coding_client": "Codex",
      "effort": "medium",
      "cost_per_task_usd": 0.39,
      "coding_index": 42
    },
    {
      "publisher": "Moonshot AI",
      "model": "Kimi K3",
      "coding_client": "Kimi Code CLI",
      "effort": "max",
      "cost_per_task_usd": 5.17,
      "coding_index": 41
    },
    {
      "publisher": "OpenAI",
      "model": "GPT-6.1 Terra",
      "coding_client": "Codex",
      "effort": "non-reasoning",
      "cost_per_task_usd": 0.45,
      "coding_index": 39
    },
    {
      "publisher": "OpenAI",
      "model": "GPT-6.1 Terra",
      "coding_client": "Codex",
      "effort": "low",
      "cost_per_task_usd": 0.2,
      "coding_index": 35
    },
    {
      "publisher": "OpenAI",
      "model": "GPT-6 Luna",
      "coding_client": "Codex",
      "effort": "max",
      "cost_per_task_usd": 0.16,
      "coding_index": 31
    }
  ]
}
```

**Dataset scope:** This initial 18-row subset is the owner-requested manually reviewed starting data, not a comprehensive snapshot. Future updates overwrite the same JSON and `updated_at`; include only verifiable source-published model/client/effort configurations, preserving original publisher names and numeric cost precision. Do not require a license status flag or review gate in the runtime schema; the publication/data-use judgment belongs to the owner, not to the coding implementation. Artificial Analysis may change its evaluation methodology: never silently combine incompatible cohorts. Do not substitute the *general Intelligence Index* or its USD/task for Coding Agent Index rows.

## Suggested implementation surfaces and acceptance

- Existing `src/web/assets/render.js` owns Models layout and currently appends the link-only `more-benchmarks` block after `BenchmarkView`; replace that placement with an independent AA section above the existing Harbor `BenchmarkView.View`.
- Existing `src/web/assets/benchmark.js` owns Harbor UI; share a small source-agnostic presentation primitive only if that reduces duplication without coupling its refresh/filters/failure semantics.
- The new static JSON is bundled in source control, read without network, validated for date, source/method, currency, safe bounded strings, numeric index range (0–100), positive costs/null handling, duplicate identities, and empty/invalid snapshot fallback.
- Add focused Python application tests for USD→relative ratios and static-data validation; DOM/real-browser tests for order, default sorting, filter independence, all effort variants, source links, presence/absence of Refresh, date label and tooltips, 360px/mobile responsiveness, keyboard navigation and both themes.
- Verify original pricing and Harbor integration/web tests still pass; update `docs/web-beta.md`, module architecture docs and affected integration tests during implementation.
- This FR does **not** authorize a live source connector, paid API, background service, model calls, UI score blending, Harbor source alterations, license circumvention or a runtime implementation in this publication.

## Publication boundary

Create only `development/backlog/ready-to-develop/001120-000680-models-artificial-analysis-static-cost-per-task/FR.md` and advance `development/backlog/identity-state.json` `highWatermark: 680`. No source code, releases, product tests, or data asset yet.
