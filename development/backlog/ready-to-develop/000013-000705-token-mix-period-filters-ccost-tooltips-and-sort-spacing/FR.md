# FR 000705 — Token Mix period filters, compact CCost tooltips, consistent spacing and single sort arrows

**Owner-approved Ready to Develop — 2026-11-13.** Permanent identity **000705**, Ready priority **000013**, following FR000704 (000012). **Feature-request publication only:** add this standalone specification and advance development/backlog/identity-state.json highWatermark from 704 to 705 in the same documentation-only commit. Do not implement code, change other FRs, modify versions/releases, or migrate to the separately provisioned private backlog repo during this authoring request.

## Owner request / intended result

Make the Web **Token Mix** page useful for selectable time periods, reclaim substantial table width by moving four per-category CCost columns into percentage-value tooltips in **both** tables, simplify header help, and fix the visible double-sort-arrow bug. Make the period button row on **Token Mix, AI Stats and Sessions** align consistently below the top navigation. The existing Sessions page's tighter top spacing is the visual reference.

This is **one cohesive Web UX request**, not a change to the historical CLI Token Mix output. Preserve accurate model/request attribution, pricing semantics and useful accessibility.

## 1. Five period filters, placed ABOVE the Token Mix heading

- Add the same five period buttons and ordering used by AI Stats and Sessions: **Today | 7 days | 30 days | This month | All time**. Place this single button row at the very top of the Token Mix content, **above** the existing **Total Token Mix %** heading, rather than below it. Preserve the established visual button styles, selected state and keyboard/focus/touch behavior.
- **Default Token Mix to All time**, including a fresh visit or reload without an explicit period. Do **not** change AI Stats' current 30 days default or Sessions' current Today default.
- Selecting a period must update **every dependent Token Mix datum**, not just visual labels: exact recorded total tokens, the four total-category percentages and category CCosts, both model/publisher row populations, Prompts, Calls, Tokens, percentages, Total CCost, sorting values, and all value/heading tooltips. Rows belonging only to another period must disappear; no mixing All time summary with a short-window table.
- Use the **same period IDs/window meanings and configured timezone** as the existing AI Stats/Sessions controls where applicable: Today and This month follow local calendar boundaries; 7 days and 30 days are rolling windows; All time covers the complete currently available historical source scope. A request's membership and its token/cost contribution must use consistent source-backed event-time rules; avoid boundary double counts, excluded valid child usage or inclusion of out-of-scope usage.
- Perform **real period-scoped backend/report aggregation**, preserving canonical deduplication, source read-only constraints, per-request model/tier category valuation, publisher grouping, large exact token counts and genuine partial/unknown states. Do not implement a display-only percentage filter or derive category CCost as percentage × total cost.
- Avoid unbounded full-history rescans for rapid period changes. Reuse safe cached/derived history and existing report loading, cancellation, quiet refresh and last-good behavior. Keep period/source/timezone/catalog identities distinct so slow or stale responses cannot overwrite a newer selection. On normal loading/refresh, do not flash old/stale values as though they belonged to the newly selected period. Keep sorting state where sensible; changing period must not change Credits/USD or silently change other pages' period selections.

## 2. Consistent vertical spacing beneath the main navigation

- **AI Stats currently has extra vertical spacing** between the top main menu/navigation and its period buttons; **Sessions** does not. Remove the discrepancy and use the **Sessions period row's compact top spacing** as the reference for **AI Stats and Token Mix**.
- All three pages' period button rows should visually begin at the same distance from the top navigation and have consistent horizontal alignment, controls, wrapping and gap. Do not add a separate oversized section heading or spacer above Token Mix filters. Keep appropriate spacing **below** the controls before Token Mix's Total heading.
- Check desktop and narrow/mobile widths and both Web themes; avoid changing unrelated page layouts.

## 3. Make BOTH tables 9 columns, placing category CCost in percentage-value tooltips

Today, each table has 13 columns. Remove the four category CCost columns **in both Token Mix % by model and Token Mix % by publisher**. The sole remaining visible cost column is **Total CCost**. Keep this exact nine-column order:

1. Model (or Publisher)
2. Prompts
3. Calls
4. Tokens
5. Input %
6. Cached input %
7. Cache write %
8. Output %
9. Total CCost

- The four category percent **data cells**, not just header labels, become hover/focus/touch help targets. Hovering/focusing a percentage value shows that **row's matching category CCost**, with an unambiguous category label and the current Credits/USD unit. Example: percentage shown as 17%; tooltip **Input CCost: 123 Credits** (synthetic). Do this for Input, Cached input, Cache write and Output in each table, on every applicable row. A category's token share is still the visible percentage; its CCost is only the tooltip, not a substitute percentage or an added column.
- Keep source-backed category cost precision and truthful missing/partial pricing semantics. Where category pricing is incomplete or unavailable, make that clear in the category tooltip rather than presenting fabricated zero or certifying a partial subtotal as complete. Retain any existing meaningful exceptional token/total-cost help, but do not show duplicate competing popovers. The normal visual table should stay concise.
- Keep Total CCost visible and sortable, retaining its reference-valuation semantics; do not alter the compact total category summary above the tables unless needed to reflect the selected period.
- **Every remaining column remains sortable**, with independent sorts for model and publisher tables, actual underlying integer/share/Decimal values, unknowns last and stable tie behavior. Default remains **Total CCost descending**. Do not accidentally sort shares by the tooltip cost. Improve narrow viewport readability without clipping model/publisher names unnecessarily.

