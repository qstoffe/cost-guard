# Windows startup evidence

Source revision: 2ad45793e26742f90112f0d0383911b64c309408
Checked revision: 2ad45793e26742f90112f0d0383911b64c309408
Last checked: 2026-10-28
Status: current

## Summary

The Windows Web Beta batch must delegate before Python discovery and lifecycle arbitration. Batch exit acknowledges process creation, not host/tray readiness, supervisor exit or browser paint. Hidden PowerShell is a no-build route; no Windows executable cache exists. Direct PowerShell invocation retains synchronous troubleshooting status. Shared lifecycle ownership and paired pythonw report workers remain unchanged. Native probes must join their exact delegated launcher before stopping its host.

## Evidence

`development/architecture/governance/verification/windows-handoff.md` retains reproduction, native results and limitations for v80.101. On Windows 11 AMD64/Python 3.14.7 the final joined probe measured batch exit 0.028/0.026 s, host/tray readiness 2.415/3.573 s, and delegate exit observed at 2.759/3.973 s. An earlier separate synchronous fallback took 1.023/1.649 s. These are single observations, not browser-paint or physical flash comparisons. Full passed 113 files in 47.7 s; native tray/lifecycle/ShellExecute, bounded discovery and retained-handle delegate joins passed. Final inspection found zero task delegates, no managed state and no new startup-error record. OpenCode's built-in browser verified synthetic authenticated report and expired-session recovery without a Chrome automation fallback.

## Next investigations

Physical Explorer double-click/flash duration, consumer tray appearance/accessibility and native macOS Finder/Gatekeeper remain unverified. Use the normal source entry and distinguish visible launcher lifetime from source/report readiness. Do not delete private instance state or user caches to diagnose startup. If a residual flash proves unacceptable, compare a truly GUI entrypoint before adding a compiler/cache.

## Rejected hypotheses

A persistent launch console is not proof that pythonw report workers regressed: the old batch synchronously waited through host/browser handoff. A native executable is not automatically necessary when detached in-box PowerShell removes that wait; no native binary comparison was run. The local independence probe's 60-second `Total today` wait did not prove Web killed Watch: a separate read-only probe found live Watch startup/loading. The repaired probe asserts startup/process survival and does not claim full real-history completion. Deterministic report assertions were retained.

A leftover startup dialog in the first native run was not suppressed as a cosmetic fault. Its allowlisted startup failure followed teardown that stopped a ready host before the asynchronous supervisor necessarily observed readiness/completed handoff. Joining exact-root delegates with retained process handles and birth verification before test Exit eliminated the race in the full native rerun. Host readiness is never supervisor-completion proof; tests must close their own process trees, not shorten production lifecycle or hide its errors.
