# FR 000654 — Web subscription and Mini Watch display polish

**Owner-approved Ready Feature Request, 2026-11-09.** Permanent identity **000654**, Ready priority **000890** (after currently Ready FR000653 at 000880). **Backlog-only publication:** add this FR and advance `development/backlog/identity-state.json` highWatermark **653 → 654** in one documentation-only commit. No implementation, product tests, version/release changes or unrelated backlog work in this publication.

## Problem

On **Cost Guard Web → Accounts**, subscription/quota cards currently show **?** for unknown period CCost Capacity, but **N/A** for an unavailable derived Monthly Capacity. This is inconsistent: the latter often means insufficient evidence for an estimate, not that the comparison is conceptually inapplicable. Both non-values clutter small cards.

Numeric inferred capacities append the long visible `(guesstimate)` suffix. The associated hover/focus help is disproportionately long, mixes the capacity explanation with exact unrounded arithmetic, repeated caveats and native details, and has little useful paragraph spacing. Provider-supplied quota/window names also begin with inconsistent capitalization (e.g. `weekly`, `Weekly`, `Fable Weekly`, `5-hour`).

**Full Watch and Accounts share the same subscription-card renderer**, so subscription display changes are one shared behavior. **Mini Watch** has two additional, narrowly scoped owner-requested presentation changes detailed below.

## Desired UI

1. **Hide unknown period Capacity rows.** For each primary or secondary quota, when the reference CCost Capacity cannot be computed/trusted (currently displayed as `?`), omit the **entire period Capacity line**, including its label, placeholder and associated help target. Do not display a blank row, convert unknown to zero, or hide the native usage percentage/bar, quota/window name, reset information or provider warning. A genuinely provider-reported unlimited quota remains truthfully described as unlimited; do not silently invent a finite capacity or conflate that case with missing evidence.

2. **Hide unavailable derived Monthly Capacity rows.** For a nonmonthly window, show the **Monthly Capacity** line only if a valid numerical 30-day-equivalent estimate exists. If missing/incomplete/stale evidence currently produces `N/A` (or would produce `?`), omit the entire line rather than showing either placeholder. Treat an uncomputable estimate as **unknown**, not an assertion that a monthly equivalent is inherently inapplicable. An actual native monthly window must continue to have only its own period Capacity line, never a redundant derived monthly row.

3. **Replace the visible `(guesstimate)` suffix with a leading approximation sign.** Show `~` directly before an **estimated numeric value** (for both ratio-inferred period Capacity and every calculated monthly equivalent), such as `5-hour Capacity: ~1,000` or `Monthly Capacity: ~$25`. Do not add `~` to a verified provider-native comparable amount, an unknown value or an unlimited state. Retain existing Credits/USD formatting and intentional display rounding; the approximation marker is presentation, not a new calculation.

4. **Rewrite capacity tooltips to be short and scannable.** The value itself remains an intrinsic hover/focus/touch help target. Start with **one plain-English sentence** explaining the relevant estimate:
   - **Period Capacity:** estimated full-window reference CCost from observed same-window CCost and the provider's reported usage fraction.
   - **Monthly Capacity:** an approximate 30-day equivalent of that window's capacity, **not** a guaranteed monthly entitlement.
   
   Separate genuinely different topics with blank lines or compact named lines. Keep only essential provenance/uncertainty and useful provider-native details (quota/window, native Used/Remaining and reset when available), with no repeated paragraphs. **Do not expose the exact raw numbers, arithmetic formula, display-rounding methodology or long defensive disclaimer chain in these capacity tooltips.** This intentionally simplifies earlier exact-calculation help for these two card metrics; it does **not** change underlying unrounded calculation, units, native quota evidence, other CCost estimates, or unrelated diagnostic surfaces.

5. **Normalize the displayed quota/window label's first character only.** If the **label begins with a letter**, make that first character uppercase: `weekly` → `Weekly`; `monthly` → `Monthly`; `Fable Weekly` stays unchanged; a leading digit such as `5-hour` stays unchanged. Preserve every other character and the original provider/API value internally. Apply the display normalization consistently to primary/secondary quota summaries, related help and accessible labels; do not title-case every word, translate labels or change how native period metadata is interpreted.

## Mini Watch: split CCost / Total, highlight live Duration in cost help

### Separate CCost and Total into two real columns

On **Mini Watch**, replace the current four-column session table **Activity | Session | CCost (Total) | Ctx** with **five columns: Activity | Session | CCost | Total | Ctx**. Both headers are plain, without parentheses, and have their own short, distinct header tooltips. **CCost** means the represented prompt's reference cost; **Total** means the entire corresponding session's reference cost (including attributed linked subagents). These must be separate table header/data cells, **not** one combined cell with two spans; remove the literal parentheses around the session total's value.

Apply to running, terminal-grace and historical rows, including unavailable, partial, loading and zero amounts. Preserve server-prepared values, updates, cost provenance and the **two already-independent value tooltips**. Do not modify the calculations or representative prompt/session selection.

