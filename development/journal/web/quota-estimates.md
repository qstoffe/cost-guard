# Quota guesstimate display precision

2026-11-09 · FR000641 · v80.221

## Ownership and behavior

`application/quota_estimates.py` is a pure Decimal presentation policy, not a
change to source evidence or global numeric formatting. Try nearest one significant
digit with decimal half up; accept only within an inclusive 10% of raw Credits,
otherwise try two and retain raw precision if necessary. Compare by exact decimal
multiplication rather than dividing into a rounded repeating fraction.

`quota_ccost.py` keeps raw Used/Remaining/Capacity and the independently calculated
30-day equivalent in `ccost_reference`. Ratio Capacity/Remaining are estimates;
observed Used is not. Theoretical monthly extrapolation is an estimate even when
its original period Capacity is verified. Pace carries its own basis and divides
unrounded Remaining by the actual existing day/workday counts before presentation.
`display.py` prepares both units and help on the server. No browser parsing,
pricing, quota calculation, extra fetch, source scan or CLI formatter changes.

Credits retain necessary fractional precision. USD converts the rounded Credits
then keeps two decimals; a positive amount below currency precision is `<$0.01`,
not zero. Raw full-retained-Decimal Credits remain in help/canonical payload;
help explicitly discloses when two-decimal USD cannot meet Credit-space tolerance.
Known zero, missing/unlimited/unavailable, native percentages/bars/reset and
provider-authoritative figures retain their independent semantics.

Shared Watch/Accounts cards expose intrinsic Remaining, Capacity, Monthly Capacity
and estimated pace help. Mini appends only the current primary Capacity/Remaining
raw help to its existing Capacity/reset facts. Bound targets survive unit, mode
and ordinary Live updates; nonestimated Used/provider pace do not acquire empty
tab stops or a misleading before-rounding claim. Existing ContextHelp owns
hover/focus/touch, suppression and dismissal.

## Narrow accepted example exception

Decision Delegate authorized following the FR's deterministic nearest-half-up
algorithm rather than the contradictory Remaining example in acceptance #3.
Raw Used **613**, Capacity **6130**, Remaining **5517** stay intact. Visible Used
is **613**, Capacity **6000**, Remaining **6000**, not the example's **5000**:
nearest one-digit 6000 has approximately 8.755% relative error and therefore must
be accepted. 5000 is within tolerance but is not the prescribed nearest candidate.
The literal 5000 expectation is **not passed**. No other acceptance was waived;
no FR rewrite, Suggestion or hold was needed.

Exact 10% inclusion/just-over are tested on the tolerance predicate. End-to-end
nearest rounding straddles the repeating threshold (200 ÷ .9) with finite Decimals;
it does not pretend that threshold is an exactly representable finite input.

## Verification and limits

- Full bounded local suite: **179 files, zero failures**, 126.8 seconds, including
  the newly admitted estimate test owner. Final targeted run after empty-tab-stop
  refinement: **86 tests passed**, including both Watch/Mini VM suites and legacy
  Accounts/display paths.
- Pure tests cover every FR table example, both rounding directions, half-up,
  powers, huge/tiny Decimals, low ambient precision, missing/invalid/nonfinite,
  zero, fractional raw help, USD conversion and honest currency limits. Projection
  tests retain 613/6130/5517, independent pace 613/1839, independent identities,
  unrounded monthly extrapolation and verified 3123/6877/10000 controls.
- Final hidden Edge 157 shipped HTTP/assets/SSE and real Document PiP probe:
  **PASS** (`probe_accounts_live.cjs ... --quota-only`). Accounts/Watch/open Mini
  agree across Used/Remaining × Credits/USD and Classic/Web light/dark. Primary,
  secondary, monthly and daily/workday values match server tokens. Actual Tab,
  delayed hover, touch, Escape, monthly/pace focus, same-target unit changes and
  Live raw-help refresh are checked. Native bars, source payload, Today,
  stream/report counts, retained nodes/focus and existing narrow/zoom geometry
  controls remain intact. No estimate input is fetched by a display switch.
- Initial failures were obsolete precise estimate/help expectations, the conflicting
  5000 example and Decimal representation/order assertions. These were corrected
  without changing retained calculations or weakening the declared algorithm.
  One subsequent broader browser attempt failed the existing account-link synthetic
  exhausted-flag assertion during concurrent suite load; no source cause was proven.
  Its final serialized rerun passed the complete link/quota/estimate checks; the
  failed attempt is not counted as a pass.
- Integrated browser was disconnected. Permitted isolated hidden Chromium supplied
  evidence without a personal browser or external-desktop interaction. Headless
  input/DOM is not physical OS, screen-reader or macOS proof.
- Real installation `probe_web_live.py --accounts`: **PASS**, registered V2,
  three accounts, one Live/account-refresh owner, advancing publications, one
  verified native capacity/amount pair/pace, zero finite jobs/model calls. The
  observation exposed **zero eligible estimates**: new rounding is proven by
  synthetic/browser tests, not a fabricated live-estimate pass. Owned workers
  closed cleanly; shared OpenCode was untouched.
- Final working-tree validator: **11 passes, zero failures**, seven advisory size
  warnings. No hard cap/baseline was raised. `git diff --check` passed.

Owned evidence: `scratch:/full-tests-final.txt`, `scratch:/accounts-browser-complete.json`,
`scratch:/real-accounts.jsonl`, `scratch:/validation-final.txt`.
No dependency, inference, ZIP, GitHub Release, installation or runtime reload.
