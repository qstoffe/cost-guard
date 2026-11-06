# Live Sessions catalog and complete history

FR 000593 baseline and FR 000602 follow-up. Current owner map: `development/architecture/modules/web.md`.

## FR 000602 — table parity and truthful acquisition, 2026-11-06

This supersedes the baseline's alternating admission policy below: seven latest-visible-page
admissions share each eight-turn cycle with oldest-attempt background work. The same four-root,
two-second admission limits remain; slow individual reads still use source transport bounds.
The 120-root deterministic regression follows page 1 then page 2, proves background progress
and observes exactly one acquisition per unchanged root. Full-catalog metric sorting remains
explicitly pending until every key validates, never a visible-page approximation.

Catalog summaries now distinguish pending, unavailable, retained and validated values. Root
failures back off; terminal source contracts wait for changed evidence. Lane-wide factory or
dependency failures also expose unavailable/retained state, rather than infinite Loading.
Current successful summary evidence alone confirms running; status updates do not replace a
selected title. Dates use local Date fields (real timezone/DST), not locale-string parsing.
Web detail selects a separate first-request context token; raw context, rich CLI/Watch
transitions, canonical cost splits and complete-session totals retain their meanings.

Watch, Sessions/detail, Models and both actual post-596 Token Mix tables share compact cells,
surface headers, full dividers and one rounded horizontal shell. Detail grows previews on
roomy screens, yields before metrics and keeps one document-scrolling semantic history.
Initial/pinned acquisition has indeterminate progress; complete retained history stays usable.

The integrated OpenCode browser served the source-neutral fixture and measured all six table
types: 5.25px/9px header padding and 6px rounded shells with the 15px root font. Its screenshot
operation refused a non-visible Review tab after focus; no external desktop was opened.
Hidden Chrome separately captured synthetic pixels and actual HTTP/assets, all three themes,
1920/1366/800/360 CSS widths and 1/1.5 CSS zoom. Thin borders legitimately compute to fractional
CSS pixels under zoom; assertions check the resulting one-pixel line instead of false 1px
computed-style equality. The fixture was corrected to publish current Watch cards rather than
its older row-only projection; neither case waived product assertions. Large history,
selection/scroll, navigation, failures/recovery, running colors, long pager labels and both
13-column tables are covered. Browser/VM locale/DST checks use Swedish and US locales plus
Stockholm/New York spring/autumn instants; timestamp sorts remain raw.

Read-only V2 probe: 2,731 roots, global index 0→12 in the bounded observation, 50ms first page,
211ms maximum API reply; a real two-prompt detail arrived in 23.910s (14,701 bytes). One Live
owner/two streams were preserved, with zero inference calls, source writes or shared-service
stops. All owned workers closed. Global metric sort correctly remained pending; this is not
full cold-catalog readiness or a latency improvement claim. One index slice reached 7.005s
because its individual read exceeded the admission budget. Independent history phase errors
were counted but not classified; this probe does not certify those unrelated lanes. Natural
new-session arrival and physical desktop/browser-zoom/macOS/assistive behavior remain unmeasured.
The first live attempt lost its probe host during concurrent source edits and is not PASS;
the unchanged-source repeat above passed.

The first Full run found the obsolete anchor-only pager selector in the real-HTTP VM test;
it now verifies an enabled button and the same URL-backed older page. A later concurrent Full
run hit the unchanged Windows PATH-discovery fixture's five-second child-probe boundary;
isolated native and changed-detail reruns passed without changing assertions or timeouts.
Contention is plausible, not established. Final serial Full passed all **149 files**, zero
failures, **317.5s**, with unchanged timeouts; validation passed 11 checks with six existing
advisory warning categories. Final rendered discovery was **5,131ms**. An optional synthetic
scratch summary encountered native `SCRATCH_SESSION_BOUNDARY`; the active read-only Decision
Delegate directed omission, no substitute read/rebootstrap, and permitted the independent
owning-transport branch GET. This waived no tests. No new product requirement or test
exception was requested or approved. The completion retains explicit unmeasured scope.

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

## PR CI follow-up

The first PR run failed Linux Full in `test_web_views.py` (one failure; validator
passed), and the rendered smoke stopped at its obsolete Sessions `Snapshot captured`
expectation. All three narrower native jobs passed; that did not waive Linux Full.
Raw job-log retrieval returned HTTP 401, so the existing supported Checks API was
used without changing authentication. Final annotations identify the failed file,
but omit its exact test/diagnostic. Two independent local focused runs passed both
web-view tests; the original Linux regression cause remains unestablished.

