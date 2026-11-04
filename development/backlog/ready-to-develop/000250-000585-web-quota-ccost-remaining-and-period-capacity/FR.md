# FR 000585 — Web quota CCost Remaining, period Capacity, and cleaner Watch account cards

## Owner request and backlog decision

**Owner-approved executable Feature Request, 2026-11-04.** Permanent identity **000585**; Ready priority **000250**, after existing Ready FR000584 (000240). Scope: **Cost Guard Web Beta's Used/Remaining presentation across account/quota surfaces, with a new Capacity line on the full Watch account cards**. This is authoring only: do **not** implement product code, tests, user docs or a release during creation of this FR.

The current Web setting **Settings → Web settings → Quota display** correctly switches each supported finite quota's native **percentage** and **progress bar** between Used and Remaining. However the CCost amount in parentheses still says **`CCost used: <value>`** in Remaining mode. The owner now explicitly wants **the parenthesized CCost itself to switch**: Used shows CCost consumed/observed in the current quota period, Remaining shows estimated or directly comparable CCost-equivalent capacity left. The UI should display just **`(<number>)`**, no `CCost used:` prose or visible `≈` decoration; brief help on focus/hover must disclose the basis and limitations.

The owner also wants the full Watch subscription cards to be cleaner and more comparable: retain **CCost Today**, then a compact **quota name · percentage used/remaining (CCost)** line, add **`Capacity: <CCost>` as a third row above the progress bar**, and remove the redundant **`16/7000 AI credits`** or similar native numerator/denominator appended to the compact quota headline. Keep existing primary/secondary quota separators; **do not** add a divider between CCost Today and the primary quota.

This **explicitly supersedes the presentation-only ban in completed FR000577 §4** on estimating/showing remaining period CCost. It does **not** supersede FR000577's canonical native quota arithmetic, provider provenance, accurate Used/Remaining percentages and progress fill, unlimited handling, persistent Default/explicit preference meaning, or security/availability requirements. The new estimate is explicitly a **reference-cost proxy**, *not* a claim that the provider promises that many tokens/requests or actual CCost credits.

## 1. Name and compact full Watch account card layout

Use **`Capacity`** as the third-row label, **without repeating** `Monthly`, `5-hour`, `Weekly` etc. because the quota name and time window already appear directly above it. Do **not** use `Total CCost`, which can be mistaken for total historical spending, nor `CCost Capacity`, which is needlessly repetitive in this context. Explain in the tooltip that the number is expressed in the selected **CCost Credits/USD** display unit.

**Illustrative Copilot card with a verified native 7,000-credit monthly allowance:**

```text
Copilot Pro+
CCost Today: 120
Monthly · 0.2% used (16)
Capacity: 7 000
[existing used progress bar]
[existing Reset / pace details]
```

In **Remaining** mode, with the same *illustrative* provider-reported 16 credits consumed:

```text
Copilot Pro+
CCost Today: 120
Monthly · 99.8% remaining (6 984)
Capacity: 7 000
[existing remaining progress bar]
[existing Reset / pace details]
```

**Illustrative percentage-based five-hour quota with observed period CCost 100 and a credible raw 10% used fraction:**

```text
CCost Today: 35
5-hour · 10% used (100)
Capacity: 1 000
[used progress bar]
```

Switch to Remaining:

```text
CCost Today: 35
5-hour · 90% remaining (900)
Capacity: 1 000
[remaining progress bar]
```

Figures above are **examples, not hardcoded plan values**. The source's actual primary quota label, reset/window, quota state and account identity remain authoritative.

Requirements:

1. Make **CCost Today** the first metric as today; preserve its local-day scope and number, independently of the quota's rolling/calendar window.
2. Place **quota label + native percentage / Used-or-Remaining wording + a single parenthesized CCost number** on the next row. E.g. `Monthly · 0.2% used (16)` or `Monthly · 99.8% remaining (6 984)`. The amount is CCost in the selected unit, **not** the raw native `used/total` ratio.
3. Insert **`Capacity: <number|?|N/A>` immediately after the quota headline and before its progress bar**. Display **one Capacity per quota window**, including each secondary quota when shown, not merely a single account-wide capacity inherited by all windows.
4. Remove the existing redundant appended native amount strings like `· 16/7000 AI credits` (and equivalent `Used/Remaining X/Y native units`) **from these compact full Watch quota headlines**. If native money-equivalent/limit details are also cluttering that headline, move them to the corresponding accessible help rather than adding a long fourth line. **Do not destroy native data or remove it from Accounts/Diagnostics**: native values and their precise meaning must remain available in a concise, accessible tooltip/focus explanation or existing detailed Accounts surface.
5. Retain the **existing divider only between the primary quota and the secondary quota region** (and existing spacing among multiple secondary quotas). **Do not** add a line separating CCost Today from primary, nor new full-card borders. Respect the existing row/subgrid alignment of account cards so progress bars continue to start at consistent vertical positions despite the new Capacity row, even with accounts missing secondary quotas or with unknowns.
6. Preserve existing warnings, reset date/time, remaining pace/day/workday and genuine blocked/exhausted styling. A limited quota with 0% remaining must still look exhausted; Capacity is not a new spending ceiling control.