## 4. Replace the Total Token Mix heading tooltip with a short exact-value/date tooltip

For the heading **Total Token Mix % · [compact token count] tokens** beneath the new period filters:

- Completely replace the current verbose tooltip. Show only (a) **the exact, unrounded recorded token count** for the selected period, and (b) a short sentence/label such as **Recorded tokens for the selected period** with the **actual start and end dates** for that selected period, in the configured local timezone.
- A concise illustrative format: **123,456,789 recorded tokens for the selected period** followed by **2026-11-07 – 2026-11-13**. Values and dates are illustrative only. For rolling periods, represent the actual time boundaries accurately if date-only notation would obscure them; for All time use the source-backed range of available recorded history, never invent a first/last date. The displayed exact quantity should be the actual recorded/known number, not a rounded K/M/B/T string. Do not silently imply complete telemetry when it is not known.
- **Remove** all old heading-tooltip text about **the same available shown history as the CLI**, deleted/unreconstructed history, observation timestamps, **Partial pricing**, **CCost includes only known priced requests**, and other extended cost/telemetry explanations. This simplification is scoped to the **heading tooltip**: maintain truthful partial/unknown state where genuinely necessary in the data values and other appropriate UI surfaces, not as a lengthy heading disclaimer.
- Switching any period immediately changes the tooltip's numeric total and date bounds along with the visible summary; the tooltip must never remain bound to the previous period.

## 5. Header help and sorting bug in BOTH tables

- **Remove the Model header tooltip entirely** in Token Mix % by model. Keep Model as an ordinary sortable heading. Do not automatically remove Publisher's useful manufacturer-versus-provider definition unless it is genuinely redundant; the requested unconditional removal applies specifically to Model.
- **Keep the Prompts header tooltip** and its explanation of distinct contributing prompts / nonadditive mixed-model counts, but remove the sorting sentence.
- **Remove the 'Activate to sort; activate again to reverse' / 'Activate to sort' instruction from EVERY table header tooltip** on Token Mix, in both model and publisher grids. Keep concise meaningful metric definitions where currently present; do not substitute a different verbose sorting tutorial. Ordinary sortable-button semantics, keyboard actions and accessible aria-sort indicators remain intact.
- Fix the current bug where sorting a table sometimes displays **two adjacent direction arrows** at the active column header. There must be **only one visible arrow** indicating the active direction, not duplicate icons/glyphs from the custom sort-arrow span plus any shared styling. The direction must actually match the selected numeric/text sort. Check both tables, repeated reverse sorts, updates and both themes; use exactly one accessible sort-state mechanism plus one visible glyph.

## Implementation leads / non-goals

- Relevant current client code: src/web/assets/token-mix.js (13-column Table, numeric column mapping, per-cell help, titleHelp, single manually appended sort-arrow), src/web/assets/ai-stats.js and sessions.js (five controls/period IDs), src/web/assets/app.css (shared .ai-stats-periods, page top spacing, table/sort appearance), src/web/assets/help.js, and the Web route/report loading layer. Relevant backend: src/reports/token_mix_history.py and period/window definitions in existing Stats/Sessions report services. Verify against the current main branch when selected.
- Keep historical CLI --token-mix behavior, existing source-access/privacy boundaries, other Web pages, reference CCost vs billed distinctions and the prior ~five-minute quiet freshness/last-good contract. This FR does **not** ask to remove pricing availability truth, invent missing usage, introduce billing estimates, or implement the separate backlog-repo migration.
- Coordinate with pending FR000703 (app-wide stable refresh) and completed FR000596 (Token Mix report composition) instead of undoing their intended behavior.

## Acceptance / focused verification

1. Token Mix opens with **All time** selected and its five period buttons **above** Total Token Mix %. Selecting each period returns period-correct summary, two tables, row values, tooltip values and truthful dates; AI Stats/Sessions retain their own defaults.
2. Token Mix, AI Stats and Sessions show identical compact period-row positioning relative to the top navigation, including narrow widths.
3. Both Token Mix tables show **9 columns exactly** and only **Total CCost** as a visible CCost column. Hover/focus/touch on each category **percentage value** reveals its matching CCost with correct unit, source semantics and missing/partial handling.
4. Total Token Mix heading tooltip contains only the exact recorded token number, selected-period description and real local date/date-time range; no old CLI-history, observation, partial-pricing or CCost boilerplate.
5. Model header has **no tooltip**; Prompts keeps only its meaningful count explanation; all remaining headers lack **Activate to sort** text. Sorting in both grids displays **one** correct active arrow; all nine columns sort correctly independently.
6. Focused JS/Python + browser tests cover five date windows (midnight, rolling boundaries, month change and timezone/DST where relevant), stale response/refresh, model/publisher reconciliation, partial pricing, very large token counts, current unit switch, precise percent sort versus tooltip cost, no duplicate arrows, theme/mobile layout, and keyboard/focus/tooltips. No paid inference is needed.

**Publication boundary:** FR documentation and identity-state only; do not implement in this publication.