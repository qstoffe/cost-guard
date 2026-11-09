# FR 000663 — Web quota cards: separate Usage/Capacity tooltips and tighten estimate rounding to 5%

**Owner-approved Ready Feature Request, 2026-11-09.** Permanent identity **000663**, Ready priority **000980**, after FR000662 (000970) and following the ongoing account-card layout restoration in FR000661 (000960). FR000651 retains its explicit highest-priority Ready order (000001). **FR-only publication:** add this document and advance `development/backlog/identity-state.json` highWatermark **662 → 663** atomically on `main`. Do not implement code, alter completed FRs, change versions/releases or open a separate Sessions-list request in this transaction.

## Owner complaint and desired outcome

In **Cost Guard Web → Accounts** and the matching **Full Watch subscription cards**, tooltip ownership has become confused:

- Hovering/focusing a quota's main **`5-hour · N% used`**, **`Weekly · N% used`** or equivalent usage/remaining summary currently includes paragraphs about **reference Capacity estimation and pricing**. That is the wrong place to explain the full-window theoretical budget.
- Hovering/focusing the corresponding visible **`5-hour Capacity: ~...`**, **`Weekly Capacity: ~...`** or **`Monthly Capacity: ~...`** value provides only generic descriptive prose and source metadata, **not the original exact unrounded calculated amount**, even though the visible `~` is a rounded guesstimate.
- The underlying estimate-rounding policy permits a **10%** difference from the raw estimate to get a compact round number. The owner wants a tighter **maximum 5% relative difference**, retaining nearest sensible round-number / significant-digit presentation.

**Target:** distinct, short contextual help for **Usage** versus **Capacity**, with the exact raw computation and inputs owned by Capacity; a consistent five-percent tolerance for genuinely estimated reference quota display values. No extra permanent UI columns/labels and no change to actual source/account calculations.

## A. Separate the two kinds of help — no duplicated Capacity prose

### Usage/Remaining summary tooltip (on the actual quota summary label/value)

For every genuine primary, secondary and subsequent quota (including `5-hour`, `Weekly`, `Monthly` and other source-backed periods), the tooltip attached to `.watch-quota-summary` such as **`5-hour · 10% used`** should:

1. Explain **what the visible native usage percentage means** and whether the display mode is **Used** or **Remaining**, with only the relevant source-backed quota status/units when useful.
2. Preserve genuinely valuable facts specific to *usage*, such as provider-reported native Used/Remaining quantities, reset when pertinent, actual percentage and genuine restriction/staleness warnings. The amount in the adjacent **Used/Remaining reference CCost parentheses** may retain its own existing value-specific cost provenance and raw estimate help, including when the Remaining amount is itself an estimate.
3. **Remove the reference-Capacity math and prose** from this summary tooltip: no `Capacity: ...`, `Reference Capacity estimates a full period from observed CCost ÷ native fraction used`, `Used + Remaining = Capacity`, full-window derived allowance, estimated monthly-equivalent calculation, or repeated pricing-disclaimer paragraphs that belong to Capacity.
4. Avoid verbose concatenated technical identity strings such as `Weekly · rolling · account · ...` and unnecessary repetition of the period/duration already printed in the summary label. Keep any indispensable source-specific restriction contextualized in concise human language; do **not** erase useful truthful reset/availability facts.
5. **Used and Remaining are not interchangeable:** user-controlled quota orientation updates the relevant summary/help instantly, and a provider's Used percentage, native balance, and estimated Cost Guard reference CCost remain semantically distinct. No cash/billing claims.

Suggested concise example, **fictional values**:

```text
5-hour · 20% used

The provider reports that 20% of this quota window has been used.
Native Used: 40 / 200 · Native Remaining: 160 / 200
Next reset: 2026-11-10 14:30
```

Use available real source fields, the configured-local Swedish-style date standard and only the lines supported by a given quota. The `N% used` label itself already appears on the card and need not be repeated verbatim as an extra tooltip paragraph if the explanation is clear.

### Own period Capacity tooltip (on the Capacity value, not its Used summary)

For each visible native-period `... Capacity: ~...` row, and also when it shows a verified numeric source allowance or `?` per FR000661:

