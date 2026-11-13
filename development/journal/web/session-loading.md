# Session-detail loading

Current behavior is [FR000686's source-driven whole-operation plan](#source-driven-whole-operation-progress-fr000686).
The original FR000662/FR000674/FR000673 observations below are historical evidence,
including the intentionally superseded pre-acquisition 0% policy.

## Ownership and progress

Original FR000662 policy (superseded by FR000686):

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

## First-load measurement FR000673

2026-11-11: current main already contains FR000674's 500ms visible pending-read
cadence and detached source status. No duplicate runtime fix was added. New
`detail-delayed` fixture mode performs twenty measured source units at 250ms each,
then the canonical 1001-row capture through the actual owned process supervisor.
The hidden Chrome157 authenticated browser records queued/reading/publishing phases,
real counts and **0% throughout pending** without inventing a fraction or denominator.

`probe_web_sessions.cjs --detail-first-load` passed: total7654.2ms,
publication-to-first-ready-begin224.8ms, publication-to1001-row-DOM1172.1ms and
100% only after complete DOM application. The >=5s source delay plus setup/capture
is real fixture work, not claimed browser lag. Readiness discovery<1250ms and bulk
1001-row DOM<3000ms separate the avoidable polling cost from transfer/rendering.
An initial DOM<1500ms assertion failed at1602.3ms during concurrent Full; that run
is not PASS. Correcting the measurement boundary did not change product cadence.

The existing comprehensive loading probe also passed48 CSS layout cases and
authenticated1001/controlled220/1/0-row, navigation/cancel/hidden/focus/selection/
outage behavior. Native page zoom, OS scaling, physical input and macOS were not
rerun. Evidence: `scratch:/first-load.json` and `scratch:/loading-layouts.json`;
FR000673's separate [pricing/account journal](../claude-agent-ccost.md) records the
unrelated scoped live-inference exclusion. These source-shaped browser tests do
not reproduce the owner's unidentified private incident.

## Source-driven whole-operation progress FR000686

2026-11-13, v81.36. Reproduced before changing product code: the existing authenticated
browser fixture took 7939.7ms, emitted reading/analysis work, and painted **0 throughout
every pending response**. The transfer-only allocation caused the apparent freeze.

### Current contract and boundaries

`domain/progress.py::DetailProgress` defines a **milestone budget**, not an estimate of
time or one universal count denominator. Admission/selection = 3, revision verification
= 10, source reading = 15–40, analysis = 40–55, projection = 55–65, publication = 65–69.
Explicit entry alone proves the start of that stage. A known local completed/total
can consume the remainder of its band; otherwise the stage holds its entry point.
Only the parent accepting a successful source outcome marks source-ready at 70.
Known V2 discovered-tree members and already-discovered publication rows contribute
real local fractions. Analysis/projection currently expose entry milestones, not
invented total work. Their very short stages may complete between browser paints.

The child `WorkMeter` transports phase, percent and optional local counts separately
from the heterogeneous cumulative liveness counter. Nested scalar checkpoints cannot
prematurely switch the outer history stage. Existing 50ms parent observation and 500ms
visible pending polling publish progress without new source reads or another worker.
Phase/count observations contain no source text, identity paths or credentials.
`SessionDetails` qualifies updates by its current attempt and exposes a safe attempt
identifier; a new backend attempt starts its own plan. The browser retains only its
display watermark across automatic retries and labels the retry/current attempt;
previous-attempt counts never become a new denominator. Explicit cold Retry/new lease
resets the bar. Existing generation guards reject late route results.

Validated revision-pinned browser rows consume **70–95%**, with `floor(70+25*X/Y)`
(empty success goes directly to 95). For 220 rows in 50-row chunks the sequence is
**75, 81, 87, 92, 95**. Only the complete applied table sets 100, without a forced
display delay. Shared ReportLoading/CSS, other report loaders, pricing, history
identity and single-worker/retry/120-second silence supervision are unchanged.

An opaque socket/read/analysis operation has no invented within-operation fraction.
It can hold at its real phase milestone until the next actual event; this limitation
is intentional. Repeated phases, liveness units, polls and elapsed time never creep
toward completion. A stalled reading fixture holds **15**, then fails truthfully.
Phase-only callbacks still cannot renew the silence watchdog.

### Fresh verification and measured comparison

- Full: **187/187 groups passed**, four workers, 240s/file bound, 149.9s. Focused
  liveness and detail groups also passed. The final source-tree unit-counter addition
  passed `test_source_history_loading.py`; it adds one observed completed tree unit,
  not another read. Working-tree validation passed (seven existing advisory warnings).
- VM coverage includes exact fractions for **0/1/25/50/220/1001 rows**, unknown positive
  units, repeated/lower watermarks, retry/reset, detached late responses, malformed
  revision/offset/count/duplicate chunks, 100 only after actual rows, quiet retention,
  hidden polling and normal existing failure handling. Backend tests cover separate
  milestones/fractions, invalid denominators, clock-only waits and rejected old attempts;
  existing process tests retain poison/crash/locked-child/source-epoch coverage.
- Actual authenticated **Sessions → click** in hidden Chrome157 ran the shipped HTTP,
  JS, history owner and supervised child with representative delayed message batches.
  Final cold run: **8287.9ms**, source pending sequence **0,3,10,16,18,21,23,27,29,32,34,
  37,39,69**; several nonzero states survived separate requestAnimationFrame paints
  while `result:null` and the table was absent. First nonzero = **608ms** after click;
  first ready begin was 525.2ms after publication; all **1001 rows** applied 1456.3ms
  after publication, then 100%. Warm matching refresh took **20.5ms**, one begin,
  no chunks, same bar/first row and hidden loader. One child, one source snapshot read.
- Matched reference product `f0c7318` ran in this worker's separate disposable baseline
  checkout, with the same source-shaped batch delays and measurement-only fixture
  instrumentation (scalar-only observer compatibility). Cold **8464.4ms**, warm
  **16.6ms**, one child/one source snapshot read, **16 cold begins + 40 chunks**, no
  nonzero pending value. Fixed: **15 cold begins + 40 chunks**; polling cadence unchanged.
  These single-run observations show no extra hydration/child/HTTP workload, not a
  statistically proven speedup. Startup/OS scheduling varies; synthetic batch waits
  exist only in test source fixtures. Production has no intentional delay.
- Chrome's standard loading probe passed **48 theme/scheme/width/CSS-zoom/reduced-motion
  layouts**, plus stable max/value/accessibility structure, exact 220-row counts,
  focus/selection/scroll retention, navigation/Back, hidden polling and late chunks.
  Edge independently passed **48 native-page-zoom layouts**: unoverridden fixed-window
  CSS viewport/DPR were 1336/1, 1069/1.25 and 891/1.5 at 100/125/150%, with CSS zoom 1.
- The first standalone liveness browser run hit its obsolete `bar===0` assertion at
  a truthful 15% reading-entry milestone; that run was **not PASS**. Updated acceptance
  requires all blocked-reading samples to stay exactly 15. Fresh run passed three
  watchdog retirements, healthy peer, unchanged failure budget under status bursts,
  24 error layouts and keyboard Retry to 1001 rows in 2566ms (1067.8ms publication-to-DOM).
  Navigation/Back/Forward closed the blocked lane; final retired-child count was 5.
- Read-only real V2 installation: 3174 available sessions, 27 indexed during the
  bounded sample, one-row pinned detail in **2.7s**, independent freeze consistency,
  max detail HTTP **64ms**, one Live owner preserved. All owned processes/threads
  closed; shared OpenCode untouched and zero initiated model calls. Global metric
  sort stayed pending and natural arrival was unobserved; neither is claimed PASS.

Compact retained evidence: `architecture/governance/verification/session-progress-686.json`.
Detailed own-session traces: `scratch:/baseline-first-load.json`,
`scratch:/baseline-matched.json`, `scratch:/first-load-final.json`,
`scratch:/loading-layout.json`, `scratch:/loading-zoom.json`, `scratch:/liveness-final.json`.
This is source-shaped reproduction and bounded real-installation evidence, **not**
the owner's unidentified private incident. No physical input, spoken screen-reader,
OS-scaling or macOS visual proof is inferred. No acceptance waiver was needed;
no paid inference, shared-source writes, service stop, ZIP, tag or Release was added.
