# Determinate session-detail loading — FR 000662

## Ownership and progress

`session.js` reuses `ReportLoading.View` and `.report-loading`, not finite-report
admission or its waiting policy. Shared report code is unchanged. The first-open
bar is a stable DOM instance with explicit `max=100` and numeric `value`.
Opening/source waits start at 0 and cannot advance from elapsed time or polls.

The documented overall phase budget is verified rich-history transfer **0–95%**,
then applied complete DOM **95–100%**. A 220-row session in 50-row chunks reports
50/100/150/200/220 of 220 at 21/43/64/86/95%; zero-row success can prepare directly.
Retries retain the last verified phase watermark, not a fake upstream fraction.
There is no completion delay or extra source request. Stage-only polite status
is a sibling of the busy history region, not inside a busy ancestor that could
suppress announcements. Terminal failure/cancellation clears history busy state.

Begin validates total/offset/revision and row shape. Every chunk validates the
pinned revision, total, exact next offset, positive bounded length and unique IDs
before counting it. A final post-yield generation check prevents abandoned
assembly. Only applied complete rows mark 100%. Retained history never reenters
the initial loader; focus, selection, scroll, export and polling keep their owners.

## Verification

- Focused session tests: 11 tests passed, including API revision pinning, paging,
  empty/one/multi-chunk DOM, exact 220-row counts, malformed/duplicate/oversized
  chunks, expiry/recovery, terminal/auth/identity failures and navigation races.
- Real hidden Chrome and Edge: each passed 48 layout cases — Classic/Web ×
  light/dark × 360/768/1366/1920 widths × 100/125/150% CSS zoom, reduced motion.
  Geometry checks cover centered stable progress, shared bar height, explicit
  value/max, absent normal warning/overflow and stage accessibility structure.
  Actual authenticated Sessions click transfers 1001 canonical synthetic rows;
  controlled 220/1/0-row cases prove counts/completion, cancellation, hidden polling,
  retained refresh/outage, focus/selection/scroll, hover, keyboard, emulated touch
  and real browser Back.
- Read-only real V2 installation: 3088 available sessions; 47 visible scalar keys
  acquired during the bounded observation. Pinned detail returned 2 rows in one
  chunk; independent detail/freeze check returned 1 row consistently. Live owner
  stayed intact; no model calls were initiated, no cleanup failures or owned
  worker survivors, and shared OpenCode was untouched.
- Native Chrome page zoom also passed 48 cases at 100/125/150%. At fixed requested
  window width 1366 with no metrics override and CSS zoom 1, actual CSS viewport/DPR
  were 1344/1, 1075/1.25 and 896/1.5. Thus browser zoom is independently established,
  not inferred from settings readback. Matrix-only device bounds accommodate the
  headless minimum-window clamp; measured CSS widths are 360/768/1366/1920.
- Full ran all 181 groups: 180 passed and one failed on the obsolete expectation
  that retained history removes every progress node. The corrected test asserts
  one stable **hidden** loader plus unchanged 151 rows. Focused real-HTTP view and
  detail rerun passed all 13 tests on current source. The original Full run is not
  reported as green. Working-tree validator result is in `COMPLETION.md`.
- Decision Delegate accepted acceptance-6 evidence after the native-zoom check:
  actual viewport/DPR plus 48 real-zoom layouts and earlier interactions suffice.
  No verification exception, disruptive testing or correctness waiver was needed.
  Compact browser evidence: `architecture/governance/verification/session-loading-662.json`.

## Limits

The integrated browser was disconnected; existing hidden fresh-profile Chromium
transport supplied real browser evidence without desktop effects. Native page zoom
was tested independently of the CSS-zoom matrix. Renderer-local input does not prove
physical hardware input, OS scaling, spoken screen-reader output or macOS. Real installation observations are counts/
contracts, not a reconstruction of the owner's private visual incident. Natural
arrivals and complete global metric sorting were not established by the bounded
installation probe and are outside this detail-loading change. No paid inference,
new acquisition scan, shared-service stop or packaging was introduced.

## Finite source acquisition FR000674

### Reproduced causes and boundary

The owner reported v81.21's indefinite pre-publication 0% wait, without an affected
ID or sanitized trace. This investigation reproduces causal code paths, **not the
unidentified private incident**. Previously, a failed service factory called
`details.tick(None, unavailable=True)` and then dereferenced `service.source`.
An unexpected detail-future exception escaped `tick_details` into Live's outer
failure handler. A permanently blocked read also occupied the sole detail thread
indefinitely. None of these paths published a useful acquisition failure; shorter
browser polling alone could not repair them.

Watch still owns admission, retry and publication. Its one supervisor thread runs
one private spawned capture with exact-parent death ownership, detached history
and epoch-qualified interruption evidence. Web composition injects the spawn-safe
target; HTTP only records intent and reads detached status/chunks. The child owns
its source, pricing/cache resources and canonical analysis, without account work
or model calls. Ordinary detail failures are isolated from shared Live.

