# FR 000608 — Mini Watch: clean Session and CCost (Total) columns in both tables

**Owner-approved Ready Feature Request, revised 2026-11-06.** Permanent identity **000608**; Ready priority **000260**, following FR000607 (000250). This **replaces the earlier wording of FR000608 in place**, which had requested a standalone latest-prompt CCost column in Earlier Sessions while leaving the running table alone. That earlier layout is **superseded**, not an additional step to implement. This amendment is **backlog authoring only**, not product implementation.

## Owner request and exact visible layouts

The existing Mini Watch combines the session name and the *whole-session total* inside one `Session (Total CCost)` column, even though the running/recent table also has a separate prompt `CCost` column. The separate `#` prompt-number column in running/recent prompts has proven unnecessary in the compact window.

**Move the whole-session total out of Session into the same cost cell as the relevant prompt's cost.** Both Mini tables must use the **exact column header `CCost (Total)`** (including capitalization, one space and parentheses), and every populated cost cell must read:

```text
<prompt CCost> (<full-session CCost>)
```

That is **prompt first**, then one space, then the **entire session's** CCost in parentheses. Use ordinary existing Cost Guard unit formatting in both positions; values below are illustrative.

**Running / recently ended prompts — exactly four columns:**

```text
Session           | CCost (Total) | Duration | Ctx
Refactoring work  | 18 (562)      | 47s      | 86K
Debugging issue   | 173 (1 204)   | 2m 13s   | 91K
```

- Remove the separate `#` prompt-ordinal column entirely from the **visible table**. Retain the canonical ordinal in underlying data, accessible row identity and concise contextual help (see below). Do not remove its meaning from the application or the full Watch.
- The prompt component is the specific **running or recently terminated focal prompt** represented by that row, including the existing lifecycle/terminal grace. The parenthesized component is the **full root/session tree total**, not the cost of that row or the sum of visible prompts.
- **Session shows only the session title** (or canonical ID fallback), not the total CCost or a parenthesized amount. Retain the full title for accessibility and ellipsize just the title as needed.
- Retain **Duration** and **Ctx** with their current running/recent-prompt semantics. No other columns added.

**Earlier Sessions (expanded) — exactly four columns:**

```text
Activity | Session           | CCost (Total) | Ctx
08:05    | Refactoring work  | 49 (562)      | 85K
22:41    | Debugging issue   | 173 (1 204)   | 91K
```

- This replaces FR000608's original layout `Activity | Session (Total CCost) | CCost | Ctx` with **`Activity | Session | CCost (Total) | Ctx`**.
- The first cost component is the **latest actual canonical prompt** of that earlier session (the existing historical representative), **not** the entire session. The parenthesized component is the same authoritative **full-session total** already shown in Mini.
- **Session contains the name only**; its former nonshrinking whole-session total moves to the CCost cell. Preserve the previously delivered **Activity** local-finish clock and its date/time tooltip, and keep the existing historical **Ctx** scope. No prompt ordinal, Duration, Model, Effort or Calls becomes a visible historical column.

**The two tables are deliberately consistent:** `Session` is always just a session name; `CCost (Total)` always means **that row's prompt cost, followed by the whole-session cost**. Do not add another Total CCost column, split the pair into two columns, show a slash instead of parentheses or rename the heading `Session (Total CCost)`.

## Focused contextual help

1. **Both `CCost (Total)` headings** explain the two cost scopes in compact, plain English: *first is this prompt's reference CCost* (the latest prompt in Earlier Sessions); *the parenthesized value is the entire session's reference CCost*, not provider billing. The existing `N/A` (unavailable) and `?` (partially priced) conventions remain honest.
2. **Earlier Sessions: the `CCost (Total)` value is the prompt-detail hover/focus/touch target.** Preserve FR000608's original useful detail, anchored to **that specific latest historical prompt**, with a concise scannable set of available facts: canonical **Prompt #**, actual main/provider-qualified **Model**, supported **Effort**, canonical finished **Duration**, and **Calls** when known. Where genuinely relevant, note linked subagents, multiple contributing models, partial attribution/price or failed/aborted work. Do not present the main model as the only contributor to a composite cost. Don't add raw prompt text, noisy repeated definitions, or extra permanent columns. An unknown field must not be guessed or silently borrowed from a later/different prompt.
3. **Running/recent: the removed prompt number stays discoverable from the Session name** (hover, keyboard focus or touch), e.g. `Prompt #7 in this session`, using shared `ContextHelp`; retain the complete session title when it is visually truncated, without a second row-wide tooltip, dedicated help icon or duplicate native browser `title`. This targeted prompt-number help is the exception to the existing preference against unnecessary Mini row popups. Preserve outcome/abort/source-state accessibility in the row's accessible label. The cost heading itself handles the two cost scopes; no duplicate long cost help is required on each active row.
4. Existing Activity and Ctx contextual help and shared hover delay/focus/touch behavior remain intact. A Live update must keep visible values and their help coherent without detaching focused nodes or reopening dismissed popups.

