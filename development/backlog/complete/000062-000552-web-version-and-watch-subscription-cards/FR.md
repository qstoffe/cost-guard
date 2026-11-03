# FR 000552 — Show the server version and refine Web Watch subscription cards

## Owner request, priority and related work

The owner requested this combined Web improvement on **2026-11-02**:

- Display the running server's product version immediately after **Web Beta** in the application header.
- Give Watch subscription cards a clearer, centered title in a colored header band while keeping all values left aligned.
- Keep CCost Today, remove its **(estimated)** suffix, and add each quota's own period CCost after its Used percentage.
- Show the full primary quota, including reset and applicable Remaining/day and Remaining/workday rows, above a divider; put only secondary quotas below it.
- Remove verbose rolling/fixed-window descriptions from Watch.

Permanent identity: **000552**. Ready priority: **000118**, after **FR000547** (000115) and before **FR000544 Mini Watch** (000120); the low-priority Models progress FR000550 remains later at 000900.

Preserve FR000547's correct native primary selection, including weekly-only accounts, and delivered FR000549's corrected period/reset accounting. This request **supersedes FR000543/FR000547's older layout rule that primary reset/window details belong below the common-metrics divider**, and the earlier visible Today estimate qualifier. Do not rewrite those historical/queued FRs to carry this amendment.

## 1. Running server version after Web Beta

The persistent Web header should read, for example, **Cost Guard · Web Beta v80.127**, with the version immediately after Web Beta. The example is illustrative; the displayed version must always come from the **running server's canonical product version**, using the same number/convention as CLI.

Use the existing lightweight server metadata path or an equivalent server-rendered value from the same runtime constant. Do not hardcode a version in HTML/JavaScript, query GitHub for the newest release, or substitute an API/schema/runtime version. A source checkout updated on disk must not make an old running host claim it has already upgraded.

Keep the version visible across Web routes, including Models loading and Watch, with compact styling matching the existing branding. Populate it once the server value is known; do not invent a value beforehand. Preserve existing connection and host-identity handling. A fresh authorized page for a new server gets that server's version; a retained offline view must not claim a different or newly running host.

The inspected implementation already has a suitable source: `src/version.py` defines `VERSION`/`DISPLAY_VERSION`; `WebHost` imports VERSION and exposes it in its existing process identity, while the authenticated `/api/status` response consumed by `app.js::connect` currently omits it. Prefer exposing the needed product version there without a new polling loop or privileged browser API.

## 2. Card title and complete primary section

Use a distinct, theme-aware **header band integrated with the card's top border and rounded corners**. Center the subscription/account name in that band and give it stronger visual emphasis through its fill and font weight. Preserve the full identifying account/plan label, including distinctions between accounts with the same plan.

Only the title is centered. CCost Today, quota summaries, resets, Remaining values and other body text stay **left aligned**. Do not add a duplicate provider/plan subtitle. Keep long titles readable and preserve alignment of the shared Today/primary label/bar tracks across adjacent cards. Adapt the current subgrid/body geometry rather than clipping titles or forcing small text.

Use this content order:

