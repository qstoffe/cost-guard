# FR 000652 — Models: reference-price list + independent Terminal-Bench cost-per-task comparison

**Owner-approved Ready Feature Request, 2026-11-09.** New permanent identity **000652**. Ready priority **000870**, after currently Ready FR000650 (000850) and FR000651 (000860). **Backlog-only publication now:** create this FR and increment `development/backlog/identity-state.json` highWatermark **651 → 652**. No runtime implementation, tests, user docs/version/release changes or unrelated FR work in the publication commit.

## Purpose and agreed UI

The owner wants **two separate tables on Cost Guard Web → Models**, not two unlike cost metrics mixed in the current price table.

**Table 1 — Models Reference Pricing**: retain the existing four-column GitHub Copilot reference-price table and its behavior. Add this clear section title and rename its **Web header `Relative CCost` to `Relative Price List Cost`**. Its calculation still uses the current shared historical I/C/W/O token-category mix against published model/tier reference prices, normalized to the cheapest comparable model; however **that complexity is NOT displayed as a prominent paragraph**. Explain the method briefly in the relevant header tooltip. This table still highlights actual GitHub price promotions and new model releases.

**Table 2 — Coding Benchmark – Cost per Task**: an independent six-column table *directly below* the first, backed by public **Terminal-Bench 4.0 / Harbor Hub** results, with **all published eligible model/client/effort combinations**. Default sort by highest **Relative Task Cost** first. Data acquisition is optional and *best effort*, and must never delay, block or invalidate the price-list table.

The layout target (all figures **illustrative placeholders**, not observations) is:

```text
Models Reference Pricing
  GitHub Copilot · Prices last fetched: ...           [Refresh price list]
  Publisher     Model        Relative Price List Cost ↓   Release date
  Anthropic     Model A                         8.2x       ...
  OpenAI        Model B                         3.1x       ...
  [existing promotions / New Models notes / availability controls]

Coding Benchmark – Cost per Task
  Terminal-Bench 4.0 · Harbor Hub · Last fetched: ...    View source
  Model         Coding Client    Effort   Relative Task Cost ↓  USD/Task  Solved
  Model A       Claude Code      Max                  12.5x      $9.80   71.0%
  Model B       Codex            High                  4.8x      $3.76   60.0%
  Model B       Codex            Medium                1.0x      $0.78   45.0%
```

The new six headers must be exactly, in order: **Model | Coding Client | Effort | Relative Task Cost | USD/Task | Solved**.

Use **Coding Client** as a readable name for **Codex, Claude Code**, etc. Terminal-Bench calls that the *agent*; the **LLM model** is a separate dimension and **Harbor/Terminal-Bench** is the benchmark/evaluation harness. The result is the performance and cost of a **model + coding client + effort configuration**, not an intrinsic model-only cost. Agent/client version should be source-proven and retained, e.g. in targeted contextual help, if not a visible column.

A single model/client combination can have **separate Medium, High, Max, etc. rows** when the source actually publishes them. Do not prefer Max or infer nonexistent effort variants. If a user sorts alphabetically by Model, variants naturally sit next to each other; if by cost, they may separate. **Both tables default to descending relative-cost sort (most expensive first)** and have completely independent header/sort state.

## Primary source and what the numbers mean

Preferred public data source:

- Terminal-Bench: https://www.tbench.ai/
- Harbor Hub: https://hub.harborframework.com/
- Official documented unauthenticated public leaderboard endpoint: **POST `https://api.harborframework.com/functions/v1/leaderboard-read`**
- Public request body: **`{"package":"terminal-bench/terminal-bench","name":"4-0-0","page":1,"page_size":100}`**
- Harbor API documentation: https://github.com/harbor-framework/harbor/blob/main/docs-mintlify/harbor-hub/leaderboards.mdx — *Display a leaderboard on your own website*. Public leaderboard output includes `leaderboard`, `rows` and `pagination`; follow `pagination.total_pages`.
- Official Terminal-Bench 4.0 schema: https://github.com/harbor-framework/terminal-bench/blob/main/leaderboard/leaderboard.yaml
- Published results/source evidence: https://github.com/harbor-framework/terminal-bench/tree/main/leaderboard/submissions

