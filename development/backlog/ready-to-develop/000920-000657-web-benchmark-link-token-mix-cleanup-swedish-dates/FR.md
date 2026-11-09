# FR 000657 — Web polish: Artificial Analysis link, quiet Token Mix and Swedish date/time display

**Owner-approved Ready Feature Request, 2026-11-09.** New permanent identity **000657**, Ready priority **000920**, after FR000656 (000910). **FR-only publication now:** create this file and increment `development/backlog/identity-state.json` highWatermark **656 → 657** in one documentation-only commit on `main`. Do not edit or interrupt the already-started FR000656 implementation; no product code, tests, version, release or unrelated backlog changes in this publication.

## Purpose and scope

Three modest, independently testable UI improvements for the existing **Cost Guard Web** app:

1. After the two tables on **Models**, add a final standalone heading plus an outbound **Artificial Analysis** comparison link and one short explanation.
2. On **Token Mix**, remove the redundant visible `Partial` prefixes, repeated partial indicators and routine `Partial pricing.` status; move a concise, honest explanation into the already-existing overall token-count tooltip.
3. **Standardize all user-visible Web dates/times** to Swedish-style numeric date and 24-hour time, in page content **and all tooltips** across routes, including the separate Mini Watch Document PiP.

This is UI/presentation scope, **not** another source integration or a change to the underlying valuation, history or reporting.

## A. Models: third section for Artificial Analysis — link only, no imported data

FR000656 is already implementing **GitHub Reference Pricing** and **Coding Benchmark – Cost per Task**. Below the entire second benchmark table and its controls/empty state, add a **third clearly separated section**, visually aligned with the two headings above, titled for example **More Coding Benchmarks**.

Unlike the first two sections, **this section has no table, empty table shell, large card, colored background, refresh button, filters or fake rows**. Only:

- A normal, prominent external hyperlink labelled **Artificial Analysis – Coding Agent Index (performance vs cost)**.
- One compact English sentence describing the destination, e.g. **"Compare coding agents and effort settings by benchmark performance versus average USD cost per task."** Keep it concise, readable and nonpromotional; benchmark results are external, not verified/imported Cost Guard data.

**Verified official target:** https://artificialanalysis.ai/agents/coding-agents/

On that page, the chart is titled **Artificial Analysis Coding Agent Index vs. Cost per Task**: average USD API cost/task on the horizontal axis and benchmark performance/index score on the vertical axis, with distinct coding-agent/model configurations that can include different effort settings. The index is a composite across tasks, **not necessarily the percentage solved in the same standalone Terminal-Bench 4.0 cohort**; do not mislabel its score as Harbor's Solved%. It is a scatter/efficiency comparison; **do not promise connected effort-level lines unless the destination genuinely supports them**.

Ideally link directly to the chart **if a stable, tested official deep link exists** at implementation time; otherwise use the **verified official Coding Agent Index page above**, which actually contains the target chart. Do not invent an unverified hash, query flag or third-party mirror to simulate direct linking. Safe outbound `target="_blank"` and `rel="noopener noreferrer"`, keyboard focus, ordinary link styles and no hidden navigation side effects.

**No Artificial Analysis API keys, scraping, background fetch, raw data ingestion, benchmark blending, score normalization or licensing assumptions.** Harbor remains the sole data source of Cost Guard's own benchmark table. The link is simply a useful way to explore broader comparative efforts independently.

## B. Token Mix: remove repeated visible "Partial" noise, explain in title help

### Current verified behavior

`src/application/display.py::amount_tokens()` prepares `mix_*_cost`, `mix_total_cost` and `mix_total_tokens` with a literal **`Partial `** prefix on incompletely priced/observed values. `src/web/assets/token-mix.js` displays those in the four Input/Cached input/Cache write/Output overview figures and its model/publisher tables, marks incomplete-cost spans with `.partial`, and appends **`Partial pricing.`** (and sometimes **`Incomplete token telemetry.`**) in a separate `.token-mix-status` line. The **overall Total Token Mix title already has an intrinsic tooltip** with known observed tokens and an **Observed** timestamp built by `new Date(...).toLocaleString()`.

### Desired visible behavior

- On **the entire Token Mix page**, stop prefixing metric values with `Partial ` or surfacing routine `Partial pricing.` prose, repeated partial flags or warnings. This applies to the top four category CCost readouts, total tokens, total CCost, and **both** the model and publisher tables. A numeric value should be the normal value in the active Credits/USD unit, without literal `Partial`, an artificial `?` prefix or redundant dim/warning styling solely because its valuation is incomplete.
- Remove the separate **`Partial pricing.`** line under the overview. Prefer similarly moving routine **incomplete-token telemetry** prose into the same title tooltip rather than retaining another redundant passive warning; preserve genuinely actionable source/outage/unavailable states and empty-history messages when relevant.
- **Do not fabricate complete data or turn unknown amounts into zero.** Keep actual known subtotals and token counts, and keep meaningful `N/A` or unavailable entries where the relevant value cannot be calculated. Preserve the original `cost_complete`, `priced_requests`, `request_count`, exact token-category coverage and all raw numeric/sorting data. This FR only reduces noisy visible qualification **on this Web Token Mix surface**; do not globally rewrite CLI, Watch, Mini, Reports or the canonical pricing contract.
- Remove only Token Mix-specific `.partial` presentation effects when they no longer serve a purpose; keep normal layout, hierarchy, sortable columns and accessibility.

### One concise title tooltip paragraph for partial pricing

Keep the existing **hover/focus/touch tooltip on the large Total Token Mix token number/title**. It starts with the existing brief observed-token/scope explanation and **Observed** timestamp (in the standard Swedish date/time format from section C).