1. Begin with **one short plain-English sentence** telling the user what this period's **reference CCost Capacity** represents: a full-window approximation where inferred, or a native/source-verified compatible full-window allowance when such evidence genuinely exists.
2. After a blank line, show **the original raw calculated Capacity before display rounding**, clearly labelled as **unrounded estimate**, in full available **reference Credits Decimal precision** (and optionally a normal USD rendering when in USD mode). It must correspond to **this exact account, quota, period and current source snapshot**. Do not substitute the visible rounded value, a generic plan number, the last reset amount or a provider-native currency figure as though it were the exact raw CCost calculation.
3. For an **inferred ratio-based Capacity**, include a single compact, **source-backed calculation** with actual unrounded inputs: e.g. `Observed same-window reference CCost: 613 Credits`, `Provider-reported fraction used: 20%`, `Unrounded Capacity: 613 ÷ 0.20 = 3 065 Credits`. The arithmetic must reflect the existing canonical formula **`capacity = used / (1 - remaining_fraction)`**, or the equivalent verified native-used fraction. The numerical example is synthetic; actual values come from the server, not string parsing/JavaScript recomputation.
4. For a **verified native/reference Capacity** that was not estimated by dividing usage by percentage, show the genuine **unrounded source-confirmed amount and provenance**; **never fabricate the ratio formula** or falsely call it an estimated observed-cost result.
5. For `?`/unlimited/unavailable, replace the absent numeric formula/raw values with one concise reason (e.g. no reliable same-window reference CCost or full-window evidence), and retain the honest unlimited/nonfinite semantics. A missing amount never becomes `0`.
6. **Remove the redundant `weekly rolling` / `5-hour rolling` / `account scope` / implementation-detail dump**, repeated native quota inventory and irrelevant pricing boilerplate from this Capacity tooltip. The visible quota label already gives the period; tooltips should explain the *calculation*, not re-document the entire provider DTO.

Suggested fictional tooltip:

```text
Estimated full-window reference CCost capacity.

Observed CCost used: 613 Credits
Native fraction used: 20%
Unrounded Capacity: 613 ÷ 0.20 = 3 065 Credits
```

The ratio-derived value is an estimate, not a guaranteed provider budget or billed cost. Keep this distinction clear **once**, without a long defensive explanation.

### Derived Monthly Capacity tooltip (on its own value)

Keep it distinct from both the Used summary and own period Capacity. For every source-qualified **nonmonthly** quota that FR000661 displays with an extra `Monthly Capacity` line:

- Start with one short sentence: **a theoretical standardized 30-day reference equivalent, not an actual monthly provider entitlement**.
- After a blank line, show the **original unrounded Monthly Capacity calculation and amount** from the current canonical source: `Raw period Capacity × (30 days ÷ verified full window duration)`, using the **unrounded period Capacity**, not its rounded display text. Example (fictional): `3 065 × (30 days ÷ 5 hours) = 441 360 Credits`.
- Do not duplicate full observed-cost/native-usage details already available from the period Capacity tooltip, nor repeat an unhelpful `weekly rolling` metadata string. Show the raw period Capacity and full duration as necessary to explain the formula.
- For monthly-native quotas, **do not invent another derived Monthly Capacity**; their sole native Monthly Capacity uses the period-capacity help above. For missing full-duration/unknown price evidence, show `?` with a short reason instead of a fabricated exact result.

**Clear separation contract:** *Usage tooltip = usage/remaining and native status.* *Period Capacity tooltip = exact period-capacity derivation or verified source amount.* *Monthly Capacity tooltip = exact standardized monthly extrapolation.* All three are intrinsic hover/focus/touch help on the relevant label/value, not an entire-card popup.

## B. Change the existing rounding tolerance from 10% to 5%

### Verified current algorithm and requested precise change

The current pure helper `src/application/quota_estimates.py::rounded_estimate()` tries **nearest one significant digit first**, using `Decimal` and `ROUND_HALF_UP`, then the nearest **two significant digits**; it accepts the coarsest candidate only when `within_tolerance(raw, candidate)` is true. Today `within_tolerance` tests **`abs(candidate - raw) * 10 <= raw`**, equivalent to at most 10% relative error in canonical Credits.

