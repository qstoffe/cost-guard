# FR 000549 — Keep quota-period CCost aligned with the actual native window in CLI and Web

## Owner report and intended outcome

The owner requested this bug-fix FR on **2026-11-02** after seeing a CLI Watch subscription row with **0% used**, **604 CCost in parentheses**, and reset **not started**. The CCost continued falling minute by minute despite the five-hour quota showing no active period. The owner estimates that 604 would represent substantial usage for this subscription; that observation is not a conversion rule between CCost and native quota utilization.

The five-hour CLI symptom is directly reported. Inspect and fix the shared cause and affected Web account/cost cards, and check weekly and monthly variants rather than assuming every surface or plan is broken in the same way.

**Outcome:** a CCost amount presented as belonging to a quota period must cover that account's actual corresponding period. A reset or not-started window must not inherit historical cost from a trailing lookback, an earlier period, the Watch run, Today or another quota window.

Permanent identity: **000549**. Ready priority: **000100**, before the queued Watch presentation work (FR000545 at 000110 and FR000547 at 000115) and Mini Watch (FR000544 at 000120). This is a focused accounting/presentation correctness fix. The owner has requested its creation in Ready; no further product-design decision is needed to begin implementation.

## Source findings and existing requirement being corrected

Inspected main: **`f5c969cf27012aee7f7af0c2be3d53ea57da5f3f`**. These findings come from source review, not a reproduction against the owner's private runtime or provider payload.

- `src/analysis/period_ccost.py::quota_window` uses a valid native reset minus duration for an active interval. However, for `window_active=False` with no reset, it returns `now - duration` through now with the basis **observed trailing lookback; not a certified quota interval**. Thus a not-started five-hour quota can receive the cost of the last five hours. As older requests leave that moving interval, its cost falls. This directly explains the reported pattern without requiring a Watch-run-total mix-up.
- `src/reports/accounts.py::_period_scopes` assigns that fallback to the quota's normal label, such as `5-hour` or `weekly`. `src/presentation/accounts.py::_quota_ccost` and `quota_parts` then place it next to the native used percentage, while independently rendering `not started`.
- `src/application/projection.py::account` exports these same scopes. `src/web/assets/render.js::overviewAccounts` renders all of them as **CCost <scope>** on Web Accounts cards. The same misleading current-period value is therefore possible there.
- Current full Web Watch uses `src/web/assets/watch.js::accounts`, explicitly selecting the `today` scope and labeling it **CCost Today**. A nonzero Today amount beside a newly reset five-hour quota can be correct. Preserve that daily value and meaning.
- The inactive fallback is duration-generic, so a weekly or other duration-bearing component in the same state is affected conditionally. No claim is made that the owner's weekly/monthly provider currently returns that state.
- The active reset branch already rejects expired or out-of-range anchors. The defect is not proof that every active window is wrong. Still test state transitions and contradictory inactive/reset metadata, because the reset branch currently precedes the inactive check.

**This FR supersedes FR000140's allowance to use an uncertified trailing lookback as the parenthesized quota-period CCost for a not-started window.** Keeping an explanatory note in a report does not make that amount suitable for the current quota metric. Update affected documentation and regression expectations; do not preserve the old fallback merely because it was previously specified and tested. Archived FRs remain historical records.

Existing `development/tests/test_account_period_ccost.py` explicitly expects a trailing start for an inactive quota and renders **0% used (100)** together with **not started**. Replace those semantic expectations while preserving their useful formatting, pricing and attribution coverage with appropriate active-window fixtures.

## Required behavior

### 1. Represent the actual period and its state

Resolve the period from trustworthy native window identity/boundaries, duration and lifecycle evidence in shared analysis/projection. Render the native percentage, reset state and period CCost from the same coherent account/window observation.

| State | Required period-CCost behavior |
| --- | --- |
| Fresh, provider-confirmed not-started/empty window | Show zero for this explicitly empty current-period scope, e.g. `0% used (0) · not started`. Historical requests from the previous period must not enter this value or make it decay over time. This is an empty-period fact, not a percentage-to-cost conversion. |
| Active window with valid native boundaries | Sum the existing canonical attributable request costs within that actual interval, including relevant usage before Watch opened. |
| Window just reset or expired, new boundaries not yet known | Invalidate the old period value as current; use the existing unavailable/loading treatment until a current interval or confirmed empty state is established. Do not invent a replacement trailing interval. |
| Missing, stale, conflicting or unsupported period evidence | Keep truthful unavailable/stale semantics. Do not silently treat uncertainty as a fresh zero or display an old amount as current. |
| Active small usage rounded to 0% | Retain legitimate current-period CCost. The formatted percentage alone must never trigger zeroing or an inactive state. |

Do not derive CCost by multiplying a native percentage by an assumed budget. Provider-native utilization and reference-valued observed requests need not match numerically; provider lag, rounding, attribution and pricing can differ. Correct the period association, not the native percentage to make the display look consistent.