The current read-only Decision Delegate approved a justified corrective push, not
an unexplained-failure waiver: migrate the independently obsolete browser fixture,
prioritize failure notices before platform skips and require successful checks on
the corrected HEAD. The smoke now has an owned synthetic Sessions acquisition lane,
asserts the complete ten-column history/footer and hidden finite toolbar, and tests
keyboard focus on an actual visible heading-help button. It still proves the absence
of a Watch source observation and retains finite-report/security/reconnection checks.
A regression pins late failure notices before 30 earlier skips without dropping
either inventory or sanitization. VM wait failures additionally report allowlisted
synthetic catalog/detail state, not credentials; deadlines/assertions are unchanged.
Annotation truncation and fixture/poll timing remain hypotheses, not established
causes of the original regression. No unchanged CI run was restarted for evidence.
After the follow-up, local Full passed **145/145 files in 97.2s**, including the
synthetic acquisition/cleanup and failure-priority regressions; the working-tree
validator again reported **11 passes, zero failures, six existing warnings**.

The corrected-head CI run exposed the exact recurring wait: first 151-prompt detail,
5,063ms, 15 requests, detail still busy. Finite-report cache warming did not warm
`SessionHistory`'s separate observed-history analysis. The transport/DOM fixture now
warms that actual owner before its fixed five-second UI waits; dedicated cold/scale
and polling tests remain unchanged. A controlled six-second first history-analysis
delay passed the corrected test in 12.703s without changing its UI deadline.
A paired ten-second delay then reproduced the bounded UI timeout with the exact
previous committed fixture and passed with the corrected fixture. The first attempt
at the historical comparison used host-default Git-output decoding and hit its
Unicode assertion instead; that invalid comparison was discarded and repeated with
explicit UTF-8. Neither the product nor test assertions/deadlines were weakened.

The same run reached the new live history in rendered Chromium, then failed the
360px document-overflow assertion. At the user's request, the **integrated OpenCode
browser** was tried first; no Program Files inventory or external browser was used.
Electron 44.9.1 / Chromium 152.0.7977.167 rendered the exact hostile-title fixture.
Its viewport was 800px; narrowing the document's content area to 360px exposed the
unbroken h1 at 342px scroll width inside 312px. Applying `overflow-wrap: anywhere`
alone removed that spill. The shipped Sessions-only h1 rule now uses it. A fresh
owned host served the actual updated CSS: heading scroll/client widths matched at
752/752, 312/312 and 232/232 for 800/360/280px content widths, while the ten-column
table retained its independent 892px horizontal pan. This is constrained-content
causal proof, not an emulated 360px top-level viewport or the exact Linux browser.
The CI smoke retains its exact viewport assertion and now also exports bounded
layout dimensions and asserts the heading itself does not overflow.
Final local Full after these two repairs passed **145/145 files in 94.3s**; package
validation remained **11 passes, zero failures, six existing advisory warnings**.
Both temporary integrated-browser fixture hosts joined cleanly with no host failure.

The following Linux CI run passed Full (145 files, 1,709 tests: 1,688 passed and
21 named platform skips) and the validator. The exact 360px rendered check also
passed: page 360px, heading 330/330px and independent table pan 919px. Smoke then
stopped after Settings reload → Back, whose default five-second assertion raced
the actual five-second session poll. The integrated browser reproduced this path:
reload left no retained detail view, the first read had no rows, then the next read
rendered all three rows **5,032ms** later (26ms/17ms individual loads). This is normal
lease/capture freshness, not a lost title or missing history. The two post-navigation
CI waits now use the same explicit 30s acquisition bound as first entry; offline
retention, product cadence, broad-VM waits and all other assertions remain unchanged.
An observed-but-pending lease now also keeps the compact waiting message instead
of temporarily showing a blank history/status. Deterministic VM coverage exercises
pending → next 5,000ms poll → complete history, and ensures pending cannot hide an
explicit source-unavailable warning. No wider browser access was needed.
Local Full after the navigation/pending-state regression passed **145/145 files in
97.2s**, with **11 validator passes, zero failures and six existing warnings**. The
third integrated-browser host also joined with no host failure; its tab was closed.

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
