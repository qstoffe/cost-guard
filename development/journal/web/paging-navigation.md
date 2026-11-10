# Reliable explicit paging and Models entry — FR000658

2026-11-10. Scoped change against `288b08358ad3b543d86447c68f40677ecb92fe25`
(v81.7), delivered as v81.8. This is not a whole-Web architecture reassessment.

## Causal finding and ownership

The actual synthetic 321-group/33-page WebHost + DataDispatcher + ReportJobs +
ReportApplication trace reproduced the reported **80% → Waiting for source** shape:
after source revision changed, baseline `app.js::acquire` treated the pinned
`session_catalog_changed` as a generic retryable fault and repeatedly submitted the
same rejected pin. The intended catch/rebase was unreachable. The deterministic
actual-app VM test failed on that same rejected offset/retry state before repair.
This is a reproduced defect, not proof of the owner's particular historical incident.

Comparisons now escapes generic recovery for that code, deliberately rebases once
to unpinned page1 and updates route demand as well as the browser request. The
application marks a rejected **pinned Comparisons** request nonretryable so the host
cannot keep background retrying an invalid pin; unpinned/other-report semantics are
unchanged. A successful user page action resets the one-time rebase allowance.

Explicit page attempts alone get three recovery backoffs and 45 seconds without
forward work. A new work stage or increasing completed count renews that budget;
new sequence numbers/repeated old counts do not. A completed result is consumed
before the pending/no-progress check. Healthy progressing work has no total deadline;
initial/background report lifetimes and host-owned unrelated jobs are not cancelled.
Failure retains the last-good content/summary and waits for explicit Retry rather
than a background lookup silently restarting it. Paging status polls use 1s.

`matched_inputs.py` still checks source membership/revisions and its compact index
for every page, hydrates only displayed previews on a warm stable index, and emits
actual verification/group/previews stages. No unqualified pin cache was added:
live revision churn makes skipping source qualification incorrect. Waiting feedback
names the source/slot reason and recovery attempt, not a frozen completed-work bar.

Sessions and Comparisons share `.page-navigation` CSS and polite range summaries,
native disabled buttons, responsive three-zone layout and guarded action-focus
restoration. Models has a deliberate top/focus policy **only on new route entry**;
refresh/filter/sort/ordinary focus must not reapply it. Benchmark changes only the
initial raw numeric key to Solved descending; valuation, GitHub fonts and manual
retained sorting stay unchanged.

## Separate evidence populations

- Local Windows Full: **181 groups, 0 failures, 131.3s**. Earlier Full was 180/181:
  the new document focus listener exposed a missing DOM-stub method; the stub was
  repaired and this complete rerun passed. Direct report-lifetime VM covers stale
  pin, three recoveries, 45s no-progress, last-good/Retry and healthy unlimited work.
- Working-tree validator: **11 passes, 0 failures, 7 pre-existing advisory warnings**;
  budgets/baselines were not raised. New CI helper modules also compile locally.
- Prior integrated browser, synthetic real backend: Next page2 about0.888s,
  Previous0.844s, page18 0.959s, final page33 onegroup0.841s; same revision/order,
  repeated disabled click ignored and Enter focus retained. Changed pin rebased to
  page1 in0.970s with an explanation. Busy/source-error budgets exhausted in about
  3.6/4.4s, last-good retained, and Retry succeeded. These are fixture observations,
  not latency guarantees. The resumed browser is disconnected. The interrupted
  60-second stalled-source trial's final result is unavailable and is **not PASS**.
- Real installation, read-only, no inference: managed probe saw3056roots/321groups.
  Cold125.474s returned partial coverage; warm5.058s changed revision. Pinned page2
  rejected in4.149s with `session_catalog_changed`, retryablefalse. Unpinned rebase
  succeeded4.295s complete; pinned lastpage succeeded4.299s, same revision, onegroup.
  **No real-source successful page2 is claimed.** A separate ordinary cold/warm
  probe was77.375/3.794s on3055roots; observations are not a matched benchmark.
  Probe caches were isolated/disposable. No source writes, account changes, paid
  model calls, prompt exports or shared OpenCode-service shutdown occurred.
- Deterministic321x3 source checks pin correctness, offsets0/10/170/320, stable
  ordering, warm10/1-preview hydration and measured actual preview callbacks.

## Rendered follow-up and decisions

