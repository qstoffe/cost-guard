# FR 000525 — Show quota Used / Total, used-oriented progress, and a temporary Watch migration warning

## Owner decision and observed problem

GitHub reports monthly Copilot AI-credit consumption as **Used / Total**. On 2026-10-28 GitHub showed **5,608 / 25,000 used**, while Cost Guard showed a 78%-remaining bar and **19,392 / 25,000 remaining**. Both numbers were correct but the opposite conventions looked like an accounting discrepancy.

The owner accepts a deliberate **breaking presentation change**: for a finite quota with reliable consumption and total, its main bar, percentage and native fraction all become **USED-oriented**, as on GitHub. The distinct **Remaining** amount per day/workday retains its existing future-spending meaning. This replaces the old remaining-oriented primary display; merely adding labels to it is not sufficient.

The owner also requires **strictly compact CLI Watch output**: the existing `Today` and `Remaining` text must not expand into repeated cost-definition disclaimers. A short, temporary, warning-style migration notice *above* the Watch table should communicate the orientation change during the first three days the user sees the updated Watch.

FR000490 already owns Web Accounts layout; FR000190 covers independent Copilot Unaccounted usage. This FR changes quota presentation and the one-time migration notice, not quota acquisition, CCost valuation or billing.

## Required behavior

### 1. Finite quotas: Used as the primary presentation

- Where a quota describes consumption against a real, trustworthy finite limit, fill the progress bar according to **used fraction**, show **% used**, and show **used / total** in its native unit. All three refer to the same provider/window/scope. The opposite remaining percentage must not be left as an unlabeled primary figure.
- Example: 5,608 used of 25,000 gives approximately **22% used**, a **22%-filled bar** and **5608/25000 AI credits**. The 19,392 remaining still drives Remaining pace when available.
- Apply consistently to the **CLI Normal report, CLI Watch, Web Accounts and Web Watch** where a quota bar appears; do not leave a conflicting remaining-oriented bar in another presentation. Retain native units, reset, account status, critical warnings and honest unsupported states.
- **Normal report/Web Accounts** can spell out `Used`, quota units and relevant detail as needed. **CLI Watch** is strictly compact: keep the existing ten-cell bars, columns, spacing, alignment, wrapping/splitting and narrow-terminal fallbacks. At most a **single short `used` marker** is added beside the primary quota percentage so it is clear that both the bar and fraction mean Used. Do not add repeated `Used` labels, new explanatory prose, additional lines per account or a full explicit `CCost today` explanation to each Watch quota row. Keep its existing `Today` field and avoid dropping existing essential status/reset/counters merely to fit a label. Optimize for actual width/geometry at 80, 120 and 160 columns.

### 2. Remaining pace is deliberately separate

- Continue showing existing `Remaining: X/day · Y/workday` in Watch and the report where supported. It is derived from **remaining included quota** and the same reset/workday calendar; it must not become a per-day spending or Used figure.
- The word `Remaining` already distinguishes this exceptional quota pace from the used-oriented bar and fraction. No additional prose or repeated definition is required beside it.

### 3. Unlimited and other incomplete native states

- For a provider-confirmed **Unlimited** quota, show `Unlimited` plus any provider-reported **native monthly Used amount**, even without a denominator, in Normal and compact Watch where available. Do **not** show a percentage, finite progress bar, used/total fraction or remaining/day/workday pace without a finite capacity. Unknown monthly used stays unknown, never zero by assumption.
- If a provider actually supplies reliable native **Used today** for its own daily window, it may be displayed explicitly as a separate native usage quantity, including for unlimited plans, where there is room. Do **not** invent this from monthly used, Remaining pace or OpenCode CCost.
- Existing Watch `Today` / report `CCost today` is **OpenCode CCost**, not provider-metered Used today. Preserve its existing short Watch presentation and availability for finite/unlimited accounts; don't rename the ordinary `Today` number to native `Used today` or require verbose `CCost` prose on Watch.
- Preserve native zero/unknown, stale/partial/unavailable, expired or not-started, overage, blocked, multiple accounts and unlimited distinctions. A provider-reported remaining percentage may become a used percentage only if that represents the exact complement of a real finite capacity; never invent absolute used credits from a percentage, CCost or unrelated spend. Native balance/spend without a valid consumption denominator stays textual; no fabricated consumption bar.
- Colors, account statuses and critical thresholds must still mean exhaustion risk correctly after inversion: **100% used = exhausted**, **0% used = unused**, never the reverse. Never invert canonical provider storage or Remaining calculations.

### 4. Cost definitions belong in the README and normal report, not repeated Watch notes

- Keep **one clear explanation of CCost in the root README and in the existing definition/explanation area of the Normal report**. Document that, unless a cost field explicitly says otherwise, Cost Guard's reference-cost figures—including the compact Watch `Today`—are **CCost**, not actual provider billing or native quota consumption. Distinguish CCost from provider-native `Used` and from actual `Billed` in that centralized explanation.
- **No repeated CCost disclaimers, help sentences, parenthetical interpretations or extra CCost labels added by this FR to individual Watch account lines, Watch sections, other reports or Web pages**. Existing concise field names such as `CCost` and `Today` remain valid; do not duplicate definitions on every screen. Do not redesign other reports solely to add explanation.
- The quota `used` marker and temporary migration notice address the change in **quota-bar orientation**, not a change to CCost.

### 5. One short temporary migration warning at the top of Watch