The owner's expectation is roughly **unchanged or perhaps smaller** overall Mini width, not a request for a wider Picture-in-Picture window. Measure the actual intrinsic widths before/after using realistic values in Credits and USD; optimize spacing if necessary rather than allowing avoidable growth. Preserve fit-on-open, responsive/narrow layouts, scrolling only when needed, sticky headings and session-title truncation. Update accessible table/cell descriptions, empty row column span and tests to reflect five columns. Do **not** add a Δ Ctx column.

### Yellow Duration text in both cost tooltips for a running prompt only

Both **CCost** and **Total** value tooltips currently include the representative prompt's details with a `Duration: <time>` line. Only if that **represented prompt is genuinely running**, color **both the word Duration (including colon) and the current time** yellow, as one line/fragment, in **both** tooltips. Leave every other tooltip line in its normal color.

For completed, aborted, failed, historical, unverified or otherwise non-running prompts, Duration is ordinary text. While a prompt runs, the tooltip's Duration must **continue ticking live** as today; if the prompt completes, changes state, or another representative prompt replaces it, an already-open tooltip must update and remove the yellow cue when no longer applicable. Keep the existing canonical duration value, precision, formatter and text.

**Implementation constraint:** `src/web/assets/help.js::ContextHelp` currently uses **plain `textContent` only**. Add only the smallest needed **safe structured text fragment** support (created DOM text nodes plus a known CSS class/span) for highlighting this specific line. Do **not** render arbitrary tooltip strings as HTML or create a new rich-text engine. Keep untrusted names, previews and provider values as text. Reuse a theme-aware yellow/running color with readable contrast in Classic/Web light and dark themes and Document PiP. Preserve accessibility and copy/selection, focus/touch/hover interaction, tooltip placement, dismissal and refresh lifecycle.

**Existing code:** `src/web/assets/mini.js::View.table()`, `sessionRow()`, `drawCost()`, `rowHelp()`, `promptDetails()` and `drawSessions()`; `src/web/assets/mini.css`; `src/web/assets/help.js`. Update `development/tests/fixtures/mini_sessions.cjs` and relevant real DOM/Document PiP help and layout probes: they currently expect four columns and combined values such as `9 (4583)`.

**Coordination:** Ready FR000653 targets Δ Ctx semantics inside the existing Ctx column and refers to the then-current four-column structure. This later owner-approved scope change splits **only** the two cost scopes. Implement both without restoring the combined cost cell or adding a sixth Δ Ctx column.

## Scope and implementation guidance

The current ownership points are `src/application/quota_ccost.py` / `quota_estimates.py` (server-prepared capacity, monthly and help tokens), `src/web/assets/account-cards.js` (shared primary/secondary rows and responsive alignment) and `src/web/assets/render.js::quotaHelp()` (aggregated help). For the subscription-capacity requirements above, scope changes to the shared account subscription UI and its presentation tokens. Use an explicit known-numeric/unknown distinction rather than deciding availability solely from a truthy formatted string: currently `N/A` is truthy and therefore creates an unwanted monthly row. Make row visibility react correctly when **live data, account membership or unit preferences** change, without a stale placeholder or awkward empty spacer.

Preserve native quota percentages, usage tracks, source warnings, availability semantics, authoritative versus ratio-derived provenance, calculation precision, and common Watch/Accounts behavior. No new provider requests, re-estimation formulas, billing semantics, CLI changes, Mini Watch changes **beyond the two explicitly scoped items above**, or additional release gates.

## Acceptance criteria

- A quota with insufficient same-window CCost evidence shows **no period Capacity row** and **no derived Monthly Capacity row**; its native quota usage and reset remain visible.
- A known nonmonthly quota with a numerical estimate shows period and 30-day equivalent values with `~`, with no `(guesstimate)` text; a verified native period capacity has **no `~`**, while any derived monthly equivalent does.
- A genuinely native monthly quota shows no duplicate Monthly Capacity line. Unlimited and temporarily unavailable states stay honest; no fabricated zero or capacity estimate appears.
- Period and monthly capacity help are short, separated into sensible paragraphs/lines, retain essential native facts, and omit raw arithmetic/rounding essays. Hover, focus, touch and accessible behavior remain functional.
- Initially lowercased quota labels have their **first character only** capitalized in the shared cards and associated help/accessibility; digit-leading labels and internal API identifiers are unchanged.
- Focused server-token and shared-card DOM/browser regressions cover primary and secondary quotas, unknown → known → unknown live updates, Credits/USD, different source bases, and both **Accounts** and **Full Watch**, without requiring real provider calls.
- **Mini shows five columns**, in order Activity, Session, CCost, Total, Ctx, without parentheses around total values; the two cost scopes each have their own header tooltip, value tooltip and accessible labels. Validate running/historical/empty/partial/zero/loading states.
- Only a **running represented prompt** shows yellow `Duration: <time>` in **both** Mini cost tooltips, with the word and time colored together; only this fragment is highlighted. Live ticking, completion, errors, unverified/historical rows, switching representatives and an already-open tooltip remain correct.
- Validate Mini width/fit in both Credits and USD, real Document PiP, narrow/zoom and relevant Classic/Web themes. No unsafe HTML interpretation, accessibility regression or unrelated tooltip-color changes.
