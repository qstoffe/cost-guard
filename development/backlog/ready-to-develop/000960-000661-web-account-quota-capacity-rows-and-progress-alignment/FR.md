# FR 000661 — Web account quota cards: restore Capacity rows and align progress tracks

**Owner-approved Ready Feature Request, 2026-11-09.** Permanent identity **000661**, Ready priority **000960**, following FR000660 (000950); owner-promoted FR000651 (000001) retains the highest Ready priority. **FR-only publication:** add this file and advance `development/backlog/identity-state.json` highWatermark **660 → 661** in one documentation-only commit on `main`. No product code, tests, version or release changes in this publication.

## User problem and desired outcome

The recent implementation of **FR000654 (v81.3)** removed entire **Capacity** and **Monthly Capacity** display rows when the reference CCost capacity was unknown. This was intended to declutter **Cost Guard Web → Accounts** but has an unacceptable visual regression: **primary quota progress bars no longer align horizontally between subscription cards**; the same alignment contract must extend to secondary, tertiary and subsequent real quota tracks. The owner expressly **reverses only FR000654's conditional removal of unknown-capacity rows**, not its other completed improvements.

Restore the earlier predictable quota layout:

- **Always display the primary quota's own period Capacity row**, whether its reference amount is known or not.
- **When the primary window is not a known native monthly window, also always display one separate Monthly Capacity row**. This is the same standardized **30-day theoretical equivalent** already calculated by the existing application logic; do not equate it with provider-native monthly entitlement. For a genuine monthly primary, show only its own `Monthly Capacity`, never the duplicate derived line.
- Apply the **same fixed visible Capacity-row rule to every actual secondary, tertiary or later quota** in its existing source-defined order: its own period Capacity is always present; if that window is not monthly, its one additional Monthly Capacity row is present, even when no numerical monthly estimate is available.
- For **an unknown/unavailable reference Capacity or Monthly Capacity**, render a simple **`?`**, not `N/A`, `—`, an empty string, a fabricated zero or a removed element. Do not attach the `~` approximation marker to a question mark. Retain native, independently proved `Unlimited` meaning if present rather than inventing a finite capacity; `?` refers to an unknown **reference CCost** estimate, not to a native quota's existence.
- **Primary progress bars line up across cards** in the same responsive grid row; second quota progress bars line up with second, third with third, etc. Keep thin, consistent **section dividers** between quota levels. An absent secondary/tertiary quota must **not** be presented as a fake actual quota/progress bar; it may need a hidden, nonsemantic layout spacer so later genuine tracks still occupy the correct ordinal slot.

This applies to the **one shared full-size subscription renderer used by Accounts and Full Watch**, and should behave identically on those routes. **Mini Watch** deliberately uses a different compact one-line quota presentation and is **out of scope**.

## A. Restore stable capacity rows (precise semantics)

**Display rules for each real source-provided quota, irrespective of whether reference pricing is currently known:**

| Source window | Own period Capacity row | Additional Monthly Capacity row |
| --- | --- | --- |
| Genuine monthly primary/secondary/etc. | Always: **Monthly Capacity: X** or **Monthly Capacity: ?** | **Never** duplicate |
| Verified 5-hour window | Always: **5-hour Capacity: X** or **?** | Always: **Monthly Capacity: ~Y** or **?** |
| Verified weekly window | Always: **Weekly Capacity: X** or **?** | Always: **Monthly Capacity: ~Y** or **?** |
| Other nonmonthly / unknown period | Always: honest source-bound Capacity label with **X** or **?** | Always: **Monthly Capacity: ~Y** only with valid evidence, otherwise **?** |

Use the existing source-backed `monthly_applicable` and period semantics; do not infer monthly eligibility by a label string. The `X/Y` placeholders in this specification are illustrative, not source values.

- **Unknown isn't inapplicable.** Convert the current `monthly_capacity = 'N/A'` or absent presentation for an unprovable nonmonthly extrapolation to **`?` on these shared Web cards only**. Keep the existing short, relevant hover/focus/touch reason for missing reference pricing or insufficient recurrence/window evidence. Uncertain native data must remain honest and not be normalized to a false numeric estimate.
- **Keep FR000654's good changes**: estimated *numeric* capacities have leading **`~`**, native comparable verified capacities remain plain, capacity tooltips stay concise and useful, and source quota labels only capitalize the first alphabetic character. Keep Credits/USD display and proper `~$...` formatting.
- Preserve all underlying `src/application/quota_ccost.py` Decimal calculations, native provider quota fractions, actual percentages/Used/Remaining values, `ccost_reference` confidence and price completeness. Changing the presentation of unknown values does not make a missing number known, or make monthly estimates actual allowances.
- Ensure both known-to-unknown and unknown-to-known live updates **change the text within the same permanent layout slot** rather than adding/removing the slot and pushing progress bars and peers vertically.

