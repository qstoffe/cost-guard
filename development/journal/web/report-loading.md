# Shared finite-report loading

Source revision: fbcfa8c (FR 000609 delivery base)
Checked revision: fbcfa8c plus FR 000609's feature diff
Last checked: 2026-11-06
Status: current

## Owners and invariants

`src/web/assets/report-loading.js` owns the shared centered determinate view,
observed monotonic stage bands, stale-sequence rejection and bounded cancelable
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

The total browser attempt remains bounded by 120 seconds, with at most eight
backoff waits (500, 1,000, 2,000, then 4,000 milliseconds). Existing server job
deadline, four pending jobs, 8 MiB result bound, session/CSRF/ownership and
cancellation remain unchanged. Historical 5/15-minute checks and one-hour
withholding, AI Stats scope extension, Comparisons revisions and explicit Models
price refresh retain their owners. No new scanner, cache schema or CLI/Live
workflow is introduced.

## Observed verification

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

## Real installation results and unresolved cause

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

## Scoped verification decision

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
