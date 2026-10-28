# Windows startup evidence

Source revision: 11fa96c2bea806c7a66341e407bc04eb1611d079
Checked revision: 11fa96c2bea806c7a66341e407bc04eb1611d079
Last checked: 2026-10-28
Status: current

## Summary

The Windows Web Beta batch must delegate before Python discovery and lifecycle arbitration. Batch exit acknowledges process creation, not host/tray readiness, supervisor exit or browser paint. Hidden PowerShell is a no-build route; no Windows executable cache exists. Direct PowerShell invocation retains synchronous troubleshooting status. Shared lifecycle ownership and paired pythonw report workers remain unchanged. Native probes must join their exact delegated launcher before stopping its host.

CLI/Watch/Diagnostics must not asynchronously share an existing interactive console. The old START /B path returned a synthetic Git-aware parent prompt while Python was still writing in the same console. A separate persistent PowerShell console isolates readers/writers and avoids leaving a batch waiting for Ctrl+C. Feedback belongs inside the child. Batch launch status is not Python completion; the child prompt retains the native result.

## Evidence

`development/architecture/governance/verification/windows-handoff.md` retains reproduction, native results and limits for v80.101. Windows 11 AMD64/Python 3.14.7: final joined probe measured batch exit 0.028/0.026 s, host/tray readiness 2.415/3.573 s, delegate exit observed at 2.759/3.973 s. An earlier separate synchronous fallback took 1.023/1.649 s. These are single observations, not browser-paint or physical flash comparisons. That delivery's local Full passed 113 files in 59.6 s. Native tray/lifecycle/ShellExecute, bounded discovery and retained-handle delegate joins passed; final audit found zero task delegates, no managed state and no new startup-error record. OpenCode's built-in browser verified synthetic report/auth-expiry recovery without Chrome automation fallback. GitHub Actions run 40724292824 passed Windows Server 2025, macOS ARM64 and Intel regression/native/browser phases on this source revision; hosted native execution is not consumer desktop acceptance.

FR 000522: `development/architecture/governance/verification/windows-console-ownership.md` retains the bounded original reproduction and separate-console probes. Explicit Windows Terminal/Console Host callers, synthetic Git prompt plus PSReadLine, cmd/Explorer-style invocation, PowerShell 7/5.1, 80/120/160-column buffers, cancellation, native results 0/1/9009 and actual report/Watch/Diagnostics input-return checks were exercised. This is native console input evidence, not a screenshot/physical keyboard or colleague-prompt claim. Diagnostics' own full-local validation passed; its generated ZIP stays private and is not committed.

## Next investigations

The colleague's exact decorated prompt remains unverified. Physical Explorer double-click/flash duration, consumer tray appearance/accessibility and native macOS Finder/Gatekeeper remain unverified. Distinguish visible launcher lifetime from source/report readiness. Do not delete instance state or user caches to diagnose startup. If a residual flash proves unacceptable, compare a truly GUI entrypoint before adding a compiler/cache.

## Rejected hypotheses

The CLI defect does not establish a third-party prompt-plugin bug. Shared-console asynchronous ownership reproduces with a bounded synthetic prompt. Merely adding /WAIT risks batch Ctrl+C confirmation; merely hiding progress does not fix competing readers. The shared Ctrl+C reset is retained for direct/legacy callers. Native probe ownership must use the PowerShell PID, not Python's immediate parent: py.exe is an intermediate launcher and can exit before post-cancellation checks.

A persistent launch console is not proof that pythonw report workers regressed: the old batch synchronously waited through host/browser handoff. A native executable is not automatically necessary when detached in-box PowerShell removes that wait; no native binary comparison was run. The independence probe's 60-second `Total today` wait did not prove Web killed Watch: read-only observation found live Watch startup/loading. The repaired probe asserts startup/process survival, not full real-history completion. Deterministic report assertions were retained.

A leftover startup dialog was not suppressed as cosmetic. Its allowlisted startup failure followed teardown that stopped a ready host before the asynchronous supervisor necessarily completed handoff. Birth-verified, retained-handle joins before test Exit eliminated that race in the full native rerun. Host readiness is not supervisor completion; close owned process trees rather than shorten lifecycle or hide errors.

The first Windows-hosted Full run's missing visibility file did not independently prove a visible console or product failure: native/browser phases passed. The fixture conflated immediate batch exit with a five-second startup budget for the separate delegate. It now retains the batch deadline and invisible-console/blocked-delegate assertions, adds explicit interpreter-failure diagnostics and gives delegate startup a bounded 15 seconds. Those assertions passed locally and in Windows-hosted regression; the full three-platform matrix also passed afterward.