The published leaderboard schema contains source metadata such as **model_display**, **agent_display**, **reasoning_effort**, date and benchmark metrics **total_cost_usd**, **n_trials**, **accuracy**, with optional successes, token totals etc. Submission files may also have more detailed `source_filter` fields for agent/model/version/effort. **Verify exactly which fields are available from the live Harbor API before designing strict parsing; GitHub submission-file metadata is not automatically identical to API rows.** Verify source terms for automated read and redistribution: public unauthenticated access is promising but does not imply unlimited permission to mirror/republish content. Do not use unofficial HTML scraping or a paid/private endpoint as an invisible workaround.

- **USD/Task** = published **total_cost_usd / n_trials** for that published benchmark row, **cost per task attempt, including failures**, NOT the cost of a successful result, Cost Guard CCost, actual individual subscription bill or a universal prediction.
- **Solved** = published accuracy/success rate in percent. Show this openly because low-cost rows might solve very few tasks. Do not create a seventh *cost per success* column.
- **Relative Task Cost** = each valid USD/Task divided by the **lowest strictly positive comparable USD/Task among ALL eligible rows in the same complete benchmark edition/snapshot**. Cheapest is **1.0x**. The displayed ratio is one decimal; sort and divide using precise unrounded numbers, with deterministic tie-breaks. A filter, source page order or rendered viewport must not change this denominator.
- **USD stays USD** in this benchmark table even if the user's existing Cost Guard reference cost display is set to Credits; reference-price ratios remain unitless and are unchanged.
- **One comparison edition**, initially Terminal-Bench **4.0**, across all rows. Never mix Terminal-Bench editions or combine with Artificial Analysis, SWE-bench, Integration Bench or Aider without an explicit new UX/source decision. The source/version/agent/effort distinctions are necessary for meaningful comparisons.

Accept only finite nonnegative source totals with a **positive integer n_trials**, supported score range (and complete identifiable source configuration); derive relative ratios only for **positive** cost per attempt. Zero/unknown cost is not a fake cheapest 1.0x. Do not invent missing tasks, model, agent, effort, currency or success rate. Define canonical handling of multiple official runs for the *same* model + client + effort but different agent versions/dates: preserve truly different published configurations or pick one documented current official result, but never arbitrarily discard data or average incompatible runs without a stated source rule. Invalid/partial responses cannot become an authoritative full snapshot.

## A. Reference-pricing table must not change analytically

1. Add the visible section heading **`Models Reference Pricing`**. Continue compact **GitHub Copilot** source/fetch/progress cues and the existing **Refresh price list** action. Existing table remains **Publisher | Model | Relative Price List Cost | Release date**.
2. Rename only this table's heading, the matching short help and accessible header/sort text. **Keep the internal `relative_cost` DTO, CLI terminology where still valid, comparison math, current sampled shared token mix, reference tiers and arrows/thresholds, pricing-refresh contract and active sorting semantics unchanged.** Don't globally rename CCost, alter CCost Today or touch Watch calculations.
3. Existing **show all priced models / latest versions only** filters, availability identity, source date and new-model/promotion notices still behave as today. Default sorting **Relative Price List Cost descending** using full raw numeric base tier and established tier tie-breaking, not formatted lexicographic values.
4. **GitHub Copilot Price Promotion stars, colors, discount descriptions, expiring offers and reference pricing help stay ONLY in this first table.** Promotions are not a statement about benchmark cost. Benchmark amounts never get discounted by reference-list offers, even if the model matches one in both tables.

## B. Critical owner clarification — the only New Models authority is reference pricing RELEASE DATE

