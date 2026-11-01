# Windows startup evidence

Source revision: 11fa96c2bea806c7a66341e407bc04eb1611d079
Checked revision: 11fa96c2bea806c7a66341e407bc04eb1611d079
Last checked: 2026-10-28
Status: current

## Summary

FR 000537 deliberately supersedes the hidden-delegation policy: the Web Beta batch retains a synchronous launch-status console through Python discovery, native preflight, verified host ready and the OS browser-open result. Discovery and stage waits show indeterminate activity; the detached/tray-owned pythonw host survives status-process exit. There is no browser-first-paint guarantee, executable cache or new supervisor. Older asynchronous timings below are historical, not current launcher acceptance.

CLI/Watch/Diagnostics must not asynchronously share an existing interactive console. The old START /B path returned a synthetic Git-aware parent prompt while Python was still writing in the same console. A separate persistent PowerShell console isolates readers/writers and avoids leaving a batch waiting for Ctrl+C. Feedback belongs inside the child. Batch launch status is not Python completion; the child prompt retains the native result.

## Evidence

FR 000537 (2026-11-01): Decision Delegate authorized one additional bounded
cold/warm sequence over only the clone's explicitly spawned console and owned
host/tray, with normal OS browser requests and no browser automation. Win32 console
buffer samples observed all `| / - \\` spinner frames, Launching web and allowlisted
discovery/readiness/browser stages. Cold/warm launchers exited naturally with code 0
at 6.063/2.496 s, from 40/56 samples; authenticated detached host remained ready and
warm restart changed instance nonce. Exact owned host was safely stopped; no shared
OpenCode service or unrelated window/process was inspected/stopped. Sampling
briefly attaches only the reader, not the host; this is console-buffer evidence,
not a physical Explorer click, visual accessibility or browser first-paint proof.

Decision Delegate explicitly approved the unavailable physical Explorer/Terminal/
Finder cold/warm/restart demonstrations as a scoped exception, conditional on this
Windows result, final Full/validator and all three normal platform CI checks PASS.
The new macOS zsh/PTY feedback/exit test must execute on macOS; its local Windows
skip is not PASS. macOS physical status/handoff/Gatekeeper and browser paint remain
unverified. No failing gate or confirmed regression is waived. Finder's existing
no-Terminal/no-Automation route is preserved without an invented new cue.

`development/architecture/governance/verification/windows-handoff.md` retains reproduction, native results and limits for v80.101. Windows 11 AMD64/Python 3.14.7: final joined probe measured batch exit 0.028/0.026 s, host/tray readiness 2.415/3.573 s, delegate exit observed at 2.759/3.973 s. An earlier separate synchronous fallback took 1.023/1.649 s. These are single observations, not browser-paint or physical flash comparisons. That delivery's local Full passed 113 files in 59.6 s. Native tray/lifecycle/ShellExecute, bounded discovery and retained-handle delegate joins passed; final audit found zero task delegates, no managed state and no new startup-error record. OpenCode's built-in browser verified synthetic report/auth-expiry recovery without Chrome automation fallback. GitHub Actions run 40724292824 passed Windows Server 2025, macOS ARM64 and Intel regression/native/browser phases on this source revision; hosted native execution is not consumer desktop acceptance.

FR 000522: `development/architecture/governance/verification/windows-console-ownership.md` retains the bounded original reproduction and separate-console probes. Explicit Windows Terminal/Console Host callers, synthetic Git prompt plus PSReadLine, cmd/Explorer-style invocation, PowerShell 7/5.1, 80/120/160-column buffers, cancellation, native results 0/1/9009 and actual report/Watch/Diagnostics input-return checks were exercised. This is native console input evidence, not a screenshot/physical keyboard or colleague-prompt claim. Diagnostics' own full-local validation passed; its generated ZIP stays private and is not committed.

## Next investigations

The colleague's exact decorated prompt remains unverified. Physical Explorer double-click/flash duration, consumer tray appearance/accessibility and native macOS Finder/Gatekeeper remain unverified. Distinguish visible launcher lifetime from source/report readiness. Do not delete instance state or user caches to diagnose startup. If a residual flash proves unacceptable, compare a truly GUI entrypoint before adding a compiler/cache.

## Rejected hypotheses

The CLI defect does not establish a third-party prompt-plugin bug. Shared-console asynchronous ownership reproduces with a bounded synthetic prompt. Merely adding /WAIT risks batch Ctrl+C confirmation; merely hiding progress does not fix competing readers. The shared Ctrl+C reset is retained for direct/legacy callers. Native probe ownership must use the PowerShell PID, not Python's immediate parent: py.exe is an intermediate launcher and can exit before post-cancellation checks.

A persistent launch console is not proof that pythonw report workers regressed: the old batch synchronously waited through host/browser handoff. A native executable is not automatically necessary when detached in-box PowerShell removes that wait; no native binary comparison was run. The independence probe's 60-second `Total today` wait did not prove Web killed Watch: read-only observation found live Watch startup/loading. The repaired probe asserts startup/process survival, not full real-history completion. Deterministic report assertions were retained.

A leftover startup dialog was not suppressed as cosmetic. Its allowlisted startup failure followed teardown that stopped a ready host before the asynchronous supervisor necessarily completed handoff. Birth-verified, retained-handle joins before test Exit eliminated that race in the full native rerun. Host readiness is not supervisor completion; close owned process trees rather than shorten lifecycle or hide errors.

The first Windows-hosted Full run's missing visibility file did not independently prove a visible console or product failure: native/browser phases passed. The fixture conflated immediate batch exit with a five-second startup budget for the separate delegate. It now retains the batch deadline and invisible-console/blocked-delegate assertions, adds explicit interpreter-failure diagnostics and gives delegate startup a bounded 15 seconds. Those assertions passed locally and in Windows-hosted regression; the full three-platform matrix also passed afterward.
