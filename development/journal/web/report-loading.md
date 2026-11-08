# Shared finite-report loading

Source baseline: 50e7fe929b6e7ccce236eb51174206dcbe26e070
Checked scope: FR000615 lifetime/UI delta; historical FR000609 evidence is labeled below
Last checked: 2026-11-06
Status: current

## Owners and invariants

`src/web/assets/report-loading.js` owns the shared centered determinate view,
observed monotonic stage bands, stale-sequence rejection and internally interruptible bounded
attempt. `app.js` automatically acquires only the eligible visible Models, Token
Mix, AI Stats or Comparisons route, validates/applies a coherent result before
100%, and keeps usable retained content/focus during quiet refresh. The stage
line has reserved height; the polite status announces stages, not every count.
The completion paint settles on document hiding or abort rather than waiting
forever for a background document's suspended animation frames.

Normal report stages remain separate from historical cache/load/projection
work. Historical report builders emit actual outer counts; nested date-batch
counts cannot consume a global-history progress band. Opaque work can hold at
its current percentage. There is no timer-driven advancement or invented global
denominator. A usable partial result completes the attempt, not history coverage.

`source_startup.py` exposes detached typed readiness from its existing actual
selection/wake owner. HTTP reads this proof before admission, never selects or
wakes a source itself. Temporary `source_starting`, typed retryable transport
failures and HTTP 429 `busy` use bounded backoff. Permission/auth/schema errors,
terminal/offline/identity loss, real report failure and timeout are not successful
recovery. An SSE reconnect alone is not failed finite HTTP/source readiness.

The browser attempt remains bounded by 120 seconds except resumable AI Stats, with at most eight
backoff waits (500, 1,000, 2,000, then 4,000 milliseconds). Existing server job
deadline, four pending jobs, 8 MiB result bound, session/CSRF/ownership and
cancellation remain unchanged. Historical 5/15-minute checks and one-hour
withholding, AI Stats scope extension, Comparisons revisions and explicit Models
price refresh retain their owners. No new scanner, cache schema or CLI/Live
workflow is introduced. FR000615 removes the global Cancel markup, event handler
and CSS/fixture assumptions rather than hiding a live cancellation path. Empty
toolbars collapse; Models' actual failed-report Retry can be reached while its
healthy toolbar remains absent. Refresh price list is independent.

Navigation and temporary hiding no longer abort unadmitted attempts or AI Stats
polling. One retained attempt continues its bounded backoff, completes into its own
view, or retains its actual terminal reason. Inactive pages never start periodic
refreshes. A throttled tab reads a settled server outcome before applying its local
deadline, so an already-completed job is not mislabeled timeout on return.

AI Stats removes polling-interest expiry and retains up to five requested goals in
one host-owned job; narrow priority cannot erase a previously requested broad goal.
The next slice resumes missing goals under the same observation/scan identity and
existing fairness/watchdogs/resource/no-progress limits. This is FR000615's narrow
override of FR000614's user cancellation/inactivity behavior, not a general ban on
internal cancellation. Closing/reloading loses page/pre-admission memory; no durable
cross-host/tab-close intent or background periodic scanner is claimed.

## FR000615 verification and scoped exception

- Actual app/Attempt VM regressions cover all four finite routes' bounded pending
  intent, admitted job identity, hidden/inactive completion, retained terminal
  source-wait exhaustion and no duplicate/new inactive checks. AI Stats tests cover
  no-poll host ownership, narrow priority, older-goal resumption, internal cancel,
  watchdog shrink/stalls and actual spawned slices.
- Hidden Chrome 156: shared loader **13 checks / 24 layouts**, all four routes in
  Classic/Web light/Web dark at 360/1366px, with no DOM/AX Cancel in load, source
  wait, quiet refresh, retained success, failure and completion. Real hidden-tab
  visibility, navigation/Back and competing Comparisons tab coalescing pass. Actual
  screenshot inspection agrees. Evidence: `scratch:/evidence/loading-final/`.