**Replace this with `abs(candidate - raw) * 20 <= raw` or an equally exact Decimal comparison**, i.e. **`|rounded - raw| / raw <= 0.05`**, inclusive at exactly 5%, with the same precision safeguards. This is the owner's idea of the **nearest sensible round number within 5%** — **not rounding in fixed 5% steps, not rounding all numbers to the nearest even integer, and not switching to banker's tie-to-even rounding**.

- Still prefer a single significant digit if its *nearest* candidate satisfies the 5% bound; else use two significant digits; retain more raw precision if necessary to obey the bound. Keep Decimal and `ROUND_HALF_UP`, no floats or positive-to-zero rounding.
- **Apply only to the existing estimate-specific display policy**, namely ratio-derived `Capacity` and `Remaining`, theoretical `Monthly Capacity`, and estimated `Remaining/day` or `Remaining/workday` pace when the existing policy covers them. Preserve the ability to display exact **raw** reference-Credit values in the appropriate capacity/pace tooltips.
- **Do NOT apply estimate rounding to measured/observed `CCost Used`**, source-verified native allowance/Used/Remaining, quota percentages or progress fractions, account Today, ordinary session/prompt costs, actual USD billing, CLI, raw canonical cache data or unrounded calculations. The owner mentions "Used" while talking about the previous 10% rule, but the current 10% helper demonstrably applies to *estimates*, not measured Used; the desired 5% precision change must retain that correct distinction.
- Keep the `~` marker **only for numeric estimated values**. Verified native/reference costs remain normally formatted. Preserve Credits↔USD synchronization: **round once in Credits before the existing USD conversion**, and keep normal two-decimal USD plus the existing truthful small-positive `<$0.01` behavior. If two-decimal USD cannot represent the raw amount inside 5% Credit-space tolerance, retain truthful raw Credits in help and **update any warning text from 10% to 5%** rather than claiming that currency-format quantization meets the bound.
- Update `src/application/quota_estimates.py::estimate_help()` and all relevant tests/docs to consistently state **5%**, including its existing small-USD display caveat.
- Deterministic synthetic examples:

| Raw CCost Credits | Old 10%-tolerance display | New 5%-tolerance display | Why |
| ---: | ---: | ---: | --- |
| `613` | `600` | `600` | One significant digit is within ~2.1% |
| `550` | `600` | `550` | 600 is ~9.1% high, so two digits |
| `949` | `900` | `950` | 900 is ~5.2% low, so two digits |
| `52 343` | `50 000` | `50 000` | Approx. 4.48%, still within 5% |
| `250` | `250` | `250` | 300 is 20% high |
| `0` | `0` | `0` | True known zero |

The synthetic examples above are **not** real users' account values. Add exact `5%` boundary tests, just-under/just-over boundary and very large/small finite decimals with deliberately low ambient Decimal precision to ensure no context drift.

## C. Implementation ownership, coordination and acceptance

**Current implementation path:**

- `src/web/assets/account-cards.js::quotaTrack()` builds the quota `watch-quota-summary`, own `watch-quota-capacity` and `watch-monthly-capacity` targets. The first currently calls `ReportView.quotaHelp(quota(), true)`; the others call `quotaHelp(quota())` or `quotaHelp(quota(), false, true)`. These call sites need distinct semantically correct help.
- `src/web/assets/render.js::quotaHelp()` currently appends a shared native Used/Remaining, scope, reset and general **Capacity** block for both usage and capacity contexts, causing the reported duplication. Prefer purpose-specific, source-owned help tokens/controllers rather than an expanding set of ambiguous positional boolean flags.
- `src/application/quota_ccost.py::quota_ccost_values()` retains **raw `Decimal` period CCost Used, capacity, remaining, monthly capacity, basis and full duration**; `quota_ccost_tokens()` already exports concise `capacity_help` and an **`ccost_capacity_help` with `estimate_help(capacity)`** for ratio estimates. That richer raw-precision token is **not currently consumed by the shared Capacity tooltip**. Reuse the real raw data/provenance rather than compute in browser tooltips.
- `src/application/quota_ccost.py::monthly_tokens()` has the source-backed `monthly_capacity` and short `monthly_capacity_help`, but it currently omits the raw unrounded amount/formula from visible Capacity help. Add server-prepared, unit-aware, plain-text tooltip data for the raw monthly estimate and full-duration basis; do not re-derive from an already-rounded parent period.
- `src/application/quota_estimates.py::within_tolerance(), rounded_estimate(), estimate_help()` own the 10% policy and its prose; change them coherently to 5%.
- `src/application/display.py` already exports the common display records and `ccost_reference` for the Web. Preserve the canonical numbers and unit/native provenance.