Measured socket reads, normalized messages/parts, analyzed invocations/prompts,
projected rows and serialization blocks renew a 120-second **silence** watchdog;
phase-only callbacks and identical polls do not. There is no total advancing-work
deadline. Even the shared progress lock has a bounded parent read: an unresponsive
child holding it cannot disable cancellation/the watchdog. Retirement addresses
only that owned child, joins termination then kill, and retains exact process/IPC
ownership if exit cannot be confirmed. No replacement is admitted in that state.

Three consecutive retryable failures exhaust the local budget, with 5/10-second
backoff. Terminal source faults and a 120-second unadmitted queue are actionable
failures. Opening/polling cannot renew a failed budget; explicit Retry resets
acquisition, not verified history. Attempt/demand/source-epoch checks reject late
outcomes. A snapshot freezes only actual verified content, not a failed generation.
Internal file IPC is capped at 256 MiB without truncating a successful report;
bulk serialization stays outside Live and HTTP locks.

The foreground Decision Delegate selected this owned-process boundary over an
unkillable thread-only alternative. This was an architecture decision, not an
acceptance waiver. Normal detail-future faults also remain harmless during host
close; an unconfirmed owned-child exit still propagates as an ownership failure.

### Verification, 2026-11-11

- Full: **183/183 groups passed**, 2273 tests passed and two native macOS zsh/PTY
  tests skipped on Windows, 138.8s with four workers and a bounded 240s/file limit.
  All **14 liveness tests** passed; coverage includes real V1 SQLite/V2 HTTP
  adapters, archived/child cost parity, revision churn, typed errors, poison/healthy
  peers, 1000/10000 rows, advancing work, Retry/late results, source epochs,
  crash/start/cancel/uncertain-exit cleanup and progress-lock starvation.
- The inherited Full had one obsolete missing-session UI-text expectation; that
  original run was not green. The corrected real-HTTP view test and the fresh Full
  passed. After adding the status-read/Retry-click regression, all **11 focused
  detail tests** passed again. Duplicate clicks serialize and the original click
  is not silently discarded while a status request completes.
- Inherited actual hidden Chrome loading and native-page-zoom probes passed:
  authenticated 1001-row transfer, 48 CSS-layout and 48 native-zoom cases,
  stable geometry, focus/navigation and no hidden-tab requests.
- Fresh authenticated hidden Chrome process-liveness acceptance passed: a truly
  blocked child retires, a competing healthy snapshot publishes, three failed
  attempts end in typed Retry rather than endless 0%, and repeated 25-request
  status bursts cannot create source captures/reset the budget. The synthetic
  silence threshold is 3s versus the production 120s; it was not enlarged to get
  acceptance. Twenty-four error layouts cover Classic/Web light/dark, 360/1366px,
  100/125/150% CSS zoom, focus/aria and Back/Forward. Keyboard Retry recovers exactly
  1001 rows/100% after DOM; hidden polling adds no request and leaving a poisoned
  route prevents old-session publication.
- Chrome recovery took 2.579s from Retry, **1064.6ms publication-to-DOM** and
  790.9ms first-ready-response-to-DOM, not an extra five-second poll. The capture
  took 0.995s, 613518 input/1094581 output bytes and one snapshot read. Work counts
  mix measured operations, not a percentage or a row-denominator estimate.
- Edge independently passed the same process-liveness/24-layout acceptance,
  including a final assertion that route retirement joined the fourth owned
  child. Recovery was 2.593s, publication-to-DOM 1138.3ms, with one snapshot read.
- Initial browser attempts failed in test transport, not accepted as PASS: console
  children under the stdin-command host stopped entering the target after the
  first retirement. Reusing the existing fixtures' verified sibling `pythonw.exe`
  child interpreter resolved it, without command-pump workarounds. The initial CDP
  Enter lacked its character text and issued no Retry; complete Enter input now
  exercises the real button. Temporary traceback/debug pumps were removed.
- Fresh read-only authenticated V2 installation probe: 3113 available sessions,
  60 indexed (50 visible), first page 0.091s; pinned detail one row/one chunk in
  2.156s, independent freeze check consistent, maximum detail HTTP 0.0794s and
  detail-worker capture 1.608s. One Live owner remained; zero owned threads/processes
  survived close, shared OpenCode untouched, zero initiated model calls. The bounded
  observation did not finish the global metric sort or observe a natural arrival;
  partial price identity evidence stayed qualified, not zero. The private incident
  was not established. These are actual controls, not synthetic reproduction.

The integrated browser was disconnected; existing hidden fresh-profile Chromium
provides non-disruptive browser evidence. No physical input, spoken screen reader,
OS scaling or macOS result is inferred. The working-tree validator passed with
zero failures and seven existing advisory budget warnings. Compact evidence:
`architecture/governance/verification/session-detail-liveness-674.json`.