- Independent hidden probes: AI Stats **14 checks / 9 layouts** plus enlarged-text,
  color/state matrices and production two-tab/spawned slice coverage; original
  30-day goal finishes after 7-day selection/navigation without another selection,
  exactly 24 synthetic root hydrations. Comparisons **9 / 12**, Token Mix **4 / 9**,
  Models price refresh **4 / 6** retain their layout/help/focus/refresh behavior.
  Evidence: `scratch:/evidence/ai-stats-frozen.json`, `comparisons-browser.json`,
  `token-mix-browser.json`, `models-refresh.json` under that same evidence branch.
- Integrated browser was disconnected. Hidden fresh profiles used no personal
  browser identity, visible desktop, shared input or clipboard. Physical speech,
  native external-desktop and non-Chromium verification remain **unperformed**.
- Real V2 `probe_web_live.py --reports --report-timings` verified shell/source/two
  SSE streams and retained Live origin, then **FAILED** at Normal's typed retryable
  `connection_timeout` (about 15 seconds in the child). Later report/cancellation
  stages were **unperformed**. Cleanup retained zero owned threads/processes.
  Cause and baseline relationship remain **unknown**, not established unrelated.
- Independent real Comparisons with an isolated disposable cache completed in
  **89.141s / 9.013s**, scanning 2,774 roots and returning 294 groups, no result error.
  Both are usable **partial coverage (`complete:false`)**, not full-coverage PASS.
  Evidence: `scratch:/evidence/comparisons-live.txt`. No inference/source writes or
  shared OpenCode stop was performed.

**Decision Delegate** authorized this FR-only verification exception: accept the
independent heavy Comparisons and hidden/VM/spawn/direct-backend evidence without
requiring successful Normal or its unreached later real-cancellation stages, physical
desktop/speech or non-Chromium proof. Genuine source failures are explicitly allowed
by the FR; expanding this change into source-performance repair or On Hold is not
justified. Delivery remains conditional on final Full and validator success; no
future failure, cleanup flaw or blanket source-performance waiver is granted.

Earlier failed checks stay visible: the first Full found an invalid synthetic Models
DTO in the new VM fixture; it now supplies the required Normal/acquired result. The
second Full encountered Windows discovery fallback and a watchdog-fixture
`process.close()` ValueError. The isolated discovery harness omitted its extracted
function's `Write-LaunchActivity` dependency, only called when startup crosses 120ms;
an explicit no-op test stub fixes that missing dependency without weakening discovery
assertions or changing production launchers. The watchdog test passed its focused
rerun; this does not prove the earlier cleanup failure harmless or pre-existing.
Browser-probe repairs used absolute profile paths, correct Stats logical coverage,
and the actual typed source-readiness seam. One earlier Stats probe was invalidated
by an intentional product-file edit during its host lifetime; the source-change guard
correctly stopped it. The frozen-source rerun passed. No watchdog/cap was increased.

The third Full again failed `process.close()` with a still-running child, this
time in the actual spawned Stats-slice test (`scratch:/evidence/full-accepted.json`);
Windows discovery and the watchdog test passed. No complete Full PASS was claimed.
Investigation established the missing confirmed-exit guard: old cleanup terminated
even after a valid result, joined for one second, killed/joined for another second,
then closed handles unconditionally. The exact cause of the rare Windows delay
remains **unknown**. A bounded owned-handle timing probe did not reproduce it;
natural-exit grace is a mitigation, not a proven OS diagnosis.

**Decision Delegate** authorized a bounded safety repair within FR000615: only
validated terminal IPC (also requeued completed Stats slices) gets up to one second
of natural-exit grace. All other paths keep prompt forced termination and the
existing one-second terminate/kill joins. Cleanup confirms exit before releasing
handles/active ownership; a still-live child latches `report_worker_stop_timeout`,
blocks polling/result reuse/replacement/eviction and retains its owner. HTTP
cancellation forwards the fault to host shutdown with a sanitized 503 instead of
an unobserved executor failure. Serving cleanup still closes Live/events/HTTP;
main-owner close retries retained work boundedly, preserves the fault and accounts
worker time once. No indefinite reaper, source-performance expansion or desktop
permission was added. This decision does not waive any recurring cleanup failure.

