# FR 000647 — Web Watch: plain prompt CCost column, with Incoming/Extra CCost in cell tooltip

**Owner-approved Ready Feature Request, 2026-11-09.** Permanent identity **000647**; Ready priority **000820**, following pending FR000645 (000800) and FR000646 (000810). This is **backlog-only authoring**: add this FR and advance the backlog identity highWatermark **646 → 647**. Do not implement product source, tests, documentation, version/release or any unrelated FR in this transaction.

## Problem and desired result

On **Cost Guard Web → Watch**, both **Running Prompts** and **Earlier Prompts** currently show a wide, redundant **CCost (I + E)** prompt-cost column. A typical Credits cell reads **1 250 (900 + 350)**: the actual total followed by the split between Incoming Context CCost and Extra CCost. The owner wants a **compact table with only the total visible** and the breakdown accessible **when hovering, keyboard-focusing or tapping the exact CCost value**.

**Required visible presentation, identically in both full Watch prompt tables:**

| UI | Before | After |
| --- | --- | --- |
| Column header | CCost (I + E) | **CCost** |
| Credits prompt cell | 1 250 (900 + 350) | **1 250** |
| USD prompt cell | $12.50 ($9.00 + $3.50) | **$12.50** |
| Known zero | 0 (0 + 0) | **0** |
| USD displayed zero | $0.00 ($0.00 + $0.00) | **$0.00** |

In the **existing value tooltip**, add short explicit **Incoming Context CCost (I)** and **Extra CCost (E)** lines before the already existing rich Main prompt/Subagents cost detail. For example, a cost cell reading **1 250** would provide:

    Prompt CCost: 1 250
    Incoming Context CCost (I): 900
    Extra CCost (E): 350

    Main prompt — [canonical model/effort]
    • Input: ...
    • Cached input: ...
    • Cache write: ...
    • Output: ...
    Subtotal: ...

    Subagents — [existing model/effort groups, when supported]
    ...
    Total CCost: 1 250

The exact total label may be consolidated to avoid a duplicate total in the same tooltip. **The I and E amounts must remain two clearly labeled independent facts.** The full existing category/subagent tooltip must NOT be replaced with only these two values. The abbreviated on-demand split and rich grouped detail explain different aspects of the same prompt.

## Repository investigation: why the change does not already exist

The current Ready queue has FR000645 and FR000646; On Hold contains no FR. The related earlier requests are complete but asked for something different:

- **Completed FR000575** (complete/000087-000575-web-watch-prompt-ccost-incoming-extra) **deliberately introduced** the visible **CCost (I + E)** header and **total (I + E)** cell value in both Running and Earlier. Completion confirms delivery in v80.155. **This new owner decision supersedes only that visible presentation**, not its source-backed incoming/extra components.
- **Completed FR000590** (complete/000102-000590-web-value-hover-tooltips-ccost-breakdown) added the **rich hover/focus tooltip** on the CCost value with main/linked-subagent, model/effort, Input/Cached input/Cache write/Output cost groups, subtotals and totals. It explicitly retained the existing visible heading and I/E display; its completion did not make the requested compact switch.
- **Completed FR000601** and **FR000620** further improved grouping, counts and tooltip copy. **Preserve** that work, including genuine distinct linked subagent prompt counts, scoped costs, grouped models/efforts, unavailable evidence and relevant subtotal/total values. Do not re-add removed price-tier prose.
- **Completed FR000586** imposed a special *visible* **0 (0 + 0)** presentation whenever the displayed total rounds to zero, including a tiny nonzero amount rounding to USD $0.00. This FR **explicitly supersedes the visual zero-component rule**, since the cell must now contain only the total. The tooltip can show actual component zero values **only when the separate source facts support them**; do not invent them because the formatted total looks zero.

This is therefore a **new, unmet simplification**, not a reimplementation or duplicate of the existing cost analysis/tooltips. Keep historical FRs and their completion reports intact.

## Verified code and minimal implementation path

1. **src/web/assets/watch.js** owns the shared **columns** definition for active and historical prompt tables. Its sixth entry currently says **CCost (I + E)**, with heading help describing I/E. Change the *visible heading* to exactly **CCost** and trim/adapt the heading tooltip to succinctly explain prompt reference cost and that the **value tooltip** contains further details. Both table types must change together.
2. **watch.js::promptCost(prompt)** currently concatenates **display(prompt, 'ccost')**, **display(prompt, 'incoming_context_ccost')** and **display(prompt, 'extra_ccost')**, with an additional displayed-zero override. Use **only the existing display(prompt, 'ccost') token for visible table text**. The canonical total, pricing, partial marker, N/A, currency switch, zero and intentionally blank sparse-compaction semantics stay unchanged; only the string assembled for the cell changes.
3. **watch.js::Card.update()** already calls **metricValue(row, 5, value, help)** with **ReportView.costHelp(prompt)** and **display(prompt, 'cost_detail_help')**. Extend that **same existing value help**, adding **Incoming Context CCost (I)** and **Extra CCost (E)** near its top. Preserve the current detailed cost-group help; no second tooltip/button, no row-wide hover and no replacement of the rich breakdown with a generic definition.
4. **src/application/live_projection.py::card_row()** already exposes the current prompt's raw **ccost**, **incoming_context_ccost**, **extra_ccost**, and independently verified **incoming_context_ccost_known** / **extra_ccost_known** fields to both tables.
5. **src/application/display.py::amount_tokens()** already formats all three fields into **Credits/USD** and treats unsupported individual I/E evidence as **N/A**, independently of the total. Reuse its prepared display tokens, not a JS recomputation like **E = total − I**.
6. **src/application/prompt_costs.py::detail_tokens()** supplies the rich grouped tooltip independently. **I/E is a split of first attributed request's incoming-context reference CCost versus the prompt's other canonical usage** (output, later physical requests and linked subagents). This is **NOT** the same as the grouped **Input/Cached input/Cache write/Output category costs**; the tooltip should make that distinction easy to grasp.
7. Existing **ContextHelp.value** handles exact value targets, hover delay, keyboard, touch, Escape and dynamic refresh. No source reads, data-model migration, new API, pricing logic, backend inference, custom tooltip timer or general CSS framework change is needed.

