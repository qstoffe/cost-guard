# FR 000656 — Models: streamlined benchmark table, unified controls and Copilot-based filtering

**Owner-approved Ready Feature Request, 2026-11-09; updated with additional owner-approved scope the same day.** Preserve permanent identity **000656** and Ready priority **000910** following FR000655 (000900). **FR-only update:** revise this existing `FR.md` on `main`, without advancing the backlog identity highWatermark (already **656**) or changing product code, tests or releases at publication.

## Goal

On **Cost Guard Web → Models**, the new **Coding Benchmark – Cost per Task** table (introduced by completed FR000652) differs unnecessarily from the pricing table: a surrounding bordered/background panel, inconsistent source/date/refresh controls, no manual Harbor fetch, and too many non-Copilot or low-interest rows. Harmonize the two sections, keep their independent data sources, and make the benchmark a compact five-column table. Move two useful but secondary benchmark fields into targeted cell-value tooltips, introduce a dynamic multiselect Effort filter, and improve the **GitHub Reference Pricing** table's Relative Price List Cost explanatory help without changing its math.

This update explicitly **supersedes** this FR's earlier seven-column benchmark design: **USD/Task** and **Coding Client** are no longer visible columns. **Effort stays visible as column 3** as well as being filterable.

## A. Unboxed sections, consistent titles, source controls and refresh

1. The two section headings must be **GitHub Reference Pricing** (rename the existing *Models Reference Pricing* heading) and **Coding Benchmark – Cost per Task** (keep that heading). Separate them with clearly visible vertical whitespace, including space after the upper table and its notes.
2. Remove the benchmark's outer **group box/card**: no surrounding decorative border, background panel or rounded frame around the benchmark section/table. Put the lower heading, toolbar, filters and table directly in the page flow. Keep modest table-internal separators and header styling for readability, but no redundant enclosing card.
3. Under **each** heading, make the source toolbar consistent in CSS typography, wrapping, spacing, link style, button size/alignment, status and fetched-time placement. Reuse shared UI styles/components when practical.
   - **GitHub Copilot:** retain **Refresh price list**, add a real **View source** link to the official Copilot models/pricing reference: https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing
   - **Terminal-Bench 4.0 · Harbor Hub:** retain the real **View source** link to https://hub.harborframework.com/datasets/terminal-bench/terminal-bench/4 and add **Refresh benchmark**.
   - Hyperlinks open the real official source without triggering refresh; do not construct URLs from model names or untrusted source labels.
4. Both use the **same configured-local, Swedish-style 24-hour fetched timestamp** (example `2026-11-09 21:45`, `YYYY-MM-DD HH:mm`). Match the existing GitHub pricing time formatting rather than using benchmark's browser-default locale-specific `new Date(...).toLocaleString()`. Preserve UTC/source timestamps internally; **Last fetched** means last *successful* retrieval, not the click or failed request. Use consistent concise unavailable text.
5. **Refresh benchmark must actually trigger a new Harbor source request** on user action even when the automatic 24-hour benchmark cache is fresh; simply reloading the local GET cache is insufficient. Reuse the existing host-owned `BenchmarkLane` worker/caching path, with an authenticated bounded/coalesced manual refresh action, brief Refreshing state and quiet success/failure feedback. Disable/coalesce repeated actions while busy. A failure retains previous good rows/fetch timestamp; Harbor errors must not block or reprice GitHub reference data. Keep ordinary 24-hour background freshness, established request/time/security budgets and independent last-good behavior.

## B. Benchmark filters: dynamic Effort dropdown + two Copilot checkboxes

Immediately above the benchmark table, place three compact controls in this **visual order**:

1. **Effort levels** — a dropdown containing a **checkbox list** (multi-select).
2. **Show all Copilot-priced models** — an ordinary checkbox, **unchecked** by default.
3. **Latest versions only** — an ordinary checkbox, **checked** by default.