5. **New/lime highlighting in BOTH tables must be decided solely by the matching model's RELEASE DATE IN THE GITHUB COPILOT REFERENCE PRICE LIST, applying Cost Guard's EXISTING New-release window.** In current source, `src/reports/semantics.py::model_is_recent(release_date, now_ms)` treats a known model release as recent for **seven days (age 0–6 calendar days)**, and `src/reports/model_comparison.py::web_model_catalog()` derives existing table `recent` from that exact reference catalog metadata. Reuse the same eligibility/window and `app.css` lime `.new` style, never a second novelty subsystem.
6. **Never use anything from Terminal-Bench to decide New**, including **leaderboard row first appearance, submitted date, publication date, source fetch time, run date, model name, new effort, added coding-client version, or an independent first-seen/12-hour clock**. The owner explicitly rejected all benchmark-driven timing. Current reference-list 12-hour first-sighting *notice* behavior may remain for existing notices; it must **not** become an additional benchmark highlight trigger. A new benchmark row never starts or extends the lime clock.
7. Match benchmark model → price-list model by a **source-backed exact canonical identity**, with publisher/provider/version/variant verified when needed, **not fuzzy name fragments**. If the benchmark model is absent from reference pricing, has no trustworthy release_date, or an ambiguous mapping, **show its benchmark row normally without New**; do not invent release metadata. All benchmark efforts and clients for the same proven model share the reference release-date state. A legitimate reference-list change can update that state through the existing reference snapshot, not through an unrelated benchmark refresh.
8. Explicit cases for acceptance:
   - Reference list model released today; benchmark now contains it: lime in both tables.
   - Reference list model released **six days ago**; benchmark first appears today: lime **only while the pre-existing reference new window remains**.
   - Reference list model released **eight or more days ago**; benchmark added today: **NO lime** in benchmark.
   - Benchmark has a recently published run for a model **missing from GitHub reference catalog**: visible benchmark row but **NO lime**.
   - A benchmark row gains new Max/Medium effort or an agent version today: **NO extra New period**.
   - Multiple model names with fuzzy collision (Sonnet 4 vs Sonnet 5.5): no wrongly inherited lime.
   - Reference-list expired New and current promotion: **reference promotion can still exist**, but no benchmark promotion or new state.
9. Preserve normal New semantic coloring of model labels (and existing reference release-date content); don't blanket-color entire benchmark cost/success row or confuse it with Copilot's promotion. Any New notice in benchmark must not claim the benchmark publication date is a model launch date.

## C. Six-column benchmark table, interaction and display

10. Place **Coding Benchmark – Cost per Task** below first table. Under its heading show compact **`Terminal-Bench 4.0 · Harbor Hub`**, **a real clickable official leaderboard link**, and **last successfully fetched/as-of** when available. A row-specific official run/submission/source link or safe accessible help should be available when its URL was actually published; do not construct arbitrary websites from untrusted labels.
11. Show the six headers exactly and without extra default technical columns. Keep readable compact rows, tabular numeric alignment and USD dollars. Long model/client labels must wrap or elide without breaking source identity; narrow screens pan the table horizontally. Each header should be sortable and keyboard accessible; the separate benchmark sort state remains through tab/view changes and must not reorder first table.
12. **Default benchmark sort: Relative Task Cost DESCENDING.** Model sort groups same models together naturally; then deterministic client/effort tie-breakers. Unknown cost/score should sort last. One row per source-supported configuration, not only Max and not one row per ambiguous family name. Preserve actual recorded source effort and client; do not derive model-specific earnings or payback from model token prices.
13. The displayed **USD/Task** is a benchmark average per attempted task, including unsuccessful attempts. Apply compact USD formatting without showing a small positive amount as exact zero. **Solved (%)** uses the true benchmark score semantics; don't silently turn success proportion 0.61 into 0.61% or into 61 dollars. Benchmark data is not a source of price promotion, provider billing, live OpenCode availability or actual user costs.
14. If source partial/unknown metadata prevents an exact model mapping **for New highlighting only**, retain its native benchmark identity where sound; no reason to hide useful sourced benchmark costs merely because the GitHub catalog does not carry that model. However invalid/missing model *within the benchmark entry itself* cannot support a trustworthy row.

## D. Fetch/cache/refresh must be *best effort*