## 2. CCost Used/Remaining: the same mode everywhere

- **Used/default:** keep the current canonical **observed period CCost** in parentheses, correctly formatted. It is not native credits deducted, actual billing, nor total usage across all accounts. Do not change the existing source, prompt attribution or pricing.
- **Remaining:** show **a CCost-equivalent remaining amount** in the same parentheses (without a `CCost used:` label). It must refer to the **same exact provider/account/quota window** as the percentage and bar, and must not borrow daily CCost, a previous quota period, another provider's quota, another account, or a different primary/secondary window.
- Apply this to **full Watch's primary and secondary quotas and Mini Watch's primary quota lines**, plus **any other Web account surface that already couples an observed-period CCost parenthesis with Used/Remaining**. In the regular **Accounts** view, the native Used/Remaining bars/fractions already switch: preserve those exact source values and add coherent CCost/Capacity presentation only where a **valid matching canonical period CCost** is available through the existing report projection; do not invent a new account-specific total from a global provider value. Avoid unintended new report scans or making Accounts inconsistent with Watch at equivalent snapshots.
- **Mini Watch must stay compact**: switch the parenthesized amount and expose the capacity/provenance via tooltip where helpful; the new visible third-row Capacity requirement is primarily for **full Watch subscription cards**, not a mandate to turn each Mini Watch list item into a multiline account card.
- Toggling quota mode in already-open Full Watch, Mini and Accounts should **immediately switch text, numbers, native percentages and bars together** from already published server-owned data, with no provider refresh, browser reload, extra SSE connection or heavy source revaluation.
- Credits/USD switching should update **Used CCost, Remaining CCost and Capacity together**, using the existing exact display conversion (`100 CCost = $1.00` reference) and normal formatting, while leaving provider-native quota/billing and actual percent completely unchanged. Do not compute rounded display strings into new numeric values.

## 3. Capacity and remaining-CCost calculation by quota type

The **canonical calculation must live on the Python projection/formatting side** and reuse existing quota/window CCost, native quota fraction, account attribution and display-token infrastructure. JavaScript only chooses formatted Used/Remaining and Capacity variants. Preserve unrounded `Decimal` values until final presentation.

### A. Explicit native Copilot AI-credit allowance (directly comparable unit)

Cost Guard defines **1 CCost = 1 Copilot AI-credit-equivalent reference unit**; see `src/domain/ccost.py` and `src/presentation/definitions.py`. GitHub's current documentation defines **1 native AI credit = $0.01** and plan-dependent included monthly allowances (e.g. 7,000 for a supported Pro+ plan), but the implementation must read the **account's actual reported native quota limit**, *not* hardcode plan name, size or pricing: https://docs.github.com/en/copilot/concepts/billing-and-usage/individuals/billing .

When there is a **credible finite positive limit in `AI credits` on a verified Copilot account/window**:

- **Capacity** = the actual **native included limit as its nominal CCost-equivalent numerical amount** (or converted reference USD when selected). This is a *comparison proxy* on the same unit scale, **not** a claim that Cost Guard's observed CCost equals GitHub's actual deductions. Do not convert requests/tokens/third-party proprietary credits at 1:1 by unit-name guesswork.
- **Remaining parentheses** = the provider's **credible native remaining AI credits** (or a safely derived `limit − native used` for the *same* window), expressed as nominal CCost-equivalent units and converted to selected CCost display currency. Don't subtract Cost Guard's independent observed CCost from the native limit and mislabel the result as provider-available capacity.
- **Used parentheses** remain the independently observed **Cost Guard period CCost** as before, not the provider-native Used credits. Their values **need not add up to Capacity** when users have other Copilot usage, distinct accounting/caching or attribution differences. The tooltip must explain this divergence plainly; don't silently claim `CCost used + CCost remaining = native limit`.
- If the **known limit** is valid but **remaining native usage is unknown**, Capacity can still show that limit; Remaining parentheses must show an honest unknown symbol, **not** `Capacity − observed CCost` presented as available provider credits. Preserve unknown native capacity/coverage distinctions.
- Apply to account-scoped Copilot plans only when they actually expose a finite native included credit allowance. Do **not** treat a billed overage budget, billing balance, per-model multiplier, request-count cap or pooled/non-attributable organization limit as a private per-account monthly AI-credit allowance.

### B. Percentage/usage quotas without a comparable native CCost-equivalent limit

