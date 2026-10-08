# Cost Guard version history

## v80.20 — 2026-10-08

- Normal model comparison now has four columns, centered on Relative CCost; `--all-models` adds original, exact GitHub USD/M I/C/W/O rates with every published tier and boundary, including without observed token data.
- Each context tier uses the same completed-prompt I/C/W/O mix and cheapest comparable base reference; dynamically aligned promotion markers, multipliers, arrows and exact > / ≥ K/M boundaries share one column.
- Both modes share full-precision descending base/next-tier price ordering, earlier price-increase thresholds and alphabetical final ties; additional tiers extend both the chain and tie-breakers. Fallback mix, model selection, CCost, Watch and quotas are preserved.
- Diagnostics removes the blank before the support address and ends success/failure with one blank before the shell prompt, preserving minimal colors and screen clearing.
- Metadata state migrates non-destructively to cache/state/, retaining retry/history/date evidence and a legacy fallback; actual failures and recoveries have separate logs, and Diagnostics exports all categories without pruning live state.


## v80.19 — 2026-10-08

- Release-date metadata has its own health, separate from fresh pricing: a catalog with priced models but missing dates is refreshed at Watch start, after resume and on the first V2 list, retried after ~1/5/15 minutes then hourly (honoring HTTP 429) across restarts, without blocking Watch or changing CCost, and never erasing verified dates.
- models.dev and the official Copilot changelog are independent, classified sources (DNS, connection, TLS, HTTP, timeout, parse, schema, missing fields, zero/partial matches, cache fallback, skipped, internal); dates record their source and never move to another model identity.
- Watch ✦ New Models never shows a model whose verified release date is old; catalog-history models without a date still qualify for seven days.
- Persistent metadata state and failure-period logs (start, change, bounded summaries, recovery) feed a new Diagnostics model-metadata section, so self-healed failures stay analyzable.
- Diagnostics ends on a cleared screen with only the green result, ZIP path and support address, or a red short reason; test failures inside a verified ZIP still count as success.
- Fatal and stopping errors end with the absolute OS-specific Diagnostics launcher path; Watch startup loading is white like other modes while Watch statuses keep their colors.
- Working-tree package validation excludes root runtime logs just like the ZIP builder; extracted packages still reject them, with regression coverage preserving nested source files and original logs.


## v80.18 — 2026-10-08

- Reports mark new models with the same ✦ New Models notice as Watch, keeping the hanging indent when the notice wraps.
- Diagnostics creates its bundle folder before staging the ZIP and never creates a runtime cache merely to report model freshness; Full-suite tests now match priced-only Watch notices, the resume-plus-forced V2 refresh and the optional changelog release-date fetch.


## v80.17 — 2026-10-08

- Treat newly observed V2 selectable Copilot IDs only as triggers for immediate forced pricing refresh; Watch notifies only verified priced catalog models, preserving the hourly catalog cadence and 15-minute V2 checks.
- Move runtime logs to root logs/, publish one verified diagnostics ZIP, safely archive legacy/current logs, clean old date-stamped ZIPs and print precise support instructions with configurable qstoffe@hotmail.com.
- Isolate runtime artifacts from releases, improve diagnostics error handling and extend regression tests.


## v80.16 — 2026-10-08

- Normalize Watch notices to ✦ New Models, retain bounded model-identity history between starts and expose metadata-fetch failures for diagnosis.
- Package owned errors, crashes and recovery records into a verified Diagnostics ZIP, safely prune unchanged quiet files, isolate synthetic tests and retain 30-day expiration.
- Restore version history release validation and add regression coverage for model and log lifecycle behavior.


## Earlier v80 history

- v80.15 added hourly Copilot catalog refresh with pinned in-run CCost, 15-minute V2 selectability checks, bounded sleep/wake recovery, sanitized metadata evidence and one-hour default pricing-cache age.

- v80.11-v80.14 added simulated macOS compatibility in Diagnostics, Windows path/release-check fixes, sanitized V1 SQLite read-error guards with read-only triage and Windows-safe synthetic SQLite cleanup.

- v80.8-v80.9 aligned Watch session subtotals with visible rows (run-scoped CCost preserved) and unified the Windows launchers under a persistent PowerShell session with corrected Ctrl+C and error handling.

- v80.7 added shared Simple HTTP account providers and adapters for OpenRouter, DeepSeek and MiniMax, with sanitized diagnostics and no fabricated CCost.
- v80.6 made Watch survive temporary source outages and retry V2 without a V1 fallback; v80.5 scoped read-only V1→V2 migration-gap notices to report windows, never merging histories or showing them in Watch.

- v80.0 established the clean 0BSD public-repository baseline with a fresh root history, retaining the Python functionality and cross-platform launchers, explicit bounded test-suite membership and public product identifiers.
- v80.1 introduced Cost Guard as an OpenCode AI usage, cost and quota tool in the README, with static Watch/report/Token Mix images, an early quick start and the detailed contracts linked in `docs/usage-and-cost.md`.
- v80.2 added the OpenAI token-expiry explanation: the next OpenCode prompt renews it; Cost Guard never refreshes or writes credentials.
- v80.3 added provider-supplied sign-in remedies and kept prompts active during verified V2 background jobs, with continuing duration, background status and resumed model work attributed to the same prompt; jobs themselves add no usage.
- v80.4 moved Diagnostics launchers under `development/windows|macos/`, keeping public launcher folders to normal report and Watch with validator-enforced placement.

## Earlier versions (v1-v78)

- v78.0 established the Python baseline: Python 3.11+, standard-library runtime, bounded layers, optional JSONC, public 0BSD packaging and cross-platform launchers. The v78 generation added read-only V1 SQLite and V2 registered-service HTTP/events, source selection and migration-gap diagnostics without merging or repairing OpenCode history.
- Retained causal child/subagent attribution, separate compactions, archived-root usage, exact fork-clone de-duplication and disposable revision-sensitive SQLite caching. V2 terminal evidence and session-move context epochs preserve request identity, duration and accounting without treating inactivity as completion.
- Separated observed usage, CCost reference valuation and actual billing. CCost uses Copilot AI-credit-equivalent units; partial pricing and missing telemetry remain explicit. Comparisons reprice recent completed prompts, retain tiers/promotions and use a hidden synthetic mix only for zero-data sorting. Token Mix displays balanced shares, per-category CCost and optional all-history model summaries.
- Added compact available-model reports, full-catalog/session/date modes, request-proven effort labels, independent colors and amber Next-Ictx warnings. Watch retains session grouping, aligned tool/failure/running/TODO status, run/session CCost totals, bounded quota recovery, fixed geometry and terminal cleanup.
- Added read-only provider/account discovery, native quota windows, aligned remaining bars, resets and Copilot Remaining/day/workday without historical account attribution. Claude Code discovery and quotas remain optional/experimental. Diagnostics omits private payloads and combines bounded Full tests with package validation.
- Earlier PowerShell generations established causal attribution, context estimation, pricing-cache safety, configurable colors and low-idle-cost Watch constraints. v77.0 remains the historical behavioral reference for the Python rewrite.