## Requirements and boundary conditions

### Visible CCost only

1. **Both Running and Earlier** full-Watch tables have **exactly the heading CCost** and **only the canonical prompt CCost token in each row**. No parenthesized split, plus sign or other I/E arithmetic after the number. The visible column stays in its current sixth position, not split into multiple columns.
2. Keep the **other nine headers, ten-column layout, session-card boundaries, prompt numbering and Preview ellipsis, status colors, width behavior and horizontal panning** unchanged. Removing the bulky split should release width for the flexible Prompt column rather than retaining an artificial minimum based on obsolete contents.
3. Correctly display known zero, small positive values rendered as less-than/minimum formats, USD $0.00, N/A, partial **?**, unknown and sparse compaction. **Do not invent zero** for a truly missing total, or erase the total's existing partial indicator. Both Credits and USD have ordinary Web formatting and no extra parenthetical strings.
4. **Out of scope:** Mini Watch's separate **CCost (Total)** prompt/session pair, whole-session **Total CCost** footer, CCost Today, quota/account cards, ordinary Sessions/Session Detail, Token Mix, CLI and any billing or historical numerical definition.

### The existing value tooltip carries I and E

5. On each **real prompt cost value**, add readable lines such as **Incoming Context CCost (I): X** and **Extra CCost (E): Y**, using the **same canonical prompt and same selected display unit**. A concise **Prompt CCost** line may orient the user. The header tooltip can be shorter now: explain that CCost is reference valuation rather than a provider bill, and that the **cell value** reveals the split and model/subagent details.
6. **Keep every useful part of the already delivered rich tooltip**: actual Main prompt and grouped Subagents, model identity, effort, genuinely supported subagent prompt count, Input/Cached input/Cache write/Output **reference cost** contributions, per-group subtotal, grand total, known unavailable/omitted information and meaningful pricing notes. Do not substitute I/E for the existing category lines, silently drop a partially known group, duplicate another help icon, or add a Token Mix percentage tooltip.
7. I and E are **independently source-verified**. An unavailable component reads **N/A** (or existing honest unknown), never forced zero, and a partially priced total keeps its existing reason/marker. **A displayed 0 or $0.00 does not prove I=E=0**; this includes small positive USD costs rounded to zero. Raw supported I + E reconciles with the raw total; independently rounded display values need not visibly sum exactly.
8. For **complete unavailable total**, the value tooltip still exposes useful actual cost-reason help when available; do not remove its focusable help solely because the numeric token is N/A. If genuinely unsupported, avoid pretending the missing detail is complete. No extra source model calls.
9. **Live updates** to running prompt metrics, later source corrections, the transition to Earlier, retained data, and Web Credits↔USD display changes must refresh the *same exact row's* visible total and its paired I/E and grouped help together. No stale numeric breakdown from another prompt/account/model, no tooltip desynchronization, and no additional polling or fetch.

## Acceptance and regressions

1. **Known values:** total 1250, I=900, E=350 in Credits → heading **CCost**, value **1250**; focused/hovered value help contains I **900** and E **350** with precise explanations. USD → value **$12.50**, help I **$9.00**, E **$3.50**. Check in **both Running Prompts and Earlier Prompts**, with same column count/order.
2. **Existing rich help survives:** Main prompt and two or more linked Subagents with distinct model/effort, category costs, Number of prompts, subtotal/total and incomplete group evidence remain available in the same value tooltip after the concise I/E lines. Check no duplicated Total CCost if a clean concise layout is chosen.
3. **Zero/unavailable/partial:** 0, $0.00, rounded tiny positive USD, N/A, ?12, known I / unknown E, unknown I / known E, both unknown, sparse compaction and partially priced/incomplete sources. Every displayed CCost cell is just the original total token. Tooltip reflects source-supported facts rather than the removed FR000586 forced-zero fiction.
4. **Real updates:** accepted same-session Live changes, reconnect retention/revision corrections, moving a prompt to Earlier, different similarly valued prompts, incomplete-to-known evidence, unit switching and both Web themes update the correct values/help without stale text, lost focus, extra request or unverified math.
5. **Browser/layout:** actual Chrome/Edge hover (normal shared 600 ms delay), keyboard focus, touch, Escape, narrow 360px/desktop widths, zoom and horizontal scroll. Tooltip targets the **number**, not empty cell area; shorter cells improve table compactness; no new button or clipping.
6. Update **development/tests/integration/web_watch_prompt_cost.cjs**, **web_live.cjs**, relevant real **probe_watch_prompt_cost.cjs** or existing Watch browser checks, **development/tests/test_watch_prompt_cost.py** and current tooltip help coverage. Update **docs/web-beta.md** and current Watch module/journal documents **during implementation** (especially older visible CCost (I + E) and displayed-zero paragraphs), but preserve historical completed FR/COMPLETION evidence.

**FR-only publication boundary:** add this file in the Ready queue, update **development/backlog/identity-state.json** from highWatermark **646** to **647**, commit both to current main atomically, and do not change any runtime implementation, tests, docs/version/release or other FR now.
