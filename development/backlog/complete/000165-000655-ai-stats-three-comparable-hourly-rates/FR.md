# FR 000655 — AI Stats: three comparable hourly rates with concise playful formula help

**Owner-approved Ready Feature Request, 2026-11-09.** Permanent identity **000655**, Ready priority **000900**, following the currently Ready FR000654 (000890). **FR-only publication:** add this request and advance `development/backlog/identity-state.json` highWatermark **654 → 655** in one documentation-only commit. No product, test, version or release changes in this publication.

## Problem and desired result

On **Cost Guard Web → AI Stats → 💸 AI Hourly Rate**, the card currently mixes two hourly rates (**24h average**, **Workday average**) with a hypothetical **Robot · 8h shift** cost expressed *per eight-hour day*. That last figure is not comparable at a glance to the others. The user's actual intent is to compare the cost intensity of **continuous active AI work per hour** with a familiar human hourly-cost concept, not to price an artificial eight-hour shift.

The underlying active-hour rate **already exists** as `HourlyRates.active_rate` in `src/analysis/ai_stats_rates.py`. It equals selected-period Total AI Cost divided by selected-period AI Working Time. The latter is the **union of overlapping AI execution intervals**, so parallel AI agents may increase cost without double-counting the same clock hour. Preserve this intentional meaning and the established fun-first, best-effort evidence policy.

## Visible card

Keep the existing **AI Hourly Rate** title, emoji, card position, fun trait line and compact three-row layout. Change only the row labels and the third displayed number:

| Row label (exact) | Value | Definition |
| --- | --- | --- |
| **Calendar average** | `CCost/h` | Existing `calendar_rate` = period total cost ÷ (calendar-day count × 24). Rename **24h average**; do not recalculate it. |
| **Workday average** | `CCost/h` | Existing `workday_rate` = **all period cost** ÷ (eligible workday count × 8). Retain the current rate and its meaning, including costs incurred outside workdays. |
| **Active AI average** | `CCost/h` | Display the **existing raw active-hour rate** `active_rate` = period total cost ÷ unioned AI Working Time in hours. Replace **Robot · 8h shift** and its `robot_day`/8h-day display; **do not multiply by eight**. |

Every numerical row uses the same selected Credits/USD preference and the existing **per-hour** units/formatters; the third row must never say `/8h day` or imply a day/shift total. Do not change calendar period windows, the workday calendar, source cost, or time analysis. A fully active parallel hour counts as one elapsed active hour, not the sum of individual agents' durations.

**Illustrative example:** seven selected days, five eligible workdays, 840 Credits total and 28 active AI hours yield **5 Credits/h**, **21 Credits/h**, **30 Credits/h**, respectively (rather than the old **240 Credits/8h day**). Another example: 100 Credits over two active AI hours gives **50 Credits/h**; over one minute it gives **6,000 Credits/h**, regardless of how many calendar days are selected. The third metric expresses **AI cost intensity during activity**, not measured human salary, billed charges, or a guaranteed prediction of an all-day robot.

## Tooltip: fun first, compact formula last

Keep **one shared tooltip on the AI Hourly Rate title** containing **exactly three short, readable paragraphs**, in card-row order. Each begins with its matching displayed row label, contains **one playful, plain-English sentence** explaining its perspective (retain Cost Guard's lighthearted robot/workplace tone), and **ends with one small parenthesized formula**. No separate mathematical preamble, fourth paragraph, detailed examples or raw data ledger.

Suggested concise structure and tone (wording may be polished without losing clarity/humor):

- **Calendar average:** “The robot keeps a budget even while you sleep. *(Total CCost ÷ (calendar days × 24))*”
- **Workday average:** “The same robot bill, squeezed into ordinary office hours. *(Total CCost ÷ (workdays × 8))*”
- **Active AI average:** “The silicon's hourly appetite when it's actually working. *(Total CCost ÷ active AI hours)*”

These are **tiny explanatory formulas at the end**, not a calculation walkthrough. Preserve a blank line between paragraphs. Do **not** clutter the tooltip with weekend/holiday caveats, DST/partial-day rules, overlapping-interval details, precision or missing-source diagnostics; those belong in documentation or tests. Do not misleadingly call the last value an eight-hour cost. Adapt existing conditional playful copy/neutral idle wording to the new active-hour concept without asserting an actual salary comparison, replacement decision or billing equivalent.

## Implementation boundaries

- `src/analysis/ai_stats_rates.py::hourly_rates()` already computes `active_rate`. Reuse that raw basis; do not derive it by dividing displayed strings or taking `robot_day / 8` after rounding. Leave unrelated calculations and other consumers intact.
- Update `src/application/ai_stats.py::rate_tokens()` / existing prepared display fields and `src/web/assets/ai-stats.js::rateRows` / idle help to present the three per-hour figures and short matching help. Retain the overall `hourly-rate` metric identity; avoid unnecessary DTO/API churn and keep raw compatibility fields if relied upon elsewhere.
- Preserve exact raw Decimal math before standard output formatting, five period selections, Credits↔USD changes, the other nine cards, retained/live result updates, keyboard/focus/hover/touch help and current theme/layout behavior. The AI Stats-only best-effort source and zero/unknown-duration fallback remain safe (never divide by zero, produce Infinity or invent a measured hourly rate).
- Keep tooltip text supplied through the existing safe plain-text ContextHelp system. No new tooltip framework, billing provider call, data scan, salary settings, release gate or unrelated refactor.
- Update narrowly relevant tests, Web guide and architectural references so obsolete **Robot 8h shift** user-facing labels, help, three-way rate examples and assertions do not survive.

## Acceptance

1. The card visibly reads **Calendar average**, **Workday average**, **Active AI average** in that order, with hourly units for every numerical value. No eight-hour-shift label or `/8h day` appears on this card.
2. The 840 Credits / 7 dates / 5 workdays / 28 active hours fixture displays **5, 21, 30 Credits/h** (USD equivalent: **$0.05/h, $0.21/h, $0.30/h**). Changing only active time changes only the third rate; changing workday count changes only the second rate.
3. Parallel/overlapping execution intervals retain their current union semantics; no duplicated wall-clock hours, cost-source change or loss of the fun-page duration/cost fallback.
4. Tooltip displays three short, humorous paragraphs with one **trailing parenthesized formula each**; wording matches the visible labels, explains the active-hour comparison without shift/day confusion, and contains no technical edge-case essay.
5. Running/idle, zero active hours, no eligible workdays, all five date scopes, Credits/USD, narrow/theme layouts, retained result updates and accessible/open-tooltip refresh behave coherently. Other nine cards remain unchanged.
