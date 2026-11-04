# FR 000575 — Show `CCost (I + E)` breakdown in full Web Watch prompt tables

## Owner request and scope

**Owner-approved executable feature request, 2026-11-04.** Permanent identity **000575**; Ready priority **000150**, after currently queued FR000570–FR000574. Scope is **CostGuard Web Beta → full Watch**, specifically the **prompt-local CCost column in both Running Prompts and Earlier Prompts session-card tables**.

Keep the existing single cost column, but make its value explain *where the prompt's reference cost comes from*: **total first**, with the existing CLI session-report **Incoming Context CCost + Extra CCost** split in parentheses. The owner prefers a plus sign, **not** a slash or two additional columns. This is a compact per-prompt cost presentation, not a new accounting metric.

## 1. Exact column label and cell format

Apply the **same** change to both full-Watch prompt tables:

| Part | Required appearance |
| --- | --- |
| Column heading | **`CCost (I + E)`** |
| Cell | **`<total CCost> (<incoming CCost> + <extra CCost>)`** |
| Illustrative Credits-style value | `1 250 (900 + 350)` |

- Use **capital I and E**, spaces around `+`, and exactly one parenthesized pair. Do **not** write `I/E`, change the column order, or add separate cost columns.
- The amount **before** the parentheses remains the current **entire canonical prompt/event CCost**. **I** is that prompt's *Incoming Context CCost*; **E** is its *Extra CCost*. The two diagnostic parts correspond to the same prompt and canonical attributed physical model requests, including supported linked child/subagent contributions.
- Respect the user's existing **Credits vs USD** Web display selection and shared number/currency formatting for **all three amounts**. Do not mix a Credits total with USD components or introduce independent conversion/rounding. When all inputs are known, **raw I + E reconciles to raw total**; separately rounded displayed values need not visually sum digit-for-digit.
- Keep the existing one-line row behavior and Prompt-only truncation. Accommodate the longer cost cell with sensible intrinsic sizing and the already-supported horizontal table scrolling at narrow widths/zoom. Do not silently truncate any of the three cost values or let the added width conceal the prompt number.

## 2. Header tooltip: explain total, I and E

Replace the existing full-Watch **CCost header tooltip** in both tables, retaining the established header help interaction (pointer hover, keyboard focus and touch/click, accessible description/popover).

Suggested English wording, using the CLI report's existing definitions:

> **CCost** is this prompt's total reference-price comparison cost, not actual billed spending or provider quota usage. **I = Incoming Context CCost:** reference valuation of the initial incoming context on the first attributed model request. **E = Extra CCost:** other attributed model usage beyond that incoming context, including generated output and later or linked-child requests. When available, **I + E = total CCost** before display rounding. This **I** means incoming-context *cost*, not the **Input** token category in Token Mix %.

The implementation may tighten the prose for readability, but must explain **all three displayed numbers, their order, their addition, and the separate meaning of I**. Preserve existing CCost-versus-billing and incomplete-coverage information; do not make tooltip visibility depend solely on mouse hover.

## 3. Reuse canonical report projection, not a second calculation

Inspected current `main` on 2026-11-04:

- The CLI session report already displays **`CCost | ~Ictx CCost | ~Extra CCost`** per prompt, with descriptions in `README.md`. `src/reports/prompt_rows.py` computes `incoming_context_ccost` and `extra_ccost` from canonical attributed request usage and reference pricing; the `PromptProjection` holds both. This is the **source of truth** for the desired split.
- `src/application/live_projection.py::card_row` currently exports a compact full-Watch `prompt` with `ccost`, but **omits** `incoming_context_ccost` and `extra_ccost` from its selected fields. Extend the established server-owned projection/export so these existing canonical values reach both Running and Earlier cards.
- `src/application/display.py::amount_tokens` already recognizes `incoming_context_ccost` and `extra_ccost` as reference-cost display fields. Reuse the existing unit-aware immutable display projection and `src/web/assets/watch.js` presentation; no JavaScript cost math or parsing of formatted CLI output.
- `src/web/assets/watch.js` currently has a `CCost` entry in its shared `columns` descriptions and displays `display(prompt, 'ccost')` in each row. Update that shared column/header and cost cell without changing the meaning of other Watch columns.

