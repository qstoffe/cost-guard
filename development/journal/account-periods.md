# Native quota-period CCost

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
