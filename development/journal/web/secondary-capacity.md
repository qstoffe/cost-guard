# Secondary quota Capacity estimates

2026-11-11 · FR000677 · v81.27

## Causal evidence and boundaries

The baseline has two independent exclusions: `quota_ccost_values()` requires
`ComparisonCost.complete` before accepting a positive ratio numerator, and
`monthly_values()` rejects incomplete pricing again. The existing synthetic
partial-cost regression codified that behavior. Separately, `render.js` replaces
all unknown server Capacity explanations with its generic fallback. No primary vs
secondary eligibility distinction exists: each identity-bound period is evaluated
by the same server-owned estimator.

A deterministic secondary Weekly reproduction uses 1,020 raw Credits, three
observed requests/two priced, raw fraction used 0.07 and verified 604,800 seconds.
It now produces 14,571.42857142857142857142857 raw Credits Capacity and
62,448.97959183673469387755101 raw Credits for the theoretical 30-day equivalent
under the existing Decimal precision. The USD formula help retains approximately
$145.71/$624.49, while visible estimates retain the existing 5% display rounding.
Changing raw remaining fraction to 0.9301 still displays 7% used, but calculates
from 0.0699 instead. Complete-pricing upgrade removes the partial qualification
without changing an identical numerator's raw estimates.

Read-only baseline acquisition against registered real V2 found a current Claude
Pro secondary account-scoped seven-day window with raw 7% used, but **no bound
period cost**: its published reason was waiting for complete period history.
The same capture's primary five-hour cost was fully priced and uniquely compatible
estimated attribution. An independent model-specific weekly restriction had no
reliable normalized model ID and correctly had no numerator. Exact current native
start/reset/fraction, scoped cost counts, attribution note and basis were inspected
in owned scratch. After a bounded additional 90-second observation, Weekly history
was still unavailable. This does **not** reproduce the owner's earlier positive
$10.20 numerator or prove that partial pricing caused that historical card. Missing
history remains missing, not zero, a partial sample, or a passing full-history oracle.

## Change and ownership

The existing estimator accepts positive **priced** same-window subtotals, retaining
native freshness/coherence, active reset, scope/model and identity-bound history
checks. Capacity help adds “Estimate from priced requests; unpriced usage may make
this low.” Account attribution remains separately qualified. Monthly uses the
accepted raw period estimate × 2,592,000 / verified seconds, without another pricing
completeness veto. Verified native allowances retain their exact path.

Unknown help names the failed fact: stale/expired source, contradictory native
facts, inactive/resetting or unverified window, unsupported account/model scope,
missing history/ambiguous attribution, no priced/positive sample, or missing/zero
native fraction. The browser uses the server explanation rather than masking it.
Used/Remaining/native/reset help stays separate. No JavaScript estimator, provider
plan constant, extra source scan, history/attribution join, billing or native-bar
change was necessary. Existing upstream account/window/model joins remain guarded.

## Verification

- Local bounded Full: **183/184 groups passed; one failed**, 153.3 seconds.
  `test_cache_lifecycle.py::test_hourly_touch_coalescing_retains_full_rolling_window`
  expected the final prune count 1 but received 0. Immediate isolated unchanged
  file recheck: **9/9 passed** (1.6 seconds). The initial Full run is **not PASS**.
  `CacheLifecycle.prune()` legitimately returns zero on its opportunistic 20ms
  deadline or SQLite failure; exact original causality was not instrumented.
  Scheduling/deadline/SQLite explanations remain hypotheses, not proven flake
  causality. The test's private database means concurrent probes do not prove
  direct SQLite lock contention.
  **Decision Delegate** accepted this combined verification as a minor nonblocking
  caveat for this FR: every group ran, the unchanged failing file passed its bounded
  recheck, and repeating 183 passing groups would not establish the original cause.
  No test execution or quota functionality is waived/excluded; no unrelated cache
  edits, broad rerun, Suggestion or On Hold. This scoped decision does not generalize
  to future failing gates.
- Focused quota CCost, account-period, daily/DOM, pace and orientation regressions:
  **80 tests passed**. Includes independent three-window numerators, raw Decimal
  calculations, unpriced/no-history/ambiguous account/missing model controls,
  source freshness/reset, native verified allowances and Claude Agent subscription
  compatibility. Existing Today/source-native accounting remains unchanged.
- Hidden Edge 157, shipped HTTP/SSE/assets, `probe_accounts_live.cjs ...
  --secondary-capacity`: **PASS**. Actual Accounts/Full Watch share independent
  primary/secondary/later estimates, partial→complete/raw/history/reset transitions,
  Credits/USD × Used/Remaining, retained rows/bars/focus and trusted hidden hover/touch.
  This is synthetic browser evidence, not physical desktop, assistive-technology
  or macOS proof. Initial probe failures were fixture Decimal serialization,
  display-sync and input-modality assumptions; corrected without weakening product
  expectations.
- Existing complete `probe_accounts_live.cjs`: **PASS**, Edge 157, 415 layout cases
  over Classic/Web light/dark, narrow/wide and 100/125% CSS zoom; genuine hidden PiP,
  native allowances, estimate rounding, idle/reset, settings, links, membership,
  stable focus and one SSE/no route-report jobs remain covered.
- Final real-installation `probe_web_live.py --accounts --quota-capacity`: **PASS**
  for read-only V2 acquisition/export/owner and shutdown checks: three accounts,
  one Live/account-refresh owner, advancing publications, one verified native
  allowance/amount pair/pace, three estimate-token checks, no finite report/model
  calls. Final bounded trace retains missing period history as unknown and exposes
  that precise help; the unidentified model quota exposes its distinct model reason.
  This is not a passing weekly-history or original historical-card reproduction.
  Owned threads/processes closed; shared OpenCode was untouched.
- Working-tree validator: **11 passes, zero failures**, seven existing advisory
  size warnings; no budget increase or rebaseline. `git diff --check` passed.

Owned evidence: `scratch:/baseline-capacity-ready.txt`, `scratch:/secondary-browser.json`,
`scratch:/full-tests.txt`, `scratch:/cache-lifecycle-recheck.txt`, `scratch:/accounts-browser.json`, `scratch:/final-live.txt`,
`scratch:/validation.txt`. Raw live quantities remain local; no private account
identities or credentials are published. No paid model calls, new dependencies,
ZIP, GitHub Release, shared-service stop or Toolkit reload.
