# Windows startup evidence

Source revision: 3f0f7997087ad13c8fa47b869a5542884b324f95
Checked revision: 3f0f7997087ad13c8fa47b869a5542884b324f95
Last checked: 2026-10-28
Status: current

## Summary

The Windows Web Beta batch must delegate before Python discovery and lifecycle arbitration. Batch exit acknowledges process creation, not host/tray readiness or browser paint. Hidden PowerShell is a no-build route; no Windows executable cache exists. Direct PowerShell invocation retains synchronous troubleshooting status. Shared lifecycle ownership and the paired pythonw report-worker fix remain unchanged.

## Evidence

`development/architecture/governance/verification/windows-handoff.md` retains reproduction, native results and limitations for v80.101. On Windows 11 AMD64/Python 3.14.7 the batch exited in 0.027 s in both trials; host/tray readiness took 1.007/2.053 s. The separate synchronous fallback took 1.023/1.649 s. These are single trials, not comparative browser-paint or physical flash measurements. Full passed 113 files; native tray/lifecycle/ShellExecute and bounded discovery tests passed. OpenCode's built-in browser verified the synthetic authenticated report and expired-session recovery without a Chrome automation fallback.

## Next investigations

Physical Explorer double-click/flash duration, consumer tray appearance/accessibility and native macOS Finder/Gatekeeper remain unverified. Use the normal source entry and distinguish visible launcher lifetime from source/report readiness. Do not delete private instance state or user caches to diagnose startup. If a residual flash proves unacceptable, compare a truly GUI entrypoint before adding a compiler/cache.

## Rejected hypotheses

A persistent launch console is not proof that pythonw report workers regressed: the old batch synchronously waited through host/browser handoff. A native executable is not automatically necessary when detached in-box PowerShell removes the observed wait. No native binary comparison was run. The local independence probe's 60-second `Total today` wait was not evidence that Web killed Watch: a separate read-only probe found live Watch startup/loading. The repaired probe proves process survival after Web restart/exit and explicitly does not claim full real-history report completion. Deterministic report assertions were retained.