PR [262](https://github.com/qstoffe/cost-guard/pull/262) runs normal hosted browser
CI. `ci_browser_web.py::check_pagers` exercises real360/1366/1920viewports,
Classic/Web and light/dark media, mouse/keyboard/emulatedtouch, focus/live summaries.
`ci_paging_navigation.py` separately uses the actual source/job/dispatcher fixture
for explicit navigation, faults, slowprogress, production45s no-progress/Retry,
empty/onegroup and before/after Models entry/async observations. Immediate fake jobs
prove layout/input, not real source lifetime. CI results are pending at this entry.

The foreground Decision Delegate authorized that normally triggered CI alternative
after integrated browser disconnection; no desktop/executable discovery, CSP
weakening or workstation `hosted_only` spoofing is permitted/used. No acceptance
waiver has yet been granted. Earlier refused executable inventory remains retired.

Models baseline from verified scrolled Comparisons returned to top in earlier
trials, but the exact-baseline hosted anchor diagnostic on `e31a2f1` reproduced a
downward shift: Comparisons2379px and Sessions1164px outgoing scroll → aftershow0
→ focus/DOMpublication123px → both rendered frames123px, focused `content`.
This exposes baseline hashchange's scrolling `content.focus()` after rendering;
the new-route `preventScroll`/explicit top policy is intended to remove it. It is
not proof that the owner's historical jump had that exact scroll amount or target.
Current before/after validation remains pending. The diagnostic uses native anchor activation,
records nonzero outgoing scroll, show/toolbar/publication and rendered frames,
compares the exact historical app when its object is available, and covers the
other populated routes plus delayed publication and same-route preservation.
Any narrow nonreproduction decision must be recorded here before completion.

First PR head `f70893c`: all three native jobs passed; Quick645/645 and validator
passed. Shared pagers passed24 actual viewport/theme/media layouts with0px center
error, no overflow, polite summary,39.75px buttons and actual mouse/keyboard/
emulatedtouch plus focus. The later navigation check failed: its large annotation
was truncated before failure metadata. The GitHub job-log endpoint returned401,
so its raw-log evidence is unavailable; normal API/annotations still work. The
Delegate authorized compact scenario/failure notices and the next ordinary CI run,
not another log-access route or acceptance waiver. First-head browser remains FAIL.

Second head `e31a2f1` retained Quick645/645/validator PASS and the baseline traces
above, then failed when Token Mix could not become ready. The synthetic finite
fixture omitted top-level `observed_at_ms`, which the actual TokenMixView validator
requires; host/job completion alone did not catch that browser-contract defect.
The fixture now exports that numeric timestamp. A controlled Models release gate
prevents background warming from invalidating the intended cold-entry test, and
the prepared benchmark now has an exact synthetic catalog join and differing raw
scores, allowing real delayed table insertion/default-sort proof. These are test
fixture corrections, not product behavior changes or removed assertions.

Third head `cbfbcf6`: all five baseline origin routes reproduced123px after focus
(outgoing Comparisons2379, Sessions1164, Token Mix3887, Accounts458, Watch2736px).
Its supposed current arm still executed baseline JavaScript: switching host asset
bytes followed by a same-document hash `goto` does not reload a page. Duplicate
show wrappers confirmed the retained document. The harness now explicitly reloads
and asserts old/current navigation-function identity before comparing arms. That
failure is not evidence that the current fix passed or failed its intended test.

Fourth head `ae3ed0f`: verified old/current script identity. All five current
routes finished at0px/contentfocus, versus baseline123px, including post-publication
frames. Cold2s publication/benchmark insertion remained0; same-route filter, manual
sort and refresh retained500px and manual sort; keyboard Models entry passed.
The run then timed out in the added Session-detail70-row check, before paging fault
tests. Those later tests remain pending. Local actual fixture source/detail capture
returned observed70rows without a runtime failure. Follow-up adds inner-tab state
diagnostics and aligns the live fixture clock with its current-wall-time source;
this is not yet an established cause of the browser timeout. Latest Full rerun:
181/181 PASS in131.6s; focused CI/report/dispatch85tests PASS.

Physical touch, screen-reader speech, non-Chromium behavior and native desktop zoom
are not certified by emulated input or viewport sizing. No feature-PR self-review,
implementation agents, ZIP, tag or GitHub Release is part of this delivery.
