# Models source isolation and shared control focus — FR000695

2026-11-13; v81.39. Instrumented RED on `b3723a2`, repaired source in
`08e1ffb` plus the final diagnostic-probe update. This is scoped evidence, not an
exhaustive audit or replay of the owner's stochastic physical-desktop incident.

## Causal observations and repair

The shipped authenticated HTTP/CSP/JavaScript ran against the existing canonical
synthetic pricing/Harbor fixture, with native CDP mouse, touch and keyboard input.
No DOM pseudo-class was mocked.

| Observation | RED Chrome 157 | Repaired Chrome / Edge |
| --- | --- | --- |
| Equal-price observation after >5 seconds | Benchmark root removed once; all price rows replaced | Zero benchmark removals; same price/benchmark rows |
| Changed price snapshot | Second benchmark-root removal | Benchmark root/rows untouched; changed price records update |
| Benchmark status/date-only refresh | All benchmark rows replaced | Same rows; factual date/status alone update |
| Tab to price Refresh, then mouse-click that same element | After completion `:focus-visible=true`, `:active=false`, solid accent 3px outline | No pointer outline or pressed shadow |

`render.js` retains a Models root and section controls. Price records use
publisher/model identity plus prepared-data signatures; benchmark records use the
source configuration ID. Same-order equal records do not move. Status/fetch dates
are not row revisions. One changed Harbor record retained the other three physical
rows. Backend source dispatch, valuation, security and host scheduling are unchanged.
Initial/route entry, explicit benchmark work and existing independent polling own
benchmark reads; price publication no longer triggers them through `show()`.

`control-focus.js` owns input modality independently for each document. Pointerdown
marks the actual button/link/filter/help target even if it already has keyboard
focus; subsequent keyboard use clears that ownership. Only those marked outlines
are gated. Native focus, visible keyboard rings, route highlight, pressed/toggled
state, native text-entry focus and tooltip lifetime remain separate. No blanket
outline removal, automatic blur, bespoke timer, extra request or persisted state.
Price recovery is keyboard-only; benchmark recovery also refuses moved focus.

## Executed browser/source checks

- `probe_models_refresh.cjs <Chrome> <output>`: PASS. Existing source failure/retry,
  duplicate coalescing, Enter/Space, deliberate filter focus, touch, 240 toolbar and
  36 table-parity cases. Shipped authenticated host with synthetic source/jobs,
  not production child-lifecycle proof.
- `probe_models_refresh.cjs <Chrome|Edge> <output> --isolation-only`: PASS for
  changed/equal prices, >5-second wait, status/equal benchmark observations, one
  changed Harbor record, independent concurrent actions, reciprocal source failures,
  retained rows/date and local feedback, route return and genuine health resync.
  Sanitized network trace records separate Models and Harbor endpoints. Chrome's
  extended run also verifies both Refresh buttons through native Tab→Enter/Space,
  restored solid keyboard rings and subsequent touch without an extra ring.
- `probe_web_help.cjs <Chrome|Edge> <output> --control-focus`: the 61-record
  control/style matrix passes. All eight nav entries, Models filter/sort, Watch/help,
  AI Stats period, controlled Sessions sort/pager/detail/export cancellation,
  Settings help, actual native Document PiP return/Fit/header, mouse/touch/keyboard,
  360/1280 Classic/Web, 100/150% CSS zoom, forced colors/reduced motion. The picker
  cancellation is simulated; no native Save As or successful file write is claimed.
- `probe_web_live.py --refresh-prices`: PASS against actual V2 installation and
  GitHub source: 31 catalog rows, new strict upstream observation in 5.207 seconds,
  pinned Watch catalog unchanged, zero model calls and owned teardown complete.
- `probe_web_live.py --benchmark`: PASS against actual sources: 53 Harbor records,
  29 matched configurations, 31 reference models, source-wide denominator and
  independent pricing retained through force refresh. Zero model calls; own
  Live/HTTP workers closed and the shared OpenCode service was untouched.

