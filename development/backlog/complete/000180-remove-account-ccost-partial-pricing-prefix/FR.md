# FR 000180 — Show plain account CCost numbers without partial-pricing prefixes

## Problem and desired result

After completed CostGuard FR000160 (v80.76), account-level CCost values in the normal `Accounts Overview` and Watch are compact, but a partly priceable period shows a leading `≥` sign (e.g., `≥250`). Before FR000160 the corresponding partial-pricing marker was `?250`. The owner wants **no `≥` or `?` prefix on numeric account CCost values**. These symbols make normal account reports unnecessarily technical; partial-pricing edge cases are already documented.

**Approved compromise:** show the already computed, known/priced part as an ordinary naked CCost number with the **same standard upward-rounded display used for complete account CCost**. Keep the partial-price knowledge and all calculation integrity unchanged internally. This is a presentation-only change, with the known limitation clearly explained in existing documentation rather than on every account line.

## Current evidence / precise scope

- `src/presentation/accounts.py::account_ccost_text` returns `≥` plus downward-rounded `value.known_ccost` when `value.complete` is false but at least one observed request was priced. The complete value uses `consumed_capacity(value.known_ccost)`, which rounds consumed CCost upward. This is the most direct existing owner to simplify.
- `src/analysis/valuation.py::ComparisonCost` preserves `known_ccost`, `observed_requests`, `priced_requests` and `complete`; the partial flag means some observed requests lack usable reference pricing. Thus the displayed number is only the priceable portion; removing its prefix **does not make it a complete estimate**.
- `src/presentation/accounts.py` already applies the common account formatter to the normal report and Watch, including today, this month (report only), rolling 5h/weekly window percentages and text-only quota values. Preserve these scopes and their existing placements.
- `docs/usage-and-cost.md`, section `Account-period CCost`, currently explicitly documents `≥37`, downward lower-bound rounding and `≥0`; this must be updated to match the simpler presentation while retaining the explanation of missing reference prices.
- `src/presentation/token_mix.py::comparison_cost_text` and `src/numbers.py::ccost_amount` still use `?` in **global, prompt, session and Token Mix CCost**. These are outside the approved scope and must not change.

## Required behavior

1. **Account presentation only:** In both normal reports and Watch, a partially priced CCost with some known priced usage shows **just the numeric known/priced amount**, with no `≥`, `?`, approximation or other replacement prefix/suffix. Apply consistently to `CCost today`, `CCost this month` in normal reports, 5h/Week rolling figures in parentheses after quota percentages, and any compact fallback CCost text on an account.
2. **Use normal CCost rounding in every account case.** Do not keep the special partial-only downward rounding. Reuse the existing complete-account `consumed_capacity`/ordinary upward rounding logic; examples: a partial underlying 37.2 CCost should display `38`, not `≥37`. Very small positive partial values follow the same ordinary small-number representation (`<0.1` where applicable), not `≥0`. This must affect presentation only, not stored Decimals.
3. **Preserve distinctions that matter:** A known acquired period with no observed requests still displays `0`. Unknown/unattributable/unacquired periods or observed requests with **no** priceable usage still display `—` under account figures, never a fabricated `0`. Multiple compatible account ambiguity and unsupported window bounds remain unknown. Native quota percentages, consumption, credit balances and billing do not change.
4. **Keep accurate internal evidence:** Do not change `ComparisonCost`, model-price matching, priced/unpriced request counts, attribution, deduplication, provider windows, daily/monthly boundaries, Watch refresh/acquisition or any billing/reference-value distinctions. Removing a visible sign must not convert partial data into complete data or suppress existing diagnostic evidence.
5. **Documentation instead of account clutter:** Update the relevant paragraph in `docs/usage-and-cost.md` to say succinctly that **account CCost values display the known priced subtotal without a partial marker and therefore may understate a period's complete reference valuation if some requests lack price data**. Preserve the documentation of the `0` versus `—` distinction and CCost-not-billing. Do not reintroduce a report footer, explanatory account prose, warning marker or tooltip. Other unrelated `≥` meanings, including model-comparison context boundaries, stay unchanged.
6. **Do not broaden the request:** The global Watch `Total today`, prompt/session subtotals, Token Mix and other global CCost presentation retain their existing `?` behavior, as well as any existing `N/A` semantics. Account-level native AI-credit/balance displays, authorization hints from FR000160 and the rest of the report layout remain as delivered.

## Minimal acceptance

- Account fixture with a known **partial** valuation: `known_ccost=37.2`, some priced and some unpriced observed requests → `38` in report and Watch, with no `≥` or `?` in that account CCost value; `complete` remains false internally.
- Fully priced account: identical existing plain numeric result. Acquired no-usage period → `0`; unknown attribution/history or wholly unpriceable usage → `—`; very small known positive amount retains existing ordinary consumed-value formatting rather than special `≥0`.
- Both 5h/Week quota-bar parentheses and regular today/month values remain in their existing positions and are not duplicated. Shared plain/ANSI and narrow/wide layout remain unaffected; another provider/account cannot inherit unknown requests.
- Existing global/prompt/session partial markers and priceability/attribution computation are untouched. Documentation honestly describes the caveat and matches output.
- Use proportionate **existing focused model-free presentation/account CCost regressions** and any normally applicable repository-owned shipped-source checks; **no new permanent gate, broad FR validator, paid live-model test or additional user approval**. A code change is eventually implemented through the normal verified Repo Backlog delivery, not by FR-only publication.

## Priority, authorization and publication

**Normal priority FR000180**, the next available multiple of ten after CostGuard's current identity high-watermark 170. Pending FR000170 is independent and higher priority; do not preempt a selected/paused implementation or Contract Sync. This is a standalone approved request, explicitly authorizing only the above account presentation/documentation change. No release version is prescribed. Authoring this FR is a documentation-only direct-main operation: it adds the todo FR plus the monotonic identity-state allocation and does not change production code, tests, packaging or product version.