The two Copilot checkboxes must have the **same wording, look and filtering semantics** as the reference pricing table's existing controls, but their selection state is **independent** of the upper table. The Effort dropdown is a third, benchmark-only filter; do not replace the two visible checkboxes with a combined dropdown.

### Effort levels dropdown

- Derive the available options **only from distinct effort values actually published in the current complete Terminal-Bench 4.0 / Harbor Hub dataset**, such as Low, Medium, High, Max or XHigh if and only if they occur. Do not hardcode a list, infer levels from model/provider, or add levels belonging to another benchmark edition. The choices must not disappear because a Copilot checkbox has hidden all rows for a level.
- **All existing effort options checked by default.** Users can uncheck any subset, e.g. keep only **High** to show only benchmark configurations actually tested at High. The visible **Effort column remains**; this filter does not replace it.
- If a valid benchmark result has an **unpublished/missing effort**, present a clearly labeled **Not specified** option when needed; its row still displays `N/A` and it is initially included. This is a truthful missing-value choice, not a fabricated effort level.
- Effort filter changes apply **locally and immediately**, without new HTTP fetches or recalculating benchmark results. Zero selected levels yield a clear *No matching benchmark rows* state; do not silently reset to all.
- On source refresh, reconcile the options against the source's new actual effort levels. If the user is still using default All, newly published levels are selected automatically. If the user chose a subset, preserve that subset and do not unexpectedly include new levels. Keep state through sorting/navigation where the benchmark view already persists.
- The dropdown should be compact and keyboard/touch accessible, with clear checked states, helpful collapsed selection summary and ordinary dismiss/outside-click behavior. Avoid new modal/help framework or excessive width.

### Copilot-model filters and non-negotiable eligibility

**Show all Copilot-priced models** unchecked restricts to benchmark rows whose confidently matched GitHub-priced models are currently selectable in OpenCode, using the same existing `model_catalog.rows[].selectable` semantics and fail-open behavior when availability cannot be verified. Checked admits **all matched GitHub Copilot-priced** models regardless of selectability.

**Latest versions only** checked hides superseded GitHub model versions according to the existing `superseded` / `superseded_selectable` policy and the other checkbox; unchecked permits historical versions **only where Harbor actually published a matching configuration**.

**Hard maximum for every filter combination:** benchmark results can include **only rows matching a model actually present in the GitHub Copilot reference price catalog**. Even Show all checked + Latest unchecked + all efforts selected must never show unmatched Harbor-only models, and must never fabricate rows for GitHub models with no benchmark result. The effort filter further narrows this intersection. Neither checkbox changes which upstream Harbor results are fetched/cached.

### Safe model matching and naming

Reuse the validated **publisher + exact/versioned model identity** mapping and supported source-backed equivalences (e.g. the existing verified Claude prefix exception). **No fuzzy family substring match.** Show the corresponding GitHub catalog's **Publisher** and canonical **Model** names, not Harbor's inconsistent display variant, while retaining the original Harbor row/configuration and accurate source data internally. If the match, publisher or version is ambiguous, **exclude** that Harbor row from this view rather than guessing. Multiple published client and effort variants of a single matched model remain distinct rows.

Only the **GitHub reference release date**, not any benchmark submission date/new client/effort, determines the existing lime **New** highlight. GitHub promotions/prices do not alter Harbor benchmark task cost. Presence in the GitHub catalog is not proof of the user's subscription entitlement.

## C. Exact five columns and targeted row-value help

Replace the benchmark's current six columns (and the earlier seven-column proposal in this FR) with **exactly five visible columns, in this exact order**:

| # | Column | Contents |
| --- | --- | --- |
| 1 | **Publisher** | Matched canonical GitHub Publisher |
| 2 | **Model** | Matched canonical GitHub Model, with supported New state; **value tooltip contains Coding Client** |
| 3 | **Effort** | Published tested reasoning-effort level; remains visible even though filterable |
| 4 | **Relative Task Cost** | Existing source-derived relative ratio; **value tooltip contains USD/Task** |
| 5 | **Solved** | Existing benchmark solved percentage; **only column that grows to fill leftover width** |

