# Presentation Diagnostics source contracts

Source revision: 61088f210250f41e2f28f2a5d1da74794995915c
Checked revision: 61088f210250f41e2f28f2a5d1da74794995915c
Last checked: 2026-10-30
Status: current

[Architecture overview](../OVERVIEW.md) · [Owner/test routes](CODE_MAP.md). Source remains authoritative.

## Responsibility and ownership

Presentation consumes report/domain projections; Diagnostics exports bounded troubleshooting evidence. Neither owns provider acquisition, identity selection or credential repair.

## Public contract

`src/presentation/accounts.py` renders shared safe transport causes for certificate validation, other TLS, DNS, connection and timeout failures. `src/accounts/diagnostics.py` exports only allowlisted TLS categories and integer verification codes in 0..255, excluding booleans. HTTP status stays zero without an HTTP response; HTTP 401/403/429 keep their existing meanings. No arbitrary exception messages, certificate subjects or response bodies cross these boundaries.

`src/display.py` owns the ordered GitHub token vocabulary: Input / Cached input / Cache write / Output and the I/C/W/O legend. CLI mix cells/headings reuse it; `src/application/display.py` exports additive `display.token_categories` (existing input/cache/write/output keys) and `display.token_category_legend` to report/Watch/detail DTOs. Web reads this metadata rather than deriving names from keys. Token acquisition, aggregation, valuation and unknown/zero semantics are unchanged. `test_token_category_names.py` separates observed zero, absent telemetry, published prices without observations and Not applicable rates; 80/120/160-column synthetic text lives in `development/tests/fixtures/token-categories/`.

`ccostDisplayUnit` defaults to `credits`; the CLI `--ccost-unit credits|usd` override changes only the effective run configuration. `src/numbers.py` owns 100:1 reference-USD display rounding. Report/Watch render entrypoints and immutable application exports bind a synchronous, exception-safe ContextVar scope, reset after each render; concurrent jobs/threads cannot share a display choice. Native quota amounts, credit residuals, money, catalog rates and relative multipliers never consult this scope. The Date report's preformatted range note receives the unit explicitly. Application report/Live/detail exports retain exact raw Decimal strings plus shared display tokens and `ccost_display_unit`; frozen detail pages retain their captured choice. USD Watch cost columns expand for whole dollar tokens rather than truncating digits. Regression owner: `development/tests/test_ccost_display_unit.py`.

Presentation renders projections/progress, never integration queries or analysis. One-shot tables shrink flexible text, not identifiers/numbers/costs. Watch retains fixed geometry and one status row. `watch_screen.py` buffers/diffs rows only when both frames fit. Wrapped/oversize frames clear screen and scrollback before one buffered rebuild: viewport-home alone cannot replace a scrolled frame. Returning from overflow also clears stale fragments; safe resizes use an overwrite with stale-tail cleanup and no clear. `domain/progress.py` carries stage/work facts; `startup_estimate.py` owns approximate mode budgets and run-local interpolation, not billing/timing telemetry. Unknown steps are indeterminate; success alone reaches 100%. Animation joins before dashboard or recovery output. `cost-guard.py` stays thin; `src/bootstrap.py` wires concrete layers.

CLI retains v77 report/Watch argument shapes. Public `windows/|macos/` hold everyday launchers; Diagnostics lives under `development/user-tools/diagnostics/windows|macos/`. Shell-native requirements feedback precedes environment checks; `launcher_feedback.py` consumes its transient row when Python can replace it (plain lines on redirection). Windows `.cmd` files hand off with `start /b` then exit; `src/windows_launcher.ps1` restores inherited Ctrl+C, detects Python 3.11+ and runs the relative entry point. `-NoExit` leaves one usable shell after completion/failure/Ctrl+C, never an Enter-to-close or batch confirmation.

## Temporary quota-warning state

FR000525 keeps provider capacity and Remaining pace canonical; `src/display.py` supplies the shared presentation-only Used conversion for CLI and immutable Web display tokens. The temporary CLI Watch warning owns a single earliest-display UTC timestamp under user-local CostGuard state, not runtime cache/config/OpenCode. Only successful interactive frame publication starts its 72-hour window. A fixed verified implementation-merge anchor imposes the independent 60-day sunset; status redraws remove expired text. SQLite handles always close, concurrent inserts retain the earliest display, and invalid/unwritable state or backward clocks suppress the notice without changing account health. No Web acquisition/view notice is added. [Removal and state-loss limits](../../backlog/quota-used-warning-cleanup.md).

## Software-failure boundaries

`cost-guard.py` and Diagnostics guard imports with stdlib-only `src/runtime_errors.py` (only version metadata may cross in). It owns logs/crashes, deduplication/30-day retention, hooks, emergency stderr and the Diagnostics hint. Faults default fatal; isolated owners may expose ERROR and continue. [Failure policy/root audit](../governance/policies/runtime-failures.md) owns details; new roots need explicit ownership/tests.

## Diagnostics boundary

`collect_diagnostics.py` composes metadata/statistics-only troubleshooting; local Full/validation failures never suppress its bundle. IDs are hashed; prompts/titles/payloads/auth stay excluded. `diagnostic_watch.py` records fixed mode/generation labels, catalog/revision/cache/hydration/analysis counts, staged startup/refresh/render timings and geometry; `domain/acquisition.py` shares numeric instrumentation. Diagnostics remains runtime output, not a release.

## Allowed dependencies

Presentation depends on projection/domain display contracts, never concrete account integrations. Development Diagnostics may compose runtime readers but runtime modules must not import development tooling or fixtures.

## Entrypoints

`src/presentation/accounts.py`, `src/accounts/diagnostics.py`, `src/presentation/report.py`, `src/presentation/watch.py`, `development/tools/collect_diagnostics.py`.

## Tests

`development/tests/test_openai_transport.py` exercises exception normalization, privacy filtering and report/Watch failure text. Existing presentation/Diagnostics routes include `development/tests/test_quota_presentation.py`, `development/tests/test_quota_observations.py`, `development/tests/test_watch_rendering.py` and `development/tests/test_rc2_public_diagnostics.py`.