## B. Progress bar alignment across all quota levels

**Non-negotiable visual invariant:** in each **visible responsive comparison row of account cards**, the `n`th real quota's progress track should begin at the same vertical coordinate across all cards that have an `n`th quota, even when different providers have monthly vs 5-hour vs weekly windows, missing reference CCost, different reset times or additional explanatory details.

1. **Primary (level 1):** retain consistent layout slots for card heading, Today, primary quota summary, primary Capacity, optional *additional* Monthly Capacity and primary progress track. Since source-mandated visible capacity lines can differ (native monthly vs nonmonthly), use **one empty visual spacer in the monthly card when compared next to a nonmonthly primary** in the same grid row. The spacer is aria-hidden, unfocusable, non-tooltipable and has no fictitious text. It must not appear when every peer has only one Capacity row, and shouldn't add needless space when a card stands alone.
2. **Secondary / tertiary / later (levels 2, 3, …):** share a stable ordinal track/slot template **across peers in the same comparison row**, including room for each quota's real Capacity and conditional Monthly Capacity and a consistent bar position. Preserve a divider before each *real* next quota (including secondary). Where cards have different numbers of quotas, use **presentation-only spacers for missing quota levels**, if needed to keep subsequent real levels aligned; never show phantom quota labels, phantom percentages, phantom bars, false Monthly Capacity or accessibility nodes. A card with no further quota should not become an artificially populated unlimited account.
3. **Dividers:** retain/add consistent thin separators between levels (primary vs secondary and secondary vs tertiary, etc.) in matching visual positions; no stray divider with no quota on a lone card. Existing `.watch-account-details` top border and `.watch-secondary-quota` spacing can be reused or adapted to a proper shared per-level grid.
4. **Responsive rows:** alignment applies to **peer cards on the same physical CSS grid row**, not to cards on unrelated wrapped rows. Recalculate when card membership, order, provider period, known/missing capacity state, number of quotas, viewport width, browser zoom or grid columns change. Cards in a single-column layout must be compact, without large phantom blank areas or unnecessary spacers. Long titles, warnings, reset info and optional pace text may need flexible slots, but must not drag one peer's bar out of alignment.
5. **Stable DOM and state:** avoid rebuilding unchanged progress nodes, destroying open help/selection/focus or visual jumps on ordinary status/CCost updates. Keep progress `aria-valuenow/valuetext`, correct disabled/unavailable states, exhaustion colors and all bounds. Never solve alignment by absolute coordinates, fixed heights derived from estimated text, padding hacks or hardcoding a maximum number of quotas.

### Representative visual layout (illustrative amounts)

```text
Card A — monthly primary          Card B — 5-hour primary
CCost Today: 100                  CCost Today: 120
Monthly · 42% used                5-hour · 70% used
Monthly Capacity: ?               5-hour Capacity: ~800
[empty monthly comparison slot]   Monthly Capacity: ?
████████░░░░ primary bar          ████████████ primary bar   ← same Y coordinate
───────────────────              ───────────────────
Weekly · 20% used                 Monthly · 40% used
Weekly Capacity: ?                Monthly Capacity: ~2,000
Monthly Capacity: ?               [empty monthly comparison slot]
████░░░░░░░░ secondary bar        ███████░░░░░ secondary bar ← same Y coordinate
───────────────────              ───────────────────
Optional third quota…             Optional third quota…
```

**Question marks are visible actual unknown reference-display values.** Empty slots are internal alignment scaffolding only and cannot be read as missing/unknown numerical values.

## C. Verified implementation context and regression cause

The most directly relevant files are:

