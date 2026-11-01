# FR 000539 — Move Web CCost Credits/USD into Settings and persist the Web-only choice

## Owner intent and dependency

Move the existing **CCost: Credits / USD** selector out of the **Models → More information** section into the new **Settings** page introduced by **FR 000538**. Changing it must immediately update CCost presentation throughout the running Web application and **persist permanently** in the actual `config/user-config.jsonc` file. **Credits** is the default unless the user explicitly chose USD.

**Implement only after FR 000538** has delivered its Settings route, Theme selection and secure user-config read/write mechanism. This FR extends that finished surface; do not alter the ongoing FR 000538 specification, reintroduce earlier Models/Overview navigation or build a second settings subsystem. FR 000526 owns canonical Credits/reference-USD formatting; FR 000528 owns the existing immediate Web display-unit switching. Retain both contracts except for the intentionally replaced page-memory-only persistence/default behavior.

## 1. One CCost preference in Web Settings

1. On the existing `#/settings` page, keep the **Theme** control from FR 000538 and add one well-labeled **CCost display** dropdown with exactly **Credits** and **USD**. Place it in the same simple, accessible settings layout, without a separate Save/Apply action.
2. Remove the **interactive CCost unit selector** from **Models → More information**, its prior toolbar/shell location and any other duplicate location. The Models section may retain useful explanatory text about CCost and reference USD, but it must not still offer the editable setting.
3. Briefly clarify by the new control that **USD is reference token valuation, not actual provider billing**. Reuse the established units/help semantics instead of inventing another definition.
4. Navigating to Settings or changing the unit must not acquire/refresh history, reports, accounts, pricing or providers; must not restart the Web host or OpenCode; and must not disturb ongoing Watch, frozen Snapshots or session state.

## 2. Persist a Web-only setting, not the CLI setting

1. Add an independently validated, top-level **`webCcostDisplayUnit`** configuration preference with exactly `"credits"` or `"usd"`. Its shipped/effective **default is `"credits"`**, including existing installations with no Web-specific override. Use the existing merged configuration and validation conventions.
2. Save user-selected overrides **only** in the existing, Git-ignored `config/user-config.jsonc`; never rewrite `config/default-config.jsonc`. Missing user config is not created just to read the default; the first actual user change may create a minimal override.
3. **Keep the existing `ccostDisplayUnit` setting and `--ccost-unit` CLI override unchanged and independent.** The new `webCcostDisplayUnit` applies only to Web; changing it must not affect any CLI report, CLI Watch, CLI default or command-line flag. Conversely, a legacy `ccostDisplayUnit: "usd"` override does not override an absent Web preference: Web still defaults to Credits. Do not silently migrate, delete or overwrite the legacy setting.
4. The saved Web value is the source of truth on a new browser tab, page reload, route navigation and later Web relaunch. No `localStorage`, `sessionStorage`, persistent browser cookie preference or URL storage. A manual valid file edit is recognized on the next settings read/launch, without adding continuous file polling.

## 3. Apply changes immediately and consistently

1. On each real selection change, use FR 000538's authenticated, narrow Settings write mechanism to persist **only `webCcostDisplayUnit`**; update the selected dropdown and every **currently rendered** Web CCost amount **immediately after a successful save**, without full-page reload or new data acquisition. No further click or route visit is needed.
2. The chosen unit remains in effect when navigating among **Models, Watch, Sessions and session detail (Snapshot/Live), Accounts, Reports, Token Mix and Cost per Active Hour**, plus any other existing CCost display. Existing frozen results, in-flight jobs, Live/SSE updates and later snapshots use the active Web preference consistently, including any route entered after switching.
3. Reuse FR 000528's Python-prepared `display_units.credits/usd` / shared Web rendering path. The frontend only switches display tokens: never calculate USD or round raw values in JavaScript, reprice models, change exact totals/sorting/thresholds, alter scroll/focus/paging or reset report identity. USD consistently uses `$` and two decimals under FR 000526.
4. Keep actual provider **Billed** money, account-native AI credits/quotas, **Unaccounted** residual credits, native price catalogs and dimensionless **Relative CCost** unchanged; this is a *CCost presentation* preference, not a currency converter for unrelated measures.
5. On write failure, validation error, concurrent file edit, unavailable host or expired authorization, **do not claim Saved** and do not leave an unsaved unit represented as persistent. Retain/revert to the last confirmed choice, show concise accessible feedback and permit retry. Loading/saving status must not block other views. Do not render a brief wrong-unit initial report while waiting for an unrelated analytics job when settings can be fetched at startup.