**Coordination:** FR000661 is restoring **always-present Capacity / Monthly Capacity rows and progressbar alignment** on the same Accounts/Full Watch cards. Implement this FR against that resulting stable card layout, not by reintroducing FR000654's conditional row deletion. This FR **supersedes FR000654's prohibition on exposing exact raw numbers/formulas in Capacity tooltip** and *restores that narrowly requested transparency*, without reverting FR000654's good short explanations, `~` prefixes, first-letter capitalization or Mini's five-column presentation. Likewise FR000641 remains the source of the 1-/2-significant-digit algorithm, with only its tolerated error threshold changed.

### Acceptance criteria

1. **No cross-topic tooltip duplication:** `5-hour Used`/`Weekly Used` (and Remaining-mode equivalents) show usage/native facts, **not capacity computation or total-budget prose**. Own Capacity shows original unrounded reference-Credit amount and the real source-backed formula/inputs or verified native provenance. Derived Monthly Capacity shows its distinct raw 30-day calculation. Test the exact focus/hover target for each quota and avoid redundant `rolling`/provider-scope metadata.
2. **Precision verified:** rounded estimates always satisfy **≤5% relative error against unrounded reference Credits**, inclusive boundary; the nearest one-significant-digit candidate is accepted only within 5%, else a two-digit candidate (or sufficient extra precision). Synthetic 550→550 and 949→950 differ from the earlier ten-percent behavior. Do not touch raw observed Used, quota fractions, verified native limits or global formatting.
3. **Raw tooltip parity:** on every current estimated Capacity and Monthly Capacity, including primary and second/third quota, all rendered tooltip numbers are **from the matching raw server snapshot and never from the rounded visible amount**. The tooltip updates with Live source changes, model/account choice and Credits↔USD mode, without stale previous-account values or accidental rerender of the whole card. Missing values give a concise reason, not invented digits.
4. **Same shared cards:** Full Watch and Accounts exhibit identical relevant tooltip text/targets, percentages, estimates, unknowns, capitalization and focus/keyboard/touch behavior. Include Used and Remaining orientations, numeric/partial/unavailable, native-confirmed vs ratio-inferred cases, `?`, genuine unlimited and monthly-native/nonmonthly windows. Preserve FR000661's aligned quota tracks, dividers and permanent rows.
5. **Scope controls:** Mini Watch retains its intentionally compact distinct help (unless its existing estimate rounding text needs the new threshold) and gets the shared 5%-precise estimate display where applicable. All reference CCost underlying calculations, native provider telemetry, paid billing, model API acquisition and unrelated session/model views are unchanged.
6. **Tests:** update targeted `development/tests/test_web_quota_estimates.py`, `development/tests/fixtures/account_capacity.cjs`, `development/tests/integration/probe_quota_estimates.cjs`, `probe_subscription_capacity.cjs` and shared Watch/Accounts DOM plus actual browser checks. Supersede FR000654's assertion that raw Capacity help must *not* contain arithmetic: this FR explicitly requires it. Test 360/800/1280/1920 px, Classic/Web light/dark, keyboard/focus/hover/touch, Credits/USD and enabled/disabled source states. Record outcomes honestly without real AI/model calls.

**Done means:** different concise tooltips for Used vs period Capacity vs Monthly Capacity, truthful exact raw estimated values and source-backed formula on the *Capacity* values, and a 5%-maximum approximation tolerance without affecting measured usage.