- `src/web/assets/account-cards.js::quotaTrack()`: builds `.watch-quota-capacity` and `.watch-monthly-capacity` but currently **conditionally inserts/removes them** using `current() && ReportView.capacityKnown(...)`. It also returns these rows only when known, causing a dynamic DOM/height shift. Restore reliable visible rows for each actual quota while retaining genuinely current/unknown annotations in help.
- `src/web/assets/account-cards.js::Subscription.align()` and `AccountCards.View.align()`: currently choose optional `.watch-capacity-spacer` and number of `--watch-card-rows` based on **known value presence** within same-grid-row peers. This is the wrong structural proxy for *how many semantic lines should be displayed* under the revised owner requirement. Align by **period/slot semantics and actual quota ordinal count**, not whether a numerical capacity happens to be computable.
- `src/web/assets/app.css`: `.watch-subscription` uses CSS subgrid `grid-template-rows: subgrid` with `--watch-card-rows`, while later quota groups live under `.watch-account-footer/.watch-account-details/.watch-secondary-quota`. Audit and adjust secondary-level layout so progress tracks genuinely line up across cards in each wrapped grid row, without making Mini or unrelated Watch tables inherit new margins.
- `src/web/assets/render.js::ReportView.capacityKnown()` currently treats `ccost_reference.capacity/monthly_capacity != null` as existence of a **display row**, while the correct rule here is: actual quota exists → own Capacity row, not native monthly → extra Monthly row; numeric knownness only controls the **text inside** the row.
- `src/application/quota_ccost.py::monthly_tokens()` currently prepares **`N/A`** for unavailable but relevant Monthly Capacity; presentation formatting on the shared Web cards should show **`?`** instead without altering calculations or unrelated CLI/native API contracts.
- **Historical visual baseline:** completed `development/backlog/complete/000131-000620-watch-tooltip-clarity-subagent-prompts-monthly-capacity-daily-summary/FR.md` created visible period/derived monthly lines and responsive primary monthly peers' empty spacer. **Later FR000654** specifically removed the lines for unknown amounts; **reverse only that suppression**, while extending alignment safely across actual secondary/tertiary quota levels. Do not blindly revert the whole FR000654 or its Mini split CCost/Total changes.

## D. Acceptance and quality gates

1. With synthetic **unknown primary and unknown monthly** data, all actual quota levels retain their Capacity rows, including Monthly Capacity for every nonmonthly quota. No `N/A`, `—`, blank value or dropped element appears **in those two numeric display fields**; instead exactly `?`. Verified numeric display and `~` remain correct. Unknown/unlimited native values are not fabricated.
2. With monthly vs 5-hour vs weekly primary windows alongside unknown/known CCost peers, measure the **actual progress element bounding rectangles** after layout settles: primary bars align vertically in the same responsive row within a small pixel tolerance across Classic and Web light/dark.
3. With 0/1/2/3+ **genuine secondary/tertiary quotas** per account and mixed monthly/nonmonthly/unknown capacities, **second bars align with second, third with third** wherever such quotas actually exist in the same grid row. Thin dividers occupy consistent inter-level slots, no extra visible phantom quota/bar is added, and a lone card remains compact.
4. Change source capacities from unknown→known→unknown, quota period monthly↔nonmonthly, account order/add/remove and viewport width: rows remain structurally stable where semantically applicable, correct spacers re-evaluate, and all peer bars stay aligned; no stale aria help, flicker, focus loss or accidental duplicate dividers.
5. **Route parity:** Full Watch and Accounts render the **same shared component**, same ordered real quota labels, capacity help, question marks, divider/bar positions, and correct Credits↔USD / Used↔Remaining state across live SSE updates. Mini Watch's one-line subscriptions, existing two-scope CCost tooltip work and unrelated account reports are unchanged.
6. **Browser proof required** beyond unit/DOM tests: 360/800/1280/1920 CSS px, at least 100% and 125–150% zoom, light/dark/Classic, a multi-card row and a wrapped single-card row. Test actual bar Y-positions and source/current/missing/unlimited states, not only text/element counts or a screenshot that conceals differing tracks.
7. Update existing `development/tests/fixtures/account_capacity.cjs`, `development/tests/integration/probe_subscription_capacity.cjs`, `probe_accounts_live.cjs` and relevant shared Watch/Accounts probes. Their FR000654-era assertions that unknown capacity **must disappear** are now superseded; reverse them explicitly rather than weakening/skipping tests. Preserve genuinely valid FR000654 tests for the `~` prefix, concise help, capitalization and Mini formatting.
8. Record a before/after screenshot and DOM coordinates for known/unknown primary+secondary mixed cases, document the bounded change in the Web quota/layout journal and guide; do not alter pricing math, native source acquisition, user credentials, session history, refresh cadence, backend semantics or unrelated Models/Watch tables.

**End state:** Each subscription card has predictable semantic Capacity slots with **`?` for unknown reference values**, and all real primary/secondary/tertiary quota progress tracks form clean, aligned horizontal rows across peer cards.
