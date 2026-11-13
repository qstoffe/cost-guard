# Today-first Sessions scope and selected Effort — FR 000696

2026-11-13, v81.40. This supersedes the historical 50-row/all-history-default
Sessions population, not the independent populations of other reports or detail.

## Ownership and semantics

The existing authoritative tree-activity observation builds one cheap timestamp
index. `application/session_catalog_scope.py` reuses AI Stats' configured-timezone
windows and selects eligible roots before scalar/history acquisition. Today is
Sessions' independent default; 7 days, 30 days, This month and All time are explicit
server scopes. Finite windows exclude invalid/missing/future activity. All time
retains history, with invalid activity shown as unavailable.

The existing single scalar lane prioritizes visible 25-row pages and schedules
the bounded union of each interested lease's eligible roots. A Today lease alone
cannot request all historical keys. Independent host warming or another All time
lease may legitimately need other roots. HTTP never hydrates history. First pages
reconcile the current cutoff; older epochs pin period/window/membership/order.
Pinned coverage counts use that epoch's population, not the new day's population.

`reports/session_effort.py` aggregates actual nonzero-usage request contributors:
one selected effort, Multiple efforts, or honest N/A. Default remains selected
Default, never a guessed explicit level. Provider/model/evidence/count breakdowns
are bounded to 24; the dedicated value help reuses FR000694's evidence-qualified
`default (effective)*` formatter. Zero-usage saved/failed settings are not usage.
Model/CCost help does not gain the value-only asterisk.

`session-summary-5` lazily rebuilds old/malformed scalar rows, preserving unrelated
caches and native history. The in-memory catalog also retains source-model/default
dependencies privately and revalidates only eligible roots through the source's
bounded model catalog. A changed source default can therefore update help without
a changed history revision. No new durable store, inference, source write or
pricing-math change is introduced.

The keyed browser table has eight columns, with Effort after Model, and 25 rows
per page. Period is carried through URL, requests, leases, epochs, sort/page
navigation, route return, Retry/Cancel and stale-lease recovery. A pending period
change hides old rows immediately rather than relabeling them as the new period.

## Deterministic performance evidence

The 5,000-root fixture contains 30 Today, 70 seven-day, 120 thirty-day and 5,000
All time candidates. Instrumented cold CCost/Effort/CTX each performed exactly
30 `_analyze` calls and 30 source hydrations, never the 4,970 unrelated roots.
Each filtered indexing denominator was 30. Ten warm polls caused zero hydration;
one revised eligible root caused exactly one rebuild.

| Sort | Cold elapsed | Process CPU | Ten warm polls |
| --- | ---: | ---: | ---: |
| CCost | 1.1920 s | 0.3281 s | 0.0240 s |
| Effort | 0.9255 s | 0.3125 s | 0.0339 s |
| CTX | 0.7441 s | 0.3594 s | 0.0248 s |

These are synthetic workstation measurements, not the owner's prior stopwatch
experience or a claimed percentage speedup. The All time request explicitly
restores the 5,000-root work target. The separate legacy 3,217-key cache fixture
performed zero history hydrations (8.492 s cold mocked keys; 0.618 s for 14 warm
sorts); it is not cold real-history throughput.

Focused coverage includes all eight sorts/five periods and 0/1/24/25/26/50/51
result boundaries, child activity, missing/future/tied timestamps, Stockholm
23/25-hour DST days, month/year rollover, exact trailing windows, pinned rollover
counts, stale period/direction epochs, lease union, empty Today, selected/mixed/
unknown/failed/child/compaction effort, stale summaries and mutable source defaults.

## Browser and installation evidence

Hidden fresh-profile Chrome 157.0.8103.51 passed authenticated shipped HTTP/DOM/AX
period controls, invalid-input rejection, Today cost/effort scope, 25+5 paging,
keyboard/touch, Back/Forward, period Cancel/Retry, route return, independent AI Stats
30-day default, Default/mixed value help and empty Today.
Sixteen Classic/Web light/dark × 360/1366px × 100/150% page-zoom layouts retained
eight columns, 25 rows, usable buttons, unwrapped metrics and no document overflow.

The existing navigation portfolio also passed 20 source/count updates with stable
progress geometry, 24 loading layouts, trusted mouse/keyboard/touch, focus and
Cancel restoration, outage Retry, exact 17-row last page and Back/Forward.
Fourteen warm seeded-key route applications measured 62–82 ms with no loader flash.

A read-only authenticated real V2 installation observation found 3,192 All time
roots versus 30 Today, page size 25, first page 0.132 s and maximum catalog HTTP
0.142 s. During the bounded observation CTX indexing advanced 0→10/30; it remained
pending, not a completed real-source sort or a cold-completion latency benchmark.
The shared lane recorded 13 attempts/12 settled/no retries; independent host work
prevents attributing every attempt solely to this lease. One detail row/chunk was
11,454 bytes and took 4.906 s. Owned workers closed; shared OpenCode was untouched.
No session identities, titles or prompt text are exported in this evidence.

## Verification history and limits

The initial Full run executed all 190 groups: 187 passed; detail-liveness narrowly
missed a timing assertion, runtime teardown timed out, and the HTTP/browser VM
still expected old paging/routes. Isolated Full-budget reruns passed the two
lifecycle files (29.72 s and 15.35 s); corrected HTTP/VM expectations passed in
11.42 s. An intervening focused attempt accidentally used Quick's 25-second file
budget and timed out: it is not a test-file pass.

Two initial period-browser attempts failed due to fixture publication/input-modality
races, not accepted product passes. Waiting for actual source state and sending a
trusted keyboard modality event corrected them; the complete period run above
passed. The final focused scope/effort/catalog run passed all 50 tests.
Package validation passed with zero failures and seven existing advisory warnings;
no budget was raised and no structural baseline changed.

Final Full passed all **190 groups**, jobs 2, **303.3 s**. The final pinned-window
regression also passed (seven period tests), and mutable-default coverage passed
again after invalidation bookkeeping was finalized (seven effort tests).
The hidden live-update probe passed cold hydration, evolving CTX/model metrics,
focused/selected row identity, mouse/focus/touch help, outage recovery and 18
Classic/Web × width/zoom layouts. Its first attempt exposed an older fixture's
obsolete model-help order/casing assertion; that expectation was corrected, not
the product's established source-qualified help.
Deep CI pager/navigation fixtures now explicitly select All time for their
historical synthetic population and expect 25-row offsets; their hosted-only
entrypoint is not spoofed locally. PR checks retain their own actual results.

Final delivery-check results are recorded in the completion/PR.
Evidence: `scratch:/full-tests.log`, `scratch:/resumed-full-tests.log`,
`scratch:/resumed-test_session_detail_liveness.py.log`,
`scratch:/resumed-test_web_runtime.py.log`, `scratch:/resumed-targeted-tests.log`,
`scratch:/sessions-periods.json`, `scratch:/sessions-navigation.json`,
`scratch:/sessions-live-browser.json`, `scratch:/live-sessions.log`,
`scratch:/resumed-validation.log`, `scratch:/resumed-final-validation.log`.
The targeted-tests log records the earlier failed HTTP attempt, not the later pass.
No paid model calls, physical desktop, macOS desktop or screen-reader audio proof
is claimed. Real-source cold sort completion and natural-arrival latency remain
unmeasured; deterministic scope proof does not depend on those optional observations.
