# FR 000622 — first-Live Models startup recovery

2026-11-07, local Windows workstation, v80.202. PR/default branch own delivery truth.

## Proven causal path

Before production edits, `integration/probe_models_startup.cjs` against the owned
`serve_models_startup.py` fixture failed the desired healthy-startup assertion.
The fixture uses the actual authenticated WebHost, SourceStartup status,
LiveRuntime, DataDispatcher, protected interest/data endpoints and shipped
live/app/loading assets. Only source acquisition, its first-frame gate and report
contents are synthetic; no private source trace is inferred.

| Stage | Pre-fix evidence | Fixed evidence |
| --- | --- | --- |
| Selected source / identity present, first healthy frame held | HTTP 503 `source_unavailable`, `retryable:true`; dispatcher `terminal:false`; no finite job | HTTP 503 `source_starting`, `retryable:true`; no finite job |
| Browser during hold | Generic red source/report error, failed=true, Retry Models visible, 5% | Waiting for source, failed=false, Retry hidden, unchanged 5% |
| First healthy frame released | Connected Live; Models job finishes, browser remains failed without data/manual Retry | Same attempt automatically applies the coherent result, 100%, no failure/Retry/withheld/sticky dispatcher error |

The host now distinguishes first-observation waiting from actual source failure.
Its existing 120-second bound yields `source_wait_timeout` when no underlying
fault exists. Actual error codes remain authoritative. The client accepts the
legacy unavailable code only with explicit recoverability and retains its eight
admission retries / exponential 0.5–4 second backoff. It neither starts an explicit
price refresh nor turns an arbitrary retryable code into indefinite recovery.
Current terminal dispatcher errors still accompany retained data as actionable
failure feedback; transient admission errors cannot override successful results.

## Repeatable evidence

- Full: all 155 files successful, 1,889 tests, 1,888 passed / one existing skip,
  107.0 seconds. Skip: macOS zsh/PTY launcher test on Windows, owned by native macOS CI.
- Final focused dispatcher/loading/source-startup run: 37 tests passed. Includes readiness/identity matrix,
  coalescing, no pre-observation admission, 120-second source-wait end, terminal
  auth/permission/schema/version/registration/source-identity faults, explicit
  legacy recoverability and retry exhaustion. Existing suite covers source/HTTP
  security, foreground arbitration, managed failures and child/parent teardown.
- Fresh hidden Chrome 156: four final consecutive host/profile cold starts,
  two tabs each plus authenticated warm deep-link reload, one logical Models job
  per host, Models before speculative AI Stats, zero failure/Retry flashes.
  First-Live / dispatcher-ready seconds from each fixture's monotonic start:
  Web 1366: 1.0224 / 1.0620; Classic 1366: 0.9938 / 1.0333;
  Web 360: 0.9722 / 1.0153; Classic 360: 1.0065 / 1.0522.
  Browser navigation-to-first-result times respectively: 2.245, 1.640, 2.008,
  2.327 seconds (different clock origin from host start).
  These artificial gate-release timings are not installation performance targets.
  Evidence records data/interest response times, logical job IDs and state transitions.
- The startup probe checks shipped DOM/AX progress semantics, centered contained
  loading geometry and no 100% before an eligible result; synthetic waiting/ready
  screenshots retained in owned scratch only. Existing `probe_report_loading.cjs`
  passed 13 scenarios / 24 layouts, including hidden/inactive completion, route
  return, no Cancel, genuine failure/Retry, source waits and focus-safe refresh.
- `probe_data_dispatch.cjs` passed eight scenarios including all four warmed routes,
  unchanged-content reuse, one-shot Retry, stale/invalidation gates, Sessions page
  restoration and new transient-versus-terminal admission/result assertions.
- Final v80.202 working-tree validation passed eleven checks, zero failures, six
  existing advisory budget categories; whitespace diff check passed.
- The older source-startup browser fixture initially stopped incorrectly: it
  replaced ReportJobs without replacing the dispatcher and compared synthetic Live
  config with real dependencies. It now binds the same owned jobs/dispatcher,
  isolates dependencies and publishes current identity-bound synthetic results in
  real finite children. The unchanged browser assertions passed success, failed
  readiness and AI Stats cases, with one wake across two tabs/navigation/reload.
- Test-harness corrections, not product evidence: the new unit wait initially
  outlived its tab lease; it now renews interest before testing foreground priority.
  One probe initially assumed Web instead of the default Classic theme, and a
  timing-instrumentation draft treated ObjectValue as a dict. Corrected final runs
  above passed; those earlier failures are not relabeled as successful runs.

## Real installation, read-only

`probe_data_dispatch.py --startup-only --foreground-only --budget-seconds 180
--idle-seconds 0 --initial models` used installed V2 source reads and normal
disposable derived caches; no cache deletion, inference or shared-service restart.
First Live: 1.471 seconds, zero finite jobs beforehand. Models usable automatically
at 71.064 seconds (the finite child spent 68.810 seconds, mostly catalog reads).
161 Live publications, maximum gap 3.156 seconds; no host failure, Live running.
One owned finite child at peak; own serving/Live threads closed, zero parked
children retained. This exercised host readiness/real finite execution, not a
physical browser or proof of the owner's previously unrecorded HTTP incident.

## Limits and reproduction

Integrated OpenCode browser returned `browser.disconnected`; permitted hidden
Chromium supplied DOM/AX/layout evidence instead. Physical Windows OS launcher,
shared-desktop focus/scroll, screen-reader speech, actual sleep/minimization and
macOS/other engines were not exercised. The optional physical-launcher path was
not needed to establish the causal race; no native/OS acceptance is claimed.
No requirement/test exception was requested or approved; these are explicit
conditional/platform evidence limits, not PASS claims. No model calls, shared
OpenCode stop, source/history writes, credentials or private rows were published.

From the checkout, supply an existing Chromium executable and owned output path:

```text
node development/tests/integration/probe_models_startup.cjs <browser> <output> 1366 web
node development/tests/integration/probe_models_startup.cjs <browser> <output> 360 classic
```

Local raw evidence: `scratch:/evidence/startup-red/startup.json`,
`scratch:/evidence/timed-web-1366/startup.json`,
`scratch:/evidence/timed-classic-1366/startup.json`,
`scratch:/evidence/timed-web-360/startup.json`,
`scratch:/evidence/timed-classic-360/startup.json`, `scratch:/evidence/full-tests.json`,
`scratch:/evidence/dispatch-browser/browser.json`,
`scratch:/evidence/report-loading-browser/browser.json` and
`scratch:/evidence/installed-startup.txt`. These are this worker's evidence only,
not a registry or durable replacement for the checked-in causal summary.