15. Add a **server-owned fixed-HTTPS Harbor adapter and separately versioned cache**, not a browser-side third-party API request, using the documented public API. Make acquisition independently scheduled/coalesced from GitHub Copilot pricing, bounded by strict response size, page count, timeout, total read work, parse/schema/identity checks and reasonable backoff. Use full official public pagination and atomically publish a complete, coherent valid leaderboard snapshot. A later failed or incomplete fetch never overwrites a last-good complete snapshot.
16. An upstream timeout, rate limit, malformed response, contract change, unsupported source terms, missing page, no score or empty board **must not delay or fail the existing Models price-list first paint**, price refresh, Accounts, Sessions, Watch, AI Stats, app navigation, other report jobs or CLI. It must not start uncontrolled parallel workers or make historical-source/model scans. A reasonable independent maximum cache age is **around 24 hours**, with refresh as appropriate; do not request the whole leaderboard on every Web navigation or per row/cell. If a small **Refresh benchmark** action is provided, it is separate from **Refresh price list** and cannot cause a cross-source failure.
17. Show last good cached benchmark **with an honest old fetch date** when offline/stale; not with fresh-date fiction. If there is no usable snapshot, show a small **Benchmark unavailable / no benchmark data yet** message, a source link and optional retry, **not fabricated ratios, zeros, a mandatory loading wall or large warning**. Both tables can have different observation timestamps and different successful refreshes.
18. **No subscription, model calls, prompts/transcripts/user OpenCode history, auth tokens, credentials, local OpenCode metadata or personally identifying information is sent to Harbor.** No downloaded product dependency, paid key or headless browser scraper; confirm legal/API terms and document any conditions. Public aggregate read only, via current authenticated Cost Guard Web host. Benchmark data does not enter `PricingCatalog`, canonical valuation, CCost cache identity, historical analysis, model-version verification or GitHub reference price records.

## E. Short tooltips, separated by blank lines when covering multiple topics

19. **Owner-wide writing rule for ALL new and edited Cost Guard tooltips:** be short, natural and immediately useful. A single concept should be one compact sentence. **Two or more distinct concepts must occupy distinct short paragraphs, separated by one blank line (`\n\n`)**. Avoid a long uninterrupted paragraph, formula dump, arbitrary hard line wraps, repeated source disclaimers, bulky status lists or splitting into multiple unrelated tooltip widgets. The user considers this a global quality standard, not a one-off coding-benchmark exception.
20. **Relative Price List Cost** header can be two tiny paragraphs: `Reference-price ratio to the cheapest comparable model (1.0x).` then blank line then `Uses the same recent token mix for every model and price tier; not task performance.` More technical details (I/C/W/O sample up to 100, context-tier thresholds, no-sample policy) belong in a genuinely optional deeper explanation where necessary, rather than a huge header tooltip. Keep the displayed table free from tokenmix derivation chatter. Other simple headers get a one-line description.
21. New benchmark tooltips should be short examples:
   - **Model:** `The model that ran this benchmark configuration.`
   - **Coding Client:** `The coding agent application, such as Codex or Claude Code.`
   - **Effort:** `The tested reasoning effort. Missing effort is not guessed.`
   - **Relative Task Cost:** `Cost per attempt relative to the cheapest comparable benchmark run (1.0x).`
   - **USD/Task:** `Average US dollars spent per attempt, including failed attempts.`
   - **Solved:** `Percentage of benchmark attempts solved successfully.`
   Section/source tooltip can have two short paragraphs: `Terminal-Bench 4.0 results depend on model, coding client and effort.` blank line `These are benchmark tasks, not your bills or predicted OpenCode costs.`. Source link and as-of belong in the compact provenance row, not in every header.
22. Add the owner's general **short-and-blank-line tooltip writing guidance** to the current `development/architecture/modules/web-help.md` when implementing. Use existing shared `ContextHelp.heading/value/attach` and its 600 ms hover, keyboard/touch, Escape, exact intrinsic targets, safe plain text and preserved newlines. **Improve tooltips modified by this FR, not a bulk rewrite of every unrelated existing tooltip**. Preserve current global design system and practical accessible help.

## Source / code navigation and boundaries

