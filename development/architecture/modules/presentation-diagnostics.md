# Presentation Diagnostics source contracts

[Architecture overview](../OVERVIEW.md) · [Owner/test routes](CODE_MAP.md). Source remains authoritative.

## Presentation and CLI

Presentation renders projections/progress, never integration queries or analysis. One-shot tables shrink flexible text, not identifiers/numbers/costs. Watch retains fixed geometry and one status row. `watch_screen.py` buffers/diffs rows only when both frames fit. Wrapped/oversize frames clear screen and scrollback before one buffered rebuild: viewport-home alone cannot replace a scrolled frame. Returning from overflow also clears stale fragments; safe resizes use an overwrite with stale-tail cleanup and no clear. `domain/progress.py` carries stage/work facts; `startup_estimate.py` owns approximate mode budgets and run-local interpolation, not billing/timing telemetry. Unknown steps are indeterminate; success alone reaches 100%. Animation joins before dashboard or recovery output. `cost-guard.py` stays thin; `src/bootstrap.py` wires concrete layers.

CLI retains v77 report/Watch argument shapes. Public `windows/|macos/` hold everyday launchers; Diagnostics lives under `development/user-tools/diagnostics/windows|macos/`. Shell-native requirements feedback precedes environment checks; `launcher_feedback.py` consumes its transient row when Python can replace it (plain lines on redirection). Windows `.cmd` files hand off with `start /b` then exit; `src/windows_launcher.ps1` restores inherited Ctrl+C, detects Python 3.11+ and runs the relative entry point. `-NoExit` leaves one usable shell after completion/failure/Ctrl+C, never an Enter-to-close or batch confirmation.

## Software-failure boundaries

`cost-guard.py` and Diagnostics guard imports with stdlib-only `src/runtime_errors.py` (only version metadata may cross in). It owns logs/crashes, deduplication/30-day retention, hooks, emergency stderr and the Diagnostics hint. Faults default fatal; isolated owners may expose ERROR and continue. [Failure policy/root audit](../governance/policies/runtime-failures.md) owns details; new roots need explicit ownership/tests.

## Diagnostics boundary

`collect_diagnostics.py` composes metadata/statistics-only troubleshooting; local Full/validation failures never suppress its bundle. IDs are hashed; prompts/titles/payloads/auth stay excluded. `diagnostic_watch.py` records fixed mode/generation labels, catalog/revision/cache/hydration/analysis counts, staged startup/refresh/render timings and geometry; `domain/acquisition.py` shares numeric instrumentation. Diagnostics remains runtime output, not a release.
