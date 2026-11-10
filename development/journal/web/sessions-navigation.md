# Sessions global sorting and cancellable navigation — FR 000664

2026-11-10. Scope: host scalar catalog plus Sessions browser navigation, not finite
reports, session detail, pricing mathematics, Mini or OpenCode lifecycle.

## Finding and change

The old client intentionally ignored `pending_sort` when it had usable content.
The server correctly withheld metric ordering until every root had a current key,
but the browser gave no operation feedback or rollback control. Terminal root
failures could keep that gate unresolved indefinitely.

The server now exports source/index generation, requested versus applied sort,
actual global/page counts, typed failure reason and sanitized hit/miss/attempt/retry
counters. Completed source-backed unknowns remain valid sort-last values; an
unresolved model selection is not promoted to an unknown. Existing scalar cache
validation, four-root/two-second admission and source transport limits remain.
Qualified older-page epochs no longer re-gate on unrelated new root membership.

The browser retains the last applied DOM and its pager/epoch, uses the shared
`ReportLoading.View` only for pending navigation, and reserves 100 for an applied
matching page. Local AbortSignal/generations retire obsolete intent. Cancel restores
sort/page/hash/focus/scroll and reasserts that lease demand; shared cache/acquisition
is not cancelled. First-response admission avoids warm loading swaps. Source
failures, three failed scalar attempts, eight rebases, a 45-second no-count-progress
wait or a 15-second unresponsive HTTP request produce visible Retry/Cancel.

## Evidence

- Focused catalog/detail regressions: 40 passed, including shipped-controller VM
  rollback, obsolete responses, genuine failure/recovery, per-page denominators,
  known unknowns and independent prompt/model/CCost facts.
- Synthetic 3,217-root test: four-key slices acquired 3,217 **stubbed scalar-cache
  hits** in 6.892 seconds, without transcript acquisition. Twelve warm global
  asc/desc sorts plus last-page checks took 1.037 seconds combined. These are
  deterministic synthetic scalar timings, not real-source cold hydration speed.
- Real installed V2 source, read-only before: 3,090 available; 0→46 indexed over
  36.198 seconds, metric sort still pending; first page 0.061 seconds, max HTTP
  0.144 seconds. The older probe inadvertently alternated global and Activity
  interest; it is not an equivalent throughput benchmark.
- After, preserving global interest: 3,090 available; 0→75 indexed over 39.315
  seconds, 49 scalar-cache hits/32 misses/81 attempts/0 retries, six observed
  source generations. Requested CCost remained explicitly pending with applied
  Activity and no terminal reason. First page 0.061 seconds, max HTTP 0.249 seconds.
  Detail acquired one row in 1.533 seconds. This bounded observation does **not**
  establish full real-catalog metric-sort completion or reproduce the owner's
  original minute-long click. Watch/history had one concurrent transient failure;
  no Sessions terminal failure was reported. Both probes closed their owned host
  and preserved the shared OpenCode service; no model inference was started.

## Verification and scoped test decisions

- Full: **PASS**, all 181 registered files, 132.7 seconds. The first Full run
  failed `test_web_views.py`: rapid aborted navigation produced `ECONNREFUSED`
  because that fixture performed source acquisition on the HTTP accept thread.
  Separating its acquisition/accept lanes to match the shipped host repaired the
  cause; the focused test and complete Full rerun passed. No product HTTP retry
  or DTO-validation rule was weakened.
- A final one-line failure-generation guard demotes late failed demand instead of
  reissuing an expensive sort. **Final-tree focused VM PASS** after Full, including
  explicit assertions that a timed-out late answer sends `interest(false)` and
  sends no new Model request. Legitimate current reattachment remains covered.
  Full was not rerun after that final narrow refinement.
- Real hidden Edge `--catalog-detail-only`: **PASS**, 156 layout observations,
  seven check groups and zero runtime exceptions. Includes six-column catalog,
  cold metric completion, 120→121 arrival/stable older page, 1,001→1,002 detail
  rows, selection/scroll/end, consumed outage/recovery replies, configured clock
  and DST, plus Watch/Models/Sessions/detail/Token Mix table parity.
- Final-tree navigation-only real-browser acceptance: **PASS**, zero runtime
  exceptions; twelve warm sort applications took 83–144 ms without a loader flash.
  Uses 3,217 seeded scalar keys, all six
  sorts in both directions, cold measured counts, Cancel/failure/Retry, exact
  17-row last page, history, focus, trusted keyboard Enter and touch. The actual
  matrix is **24 layouts** (three themes × four widths × two zooms), not 48; an
  earlier progress/check label miscounted this and is corrected. Post-HTTP held
  responses prove delayed-answer rejection, not network cancellation. Separate
  VM assertions prove AbortSignal retirement and request timeout behavior.
- Working-tree package validation: **PASS**, zero failures and seven advisory
  pre-existing prose/module budget warnings; no limits or baselines increased.

The original no-mode broad browser run **FAILED at line 159**, asserting no Token
Mix request after first navigation; later checks in that run were **NOT REACHED**.
Decision Delegate authorized a `--catalog-detail-only` entrypoint because this
prelude contradicts completed FR000609's automatic first acquisition. The scoped
run preserves the existing relevant fixtures/assertions and awaits automatic Token
Mix completion rather than clicking a hidden Refresh. This is a test-entrypoint
scope decision, not a product acceptance omission. The delegate also authorized
repairing the stale detail-warning expectation to observe the controller's actual
`source_unavailable` then `observed` replies while asserting quiet retained rows,
consistent with FR000634. A further instant-color assertion was corrected to wait
for actual uniform rendered colors across the existing CSS transition. Failed
test-repair attempts are not counted as passes; the subsequent scoped run passed.

Raw sanitized local evidence: `scratch:/sessions-before.log`,
`scratch:/sessions-after.log`, `scratch:/catalog-browser.json`,
`scratch:/catalog-detail-browser.json`, `scratch:/full-tests.log`,
`scratch:/full-tests-final.log`.

## Limits

The integrated browser was disconnected; hidden fresh-profile Chromium is the
available non-disruptive browser route. Synthetic browser fixtures seed scalar
keys independently of transcript hydration. No physical desktop, assistive-reader
audio or personal-browser-profile claim is made. No archive/release ZIP is built.
