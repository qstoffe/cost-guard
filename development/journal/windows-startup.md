# Windows startup evidence

Source revision: 3ed0be0e514e72ab1fd586e8bf1e113d8efa917b
Checked revision: 3ed0be0e514e72ab1fd586e8bf1e113d8efa917b
Last checked: 2026-10-28
Status: current

## Summary

The Windows Web Beta batch must delegate before Python discovery and lifecycle arbitration. Batch exit acknowledges process creation, not host/tray readiness, supervisor exit or browser paint. Hidden PowerShell is a no-build route; no Windows executable cache exists. Direct PowerShell invocation retains synchronous troubleshooting status. Shared lifecycle ownership and paired pythonw report workers remain unchanged. Native probes must join their exact delegated launcher before stopping its host.

## Evidence

`development/architecture/governance/verification/windows-handoff.md` retains reproduction, native results and limits for v80.101. Windows 11 AMD64/Python 3.14.7: final joined probe measured batch exit 0.028/0.026 s, host/tray readiness 2.415/3.573 s, delegate exit observed at 2.759/3.973 s. An earlier separate synchronous fallback took 1.023/1.649 s. These are single observations, not browser-paint or physical flash comparisons. Latest local Full passed 113 files in 59.6 s. Native tray/lifecycle/ShellExecute, bounded discovery and retained-handle delegate joins passed; final audit found zero task delegates, no managed state and no new startup-error record. OpenCode's built-in browser verified synthetic report/auth-expiry recovery without Chrome automation fallback. GitHub Actions run 40724292824 passed Windows Server 2025, macOS ARM64 and Intel regression/native/browser phases on this source revision; hosted native execution is not consumer desktop acceptance.

## Next investigations

Physical Explorer double-click/flash duration, consumer tray appearance/accessibility and native macOS Finder/Gatekeeper remain unverified. Distinguish visible launcher lifetime from source/report readiness. Do not delete instance state or user caches to diagnose startup. If a residual flash proves unacceptable, compare a truly GUI entrypoint before adding a compiler/cache.

## Rejected hypotheses

A persistent launch console is not proof that pythonw report workers regressed: the old batch synchronously waited through host/browser handoff. A native executable is not automatically necessary when detached in-box PowerShell removes that wait; no native binary comparison was run. The independence probe's 60-second `Total today` wait did not prove Web killed Watch: read-only observation found live Watch startup/loading. The repaired probe asserts startup/process survival, not full real-history completion. Deterministic report assertions were retained.

A leftover startup dialog was not suppressed as cosmetic. Its allowlisted startup failure followed teardown that stopped a ready host before the asynchronous supervisor necessarily completed handoff. Birth-verified, retained-handle joins before test Exit eliminated that race in the full native rerun. Host readiness is not supervisor completion; close owned process trees rather than shorten lifecycle or hide errors.

The first Windows-hosted Full run's missing visibility file did not independently prove a visible console or product failure: native/browser phases passed. The fixture conflated immediate batch exit with a five-second startup budget for the separate delegate. It now retains the batch deadline and invisible-console/blocked-delegate assertions, adds explicit interpreter-failure diagnostics and gives delegate startup a bounded 15 seconds. Those assertions passed locally and in Windows-hosted regression; the full three-platform matrix also passed afterward.