For a verified **finite, active, positive-used-fraction** quota in another unit (e.g. a five-hour or weekly usage window), with valid same-window observed/reference CCost:

Let `U` be **unrounded observed CCost used** for this quota and `f` be the provider's **unrounded fraction USED** for that exact window, not the displayed rounded `10%` string.

```text
Capacity = U / f
Remaining CCost = Capacity − U
               = U × (1 − f) / f
```

For `f = 0.10`, `U = 100 CCost`: Capacity = `1 000`, Remaining = `900`.

- This is **an extrapolation of observed reference cost per native quota percentage**, **not an actual provider CCost limit**. Provider cost and quota depletion can diverge due to model mix, promotions, different efforts, external/unattributed activity, nonlinearity or source changes. The tooltip explains the ratio and limitations, while the main card shows the clean number with **no `≈`, `~` or `estimated` suffix**, per owner's explicit UX decision.
- Guard against dividing by zero, invalid/reported-only-rounded `0%`, unknown or reversed native fraction, unavailable period boundaries/history, partial/unpriceable CCost, mismatched account/window/model scope, stale/expired/resetting quota, non-finite/negative values, and extremely unreliable evidence. Never use display-rounded fraction or 0.0% text to divide. Zero used/CCost with 0% is **unknown**, not an inferred 0 Capacity.
- At **native 0% used** with no directly known credit allowance, show **`Capacity: ?`** and unknown Remaining CCost if no defensible estimate; as genuine usage arrives, calculate the estimate. If native raw `f > 0` despite a rounded displayed `0%`, calculate only when reliable actual unrounded evidence exists. `U = 0` with positive `f` is suspect/unrepresentative for extrapolation; show `?` rather than a fictitious free Capacity. Preserve truthful **actual zero** for observed Used when independently proven.
- At **100% native used** with valid observed U, estimated Capacity may be U and Remaining CCost 0 (subject to source truth and genuine exhaustion). For provider-reported overage or conflicting quota states, do not show negative Remaining as spendable credits or an impossibly certain Capacity; retain existing overage/exhaustion warning and appropriate unknown/fallback.
- Recalculate from the current valid observation as usage and quota percentage evolve; a new period resets the estimate instead of carrying the last period's CCost into the next. Avoid transient loading flashes if already valid coherent values can be retained without presenting them as newly observed.

### C. Unlimited, no valid finite denominator, no evidence

- **Provider-confirmed unlimited / not subject to a finite usage limit:** **`Capacity: N/A`** (inapplicable). No invented infinite credit amount or remaining quota. Continue the established Used-oriented fallback for native unlimited data under the Remaining setting; explain the exception on focus/hover. Keep the visible used reference CCost where the current view has a valid observed scope, but never invent a finite Remaining value.
- **Finite quota with insufficient evidence for a numeric capacity** (0% used, unavailable/partial/unpriced CCost, missing reliable percentage, missing window, multiple unresolvable accounts): **`Capacity: ?`** (potentially knowable later, not intrinsically inapplicable). In a Remaining-parenthesis slot, prefer `(?)` or the application's appropriately scoped unknown display; never silently substitute Used, zero or an earlier-period estimate while labelling it Remaining.
- When no period or quota can be established at all, retain current truthful N/A/unknown behavior rather than create an artificial capacity source. Distinguish inapplicable (`N/A`), temporarily unknown (`?`), genuine zero and unavailable/stale.
- All current native quota percentage and bar rules remain unchanged. The new CCost projection must **not** override provider-native capacity/used/remaining, existing billing, subscription-limit exhaustion/restriction, account identity or resets.

## 4. Tooltips, accessibility, and visual restraint

Coordinate with **FR000582 (application-wide tooltip overhaul)** to give Full Watch, Mini and appropriate Accounts figures **short, beginner-friendly, line-broken** explanations, e.g.:

```text
Capacity — Estimated CCost equivalent of 100% of this quota period.

Based on: CCost used ÷ provider-reported fraction used.
The amount can change with your models and the provider's limits.
It is not a guaranteed budget or billed balance.
```

For native credit caps, the tooltip should instead say **`Capacity comes from the provider's reported included AI-credit limit.`** and that Used CCost is a separate observed reference estimate while Remaining can be provider-native AI credits. Show the exact native `used/limit`, `remaining/limit`, unit, window/reset, validity and source/account attribution as supporting detail **in accessible help or existing Accounts detail**, rather than clutter the Watch headline.

**The visible number should be clean, but the explanatory text must never falsely claim exact prediction or omit a meaningful provenance discrepancy.** Retain actual warning/status controls for blocked, partial, expired or unavailable quotas outside the tooltip where necessary. Provide keyboard/touch access to the same explanations. A bare unlabeled native amount must not masquerade as CCost in a tooltip.

## 5. Implementation footprint, compatibility, and acceptance