Deterministic process/IPC tests cover natural success/error, Stats-slice requeue,
exhausted grace, forced watchdog/cancel/shutdown/malformed/EOF paths, retained live
handles, blocked result reuse/admission and later confirmed-exit idempotent cleanup.
Real host-thread and authenticated loopback-cancel tests prove fault propagation,
independent resource closure and main-owner retries. The first new latch test used
a foreground Normal request ahead of its intended Comparisons worker; correcting
the test's queued neighbor to background Token Mix respects existing priority.
The affected runtime/Stats/shutdown/lifecycle (including parent-loss)/loader tests
then passed **94 tests**.

*Later change (FR000624):* the blocking one-second natural-exit join after valid
terminal IPC was replaced by publish-before-exit nonblocking retirement with the same
grace/terminate/kill escalation, resident-child accounting and latched failure; see
[foreground recovery](foreground-recovery.md) and the current web module contract.

Final product-source Full passed **154 file targets / 1,824 tests: 1,823 passed,
one macOS zsh/PTY-unavailable skip, zero failures/errors**, in 147.0 seconds.
Evidence: `scratch:/evidence/full-safe-stop.json` and `full-safe-stop.log`.
The v80.195 validator passed **11 checks, zero failures**, with the same six
advisory size warnings (Web guide, README, version history, context, reports/service,
Watch coordinator); no caps/baselines were raised.

The first post-repair frozen production-browser run **FAILED** the generic
15-second broad-goal wait while valid progress reached 20/24 roots in ten children;
no runtime/host/cleanup fault was reported. Exact contributions from concurrent
Full load and child teardown timing remain unproven. **Decision Delegate** approved
45 seconds only for this deliberately slowed 24-root/twelve-child completion wait,
leaving other waits at 15 seconds, outer limit at 180 seconds, all assertions and
the product's 120-second child watchdog unchanged. This is a test-harness correction,
not a performance or cleanup waiver. The harness also now asserts runtime errors
on its slices-only path and checks post-cleanup process exit/errors rather than
writing PASS before teardown.

The single corrected frozen-source run **passed**: 7-day coherent milestone at
2/24 roots before broad readiness, original 30-day goal finishes after navigation,
two-tab identity/reuse, twelve finite children and exactly 24 hydrations. Final
owner evidence shows no active child, host failure, serving/HTTP threads or runtime
errors; events closed and both fixture processes/browser exited normally (code 0,
no signal, empty server errors). Evidence:
`scratch:/evidence/ai-stats-safe-stop-final.json`. The saved failed first run remains
`scratch:/evidence/ai-stats-safe-stop.json`; its detailed progress is recorded above.
Earlier full UI/layout probes predate only the safety repair; no later UI changes
invalidate their scoped evidence. Real Normal and physical/non-Chromium limitations
remain exactly as described above, not PASS.

## Historical FR000609 verification

- Full local suite: 153 bounded file targets, 1,787 tests; **1,786 passed, one
  existing macOS zsh/PTY skip, zero failures**. The Windows host cannot execute
  that native macOS case. Evidence: `scratch:/full-tests.json` and
  `scratch:/full-tests.log`.
- After final completion-paint/visibility/source-wait changes: **60 focused tests
  passed** across `test_web_loading`, `test_web_views`, `test_web_runtime`,
  `test_web_source_startup` and `test_application_reports`. Deterministic Node
  checks cover real work maps, opaque/batch/stale events, never-ready exhaustion,
  cancellation, deadline, permanent errors and hidden completion settlement.
- Final working-tree validation including delivery documentation: **11 passes, zero
  failures, six advisory size warnings** (Web guide, README, version history,
  context, report service, Watch coordinator). No caps were raised.
