# Quota help ownership and five-percent estimates

2026-11-10 · FR000663 · v81.13

## Implementation

- `application/quota_estimates.py` accepts the nearest half-up one-significant-digit
  candidate only within an inclusive **5%** in raw Credits, otherwise two digits
  or retained precision. Decimal safeguards, positive small amounts, known zero,
  conversion after Credit-space rounding and the explicit USD precision caveat remain.
- `quota_ccost.py` prepares period Capacity help from the accepted snapshot's raw
  observed cost, exact native-used fraction and raw Capacity. Native-compatible
  allowances instead show the full retained source-confirmed amount and provenance,
  never the observed-cost ratio. Monthly help uses the raw period Capacity, verified
  full duration in seconds and the existing raw standardized 30-day result.
- `render.js` has named usage/capacity help purposes, not positional topic flags.
  Usage retains oriented percentages, native balances, configured-local resets and
  real warnings without reference-Capacity prose or rolling/scope inventory.
  `account-cards.js` binds each topic to its existing intrinsic target. Stale or
  missing Capacity cannot display an old numeric calculation. No layout, canonical
  arithmetic, acquisition, cache, billing, CLI or Mini-layout changes.
- Current user guide and code map are updated. The old ten-percent journal is
  explicitly historical; FR000654's arithmetic prohibition is superseded by this FR.

## Verification

The real read-only installation probe (`probe_web_live.py --accounts`) passed:
V2, three accounts, one account-refresh/Live owner, advancing publication, one
verified native Capacity/amount-pair/pace, zero finite jobs or model calls. It
observed **zero eligible estimates**; synthetic tests, not live evidence, prove
the new estimate policy/formulas. Owned workers closed; shared OpenCode was untouched.

Integrated browser access returned `browser.disconnected`; the isolated repository
headless Chromium driver supplies actual browser evidence without a personal
browser or visible desktop interaction. This is not physical input, screen-reader
or macOS proof. No inference, dependency, ZIP, Release or runtime reload is involved.

- Actual hidden Edge **157.0.4341.42** shipped HTTP/assets/SSE/Document PiP driver:
  **PASS**, 59.032s, 415 layout records. Shared Accounts/Watch text, progress/divider
  coordinates and intrinsic help survive mixed/single/all-monthly, 0–4 secondary,
  unknown/recovered/reordered/missing/unlimited/stale transitions at
  **360/800/1280/1920 px**, 100/125% CSS zoom, Classic/Web light/dark. The representative
  full-ordinal case focuses every topic; other geometry cases focus first/last topics.
- Estimated primary/secondary help is compared directly with the matching server
  tokens across both routes, **Used/Remaining × Credits/USD × Classic/Web light/dark**.
  Usage rejects Capacity/math/metadata. Period/Monthly help rejects native inventories.
  Actual Tab, delayed hover, shared-target touch, Mini touch, Escape and same-mounted
  Capacity focus through unit/Live raw-input changes pass. Native allowance, unknown,
  disabled/failed source, retained card identity, fractions, source payload and fetch
  counts retain their independent controls.
- Initial runs exposed obsolete ten-percent/help assertions, a new full-precision
  expected value exceeding the existing canonical Decimal precision, and a browser
  sample-index error on the two-target monthly-only card. Expectations/index bounds
  were corrected. Partial/estimated observed-cost attribution moved to its own CCost
  parenthetical help instead of being lost or leaking into native usage help.
  Failed attempts are not counted as PASS.

- Final bounded local **Full: 181/181 files PASS**, zero failures, 141.6s.
  Decimal tests cover 550→550, 949→950, inclusive/just-under/just-over 5%, repeating
  nearest-candidate thresholds, huge/tiny values with low ambient precision, full
  retained raw input/output, unknown/native controls and independent pace rounding.
- Working-tree validator: **11 passes, zero failures**, seven advisory size warnings;
  no cap or baseline was raised. `git diff --check` passed.

Owned evidence: `scratch:/full-tests-final.txt`, `scratch:/accounts-browser-final.json`,
`scratch:/real-accounts.txt`, `scratch:/validation-final.txt`.
No acceptance exception, deferred work or hold was needed.