Current relevant source inspection:

- `src/application/watch_accounts.py` binds a canonical native quota and its **own matching period CCost**, native used fraction and note for each primary/secondary quota.
- `src/reports/accounts.py` / `src/analysis/period_ccost.py` own the indexed provider/account/window-specific CCost and actual acquisition scope. Reuse rather than recompute from visible prompts, run a new independent history scan, or infer ownership from the currently selected tab.
- `src/application/quota_display.py` already defines server-owned Used and Remaining native variants. Extend with CCost Used/Remaining/Capacity variants in an appropriate shared projection/formatter, including both Credits/USD tokens, without changing native variants.
- `src/web/assets/watch.js::quotaTrack()` appends `CCost used:` and native `X/Y` to the quota headline, while `accounts()` composes `CCost Today`, primary quota, bar, reset/pace details and existing secondary divider. `src/web/assets/mini.js::drawAccounts()` repeats the label and native/period explanatory prose. `src/web/assets/render.js::accountQuota()` owns Accounts native quotas and must retain their native truth.
- `src/web/assets/app.css` uses a six-row subscription-card subgrid to align the current elements. Adapt its tracks/bars and internal grouping to add the Capacity line without introducing a divider before primary, changing 448px card constraints or losing aligned bars.
- Current completed **FR000556** and **FR000577** document that observed period CCost and provider-native used amount differ (e.g. native `2 088/25 000`, observed CCost `1 814`). This FR intentionally adds **estimated** CCost capacity/remaining displays while preserving that source distinction. Don't rewrite older completed records.

**Acceptance criteria:**

1. With a finite percentage-based five-hour quota and known `U=100`, **raw** used fraction `0.10`, Full Watch/Mini render **Used `(100)`**, **Remaining `(900)`**, and full Watch **`Capacity: 1 000`**. Native bars and percentages remain 10% used or 90% remaining in the established orientation. USD yields reference `$1.00`, `$9.00`, `$10.00` respectively. The tooltip explains the extrapolation.
2. A verified native Copilot included quota of **7,000 AI credits** displays full Watch **`Capacity: 7 000`** in Credits or `$70.00` in reference USD, with Remaining parentheses based on *actual native remaining credits* and Used parentheses on *the independent observed period CCost*, not forced to reconcile. Include the regression fixture **native used 2,088 / limit 25,000, native remaining 22,912, observed CCost 1,814**: Used and Remaining modes show the appropriate **distinct** values and the tooltip explains why the figures differ.
3. Compact full Watch primary and secondary quota headlines no longer display `16/7000 AI credits` or equivalent native ratios after the parenthesized CCost. The underlying native data remains available on hover/focus/Accounts detail. **CCost Today → quota Used/Remaining (+ parentheses) → Capacity → progress bar** is the visible order, with reset/pace beneath as before. Existing primary/secondary separator remains the **only** quota-region divider, and aligned bar rows stay consistent across neighboring cards.
4. At 0% used with a genuinely unknown percentage-based proxy, show `Capacity: ?`; at 0% with a verified numeric AI-credit allowance, keep the real finite Capacity. At confirmed Unlimited show `Capacity: N/A` and preserve the current native Used fallback. Missing/partial/unpriced/expired/out-of-window/ambiguous/overage states show correct unknown, inapplicable or stale treatments — never invented exact capacity, false zero or negative available amount. A valid 100% used case yields no fabricated positive Remaining value.
5. Primary and secondary quotas are **independent**: switching between Monthly, weekly, five-hour and model-scoped windows, resetting one quota, delayed old-window results, multiple accounts, cache correction and provider repricing never mix cost/fraction/limit or change native primary selection.
6. The display switches **immediately** and consistently in already-open **Full Watch, Mini Watch and applicable Accounts UI**, including unit changes and theme/zoom/resizing; no native percentage/bar mismatch, layout jump, extra SSE/HTTP/provider polling, per-frame valuation, new source telemetry, browser persistence or CLI changes. All visible CCost data comes from server-owned immutable/reference projections.
7. Focus/hover/touch help correctly discloses **direct comparable native credit cap versus estimated cost/percentage extrapolation**, reference USD, unknown reasons and nonreconciling native/observed cost. Update `docs/web-beta.md`, `docs/web-mini-watch.md`, account/CCost help and relevant module descriptions after implementation, and add focused Python calculation/projection and JS/real-browser coverage for primary/secondary/full Watch/Mini/Accounts, Used/Remaining, Credits/USD and difficult quota states.

**Not in scope:** changing provider quotas, actual subscription allocation or billed spending, inferring that a provider has promised a stable CCost-to-percent rate, changing CLI, adding quota/account settings, historical repricing, changing daily costs, inventing a new provider cap when none exists, provider network polling or implementation/version/release work in this authoring session.