- Final hidden Edge 156.0.4314.58 shared-loader probe: **10 checks, 24 layouts**,
  four routes by Classic/Web light/Web dark and 360/1366 widths. Actual served
  authenticated assets verify automatic first acquisition, retained loader/bar,
  monotonic counts, integer AX progress, stage below bar, reduced motion,
  applied-completion settlement, quiet retained data/focus, real HTTP 429 recovery
  and cancellation while waiting. Comparisons' empty notice/search are absent and
  its reserved empty pager is invisible. Screenshot inspection agrees. Evidence:
  `scratch:/loading-final-evidence/browser.json` and four route screenshots.
- Independent existing hidden probes passed: Token Mix **4 checks/9 layouts**,
  AI Stats **8/9**, Comparisons **7/9**, including sorting, scopes, retained/withheld
  results, help, focus, paging and visible/hidden cadence. Evidence:
  `scratch:/token-mix-browser.json`, `scratch:/ai-stats-browser.json`,
  `scratch:/comparisons-browser.json`.
- Production HTTP/source-startup fixture: **three browser cases passed**,
  including immediate AI Stats entry, `source_starting`, one existing wake and
  automatic readiness recovery. A CLI success without real readiness remains a
  truthful failure. Evidence: `scratch:/startup-evidence`.

Reproduce the focused browser check with `node
development/tests/integration/probe_report_loading.cjs <Edge executable>
<owned evidence directory>`. The manually stepped fixture is UI/admission proof,
not production-process timing or real private-source coverage. The older optional
Playwright overview script was updated but not run (Playwright unavailable).
Integrated browsing returned `browser.disconnected`; fresh-profile hidden Edge
used no personal profile, visible desktop, shared input or clipboard.

## Historical FR000609 real installation results and unresolved cause

Read-only real V2 probes made no model inference calls and did not stop the shared
OpenCode service. `probe_web_live.py --models` verified shell/source/SSE ownership,
but its Normal report **failed `report_timeout` at the unchanged 120-second
deadline**, last observed in account-cache work (373/404). Owned cleanup succeeded.
Evidence: `scratch:/real-source.log`.

The separate `probe_ai_stats.py` observed:

| Scope / attempt | Actual outcome | Seconds |
| --- | --- | ---: |
| 30 days / initial | **FAILED `report_timeout`**, no periods | 120.065 |
| 30 days / next | Complete, four periods | 55.546 |
| All / initial | Complete, five periods | 9.108 |
| All / next | Complete, five periods | 7.041 |

Evidence: `scratch:/real-ai-stats.log`. Failed/successful work incrementally warmed
the current probe cache; this is not an isolated blank-cache benchmark. A zero
probe-shell exit is not proof that every contained attempt passed. There was no
comparative base performance run: the underlying timeout cause is **not proven
pre-existing or unrelated** to this change.

The controlled startup investigation established that the existing host already
waited for `prepare.finished` before executing finite jobs; the hypothesized early
job-execution race was not established. Typed source readiness now distinguishes
ordinary startup/slot waits from terminal errors and actual expensive-job timeout.
The owner's original precise startup incident remains untraced.

## Historical FR000609 scoped verification decision

**Decision Delegate authorized FR 000609 delivery/merge only** without physical
screen-reader speech/native-platform/non-Chromium certification, successful cold
real-source completion on all four routes, or definitive attribution of the
original incident. Deterministic, hidden Chromium, production HTTP fixture and
live evidence support the UX/recovery correction; repeated cold scans or
disruptive desktop reassurance are not indispensable. These omitted checks remain
**unperformed/unverified, not PASS**; the actual timeout failures above remain
failures and must be disclosed in delivery.

The delegate also waived another Full run solely for the bounded final
presentation/paint changes, requiring the final focused shared-loader browser
regression instead; that regression passed. This decision does not authorize
deadline/throughput rewrites, service stops, inference, desktop access, permission
or Git-protection bypass, nor a blanket future exception. No ZIP, tag or GitHub
Release is generated; current main remains the supported source distribution.