Do not retain the trailing fallback under a renamed or weakly qualified parenthesis beside the quota percentage. This fix does not require a new historical-lookback feature.

### 2. Handle reset transitions without stale-period mixing

When a native period ends, a new one starts, or the provider returns a confirmed not-started state, replace/invalidate only that period's CCost consistently with the corresponding quota state. Delayed account/history work or a cached projection from the previous account/window must not restore an old value beside the new percentage or reset timer.

A five-hour reset must not zero an ongoing weekly quota. Correctly overlapping five-hour and weekly scopes may contain the same requests; do not add them together as though disjoint. Preserve relevant history for Today, monthly comparison and other scopes. Starting or restarting Watch must not change the meaning of a native-period sum.

### 3. Cover CLI, Web and queued Mini Watch

Apply the shared correction to CLI Watch, the normal account report, Web Accounts and any other renderer that labels the affected scope as quota-period CCost. Preserve compact CLI placement, numeric formatting and CCost-unit selection.

Audit full Web Watch and its shared projection, but retain its explicitly labeled **CCost Today**. Daily cost can remain 604 while a five-hour window is zero/not started. Do not replace Today with quota-period cost or zero the daily summary to hide the discrepancy.

FR000544 already requires same-primary-period CCost for Mini Watch, rejects uncertified trailing intervals, and prohibits old-period cost beside a new-period percentage. Have it consume the corrected shared semantics when implemented. FR000547 separately fixes selection of the real native primary, including weekly-only accounts; respect that requirement without inventing a five-hour quota or duplicating its work.

### 4. Verify weekly and monthly meanings explicitly

Apply the same lifecycle rules to every supported duration-bearing native period, including weekly windows. Verify model-specific quotas without combining their scope with an account-wide quota.

Distinguish a **native monthly/billing interval**, an explicitly labeled **Today** amount beside a monthly quota, and **CCost this month** for the configured local calendar month. These can legitimately differ.

Use existing supported native-month resolution where applicable. `monthly_quota_window` currently supports provider-native fixed UTC calendar months with a day-one midnight reset; it is also used for Copilot residual accounting. Do not substitute an arbitrary trailing 30 days, a guessed billing date or the local calendar month for a different native interval. Unsupported boundaries remain unavailable.

The current CLI `Today` field on monthly components without a duration is intentionally daily; preserve it. Check affected monthly paths for stale-period leakage and record which are corrected or already valid. Do not claim a monthly defect was reproduced solely from the five-hour report.

## Focused acceptance and verification

1. **Reported five-hour case:** with expensive prior-period history totaling 604 in the last five hours and a fresh confirmed not-started quota, CLI Watch and Web Accounts show the empty current-period cost, zero used and not-started state. Advancing time by successive minutes with no new usage never makes a historical 604 decay inside the current-period field. Today/history retain their legitimate totals.
2. **Active interval:** requests before the native start are excluded; requests at/after the start through the observation time are included once, including pre-Watch history. An active fraction rounded to 0% may still show nonzero cost.
3. **Lifecycle:** cover active → expired/reset → not-started → newly active, repeated refreshes, a delayed old-period response, and account changes. Percentage, reset and period CCost cannot mix periods; stale/unknown/conflicting states do not become fabricated zeros or new trailing windows.
4. **Weekly independence:** reproduce the inactive fallback case with a weekly duration, verify a real active weekly sum, and show that a five-hour reset preserves valid weekly usage/cost. Cover weekly-only and account/model-scoped fixtures without fabricating unsupported windows.
5. **Monthly boundaries:** verify supported native month/reset transitions, month/year rollover and an unsupported billing anchor. Preserve the separate daily and configured-local-calendar-month values, including when their boundaries differ from native UTC boundaries. Do not regress Copilot residual accounting.
6. **Surface agreement:** equivalent account/window inputs give the same period meaning in CLI Watch/report and Web Accounts. Full Web Watch keeps correct `CCost Today`; Mini Watch's future same-period contract remains compatible. Include compact/plain/ANSI output and the existing credits/USD formatting where affected.
7. **Accounting and efficiency:** retain unknown/partial pricing and account-attribution distinctions, request deduplication, provider-only ambiguity and existing bounded indexed history reuse. Do not implement the fix by deleting old history, increasing provider polling or rescanning full history on every redraw.

Use focused existing period/account projection and CLI/Web rendering tests. Inspect `test_account_period_ccost.py`, `test_accounts_ccost.py`, `test_web_accounts.py`, `test_watch_daily.py` and the applicable integration fixtures. Update only assertions invalidated by the corrected semantics. Record actual checks and any unverified live-provider behavior honestly.

## Delivery scope

This FR changes shared period semantics and affected presentation, with corresponding tests/documentation. It does not request a new billing ledger, new authentication/provider access, quota-budget estimation, a Watch redesign or a new permanent release gate.

Creating this FR is a backlog-only change. Publish the FR and permanent-identity counter without changing product code, product version, release date or release history. The subsequent implementation follows the repository's normal delivery process.
