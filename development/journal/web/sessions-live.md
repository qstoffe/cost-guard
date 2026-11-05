# Live Sessions catalog and complete history

FR 000593, 2026-11-05. Current owner map: `development/architecture/modules/web.md`.

## Design and scoped decision

Catalog metadata cannot establish exact Model, CCost, Prompts or Duration keys.
The active read-only Decision Delegate explicitly approved a bounded reconstructible
scalar index and temporary metric-sort unavailability during cold indexing/revalidation.
This exception applies only to acceptance 3 and the metric-sort part of acceptance 4:
activity/name remain available, all metric keys across the available catalog must be
validated before publishing that sort, and unavailable is never PASS/page-only order.
Canonically established unknown/partial values sort deliberately last; unindexed is
not canonical unknown. Delivery need not wait for the entire real historical catalog.
The reason is correctness without eagerly hydrating every history interactively.
No other requirement or verification exception was authorized.

One shared observed catalog feeds Sessions without report jobs/per-tab scans. A
single index worker alternates visible/live priority with oldest-attempt admission,
at most four roots/slice and no further admission after two seconds; individual
source work retains existing transport bounds and cancellation. Dependencies are
rechecked every 60 seconds while browsing. Scalar caches include source provenance,
root revision, analysis/configuration, comparison prices and algorithm. Live/running
roots force fresh reads; cache corruption is a miss. Stable older-page epochs retain
membership/order while page 1 tracks current applied keys.

Detail reuses isolated canonical history capture. Internal 25-row rich chunks pin
one revision across concurrent capture changes. Complete-session footer/context are
canonical, not chunk totals or a browser estimator. Watch's context/help components
are shared; the old mode/pager/report shell is absent only from Sessions.

## Actual observations

The first Full run found two causal regressions: a removed Watch contextLabel field
and obsolete Sessions snapshot expectations in the broad HTTP/VM test. The field was
restored; the test now verifies Sessions produces no finite jobs while retaining
other routes' explicit/frozen semantics. Focused reruns passed after these repairs.

Hidden fresh-profile Chromium over synthetic HTTP/assets covered 120 roots, a cold
index becoming globally sortable, stable older pages/live arrivals and 1,001→1,002
complete chronological prompts. The initial large-table render stalled: per-row
selection queries and attached grid insertion caused pathological layout work.
One selection snapshot per update and detached/batched suffix insertion fixed it.
Selection/document anchors and running→ended/source-failure/recovery were observed.
Classic/light/dark × 1920/900/360 CSS pixels × 1/1.5 CSS zoom covered catalog layout;
detail covered all three themes at 1920/360. This is hidden rendered proof, not
physical desktop/browser-zoom/macOS/screen-reader acceptance. Initial successful
synthetic source-arrival-to-visible-page latency was 5,071ms. The post-Resume repeat
passed the same matrix in Chrome 156.0.8078.80, with 5,078ms discovery. The final
rendered repeat after identity/selection hardening passed with 5,097ms discovery.
The final row-order repair repeat passed with 5,047ms discovery.

Read-only real installation: `py -3 development/tests/integration/probe_web_live.py --sessions`
used the normal production composition, V2, one Live owner and two verified streams.
No model inference, source write, visible desktop operation or shared OpenCode stop.
The available catalog contained 2,692 roots. The first 50-row response took 48ms;
index coverage advanced 0→7 during the 30-second observation and global metric sort
correctly remained **pending**, not passed. Maximum observed API response was 195ms.
One real two-prompt detail used a coherent 13,718-byte rich response; first acquisition
took 47.540s (detail worker maximum 43.901s). Index slices reached 7.607s, illustrating
that a single source operation exceeds the two-second *admission* budget. Parallel
card/history work was also slow (70.027s/46.142s maxima). The API remained responsive;
separate lanes do not eliminate shared source/CPU contention. No natural new session
was observed, so real source-to-browser arrival latency remains **unmeasured**.
All probe-owned threads/processes closed with no cleanup failures.

A second real-source run after the scalar-completeness repair observed 2,695 roots,
coverage 0→19, 51ms first page, 282ms maximum API response and 32.208s two-prompt
detail acquisition (29.548s worker). Metric sorting remained explicitly pending;
natural arrival latency was again unobserved. A single index slice reached 8.802s.
One history-batch exception and its enclosing advance exception appeared in the
phase counters (which do not classify the exception); the probe still verified
owner/stream continuity and zero remaining owned workers, with no cleanup failure.
These observations do not certify fast real-source history or full cold coverage.

The next Full run passed 144/145 files but exposed cold/warm completeness drift in
the legacy finite session-list API: a generic row change used a transient snapshot
flag that disappears on derived-analysis cache hits. The fix keeps that historical
API's pricing semantics unchanged and establishes source-completeness specifically
on a scalar-index cache miss, retaining it in the scalar summary. This is a causal
compatibility repair, not a weakened parity assertion.

The selected-row reclassification regression first exposed an incoherent VM fixture
(removed row without matching total), then a real reconciliation defect: stale
pre-mutation row positions could reorder the suffix. The fixture now retains the
API's coherent total; structural changes wait for protected obsolete text to be
released, then reconcile against current DOM positions. The focused ten-test detail
file and rendered 1,001-row repeat passed. One concurrent Full run also encountered
the unchanged Windows Python-discovery fixture's PATH-fallback assertion; its
five-second child-probe bound and AST harness were inspected and the isolated
20-test file passed unchanged. Contention is plausible, but the exact transient
cause was not established; no product timeout or assertion was weakened.

Final local verification after all repairs: Full **145/145 files passed, 90.9s**;
working-tree validator **11 passes, zero failures, six existing advisory warnings**.
The final hidden Chrome repeat passed separately, avoiding competing browser work
during the unchanged native discovery fixture. No hard caps or baselines were raised.

## Limits and retained lessons

The real cold catalog is not fully indexed and churn/large-history warm-up latency
is not certified. A restart can reuse validated scalar caches, but source/config/price
changes reopen pending coverage. Do not replace this with deceptive loaded-page sort.
The production-coordinator regression blocks the catalog worker and separately proves
detail completion and catalog HTTP-owner reads; this proves lane isolation, not a
universal real-source latency bound. Physical/native macOS/assistive checks were not
run, and synthetic CSS zoom is not native OS scaling. No paid/model session was
created to manufacture arrival evidence. Retained history cannot reconstruct source
data deleted before first observation. No ZIP, Git tag or GitHub Release is produced.
