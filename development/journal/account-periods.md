# Native quota-period CCost

## FR 000552 — 2026-11-03

Watch opts into the existing native UTC-month resolver and extends its revision-reused
background history scope before admission. Unsupported billing anchors remain unknown;
neither a local month nor trailing 30 days substitutes for native evidence. The immutable
history index rebinds current quotas at publication. Coverage is now per scope, so an
unacquired longer period cannot erase an acquired Today or independent secondary window.
Two older tests were updated to assert acquired empty Today/sole-provider estimates
without claiming verified account attribution. Direct projection fixtures preserve
their existing known-request behavior; only acquired-history publication requires coverage.

`QuotaPeriodProjection` associates exact quota objects with cost and canonical pace,
including equal-label model quotas. Watch consumes this association, not a label join.
Monthly/weekly-only cards have no secondary section; genuine warnings do not create one.
The authenticated status exports the process-loaded product version, never a source reread.

### Verification and scoped decision

- Deterministic tests cover pre-Watch monthly acquisition/reuse, month/reset/empty/stale
  boundaries, overlapping/model quotas, per-scope coverage, canonical pace, units, and
  real HTTP/DOM version display (including an alternate running-version fixture).
- Headless Edge checks the real assets in Classic/Web light/Web dark at wide and narrow
  widths, with screenshots and geometry assertions for centered title bands, left body,
  aligned common tracks, unclipped long account names and secondary-only dividers.
  Integrated browser DOM/CSS checks also worked; its screenshot API refused because the
  tab was not visible despite focus. No external desktop was opened to work around it.
- The first real V2 `probe_web_live.py --watch-cards --daily` observed 870 requests,
  44 initiating prompts (attribution incomplete), complete cost/category reconciliation,
  three accounts and two active/two history cards, but **failed** owned shutdown with
  `web_shutdown_timeout`. Those observations are not an overall probe PASS.
- Decision Delegate authorized a narrower real-installation check, not a shutdown waiver:
  full real-month completeness may remain unverified if deterministic monthly tests and
  a truthful bounded provider/source sample are accompanied by shutdown investigation.
  No production deadline or shared OpenCode lifecycle was changed.
- The diagnostic owned-host run then **passed**: 920 requests/44 prompts, one V2 owner,
  two streams and preserved run origin. HTTP/Live/coordinator/card cleanup all returned;
  total close took 3.728s (card lane 3.260s), within the unchanged ten-second budget.
  No timeout stack was triggered and no post-stop history batch was observed. This does
  not explain or erase the earlier intermittent failure; its cause remains uncertain.
- A separate service sampled one real root (30 requests), normalized three available
  accounts and exported exact quota/pace DTOs. Copilot had a valid native UTC Monthly
  interval and canonical pace; Claude five-hour/weekly and OpenAI weekly retained their
  actual scopes. Because this was only a sample, all active-period costs stayed unknown:
  no fake full-month zero or cost was published. Complete real-month valuation remains
  unperformed under the Delegate's scoped decision. No inference, credential change or
  shared OpenCode stop occurred. Final suite/validator outcomes are in `COMPLETION.md`.

## FR 000549 — 2026-11-02

The reported declining CCost beside a not-started five-hour quota was explained by `quota_window` selecting a trailing duration instead of the native period. That historical fallback is removed, superseding FR 000140's earlier allowance without rewriting its archived specification.

- Provider-confirmed inactive, reset-free, non-conflicting native components resolve to an empty half-open range. Their zero is an empty-period fact, independent of pricing, attribution and history loading, not a conversion of native utilization.
- Active components retain reset-minus-duration through the observation clock, including usage before Watch opened. Missing/expired/unsupported or contradictory boundaries have no interval; stale account observations cannot publish current native-period costs.
- `AccountPeriodHistory` captures the prefix index, catalog and acquired start, not old quota values. Delayed Web history is rebound to the current account, model scope and native interval. Watch's existing history-loading gate remains for scopes not provider-confirmed empty. No polling, full-history redraw scan or durable ledger is added.
- Native account responses older than the published observation cannot restore an older window or regress its successful-observation epoch. Partial lifecycle transitions cannot inherit a previous active reset into a confirmed inactive component.
- Five-hour/weekly/model scopes remain independent. Full Web Watch's `CCost Today`, CLI durationless monthly `Today`, configured-local month and supported native UTC calendar months used by Copilot residuals remain distinct. Unsupported billing anchors stay unavailable; no monthly-provider defect was inferred from the five-hour symptom.

## Evidence and limits

Deterministic owners are `test_account_period_ccost.py`, `test_quota_period_lifecycle.py`, `test_accounts_ccost.py`, `test_web_accounts.py`, `test_watch_daily.py` and `test_copilot_unaccounted_usage.py`. The new lifecycle suite is registered in Quick/Full and uses responsibility-owned `fixtures/account_periods.py`; real Accounts JavaScript checks the 0-period/604-Today distinction. Completion records the final suite/validation results.

A read-only task-focused real-installation probe retrieved three accounts and analyzed one bounded source root (20 requests). Claude Code returned an available five-hour component with `window_active=false`: the resolved empty period exported CCost `0`. Claude Code and OpenAI weekly intervals were valid native windows but had unavailable sums in this intentionally incomplete history sample; that is not a weekly-cost PASS or fabricated zero. No inference, provider credential change or shared OpenCode stop occurred.

The broader existing `probe_web_live.py --watch-cards --daily --reports` did **not** pass: `/api/live` exceeded its three-second HTTP timeout during the daily wait, followed by `live_shutdown_timeout` during owned-host cleanup. Its full-day live history/report behavior remains unverified by that probe; no root cause is claimed. This does not replace the narrower real provider/source observation or the deterministic lifecycle/DOM assertions with a broad live PASS. No requirement/test exception was requested or granted.
