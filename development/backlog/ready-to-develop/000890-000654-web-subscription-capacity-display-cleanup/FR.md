# FR 000654 — Web subscription cards: hide unknown capacities, simplify estimates and normalize quota labels

**Owner-approved Ready Feature Request, 2026-11-09.** Permanent identity **000654**, Ready priority **000890** (after currently Ready FR000653 at 000880). **Backlog-only publication:** add this FR and advance `development/backlog/identity-state.json` highWatermark **653 → 654** in one documentation-only commit. No implementation, product tests, version/release changes or unrelated backlog work in this publication.

## Problem

On **Cost Guard Web → Accounts**, subscription/quota cards currently show **?** for unknown period CCost Capacity, but **N/A** for an unavailable derived Monthly Capacity. This is inconsistent: the latter often means insufficient evidence for an estimate, not that the comparison is conceptually inapplicable. Both non-values clutter small cards.

Numeric inferred capacities append the long visible `(guesstimate)` suffix. The associated hover/focus help is disproportionately long, mixes the capacity explanation with exact unrounded arithmetic, repeated caveats and native details, and has little useful paragraph spacing. Provider-supplied quota/window names also begin with inconsistent capitalization (e.g. `weekly`, `Weekly`, `Fable Weekly`, `5-hour`).

**Full Watch and Accounts share the same subscription-card renderer**, so this is one shared visual behavior change, not two independent implementations.

## Desired UI

1. **Hide unknown period Capacity rows.** For each primary or secondary quota, when the reference CCost Capacity cannot be computed/trusted (currently displayed as `?`), omit the **entire period Capacity line**, including its label, placeholder and associated help target. Do not display a blank row, convert unknown to zero, or hide the native usage percentage/bar, quota/window name, reset information or provider warning. A genuinely provider-reported unlimited quota remains truthfully described as unlimited; do not silently invent a finite capacity or conflate that case with missing evidence.

2. **Hide unavailable derived Monthly Capacity rows.** For a nonmonthly window, show the **Monthly Capacity** line only if a valid numerical 30-day-equivalent estimate exists. If missing/incomplete/stale evidence currently produces `N/A` (or would produce `?`), omit the entire line rather than showing either placeholder. Treat an uncomputable estimate as **unknown**, not an assertion that a monthly equivalent is inherently inapplicable. An actual native monthly window must continue to have only its own period Capacity line, never a redundant derived monthly row.

3. **Replace the visible `(guesstimate)` suffix with a leading approximation sign.** Show `~` directly before an **estimated numeric value** (for both ratio-inferred period Capacity and every calculated monthly equivalent), such as `5-hour Capacity: ~1,000` or `Monthly Capacity: ~$25`. Do not add `~` to a verified provider-native comparable amount, an unknown value or an unlimited state. Retain existing Credits/USD formatting and intentional display rounding; the approximation marker is presentation, not a new calculation.

4. **Rewrite capacity tooltips to be short and scannable.** The value itself remains an intrinsic hover/focus/touch help target. Start with **one plain-English sentence** explaining the relevant estimate:
   - **Period Capacity:** estimated full-window reference CCost from observed same-window CCost and the provider's reported usage fraction.
   - **Monthly Capacity:** an approximate 30-day equivalent of that window's capacity, **not** a guaranteed monthly entitlement.
   
   Separate genuinely different topics with blank lines or compact named lines. Keep only essential provenance/uncertainty and useful provider-native details (quota/window, native Used/Remaining and reset when available), with no repeated paragraphs. **Do not expose the exact raw numbers, arithmetic formula, display-rounding methodology or long defensive disclaimer chain in these capacity tooltips.** This intentionally simplifies earlier exact-calculation help for these two card metrics; it does **not** change underlying unrounded calculation, units, native quota evidence, other CCost estimates, or unrelated diagnostic surfaces.

5. **Normalize the displayed quota/window label's first character only.** If the **label begins with a letter**, make that first character uppercase: `weekly` → `Weekly`; `monthly` → `Monthly`; `Fable Weekly` stays unchanged; a leading digit such as `5-hour` stays unchanged. Preserve every other character and the original provider/API value internally. Apply the display normalization consistently to primary/secondary quota summaries, related help and accessible labels; do not title-case every word, translate labels or change how native period metadata is interpreted.

## Scope and implementation guidance

The current ownership points are `src/application/quota_ccost.py` / `quota_estimates.py` (server-prepared capacity, monthly and help tokens), `src/web/assets/account-cards.js` (shared primary/secondary rows and responsive alignment) and `src/web/assets/render.js::quotaHelp()` (aggregated help). Scope the changes to the account subscription UI and its presentation tokens. Use an explicit known-numeric/unknown distinction rather than deciding availability solely from a truthy formatted string: currently `N/A` is truthy and therefore creates an unwanted monthly row. Make row visibility react correctly when **live data, account membership or unit preferences** change, without a stale placeholder or awkward empty spacer.

Preserve native quota percentages, usage tracks, source warnings, availability semantics, authoritative versus ratio-derived provenance, calculation precision, and common Watch/Accounts behavior. No new provider requests, re-estimation formulas, billing semantics, CLI changes, Mini Watch redesign, or additional release gates.

## Acceptance criteria

- A quota with insufficient same-window CCost evidence shows **no period Capacity row** and **no derived Monthly Capacity row**; its native quota usage and reset remain visible.
- A known nonmonthly quota with a numerical estimate shows period and 30-day equivalent values with `~`, with no `(guesstimate)` text; a verified native period capacity has **no `~`**, while any derived monthly equivalent does.
- A genuinely native monthly quota shows no duplicate Monthly Capacity line. Unlimited and temporarily unavailable states stay honest; no fabricated zero or capacity estimate appears.
- Period and monthly capacity help are short, separated into sensible paragraphs/lines, retain essential native facts, and omit raw arithmetic/rounding essays. Hover, focus, touch and accessible behavior remain functional.
- Initially lowercased quota labels have their **first character only** capitalized in the shared cards and associated help/accessibility; digit-leading labels and internal API identifiers are unchanged.
- Focused server-token and shared-card DOM/browser regressions cover primary and secondary quotas, unknown → known → unknown live updates, Credits/USD, different source bases, and both **Accounts** and **Full Watch**, without requiring real provider calls.