| Area | Content |
| --- | --- |
| Header band | Centered subscription/account name. |
| Primary body, first row | **CCost Today: <daily CCost>**, left aligned. |
| Primary quota summary | **<period> · <N>% used (<that period's CCost>)**. |
| Next row | Primary Used progress bar. |
| Directly below the bar | Primary reset, e.g. **Resets at <time>** or **Reset: not started**. |
| Primary-specific rows, when supported | **Remaining: <amount>/day** and **Remaining: <amount>/workday**, on two separate rows. |
| Divider, only when secondary quotas follow | One restrained horizontal separator. |
| Secondary body | Each real secondary quota's summary, own bar, own reset, and applicable quota-specific pace. |

The primary quota remains the account's actual native primary. Monthly-only Copilot has its complete monthly information in the primary body and **no trailing divider or empty lower section**. A weekly-only subscription likewise stays entirely in the primary section. A five-hour primary with a weekly secondary has the complete five-hour block above the separator and the weekly block below.

Keep concise genuine unavailable/stale/error or restriction information in the appropriate account/quota area. Such an exceptional status must not create a fake secondary-quota section or restore routine window-description clutter.

## 3. Today and each quota's own CCost

### Keep Today; remove the visible estimate suffix

**CCost Today** retains its current-local-day scope and position near the top of every card. Remove **(estimated)** from this displayed line. Do not replace it with another adjacent estimate badge or qualifier.

This is a presentation change: preserve canonical attribution/completeness metadata and the actual known value. Do not mark estimates as verified, fabricate a known amount for an ambiguous account, or change Today to the primary quota's period. Existing internal provenance and information on the separate Accounts page can remain.

### Parentheses after Used, for primary and secondary quotas

For every supported quota, append its own **period CCost** directly after the Used percentage. Illustrative summary forms are:

- **Monthly · 22% used (5608)**
- **5-hour · 0% used (0)**
- **Weekly · 6% used (420)**

These numbers are examples, not a formula relating native utilization to CCost. The parentheses contain canonical observed **CCost for that exact account/window/scope**, valued in the effective CCost Credits/USD display unit. They are not native used credits, a percentage-derived estimate, Today, or a Watch-run total.

For Monthly, use the actual current native month/billing interval from its start through now. For five-hour and weekly quotas, use their actual current native windows. Apply the same rule to primary and secondary quotas, preserving model-specific scope where applicable. A request can legitimately belong to overlapping windows; do not sum those window costs as separate consumption.

**Native monthly support is part of this FR.** Current Watch scopes only cover duration-bearing quota components, while Copilot's monthly component has no duration. Acquire/reuse sufficient history and project a genuine native monthly scope; adding parentheses around Today does not satisfy the requirement. Reuse the existing native-month resolver where supported. Do not substitute an arbitrary last 30 days or the configured local calendar month for a different native billing interval. Unsupported/unestablished boundaries remain unavailable.

Share this period resolution/acquisition with FR000544's same-period Mini Watch requirement, whichever implementation supplies it first. This FR's monthly Watch card must be complete without waiting for the Mini UI.

Preserve delivered FR000549 semantics: a fresh provider-confirmed empty/not-started period has zero CCost; stale, expired, conflicting or unknown period evidence stays unavailable; old-period results must not reappear beside a new-period percentage. An active fraction rounded to 0% may still have real CCost. A known percentage with unavailable CCost retains the percentage and uses **(—)**, with existing truthful state handling. Keep Unlimited distinct from unknown or zero; do not fabricate a finite percentage/bar.

Continue using canonical indexed valuation, account attribution, deduplication and bounded history reuse. Include relevant pre-Watch usage. A longer required monthly history scope must not cause a full-month rescan on every redraw or block live prompt updates. Preserve Today and independent secondary scopes when another window resets.

## 4. Restore Remaining/day and Remaining/workday

Where CLI Watch already computes a remaining allowance for a supported fixed/monthly quota, display the same canonical information in Web Watch on **two separate left-aligned rows**, associated with that quota.

For a monthly primary, place both rows after its reset and **above any secondary divider**. These rows are subscription-specific information within the complete primary block; they are not grounds for moving primary data into a secondary area.

Reuse `QuotaPace.per_day` and `per_workday`, including the configured timezone, workday calendar, native reset, native remaining quota and established numeric formatting. Do not recalculate them from CCost or from the visible Used percentage in the browser. CCost's Credits/USD toggle must not convert native Remaining amounts into another unit.

Show a truthful no-workdays-left value when no configured workday remains. Missing balance/reset data or unsupported/unlimited quota types must not produce fabricated allowances. If pace applies to a genuine secondary quota, attach its rows to that secondary block.

## 5. Compact quota and reset wording

Each quota's ordinary display is its **period label + percentage Used + parenthesized period CCost**, its own bar, and its reset directly underneath. Keep meaningful reset dates/times and inactive/reset state.

Remove separate routine descriptions such as **Rolling 5-hour window**, **Rolling 7-day window**, **Fixed window**, and verbose **5-hour window not started** wording from Watch subscription cards. Represent the last case once as the concise reset state beneath the matching bar. Do not remove the actual Monthly/5-hour/Weekly label or hide the reset altogether.

Scope this cleanup and card styling to Watch. The separate Accounts page may retain detailed period semantics; its redesign is not requested here. Preserve current primary/secondary exhaustion, near-100% precision, native unknown/unlimited distinctions and genuine provider warnings.

## Source findings and affected areas

Inspected main: **`44f4c9e8bdf619bb0d03ef13b4303325ec641662`**, product **v80.127**. Source review only; no private live-account payload was inspected for this FR.

- `src/web/assets/index.html`, `app.js`, `src/web/host.py`, `http.py`, `src/version.py`: header and running-version metadata.
- `src/web/assets/watch.js::quotaTrack/quotaDetails/accounts`: missing period parentheses, Today estimate suffix, primary reset currently placed below the divider, and rolling/fixed description rows.
- `src/application/watch_accounts.py`: Watch-specific projection currently drops the ordinary account's `pace`; primary/secondary quota records lack directly associated CCost/pace. Extend the shared projection rather than joining unrelated values by browser guesses.
- `src/reports/accounts.py`, `src/analysis/period_ccost.py`, `src/watch/web_coordinator.py` and the existing history owners: native monthly scope/history and coherent period publication. Retain FR000549's immutable history evidence and current-window reprojection.
- `src/analysis/quota_pace.py` and `src/application/projection.py`: existing canonical pace calculation/export.
- `src/web/assets/app.css`: current five-row subscription subgrid and always-bordered details section need the new title band/complete primary/conditional secondary layout. Keep styling scoped, with appropriate Classic, Web light and Web dark colors.

## Acceptance criteria

1. **Server version:** the persistent header shows Web Beta followed by the running host's canonical CLI version. A different server-version fixture updates the display without editing static assets. Loading, routing and existing connection/identity handling remain correct.
2. **Monthly-only Copilot:** the card has a centered colored title, separate Today, Monthly percentage with true native-month CCost, bar, monthly reset and two Remaining rows, all body text left aligned. There is no secondary divider/panel.
3. **Five-hour plus weekly:** both quotas have their own percentage, correct period CCost, bar and reset. The primary reset is above the divider, the secondary below; no rolling/fixed-window boilerplate appears.
4. **Weekly-only and multiple quotas:** FR000547's native primary is respected. Weekly is not duplicated, no five-hour placeholder is invented, and all real secondary/model quotas retain their correct scopes and states.
5. **Accounting and transitions:** verify pre-Watch month history, native month/reset boundaries, not-started zero, unknown/stale cost, active rounded-zero percentages, delayed period results and independent overlapping quotas. Today remains a daily value and the visible estimate suffix is absent without changing attribution metadata.
6. **Pace and units:** Web matches canonical CLI Remaining/day and Remaining/workday values, including no-workday handling. CCost Credits/USD changes Today and period amounts only; native Remaining retains its unit.
7. **Visual result:** in a browser, check all three themes, side-by-side monthly/five-hour/weekly-only cards, long distinct account names and a narrow viewport. Titles are centered in integrated header bands; metrics stay left aligned, common tracks remain readable/aligned, resets remain attached to their bars, and no empty secondary divider is left behind.

Use focused existing status/lifecycle/Web-view tests for version display and account-period/pace/Watch-summary fixtures for card behavior, including `test_watch_daily.py` and `development/tests/integration/web_watch_summary.cjs`. Record actual verification and any live-provider limitations honestly. This defines acceptance for the requested feature, not a new permanent release gate or broad live-testing project.

Creating this FR is backlog-only: publish this document and update the permanent-identity counter without changing product code, version, release date or release history. The subsequent implementation follows normal repository delivery.
