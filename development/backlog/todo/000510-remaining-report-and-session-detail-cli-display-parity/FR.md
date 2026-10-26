# FR 000510 — Finish CLI-first presentation parity in remaining Web Beta reports and session detail

## Goal

After fixing Overview, Watch, Sessions list, Models and Accounts in focused FRs, complete the remaining user-visible CLI-first pass so no report route still looks like raw API data pasted into HTML. Include full session Snapshot/Live detail, Date/Range Reports and historical Token Mix, plus cross-view consistency, without altering already delivered historical analysis.

## Required behavior

- Audit each remaining route against the matching CLI mode using the same canonical fixtures, clock, timezone and source snapshot. Match visible table fields, values, meaningful decimal/text formatting, order, totals and total placement, section labels, context warnings, incomplete/unknown/running semantics, session-child breakdown, lifecycle/provisional indications and explanatory emphasis. Only intentional browser interactions/layout may differ.
- Session-detail Snapshot and Live keep the existing **complete** 50-row revision-aware backend page contract, all-history totals and stable row anchors; do not replace it with a truncated Watch slice. Make paging, latest-jump, refresh/freeze modes and source provenance easy to understand without a wall of status prose. Preserve selection/scroll/focus under live updates.
- Date/Range shows configured-local inclusive boundaries with human-readable dates (not raw epoch milliseconds as default explanatory text), canonical totals/duration and links to relevant session detail. Token Mix remains an explicit user-started potentially expensive historical capture with honest progress, cancellation and no automatic scanning on navigation.
- Replace unrounded raw account/cost/tokens/quota/percentage/duration text with shared FR000430 display rules, but preserve intentionally exact raw reference prices and canonical backend values. Place help/warnings contextually; move repeated technical implementation notes into small optional explanations.
- Check cross-view navigation, naming, status and visual consistency with FR000440, including stopped/offline state FR000500. Keep no-provider-call-on-navigation, independent source ownership, authentication and no user-data persistence in browser.
- Add a final **owner-facing browser review matrix** for Overview, Watch, Sessions, Models, Accounts, Date/Range, Token Mix and session Snapshot/Live (Windows first; macOS limitations explicit); record any accepted intentional differences from CLI. This is scoped Beta acceptance evidence, **not** an invented permanent release gate or substitute for FR000410's cross-platform CI.

## Acceptance

- Side-by-side deterministic CLI/report-to-Web fixture checks and real-browser screenshots/inspection confirm visible tables, labels/formatting, empty/running/partial/unknown states, totals and source scope. Report remaining mismatches honestly, don't claim semantic parity tests alone prove attractive design.
- A normal user can navigate from Overview/Watch/Sessions to complete detail and back, browse long sessions, and use date/Token Mix actions without being required to understand API contracts or raw floats.
- Existing CLI, source valuations, history retention, account observations, session security and standalone server lifecycle remain intact.

Relevant owners: `src/web/assets/session.js`, `render.js`, `reports.js`, `app.css`, `src/presentation/`, `src/application/session_detail.py`, and established Web view/detail tests.