## Data, layout, and compatibility constraints

- Reuse the **existing source-neutral Live projection and canonical pricing**, not browser-side subtraction or aggregation. The running prompt already exposes its own `ccost`; Earlier Sessions has one representative row with prompt-local `ccost`, model, effort, `watch_duration_ms`, `prompt_number` and `calls`. Full-session cost is `card.session_summary.cost`, already shared across both tables. Reuse current shared display and `ContextHelp` facilities, including Credits/USD selection.
- Preserve true zero, unpriced/partial prompt costs, still-loading/partial/retained/unavailable whole-session totals and live corrections **independently for each component**. Examples such as `N/A (562)`, `49 (Loading…)` or `?49 (?562)` are conceptual rather than new required formats; use established application formatting. Never substitute one amount for the other or imply a complete, fully priced total when evidence is partial.
- Preserve historical **newest up to three distinct eligible finished sessions**, oldest-to-newest order, their representative latest prompts, running/history deduplication, `~30s` terminal grace, resumption transitions, historical Activity finish semantics and full-date tooltip, separate historical next-Ctx semantics, and the **shared Mini prompt/session scrolling region**. Historical Activity is not an indicator of when the UI last polled or refreshed.
- Update `src/web/assets/mini.js` and `mini.css` table headings, cell creation/indices, CSS selectors, source notes, empty/loading/unavailable `colSpan`, ARIA labels, accessible values and width/height measurement placeholders. The **running table changes from five columns to four**; historical goes **from three existing columns to four** but uses the revised pair-in-one-cell layout. Ensure no old assumption that Session is index 0 in both tables, historical Session is index 1, or `#` occupies index 1 leaks through the update.
- **Keep `CCost (Total)` and both amounts on one line**, with compact tabular numerals and right alignment, and make the session title the flexible/ellipsizing part. Neither the parenthesized whole-session cost nor the prompt cost should truncate just to give the title more room. At truly narrow manually sized/zoomed PiP widths, use the existing accessible horizontal overflow within the combined prompt/session region instead of hiding values, forcing costs to wrap or adding another vertical scrollbar. No hardcoded pixel width.
- **FR000607 compatibility:** the default `Fit on open` width is determined by the **three top header elements** staying on one line, not by how wide these tables would prefer to be. Do **not** widen the initial collapsed PiP solely to accommodate `CCost (Total)`. Preserve user-controlled width, the click-driven Earlier Sessions height fit/collapse behavior, two-running-row initial height reserve and no background/SSE-triggered native resize.
- This FR concerns **Mini Watch only**. Do not change full Web Watch, CLI, accounting, source acquisition, history membership, storage/schema, providers, subscriptions, Settings choices, release policy, or product-wide tooltip conventions.

## Acceptance and implementation verification

1. Both tables show **`Session` (name alone)** and **`CCost (Total)`**; running/recent has exactly **`Session | CCost (Total) | Duration | Ctx`** without `#`, and expanded Earlier has exactly **`Activity | Session | CCost (Total) | Ctx`**. Verify visible `49 (562)`-style values in both, not a total still attached to Session.
2. Use multi-prompt sessions to prove that the prompt part and whole-session part are **distinct scopes**; ensure active/recent rows display the correct focal prompt and Earlier displays the latest actual canonical prompt. Include concurrent running rows sharing the same session total, mixed/subagent work and corrections.
3. Running Session focus/hover/touch exposes the correct canonical `Prompt #` despite its removed column. Earlier cost-cell focus/hover/touch exposes correct model, effort, duration and known prompt number/calls; unknown/mixed/partial data remains truthful. No raw prompt text or browser-native duplicate popups.
4. Verify Credits/USD and price/valuation changes, zero, `N/A`, partial `?`, one cost available while the other is pending, retained/unavailable source states, accessible labels, Live keyed updates, and keyboard/touch focus.
5. Test empty/loading/unavailable table rows, three Earlier sessions, Activity dates/DST, Ctx, running→history→running movement, compact and manually narrow PiP widths, themes, zoom/scaling and Earlier toggle sizing. If a physical Windows host is unavailable, distinguish browser/headless tests from physical-native verification.
6. Update `docs/web-mini-watch.md` and focused Mini tests/fixtures/browser probes, including `development/tests/test_mini_watch.py` and appropriate `development/tests/integration/mini_*.cjs`. Run checks only **when implementing**, not while editing this FR.

**Publication boundary for this amendment:** update the existing Ready `FR.md` at priority **000260**, retaining identity **000608** and `development/backlog/identity-state.json` highWatermark **608**. No additional FR, new identity, implementation, tests, release/version bump or change to unrelated backlog entries is authorized here.