Evidence files use the worker's own scratch, not another worker's state:
`scratch:/isolation-red.json`, `scratch:/isolation-chrome-final.json`,
`scratch:/isolation-edge.json`, `scratch:/prices-chrome.json`,
`scratch:/focus-transfer-chrome.json`, `scratch:/focus-transfer-edge-diagnostic.json`,
`scratch:/live-prices-final.log`, `scratch:/live-benchmark.log`.

## Precise PiP evidence boundary

The final probe first leaves the owner on Models with the same PiP open. Native
mouse, Tab→Enter and Tab→Space return it to Watch. Before any harness focus command
or focus emulation, it records both documents' `hasFocus()`, native focus/blur events,
PiP identity and computed styles. It then revisits PiP and samples before another Tab.

Both Chrome 157 and Edge 157 report **both documents focused before and after**
each action, with **no distinguishing window focus/blur events**. Headless Chromium
therefore does not establish exclusive PiP focus initially or prove actual
PiP-to-owner focus transfer. Result: **MATRIX_PASS_FOCUS_TRANSFER_UNVERIFIED**, not
full PiP/physical-focus PASS. Actual route change and the same open window are
verified. Mouse resting/revisit has no outline, shadow or active state; keyboard
resting/revisit retains its solid focus ring with no active state. No product
failure is inferred from these non-discriminating headless window signals.

The owner's exact intermittent OS-window incident, exclusive OS/window focus
transfer, native successful Save As and physical assistive-technology behavior
remain **UNVERIFIED**. This repair addresses the reproduced source-shaped DOM and
same-element modality failures; it does not claim every stochastic permutation is
permanently eliminated.

### Authorized minor verification exception

Decision Delegate, 2026-11-13, authorized **FR000695-only** completion without
verified exclusive owner/PiP focus transfer or halo behavior across genuine native
window blur/revisit (§5G). These observations remain **UNVERIFIED**, not PASS.
Reason: both browsers' headless focus signals are non-discriminating, while the
per-document modality implementation does not depend on `hasFocus()` or blur
events and leaves the native return callback intact. Source-shaped RED/after,
independent source/DOM behavior and native keyboard-preserving PiP/control styling
provide useful discriminating evidence. Focus emulation would manufacture the
missing condition; visible-desktop disruption and equivalent headless repetitions
are not warranted.

Residual risk: browser/OS-specific focus/event behavior absent from this environment.
No product work is deferred, no new access is authorized, and no Suggestion or On
Hold is required by this decision. The owner incident remains unobserved; native
successful Save As and physical assistive technology are not additional claimed
outcomes. Simulated picker cancellation remains explicitly synthetic.

## Final local gates

- Full: **188 groups, zero failures**, 159.0 seconds; run after final production
  presentation/metadata changes. Deterministic focus and retained-row regressions
  are included.
- `validate_package.py --working-tree`: **11 passes, zero failures, seven existing
  advisory warnings**, v81.39. No caps were raised or exceptions rebaselined.
- Final browser-only diagnostic harness changes were exercised by the completed
  Chrome/Edge runs above; they do not change product behavior.
- Current docs/architecture and the three related journals are updated. No ZIP,
  paid inference, installed-source/cache edits or shared OpenCode restart.

## Failed/interrupted attempts retained honestly

The first Full run exposed old deterministic DOM harness assumptions (no keyed
insertion/parentage and an optional benchmark). Those were repaired, and all 188
groups subsequently passed. Tests retain their assertions, using physical-node
identity in the updated Models regression.

An earlier broader `--models --refresh-prices` live run completed the strict
31-row price action, then encountered a connection reset during an additional
Normal report. Source edits occurred while that test host was running; its
source-change guard is a plausible explanation, not a proven diagnosis. That
broader run remains interrupted, not PASS. The focused immutable-source rerun
above passed the actual required price action and owned cleanup.

One Edge diagnostic attempt recorded only FAIL and encountered a disposable-profile
`EBUSY` during cleanup, obscuring the primary failure. The harness now retains
primary evidence and reports locked cleanup without masking it. The subsequent
diagnostic matrix completed with the explicit focus-transfer limitation above.
No locked target was retried/force-unlocked; bulk cleanup belongs to native finish.