**Definition boundary:** I is **not** the whole session's estimated *next* context cost, the ECTX/Δ Ctx count, a Token Mix token share, or simply all Input token charges over every call. E is **not** a new charge/billing category. Follow the current report's first-attributed-request incoming context and remaining causal usage semantics, across model switches, context tiers, cache reads/writes, subsequent calls and child contributions.

For **running prompts**, reuse the report's supported provisional snapshot behavior and the existing bounded accepted-capture/SSE update path. The split should update as new attributable usage becomes available; do not invent intra-request streaming, add backend polling, duplicate full-history scans or calculate the difference in the browser. Corrected, stale, partial and terminal observations continue to follow existing causal/retention rules.

## 4. Unknown, partial and zero values

- Preserve the existing total CCost's **true zero, fully unavailable/N/A, partial-pricing `?` and established unit/provenance rules**. Adding parentheses must not make a known partial total look complete.
- A genuinely unavailable **I** or **E** must remain **N/A/unknown** in that component's slot; do not silently turn it into `0`, assume `E = total − I` from mismatched incomplete coverage, or substitute the session's next-context estimate. A known zero is `0` only with supporting evidence.
- If the underlying report intentionally withholds active-provisional split metrics or the required pricing/token categories are unavailable, keep that distinction. Example structural fallback: `<known total> (N/A + N/A)` if both component diagnostics are unsupported. For a wholly unpriced prompt, show the existing unavailable-total state rather than invented arithmetic.
- If reconciled raw values disagree unexpectedly, investigate parity with the canonical CLI report rather than adjusting one displayed value to force a visually exact sum after rounding.

## 5. Dependencies, boundaries and acceptance

**Coordinate with Ready FR000572** (ECTX, session-level context/CCost summary and full-Watch table layout). This FR adds a **prompt-local breakdown in the existing CCost column** after/alongside that change. **Session CCost** in FR000572 remains a distinct **whole-session** aggregate; never replace it with the in-cell total or sum only visible Watch rows. Preserve FR000558's established Watch header-help controls.

**Explicitly out of scope:** **Mini Watch** (its compact CCost column stays **total only**), CLI session/Watch rendering, Sessions and other Web reports, token-mix definitions, daily and account CCost displays, quota/billing data, canonical valuation, source acquisition and session/prompt lifecycle. In particular, do not apply the new text via a global replacement of every `CCost` heading.

Acceptance criteria:

1. **Both** full-Watch Running Prompts and Earlier Prompts show **`CCost (I + E)`** and every supported prompt row shows **total followed by `(I + E)` numeric components** in that order. Column positioning/other headings remain as established by FR000572.
2. For a fully priced, known prompt, compare all three **unrounded source costs** with a corresponding CLI session report snapshot: I and E use the canonical report fields and reconcile to the same total, including multi-call, cache-heavy and linked-child cases; rounding and USD/credit formatting remain consistent.
3. For live active prompts, updated accepted usage changes the correct row's total and components without a manual page reload. Retained earlier rows, aborted/completed prompts, restarts/reconnects and later source corrections remain consistent and never acquire another row's split.
4. Partial/unpriced/unknown and legitimate zero cases remain truthful in total **and independently in I and E**; unknown never becomes synthetic zero. Header tooltip is correct and accessible on pointer/keyboard/touch.
5. Narrow windows, browser zoom and the established table scroll keep costs readable without losing Prompt numbering; existing one-line behavior remains. **Mini Watch still shows only the original prompt total CCost**, and unrelated cost tables/tooltips remain unchanged.
6. Extend focused canonical projection/formatting and Web Watch DOM/interaction tests for both table types, unit switching, live accepted updates and missing evidence; update the current `docs/web-beta.md` Watch column description. Do not rewrite historical completed FRs.

**Authoring only:** Publish this approved Ready FR plus advance the permanent identity high-watermark to 575 on CostGuard `main`. Do **not** implement product code, bump version/history, build a release or interact with the owner's live server in this authoring session.