**USD/Task:** Remove the dedicated column entirely, but keep the source-derived number and the numeric sort/provenance data. Hovering, focusing or tapping **each Relative Task Cost cell's actual numeric value** (e.g. `65.4x`) must reveal that same row's USD-per-attempt amount, with a concise **Terminal-Bench 4.0 · Harbor Hub** identification. Suggested short text (example amount is fictional):

    Terminal-Bench 4.0 · Harbor Hub
    USD/Task: $14.23 per attempted task

State clearly by this short wording that the amount is the published benchmark average per task *attempt* (failures included), not actual billing/Cost Guard CCost. Keep correct exact-source zero, partial/unavailable and small-positive formatting; never invent a USD amount when the source is missing. Keep header meaning help distinct from row-value help.

**Coding Client:** Remove the dedicated column entirely, but hover/focus/tap on **each Model cell's displayed name** must show the **actual Coding Client for that specific Harbor configuration**, e.g. `Coding Client: Claude Code`. If a version is genuinely published, it may also be shown, and brief existing source-configuration facts may be retained. Do **not** assume the client from a model's publisher or provide a generic client shared by every variant. If the same Model has multiple clients/efforts, each row's tooltip must correctly reveal its **own** client; never merge or discard distinct benchmark configurations.

Reuse existing safe intrinsic `ContextHelp.value` hover/focus/touch behavior on **just the cell value**, not an entire row, and never render untrusted source text as HTML. Removing visible columns must not remove their data/tooltip accessibility.

### Sizing, sorting and semantics

- **Publisher, Model, Effort, Relative Task Cost** must be compact *intrinsic/min-content fitting* tracks, without wasteful arbitrary 12ch/30ch minimums, clipped ellipses or the benchmark's unconditional 52rem minimum width. **Solved** alone expands to fill the rest of the table/available space. Keep header and cell alignment compact, with no loss of readable labels or values; truly narrow layouts may scroll horizontally.
- All **five visible columns** remain sortable and keyboard accessible in their new order; benchmark default remains **Relative Task Cost descending** (fourth visible column, zero-based index 3), with independent sort state and deterministic ties. Hidden USD/Task and Coding Client do not require their own visible sort headers.
- Filtering **must not change the relative-cost denominator**: it still comes from the lowest positive USD/Task of the full valid **Terminal-Bench 4.0** edition, even when most source rows are filtered out. A visible minimum ratio above 1.0x can therefore be correct.
- Preserve source task cost, solved rate, client/effort configuration identity, row data precision, true zero/unknown/partial semantics, New highlighting and USD-only benchmark values, independent of the user's reference-price Credits/USD setting.
- Keep the two source tables independent and maintain good layout in Classic/Web light/dark, narrow viewports and browser zoom.

## D. GitHub Reference Pricing: Relative Price List Cost tooltips

These additional owner-approved changes apply to the **first, GitHub Reference Pricing table**, not the Harbor benchmark. Keep its visible column layout, reference-price ratios, sorting and sampled token-mix computation intact.

### Column-header help: retain two existing paragraphs, add a third

The **Relative Price List Cost** column header currently has two useful short paragraphs. **Preserve both existing paragraphs unchanged in meaning and wording**, including the distinction from task performance:

> Reference-price ratio to the cheapest comparable model (1.0x).
>
> Uses the same recent token mix for every model and price tier; not task performance.

After another blank line, append **exactly one new third paragraph, consisting of two short sentences**, such as:

> Token Mix is the percentage split of Input, Cached input, Cache write and Output tokens. It is pooled from your latest up to 100 completed, priceable prompts.