## 4. Narrow, safe configuration integration

- **Extend the FR 000538 infrastructure**, which currently authorizes only `webTheme`, to additionally allow this one fixed `webCcostDisplayUnit` key; keep an explicit allowlist and strict enum/body validation. A dedicated `/api/settings/ccost-unit` endpoint or equally narrow extension is acceptable; **no generic configuration editor/write API**.
- Reuse authenticated loopback Host/Origin, session, CSRF, request size/type, lifecycle/stopping and path-ownership protections. Never expose arbitrary config contents, secret values or local paths to the browser.
- Preserve all unrelated keys, nested objects, comments, formatting/order where safely possible, and particularly `webTheme` and legacy `ccostDisplayUnit`. Use canonical validation of the resulting effective config, bounded file operations, safe atomic write and concurrent-change detection from FR 000538. If safe preservation fails, reject without modifying the user file.
- Theme and CCost preferences must not overwrite one another, including changes from two tabs or an external editor. Keep behavior proportionate; no new storage layer, synchronization service or mandatory page polling.
- Updating the approved user config must not trip the existing runtime source-change guard, restart the Web application, or change CLI color/theme preferences.

## Acceptance criteria

1. **After FR 000538**, Settings contains exactly the existing **Theme** control and the new **CCost display: Credits / USD** control; Models → More information has **no CCost selector**. Keyboard, screen reader, mobile layout and validation/status messages remain usable.
2. With no `webCcostDisplayUnit` override, Web renders **Credits**, even if `ccostDisplayUnit` is already set to `usd` for CLI. Selecting **USD** writes `webCcostDisplayUnit: "usd"` to `config/user-config.jsonc` and updates the **current page** and all subsequently visited views immediately. Selecting Credits writes `"credits"` and reverses the display.
3. Navigate every Web report route, use Live/Watch publication, reopen frozen session detail, refresh an existing report, reload the page, open a fresh tab and relaunch Web: **all CCost labels/amounts remain consistent with the saved Web choice**; no unintended data acquisition due only to selecting the unit.
4. A JSONC file containing comments, nested account options, legacy `ccostDisplayUnit`, CLI color overrides and `webTheme` survives Credits → USD → Credits without unrelated changes. Missing files, malformed/invalid config, permission failures, symlinks/reparse hazards, stale/concurrent writes and unsafe file states fail non-destructively and with truthful UI feedback.
5. CLI displays the same original behavior before/after either Web choice, including its configuration and `--ccost-unit` override. Web choice never changes valuation, warnings, sort order, native billing, quotas or price-rate displays.
6. Focused configuration/API/authorization/security and deterministic Web DOM/real-browser tests cover defaults, failed/successful persistence, both settings coexisting, same-page immediate updates, multiple routes, Live/Snapshot and restart/reload. Update user documentation that currently describes the Web selector as page-memory-only.

## Boundaries and scheduling

**No** new pricing or conversion logic, new browser persistence, report redesign, general config editor, changes to CLI display options or modification of FR 000538 while it is being implemented. Deliver this as a **separate subsequent FR** against FR 000538's completed Settings implementation.

**Permanent identity:** `000539`. **Queue priority:** `000300`, after FR 000538 (`000200`). This commit is **backlog metadata only**: no runtime implementation, tests, version or release changes.