23. `src/web/assets/render.js::overviewModels()` currently renders **one four-column table**, with `modelHeadingHelp()`, independent model controls, full raw sorting, `modelRelative()` tier/promotion markers and model `recent` class. Add two titled sections and **independent benchmark table state**. `src/web/assets/app.css` owns the existing `.overview-model-table` grid and `.new` lime class; scope benchmark CSS separately. Preserve old DOM/scroll/sort behaviors.
24. `src/reports/model_comparison.py::web_model_catalog()` owns reference model rows, `src/reports/semantics.py::model_is_recent()` owns seven-day releasedate New logic and `active_model_promotion()` owns GitHub offer notes. Benchmark ingestion should be **typed independent data**, with New eligibility attached from the **reference model catalog only on proven exact joins**, not derived from benchmark dates. `src/analysis/comparisons.py` and `src/pricing/catalog.py` own present reference relative-price math and **must not be retuned**. `src/pricing/github_copilot.py` owns reference acquisition and should not be made responsible for external benchmark costs. Web `src/application/projection.py` should publish bounded prepared benchmark display data; no third-party JS fetching or pricing math in the browser.
25. Use the current host/job/cache ownership and bounded execution for optional acquisition rather than creating a new background daemon. Source/price refresh and optional benchmark update are independent transactions. The new feature should remain compatible with pending **FR000650** (Web promotion to v81) and current guide/launcher naming at implementation time. Historical completed FR wording is immutable evidence.

## Acceptance checks

1. The Models page contains **two headings**, **four exact first-table headers** and **six exact second-table headers** in the requested order. No mixed Relative CCost and task cost in one table. Existing first table still sorts expensive reference rates first, promotion and release-date highlights intact; the second defaults to expensive benchmark attempts first and sorts independently by Model, Coding Client, Effort, USD/Task or Solved.
2. A published same-model/same-client fixture with **Medium, High and Max** yields three independent rows, no inferred values and correct model-name sort grouping. A different client using the same model is another row, not folded into a model-only average.
3. Numeric edge fixtures: pages 1–N with cheapest row on last page, unchanged raw denominator after sort/filter, positive/zero/missing cost, n_trials zero/invalid, ratio ties, mixed relative 1.0x, source accuracy 0–100, missing effort/ambiguous model, variant versions, partial/duplicated source pages and tiny positive USD/Task. Assert no false 1.0x from incomplete or zero-priced data and no accidental display-rounding sort.
4. **New highlights tests using only reference catalog release_date**: exact same model on both tables released today / six days ago / eight days ago; benchmark first appears today after an old release; model absent from reference catalog; ambiguous Sonnet version; same model with different effort/client; source refresh while highlight window expires; first-sighting notice independent. In every case the benchmark's own `date` and appearance do not control lime. **Promotions only on the GitHub reference table**.
5. Real Harbor public API contract verified or explicitly limited, one exact benchmark edition, complete pagination and source metadata; bounded secure read; cached last-good retained across failure, visible as-of; offline/no snapshot is benign; **reference table always works without Harbor**. No network call from sorting/hover, no API key and no raw local session information transmitted.
6. Browser UX in Chrome/Edge Classic/Web light/dark, 360px/zoom/horizontal pan, user input and accessibility: compact labels, source link, keyboard sorting, independent state, no clipped columns, intrinsic readable tooltip targets, short one-topic help or paragraph-separated multi-topic help and no giant tooltip slab. No promotion tint in benchmark.
7. Preserve reference costs/CCost, tokenmix sample, long-context arrows and warnings, existing model sample/caches, quota/account/Watch/CLI and version behavior. Update focused tests: **`development/tests/test_web_models.py`**, `test_model_comparison_tiers.py`, `test_web_price_refresh.py`, `test_web_overview.py`, benchmark parser/cache/HTTP tests, **`development/tests/integration/web_models.cjs`**, `web_overview.cjs`, model toolbar/ContextHelp browser probes, and current Web models documentation. Update `development/architecture/modules/web-help.md` and the current user guide when implementing. No implementation/testing required for the present FR-only commit.

## Explicit exclusions

No benchmark-based New/first-sighting dates, no reference-list promotions in the benchmark, no cost-per-success main column, no forced Max effort, no inferred nonpublished results, no merging different benchmark editions, no hardcoded per-model table, no user data upload, no remote benchmark execution, no new provider billing/price engine, no bundled API key, no paid service, no new runtime dependency and no wholesale rewrite of unrelated tooltips.

**Publication boundary now:** create `development/backlog/ready-to-develop/000870-000652-models-reference-pricing-and-terminal-bench-cost-per-task/FR.md` and advance `development/backlog/identity-state.json` to **652** together on current `main`, with *only those two files changed*.
