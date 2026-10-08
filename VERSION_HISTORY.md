# Cost Guard version history

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


## v80.15 — 2026-10-08

- Refresh Copilot catalog/notifications hourly in running Watch while keeping in-run CCost pricing stable; separately check V2 OpenCode selectability every 15 minutes and use ✦/✧ Unicode discovery notices without assuming account entitlement.
- Bound extra V2 recovery time after detected sleep/wake. Record sanitized recovery transitions and cached model-freshness metrics in Diagnostics without sessions, IDs or credentials.
- Default pricing cache age to one hour; add isolated cross-platform regression tests.


## v80.14 — 2026-10-08

- Close synthetic SQLite connections before Windows temporary-directory cleanup, fix the missing V1 SourceError import and accept string-backed database paths in read-only Diagnostics triage.
- Keep the SQLite runtime read-only, preserve sanitized failure reporting and restore all-platform diagnostic regression coverage.


## Earlier v80 history

- v80.11-v80.13 added simulated macOS compatibility in Diagnostics, Windows path/release-check fixes and sanitized V1 SQLite read-error guards with read-only SQLite triage.

- v80.8-v80.9 aligned Watch session subtotals with visible rows (run-scoped CCost preserved) and unified the Windows launchers under a persistent PowerShell session with corrected Ctrl+C and error handling.

- v80.7 added shared Simple HTTP account providers and adapters for OpenRouter, DeepSeek and MiniMax, with sanitized diagnostics and no fabricated CCost.
- v80.6 made Watch survive temporary source outages and retry V2 without a V1 fallback.

- v80.0 established the clean 0BSD public-repository baseline with a fresh root history, retaining the Python functionality and cross-platform launchers, explicit bounded test-suite membership and public product identifiers.
- v80.1 introduced Cost Guard as an OpenCode AI usage, cost and quota tool in the README, with static Watch/report/Token Mix images, an early quick start and the detailed contracts linked in `docs/usage-and-cost.md`.
- v80.2 added the OpenAI token-expiry explanation: the next OpenCode prompt renews it; Cost Guard never refreshes or writes credentials.
- v80.3 added provider-supplied sign-in remedies and kept prompts active during verified V2 background jobs, with continuing duration, background status and resumed model work attributed to the same prompt; jobs themselves add no usage.
- v80.4 moved Diagnostics launchers under `development/windows|macos/`, keeping public launcher folders to normal report and Watch with validator-enforced placement.
- v80.5 scoped V1→V2 migration-gap notices to report windows; Watch omits them and Diagnostics retains full counts, without merging or source changes.

## Earlier versions (v1-v78)

- v78.0 established the Python baseline: Python 3.11+, standard-library runtime, bounded layers, optional JSONC, public 0BSD packaging and cross-platform launchers. The v78 generation added read-only V1 SQLite and V2 registered-service HTTP/events, source selection and migration-gap diagnostics without merging or repairing OpenCode history.
- Retained causal child/subagent attribution, separate compactions, archived-root usage, exact fork-clone de-duplication and disposable revision-sensitive SQLite caching. V2 terminal evidence and session-move context epochs preserve request identity, duration and accounting without treating inactivity as completion.
- Separated observed usage, CCost reference valuation and actual billing. CCost uses Copilot AI-credit-equivalent units; partial pricing and missing telemetry remain explicit. Comparisons reprice recent completed prompts, retain tiers/promotions and use a hidden synthetic mix only for zero-data sorting. Token Mix displays balanced shares, per-category CCost and optional all-history model summaries.
- Added compact available-model reports, full-catalog/session/date modes, request-proven effort labels, independent colors and amber Next-Ictx warnings. Watch retains session grouping, aligned tool/failure/running/TODO status, run/session CCost totals, bounded quota recovery, fixed geometry and terminal cleanup.
- Added read-only provider/account discovery, native quota windows, aligned remaining bars, resets and Copilot Remaining/day/workday without historical account attribution. Claude Code discovery and quotas remain optional/experimental. Diagnostics omits private payloads and combines bounded Full tests with package validation.
- Earlier PowerShell generations established causal attribution, context estimation, pricing-cache safety, configurable colors and low-idle-cost Watch constraints. v77.0 remains the historical behavioral reference for the Python rewrite.
