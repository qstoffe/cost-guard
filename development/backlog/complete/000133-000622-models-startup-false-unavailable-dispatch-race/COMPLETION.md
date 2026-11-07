# FR 000622 completion — v80.202, 2026-11-07

Implemented the reproduced first-Live readiness/admission race. Models now waits
automatically and consumes its coherent host result without manual Retry. A
transient admission error cannot poison success; genuine terminal faults retain
actionable Retry feedback. Existing bounded retries, shared/coalesced work,
foreground priority, finite process and authenticated source boundaries remain.

The whole specification bundle is preserved intact. Maintenance progress includes
ordinary delivery 72 (`fr/000622`), effective only when merged to default.
Product version/date, README, version history, current Web guide, architecture and
code-map navigation are updated. Detailed RED/GREEN, causal trace, measurements,
test-harness repairs and limits: [verification journal](../../../journal/web/models-startup.md).

## Verification

- Mandatory pre-fix RED: exact generic red failure / visible Retry and persistent
  failure after release, through real authenticated HTTP and shipped browser assets.
- GREEN: four final fresh hidden Chrome host/profile starts across 360/1366 and
  Classic/Web, two-tab automatic recovery, warm deep-link reuse, one Models job,
  truthful 5% waiting then 100% only with valid data, no false failure/Retry flash.
- Full: 155/155 successful files; 1,889 tests, 1,888 passed / one existing macOS
  zsh/PTY skip on Windows, 107.0 seconds. Final focused dispatcher/loading/source-startup: 37 passed.
- Existing hidden browser probes: dispatcher eight scenarios; shared loader 13
  scenarios / 24 layouts; source startup success, failed readiness and AI Stats.
- Read-only installed V2 source: first Live 1.471 s, zero finite jobs before it,
  automatic Models ready 71.064 s, no host failure, own workers closed cleanly.
- Working-tree package validation passed; existing advisory budgets remain.

## Remaining evidence limits

The owner's private incident trace was unavailable; the causal reproduction is
controlled synthetic evidence, not a claim to have captured that private trace.
The real-source probe exercised host/finite readiness rather than a physical
browser. Integrated browser disconnected; physical OS launcher/desktop input,
sleep/minimization, screen-reader speech and macOS acceptance were not performed.
No requirement/test exception was approved or relied on. No paid inference,
shared OpenCode stop, source/history mutation, release ZIP or GitHub Release.