Do not add a lengthy formula, sample table, provider disclaimer or fourth paragraph to this **header** tooltip. "Up to 100" is intentional: the eligible sample can be smaller, and it consists of **completed, non-aborted, reference-priceable prompts** across the available history, not necessarily the latest 100 prompts of any kind. This is the **pooled token-share distribution**, not an arithmetic average of per-prompt percentages and not the separate Token Mix report's potentially different sample.

### Every numeric Relative Price List Cost value: GitHub rates, then observed Token Mix

Attach an intrinsic **hover/focus/touch tooltip to every row's actual Relative Price List Cost value**, including rows with multiple context-tier ratios and promotional markers. Do not leave most regular rows without help simply because the existing `modelRelative(..., evidence=false)` disables the generic evidence help. Scope the hover/focus target to the visible value, **not** the full cell, row or whole table.

The **core tooltip has two clearly separated, scannable blocks**:

1. **GitHub published USD token prices for this model** (first block). Show the exact source-backed price rates in **USD per 1 million tokens**, visibly named **Input, Cached input, Cache write and Output**, rather than just an unlabeled slash-separated sequence. Reflect the **actual GitHub reference pricing snapshot used for the displayed relative comparison**, with each distinct published context/price tier labeled by its real input-context threshold when present. Preserve rate precision (including small positive fractions); never round to arbitrary two-decimal currency values, invent missing rates, confuse USD per million tokens with USD per prompt, or use Harbor USD/Task prices here. A compact layout such as these fictional values is sufficient:

       GitHub Copilot · USD / 1M tokens
       Input $3 · Cached input $0.30
       Cache write $3.75 · Output $15
       Higher context tier (>200K): [same four labeled published rates, if applicable]

   Where a field/tier is not actually published, show a truthful unavailable marker (or omit the unsupported line) instead of claiming a rate. Preserve any **existing promotion help for a promoted ratio** (e.g. promotion description and end/resume information) within or after the price information without overwriting the two primary blocks or misrepresenting discounted/standard rates. Do not duplicate unrelated header explanations.

2. **Actual shared Token Mix percentages** (second block, after one blank line). Show the **same four category names in the same order** with their percentage shares: Input, Cached input, Cache write, Output. Label the shared sample succinctly, ideally with the **real eligible prompt count** (e.g. `Token Mix · 87 completed priced prompts`, illustrative). Every model row uses the **same pooled I/C/W/O comparison mix**, exactly the one used to compute its Relative Price List Cost, regardless of which row, filter or context tier is hovered. Provide compact percentage values (use a coherent 100%-summing display convention when the mix is known); no raw token counts or long explanation is needed.

   When there is **no eligible priceable sample** or the true percentage distribution cannot be established, do **not** present the existing hidden default/sorting fallback mix as the user's observed history. Give a brief, accurate unavailable/empty sample description instead. In particular, don't silently substitute `view.token_mix` from the broader report if its included prompts differ from this comparison's eligible sample.

**Data boundary:** `src/reports/model_comparison.py::price_summary()` already prepares per-model, per-tier published GitHub I/C/W/O USD-per-million rates, and `src/application/projection.py::model_rows()` already exports `price_summary`; format/restructure this securely for readable labeled help while preserving native digits and tier boundaries. The **comparison mix** is currently produced from `src/reports/service.py::_relative_usage(latest_prompts(...))` via `src/pricing/catalog.py::normalized_average_token_mix()` and reused by `src/analysis/comparisons.py::model_comparison_rows()`. Ensure its four shares and actual sample size are available as **server-prepared read-only help data in the same report snapshot**; do not reconstruct the mix from rendered percentages or rescan/prerice history in the browser. Keep the pricing/ratio math and other Token Mix definitions unchanged.

The tooltip must update coherently with reference price refresh, report/mix sample refresh and any relevant retained result, without stale model/tier/snapshot values or re-fetching on hover. Retain safe plain-text `ContextHelp.value` semantics, readable blank-line spacing, keyboard/touch support, selection/copy and existing promotional details in Classic/Web light/dark.

## E. Implementation scope and acceptance

