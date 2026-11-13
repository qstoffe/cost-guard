# Quota help ownership and five-percent estimates

## FR000699 — concise numbers and local reset days

2026-11-13 · v81.43

This supersedes the verbose raw-precision/formula/provenance help below, **not**
FR000663's visible five-percent estimate policy. `reference_help_amount()` formats
the corresponding canonical raw Decimal using ordinary reference units, not
`rounded_estimate()` or browser arithmetic. Synthetic 3065.617… Credits therefore
has help `Capacity: ~3066 Credits` / `Capacity: ~$30.66`, while the card remains
`~3000` / `~$30.00`. Monthly help uses its independently calculated raw equivalent.
Source-confirmed allowances have no `~`; derived monthly values always do.

`quota_ccost.py` exports compact numeric help plus source-prepared raw amount/status
tokens. Mini orders Capacity, Next reset, useful numeric Remaining and exceptional
status once, without an extra Capacity paragraph. Usage help keeps native amounts,
reset and real restrictions; partial pricing and uncertain attribution retain short
warnings. Unknown history/stale/invalid/unlimited do not manufacture zero or numbers.
No accounting, native fraction, canonical value, source access, billing, visible
estimate rounding or provider allowance arithmetic changes.

`display.py::web_quota_reset()` shares the server observation and configured zone
across Web quota and slot tokens. It renders duration, local HH:mm, then `today`
only for the same local date, otherwise an English weekday through exactly seven
elapsed days; beyond seven days it renders HH:mm then YYYY-MM-DD. Invalid, expired
and not-started states remain explicit. Absolute-date clock help still agrees;
CLI `format_reset()` is unchanged.

### Scoped formatting decision

The **Decision Delegate** approved one tooltip-only interpretation/exception:
ordinary Credits formatting uses decimals below 1, conflicting with the FR's
explicit whole-Credits requirement. Positive raw values below 1 instead show
`<1 Credits`; ordinary zero/upward whole-number rounding is retained otherwise.
USD uses its ordinary two decimals, with `<$0.01` **only** if a positive amount
would otherwise display `$0.00`. An inferred bound retains `~`; a verified bound
does not. No global formatter, visible card, test or other acceptance is waived.
Fractional detail is deliberately omitted from help, not lost from canonical data.

### Verification

- Local bounded **Full: 192/192 groups PASS**, zero failures, 164.8s.
  The initial Full run failed four groups on deliberately superseded tooltip/reset
  wording. Updated assertions retain raw-value/native/identity controls; the final
  complete run passes. Formatting tests cover repeating raw amounts, independently
  derived monthly values, verified amounts, both units, zero/tiny/huge/invalid inputs.
  Reset tests cover today, 23h crossing midnight, exactly/over seven days,
  Stockholm spring/fall DST, month/year boundaries and unavailable states. CLI
  token assertions remain unchanged.
- Hidden **Chrome 157.0.8103.51**, shipped HTTP/assets/CSP/SSE and real Document PiP:
  `probe_accounts_live.cjs ... --quota-only` **PASS**, 12 check groups/63 layout
  records. Accounts/Watch/open Mini cover native/inferred, primary/secondary,
  monthly/pace, Used/Remaining, Credits/USD, Classic/Web light/dark, narrow/DPR/zoom,
  unavailable/idle/stale/retained transitions. Actual hidden Tab/hover/touch,
  Escape/leave and same-target Full/Mini help through unit/observation changes pass;
  no duplicate tooltip, source mutation or extra display-triggered fetch.
  The first browser attempt failed an obsolete Mini Credits-units assertion;
  updated expected ordinary units and the final expanded run passed.
- Final read-only real-installation `probe_web_live.py --accounts --quota-capacity`:
  **PASS**, registered V2, three accounts, one Live/account-refresh owner,
  advancing publications, one native Capacity/amount pair/pace, no finite jobs
  or model calls, zero owned threads/processes and zero cleanup failures.
  Five inspected quota records have no legacy verbose help. **Zero eligible
  inferred capacities were observed**: missing history/sample/model evidence
  remains unknown, not a live inferred-value PASS. The first attempt stopped on
  actual `source_changed` and then connection refusal; that attempt is not PASS.
  A fresh current-source probe completed; shared OpenCode was never stopped.
- Working-tree validator: **11 passes, zero failures**, seven existing advisory
  size warnings; no cap/baseline increase. `git diff --check` passes.

Owned evidence: `scratch:/full-tests-final.txt`, `scratch:/quota-browser-open-help.json`,
`scratch:/live-quota-final.txt`, `scratch:/validation-final.txt`. Private live
quantities remain local. No inference, dependencies, visible-desktop interaction,
ZIP, GitHub Release, installation or Toolkit reload. Headless DOM/input/PiP is not
physical desktop, assistive-technology or macOS proof. The tiny-value interpretation
above is the only approved exception; no functionality or verification is deferred.

## Historical FR000663 implementation and evidence

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
