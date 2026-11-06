# FR000611 completion — 2026-11-06

## Outcome

Fixed shared AI Stats Overview/Fun Facts text clipping in v80.191. The detail
track is content-sized, and long card text can wrap without overflow clipping.
Responsive sibling cards retain equal height within each grid row. No metric,
copy, URL, period, formatting, acquisition, keyed-DOM or unrelated layout changes.
The optional eleventh card uses the same corrected layout.

## Verification

- Pre-fix rendered reproduction: 22.5px detail track minus 7.5px margins left a
  15px clipping box for 23.25px line-height and 20px text ranges. Both session
  links and Busiest Day date failed the new geometry assertions, even though
  outer cards fit. Evidence: `scratch:/ai-stats-before.json`.
- Final hidden Chromium probe: **PASS**, 10 checks, 9 normal layouts and 80 text
  layouts. Actual ranges, clipping rectangles, separate rows, focus outlines,
  hit/hover/click and Tab/Enter navigation; short/long/unbroken names, dates,
  N/A/partial/unknown/empty, large values, long traits, both optional fact labels,
  five periods, Credits/USD, Arial/Georgia, Classic/Web light/dark at
  360/1366/1920px and 100/125/150/200% root text sizing. Existing accessible,
  safe-link, retained DOM/focus, touch/help and refresh tests remain.
  Evidence: `scratch:/ai-stats-final.json`.
- Full registered local suite: **153 files, zero failures, 105.5s**;
  `scratch:/full-tests.json`.
- Working-tree validator: **11 passes, zero failures, six existing advisory
  warnings**. No budgets or structure baselines changed. `git diff --check` passed.
- Real V2 read-only `probe_ai_stats.py --cold-and-warm`: cold 30-day acquisition
  **FAILED** with `report_timeout` at **120.029s**, zero periods, progress
  **2688/2725**. Warm 30-day completed **9.003s** (four periods), All-time
  extension **10.212s** and warm All time **5.165s** (five periods each).
  No inference, account refresh, service stop or new deadline was involved.

## Scoped decisions and remaining uncertainty

**Decision Delegate authorized an FR000611-only exception to successful cold live
acquisition.** The failing probe does not exercise the changed CSS; directly
verified rendering can ship without an unrelated backend performance repair.
Further cold retries were not required. Cold-acquisition reliability and the
cause of timing variance remain unresolved; concurrent tests are only a possible
influence. Warm success and exit zero do not convert the cold failure to PASS.
Full tests, validator and protected Git delivery were not waived.

**Decision Delegate authorized an FR000611-only documentation exception:** the
knowledge helper read the existing leaf but rejected apply before writes with
`INDEX_LIMIT`. Existing ancestor indexes exceed eight routes and the Web index's
leaf route uses backticks. A context-checked ordinary leaf patch was allowed;
indexes, helper code, limits and unrelated documents remain unchanged. No helper
PASS or complete ancestor validation is claimed; the leaf remains below 12 KiB.

The integrated browser was disconnected, so shipped HTTP/assets were tested in
hidden Chromium with a disposable synthetic-data profile. This does not claim
physical desktop/font, screen-reader speech, non-Chromium or real-source browser
paint verification. The separate read-only source probe establishes only its
reported acquisition outcomes.

## Documentation and accounting

Updated Web guide, current README, version history and the existing AI Stats
journal with reusable geometry findings, failed hypotheses and exact limits.
Architecture **no-update**: a shared CSS sizing fix changes no module boundary.
The task body/attachments were moved intact to completion ordinal 000122.
The selected ordinary progress advances 60→61 only when this PR merges.
Current main remains the distribution; no product ZIP/tag/Release was created.