- Show **one short warning line** in the Watch notice area **above the main table**, following the existing `✦ New Models` notice placement/one-line style but using an appropriate warning role (e.g., amber/yellow rather than New Models' green), with an unmistakable warning symbol such as `⚠`.
- Suggested exact concise text: **`⚠ Quota bars now show Used instead of Remaining`**. This is deliberately precise: the **bars/proportions change**, while the separately labeled Remaining-per-day/workday pace still exists. No paragraph, tutorial, repeated tooltip or per-account warning; make it one self-contained line. Do not add it to Normal report or unrelated modes.
- **Time window: three elapsed days (72 hours) starting on the user's first actual display of this notice in the updated Watch**, *not* implementation date, commit date, installation/update date or any Watch process started invisibly without the UI being shown. For CLI, anchor the first successful visible Watch rendering including the notice; for Web Watch, if the same notice is surfaced there, use actual Watch-view presentation, not merely automatic server-side acquisition. Someone who launches Watch weeks after installing the new version must still receive their full three days.
- Persist a **stable, feature-specific first-shown timestamp** in tiny, bounded, user-local Cost Guard application state so that exit/restart, subsequent Watch launches and updates **do not restart the timer**. Reuse a suitable existing state owner or introduce the smallest safe one; store no session content, credentials, quota/usage/billing history or personal identifiers, and do not write to OpenCode, a tracked source file or the user's configuration. Concurrent Watch processes must not overwrite the first recorded timestamp with a later one. An expired marker must remain remembered (not forgotten and rearmed as a fresh three-day window).
- Derive visibility from that original first-shown time: display while the elapsed interval is **less than 72 hours**; hide at/after expiry on the next appropriate redraw without waiting for a process restart. Repeated polling/redraws never extend the interval. Clock rollback, invalid state or state-write failures must fail safely without blocking Watch, inventing a new billing/source status or causing an endless stream of notices; document any genuine loss-of-local-state limitation.
- Keep the warning independent of the existing New Models seven-day lifecycle and warning styles, Watch row cap, source outage/status and report/Watch quota refresh rates. Preserve printable, non-ANSI/redirected output behavior and avoid height/overflow flicker from the transient one-line notice. It must remain a small migration announcement, **not a permanent banner feature or an ongoing monitoring system**.

### 6. Monetary equivalents and existing boundaries

- Copilot currently exposes `remaining_money/limit_money` alongside remaining credits. If the main native fraction switches to used/total, any *unlabeled companion dollar fraction* must also represent **used/total** when the documented credit-dollar equivalence supports it (e.g., **$56.08/$250.00** for 5,608/25,000); otherwise separately identify an explicitly remaining-specific monetary value. Do not juxtapose an unlabeled remaining-dollar fraction with used-credit values.
- Respect true provider-native currencies. The dollar equivalent is not verified billing. FR000526's optional CCost display unit is independent and must not alter native quotas, account balances or native Billed fields.
- Reuse shared Python/report presentation and existing verified account/source projections. No new quota-provider calls, billing APIs, authentication, polling, permanent usage ledger, CCost repricing, prompt attribution or source mutation. Do not sacrifice Watch performance or CLI/Web independent acquisition to deliver a one-time notice.

## Acceptance / regression evidence

1. **Finite Copilot parity:** 5,608 native Used / 25,000 total / 19,392 remaining shows 22% used, approximately 22% filled and 5608/25000 credits consistently in CLI Normal, CLI Watch, Web Accounts and Web Watch. The separate Remaining/day/workday values are still calculated from 19,392; applicable used/total dollar equivalents agree. Reset/status stays present.
2. **Compact Watch:** no newly repeated CCost or Used explanatory prose, no per-row warning, and at most one extra `used` marker near the percentage. Existing compact `Today`, Remaining pace, reset and aligned/overflow layout survive 80/120/160-width fixtures and real terminal/redirected output. No new cost definitions appear in other views; README and Normal report contain centralized CCost meaning.
3. **Unlimited and incomplete quota evidence:** provider-native monthly Used remains visible for Unlimited if known, but no percentage/bar/Remaining pace. Available ordinary `Today` CCost remains present; neither it nor a missing daily native used value is mislabeled. Cover unknown, zero, partial, stale, exhausted, blocked and no-denominator providers without invented numbers or wrong risk colors.
4. **Migration notice lifetime:** no prior first-shown state and a first visible Watch render at T produces the one-line warning and stores T. Restart at T+1 day retains same expiry; T+71h59m shows it; at/after T+72h it disappears without resetting and stays absent on subsequent launches. Installing code and only using Normal/Diagnostics or a hidden Web engine does not consume the window. Two concurrent starts retain earliest T. Cover absent/invalid/unwritable state and backward clock safely, without blocking functional Watch.
5. **No functional regressions:** New Models and promo notices retain independent existing lifetimes, Watch row caps and status/refresh behavior are unchanged, no new provider requests or quota/CCost computations are introduced, and Billed/Unaccounted/Relative CCost continue to mean what they did before.

**Priority:** Normal, after pending FR000520 and FR000521. Relevant owners: `src/presentation/accounts.py`, `src/presentation/watch.py`, `src/watch/` and local-state owner, `src/web/assets/render.js` and `watch.js` if Web Watch shares the notice, `src/application/display.py`, account/Watch/Web presentation tests, root `README.md` and `docs/account-support.md`.