**Likely ownership:** `src/web/assets/benchmark.js` (current six-column table, row tooltips, effort dropdown, sort and fetched display); `src/web/assets/render.js::overviewModels()`, `modelHeadingHelp()` and `modelRelative()` (reference heading, source link, catalog filters, header help and pricing value help); `src/web/assets/app.css` (panel removal, unified toolbars, compact five-column layout); `src/application/benchmark.py` (exact matched GitHub model, publisher, readiness flags while preserving Harbor raw rows); `src/reports/model_comparison.py`, `src/reports/service.py`, `src/application/projection.py` and `src/application/display.py` (existing exact USD pricing tiers and matching shared reference token mix prepared for value help); `src/web/benchmark.py::BenchmarkLane` and `src/web/http.py` (authenticated forced manual source refresh). Reuse existing catalog `selectable`, `superseded` and `superseded_selectable` and configured-local time formatting. Preserve Web/host ownership boundaries, optional Harbor read/caching, full-precision reference valuation and other Token Mix/CLI/report behavior.

**Acceptance criteria:**

1. Page headings are **GitHub Reference Pricing** and **Coding Benchmark – Cost per Task** with sensible vertical separation; the benchmark has no outer bordered/tinted background group box.
2. Both sections show a matching source toolbar, verified external View source link, functioning independent Refresh action, and identical configured-local `YYYY-MM-DD HH:mm` last-successful-fetch formatting. Forced Harbor refresh really accesses Harbor when cache is fresh and retains last-good data/date after failure.
3. Benchmark filter controls appear in order **Effort levels dropdown**, **Show all Copilot-priced models** (off by default), **Latest versions only** (on by default). Source-driven effort options are all checked initially; filtering High-only leaves only actual High source configurations and no unrelated rows.
4. All permutations of the Copilot filter pair and representative Effort subsets stay within the source-backed **Harbor ∩ GitHub-priced models** intersection; ambiguous/unmatched Harbor models stay hidden, and model names/publishers reflect canonical GitHub reference identities.
5. The benchmark has **exactly five columns: Publisher | Model | Effort | Relative Task Cost | Solved**. First four shrink to useful content widths without ellipsis, **Solved** fills remaining space. The old USD/Task and Coding Client columns and their header sorting controls are absent.
6. Hover/focus/tap on a **Relative Task Cost value** shows *that row's* exact available USD/Task and Harbor/Terminal-Bench provenance; the **Model value** shows *that row's* real Coding Client. Multiple clients/efforts for one model retain distinct values, row help and valid source identities.
7. Sorting/filtering preserves the **full-edition task-cost denominator**, correct USD and Solved figures, GitHub-release-driven New marking, independently retained source/sort state and no new revaluation of model prices. Test source reload/changed efforts, zero selected options, missing efforts, early loading/error/retained state and keyboard/touch/help behavior.
8. The GitHub **Relative Price List Cost** header tooltip retains its existing first two paragraphs and adds a **third paragraph of exactly two short Token Mix sentences** naming I/C/W/O and the latest **up to 100 completed priceable prompts**.
9. Every GitHub **Relative Price List Cost** numeric cell value has intrinsic hover/focus/touch help: **first** the GitHub model's exact published USD/1M-token rates by I/C/W/O and price tier, **then** the same true pooled I/C/W/O comparison percentages and eligible sample count, split by a blank line. Promoted rows retain promotion facts; no reference rates, shares or tiers are invented. No-sample help does not expose the hidden sorting fallback as observed user usage.
10. Targeted server-contract, pricing/mix and DOM/real browser/HTTP tests cover matching, manual refetch, model/effort filters, formatted dates, source links, responsive layout/zoom/themes, accessible help and status states. Explicitly cover one-/multi-tier GitHub prices, exact tiny rate digits, changed price/promotions, empty/fewer-than-100/full-100 comparison samples, percentage-source parity and retained tooltip refresh. No live inference or unrelated code, CLI, accounts, pricing math or token valuation changes are needed.
