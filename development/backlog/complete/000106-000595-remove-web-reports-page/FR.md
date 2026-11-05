# FR 000595 — Web Beta: retire the Reports page and navigation entry

## Owner request

**Owner-approved executable Ready Feature Request, 2026-11-05.** Remove the **Reports** page completely from **Cost Guard Web Beta**. Once the modern, sortable, automatically refreshed Sessions catalog requested in **FR000593** exists, the separate date-report UI is redundant for the owner's workflow. Remove the top-navigation item and the entire Web Reports user experience instead of restyling it or hiding it behind another menu.

The owner deliberately **does not request a Sessions date-range filter now**. Sorting on **Last activity** (as well as the other Sessions columns) is sufficient as a first step, even though sorting does not reproduce every historical date-report scope/filtering operation. Do not attempt to preserve Reports merely because a future date filter might be useful.

This FR is for **backlog authoring only**; publish it after currently Ready **FR000594** without changing any source code, test, user documentation, version or release metadata in this authoring session.

## Required Web changes

1. **Remove the Reports link** (currently `<a href="#/reports">Reports</a>`) from the main navigation in `src/web/assets/index.html`. No replacement menu item, shortcut, tab or report card.
2. **Retire the entire Reports page/route**: the `/#/reports` route, `/#/reports?date=YYYY-MM-DD[:YYYY-MM-DD]` form workflow, date-range inputs, **Capture date report**, report-specific Snapshot/Refresh/Cancel/progress UI, old date report presentation, and related contextual help/status text. The result should not contain an accessible hidden duplicate of the old Reports controls or an orphaned placeholder page.
3. Remove Reports-specific Web routing, date request dispatch and conditional branches from `src/web/assets/reports.js` and `app.js`, and any date-page-only rendering/assets/styles/helpers that are **no longer used by any surviving Web feature**. Keep shared helpers when used elsewhere; delete unused web-only code instead of carrying dead functionality.
4. **Old links/bookmarks to `/#/reports` and `/#/reports?date=...`** must not trigger a hidden date report job. Redirect them safely to `/#/sessions` (preferred), or show an intentional not-found/retired route with a clear link to Sessions. The browser must not get stuck in a hash redirect loop or retain a misleading old report. Do not pretend the old date filter was applied when redirecting.
5. **Use Sessions as the visible historical navigation entry point.** In conjunction with FR000593, users should be able to sort the Sessions list on Last activity and its other specified columns; no automatic date filter, new search control, specialized report or scope option is added by this FR. Preserve `/#/sessions/<id>` deep links and Watch-to-Session navigation.
6. Update **current user documentation**, UI descriptions and live architectural route inventory so they no longer describe Reports as an available Web Beta page or direct users to its retired menu/form. Preserve historical FRs, past release notes, validation evidence and implementation history as historical records, without rewriting their original facts.

## Important scope boundary — Web page removal, NOT removal of report engines

- **Do not delete the underlying Python ReportService, date/history valuation code, canonical data projections, CLI date/date-range report support, or shared finite-job APIs** merely because the Web Reports route is retired. Those may be used by CLI, tests, diagnostics or other surviving Web views.
- Keep **Models, Watch, Sessions, Accounts, Token Mix and Cost per Active Hour**, including their own explicitly required capture/refresh/cancel semantics where applicable. The shared `src/web/assets/reports.js` script may still serve route definitions/control rendering for other pages; **do not remove the whole file** unless its retained exports are safely relocated and every consumer updated.
- **`/api/reports` is a shared backend API**, not synonymous with the `/#/reports` page. Existing authorized requests from other Web features and development/integration tests continue to work. Removing direct Web UI access to date capture must not accidentally change backend authorization, report limits or source read boundaries. An explicit Web API deprecation is *not* requested.
- Retire associated tests/docs for the **removed Web date UI** and replace with assertions that the menu and route are gone; do not indiscriminately delete shared/date logic tests which remain valid for the CLI and report core.
- Preserve privacy, read-only OpenCode history, source revision consistency, error classification and normal security/host session behavior. No new model inference, provider calls or data source changes.

## Acceptance criteria

1. The **Reports** menu entry is completely absent from Web Beta, including desktop/mobile/narrow layouts, keyboard navigation and screen-reader-visible navigation. No alternative visible Reports screen remains.
2. Navigating directly to old `/#/reports` URLs (with and without valid/invalid date query parameters) never renders the old date controls, snapshot status, progress or date report and **does not submit a date report job**. Any redirect/fallback is accessible, stable and directs users toward Sessions without silently applying an unimplemented filter.
3. `/#/sessions` remains the route for exploring historical sessions with the FR000593 sortable live catalog and default Last activity descending. Sorting works without a report capture; **date-range filtering is not introduced**.
4. No dead Reports-only Web UI code or misleading current documentation survives, but `src/reports/`, CLI date reporting, shared report APIs/jobs and other remaining Web routes continue to behave correctly.
5. Focused Web route/navigation/DOM/browser regression tests cover removal and legacy hashes plus normal use of surviving routes and their finite-report controls; CLI date-report and shared report regression tests are preserved and pass where applicable. No stale CSS/ARIA/nav references or broken browser back/forward behavior.

**Publication boundary:** create this separate owner-approved Ready FR and increment the backlog identity watermark only; no product implementation in the authoring session.