**When the aggregate `view.token_mix.cost_complete` is false and incomplete pricing is relevant, add one new paragraph after a blank line**, in plain English. Example:

> **Partial pricing:** Some recorded requests have no usable model price, so displayed CCost includes only known priced requests. Missing cost is not zero.

Where supported, a concise `X of Y requests priced` detail may improve clarity, but **no long diagnostics or calculation breakdown**. If pricing is complete, this paragraph is absent. If token telemetry is also incomplete and warrants explanation, add only a brief natural qualification in this tooltip; do not add multiple essays or routine visible warning rows. If no usage exists, avoid claiming positive partial costs. Keep the title tooltip's dynamic refresh and safe plain-text/keyboard/touch semantics intact. This title tooltip is the **deliberate exception** where the term `Partial pricing` may still appear on Token Mix; not in visible values/rows.

Other *existing* row-level help may retain truthful unavailable-cost reasons, but should not reintroduce repetitive visible `Partial` text. No new tooltip framework or data acquisition.

## C. Whole Web: consistent Swedish-format dates and 24-hour times

**Invariant:** Anywhere Cost Guard Web visibly renders a calendar date and/or clock time — labels, data cells, timestamps, status lines, source fetch/refresh information, date-range summaries, model release/promotional dates, account cards, exact reset details, report snapshots, session timelines, **every tooltip**, Mini Watch (Document PiP), and other rendered UI — use a consistent Swedish-style, year-first, numeric, **24-hour** representation. The user's report is that several currently use English/US browser-default formatting, including Token Mix's `Observed` help.

Preferred examples:

- **Full date/time:** `2026-11-09 21:45` (**YYYY-MM-DD HH:mm**), optionally seconds `:ss` only when useful.
- **Date only:** `2026-11-09` (**YYYY-MM-DD**).
- **Time only:** `21:45` (**HH:mm**).
- If essential for a precise cross-zone time, append a correctly derived UTC offset/time-zone identifier, **not** an AM/PM marker or American date.

**Never** display `11/09/2026`, `9/11/2026`, `11/9/2026, 9:45 PM`, `Nov 9, 2026`, English month-first dates, 12-hour AM/PM or browser-locale-dependent variants. For date-only release/promotional dates already in year-first format, preserve the compact form. Do not force full timestamps into locations that intentionally display just `HH:mm` or a date.

**Timezone:** preserve Cost Guard's **configured-local timezone convention** (the current report uses server-prepared `src/analysis/timezones.py::format_local_timestamp()` in many places). Use a single reliable shared display path or existing prepared display tokens rather than copying ad-hoc browser clock logic. Date-only/source-UTC semantics must remain truthful; do not accidentally shift calendar dates in ways that change model release dates, quota resets or historical membership. When unavoidable browser-side formatting is required, explicitly choose the correct timezone and numeric 24-hour output, never depend on the user's operating-system/browser locale. Preserve DST and exact source timestamps behind the formatting.

**Audit actual shipped Web code**, especially `src/web/assets/token-mix.js` (observed help), `app.js` (host/source status dates), `render.js` (snapshot and retained observation times), `benchmark.js` (fetched date, accounting for FR000656), `sessions.js`, `session.js`, Watch, Mini, Accounts, AI Stats, pricing, and other scripts that build visible dates or help text. Some files already implement `YYYY-MM-DD HH:mm`; **reuse those and don't rewrite them unnecessarily**. Keep sorting and machine timestamps numeric/raw, do not translate raw provider payloads, JSON identifiers, diagnostic logs, filenames, URL parameters, fixture data, CLI or unrelated native OS UI. This is a **Web display normalization**, not a data model migration.

## D. Coordination, boundaries and acceptance

This FR runs **after FR000656**, which is already underway. Do not move, reauthor or prematurely complete FR000656; integrate the final Artificial Analysis section with the *implemented* two-section Models layout and avoid fighting FR000656's agreed source toolbars/refresh/date rules. FR000656's own browser tests and benchmark mapping still apply.

**Acceptance criteria:**

1. **Models** ends in an unboxed **More Coding Benchmarks** heading with exactly one obvious official **Artificial Analysis Coding Agent Index** link and a one-sentence explanation; navigation reaches the site's coding-agent cost-versus-performance visualization. No API, merged benchmark rows, misleading Harbor equality or invented chart deep link.
2. Token Mix overview, both detailed tables and status area show **no routine visible `Partial` prefixes, `?` cost qualifiers or redundant partial pricing messages**, while known figures, true `N/A` and genuine operational failures stay truthful; no shadowed/dimmed partial-only styling.
3. On incomplete pricing, the large Total Token Mix title's **existing tooltip** has an additional separated, short **Partial pricing** explanation of known versus missing valuations; complete data omits it. Existing observed token text and observed timestamp remain present and accurate.
4. All **user-facing rendered date/time formats on every Web route and relevant tooltip**, including Mini Document PiP, use approved Swedish-style numeric date/24-hour time in the configured timezone. Test under an explicitly **en-US browser locale**, Swedish locale, different OS timezones and relevant UTC/DST boundaries: no US-style ordering, English month names or AM/PM leak into UI.
5. Dates/times retain their underlying numeric source, sort/refresh semantics, reset/release meaning, time-zone accuracy, and keyboard/accessibility behavior. Internal REST/JSON timestamps and CLI are unchanged.
6. Targeted deterministic server-token/unit tests, Token Mix DOM/help tests, full-page rendering searches and real browser/Document PiP probes cover partial pricing, partial telemetry, completely priced usage, empty history, Credits/USD, observed help, visible status, all route surfaces, hover/focus/touch, theme, narrow view and 12-hour-locale regression. No new paid AI calls or broader product changes.
