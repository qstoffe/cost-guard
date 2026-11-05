# FR 000590 — Web Beta: value-first tooltips, delayed hover, actionable detail and clearer Watch summaries

## Owner request and sequencing

**Owner-approved executable Ready Feature Request, 2026-11-05.** This is a further UX pass on **all Web Beta contextual help**, especially Full Watch, account cards, prompt tables and the separate Mini Watch Document PiP. It follows completed FR000582/FR000587 and should be implemented **after FR000589** (remove dotted underlines and make table-header hover text-only). FR000588 (Web OpenCode autostart) is independent. The owner has already started the earlier work: do **not** overwrite, re-implement or conflict with those in-flight changes.

The goal is **less tooltip chrome and boilerplate, more useful information exactly where the user is looking**. Remove standalone question-mark help buttons; preserve genuinely valuable explanations by attaching them directly to the corresponding *label and/or value*. Use a modest hover delay so accidental mouse passes do not make the UI flicker. Bring richer, evidence-backed *per-cell* information to selected metrics rather than repeating obvious definitions.

**Authoring scope only:** publish this FR in Ready and update the identity watermark; do not implement runtime code, documentation, tests, release/version metadata or feature behavior in the authoring session.

## 1. Remove standalone tooltip `?` icons and move their help to the relevant text/value

- Across **every Web Beta view and Mini Watch**, remove the small standalone `?` controls used *only* to trigger contextual help. **Keep the help itself when useful**: move it to the precise related visible label, number, time or grouped inline value. Examples in Watch account cards: `CCost Today: <value>` and `Capacity: <value>` should expose their useful tooltip from **both the label and the number**; there should be no adjacent question-mark icon.
- Apply the same treatment to quota/reset details, Watch daily overview, session context and cost, tool/skill activity, account/subscription facts, exact prompt dates and remaining useful contexts in Models, Sessions, Accounts, Reports/settings where appropriate. Audit dynamically created DOM, not just static `ContextHelp.beside` calls.
- Choose a **semantically exact, compact hover/focus target**: the text and/or number itself, not the whole card, unused table space, progress-bar track, header background, whitespace or an invisible oversized overlay. The header-label-only rules from FR000589 continue to apply. If there is **no useful explanation and no sensible visible target**, remove the redundant tooltip rather than moving it to a random parent.
- On passive help targets, show the native CSS **`cursor: help`** (arrow plus question mark) *as soon as the pointer is on the target*; the tooltip content appears only after the delay described below. Don't add dotted underlines back. Preserve `pointer` for actual interactive actions, native focus/selection behavior, text copy and links rather than disguising a real click action as passive help.
- This removes **standalone help icons**, **not meaningful question marks inside data**: retain `?` when it denotes *partially priced/unknown values*, and preserve real uncertainty, status and warnings. Do not remove `?` from legitimate text/data just to satisfy an icon-removal search.
- Without visible `?` icons, provide deliberate keyboard-focus and touch/tap access to every retained passive tooltip with meaningful accessible names/descriptions, no focus trap and no selection regression. Do not make any critical warning or mandatory action available *only* on hover.

## 2. One consistent hover opening delay across the whole app

- Add a **single shared delay before opening any pointer-hover-origin tooltip**, including headings, menus/action help, account card labels/values, ordinary help and conditional cell tooltips in the main document **and** Mini Watch. Aim for a Windows-like, but slightly brisker, feel: **approximately 600 ms** (one centrally defined constant, with testable tolerance, rather than per-view delays). Fast pointer flyovers should reveal nothing.
- The **help cursor changes immediately** on a passive eligible target; only the popup is delayed. Cancel pending opening when the pointer leaves the precise target, changes eligible targets, leaves the document/PiP boundary, or the trigger is removed. Re-enter must be a fresh intentional hover; stale timers and live rerenders must never open abandoned tooltips.
- Preserve FR000587's robust **hover / keyboard-focus / pinned/touch** ownership, panel-pointer transfer, short bounded *closing* grace, Escape, event-driven out-of-window dismissal and no orphaned PiP tooltips. Do not conflate *opening delay* with *exit grace* or restart it continuously during stable hovering.
- **Keyboard focus and explicit touch/tap/click help requests** should reveal help promptly (without forcing a 600 ms delay); respect native action activation and its immediate tooltip dismissal. No recurring polling, costly per-row timers when not hovered or new tooltip framework. Test same-document and separate PiP ownership.
- No new work is requested on the intermittently stuck-tooltip issue if the existing FR000587 fix already covers it; simply make sure the new delayed opening cannot **regress** that fix.

## 3. Rewrite tooltips for scanability, not legal disclaimers

- Review retained tooltip texts throughout Web and Mini. Lead with useful facts. A simple concept gets one short sentence; **independent multiple facts become concise `•` bullets or visually separated sections** with an occasional empty line. Don't force long paragraphs or endless single-line caveats.
- In **Full Watch → Model** heading specifically, replace the current three-sentence prose with **two short bullets**, e.g.:
  - `• Main prompt — The model shown in this column.`
  - `• Linked subagents — May use other models; their activity is included in prompt totals.`
  Remove the final generic clause `Unlinked or unpriced work may be missing.` from this header. It is unhelpful blanket self-protection, not a user-facing explanation.
- In **Full Watch → Effort** heading, explain reasoning effort concisely, but **remove** `N/A — This setting is unavailable.` That tautology adds no information. Do not automatically create a tooltip on every `N/A` cell. If an actual specific cell has a **meaningful supported reason** (e.g. a real source-specific limitation), show it *on that exceptional cell value*; otherwise leave `N/A` without redundant help.
- Audit other headings, labels and cells for repetitive `N/A means unavailable`, repetitive `not your bill`, hypothetical gaps, blanket caveats, raw internal freshness details, etc. **Do not remove materially important truth** about *estimated versus provider-verified Capacity*, partial/retained cost evidence, actual source outages, native quota vs reference CCost, or other facts that change how users should interpret a number. These belong near the affected figure, in plain English, **only where relevant**, instead of a paragraph of generic disclaimers in every header.
- Remove stale text that says `use the adjacent help button` once standalone buttons are gone. Keep accurate, concise wording and update Web tooltip-writing guidance.

## 4. Useful conditional per-cell help in Full Watch prompt tables

Normal cells **should not all acquire generic tooltips**. Instead, selectively reveal information that is *extra, meaningful and supported for that particular cell*. Conduct a purposeful audit of **all Full Watch column families** in both Running Prompts and Earlier Prompts; implement sensible cell-level opportunities rather than a tooltip on every cell.

**Required examples:**

1. **Started / Finished time:** remove the adjacent date `?`. Hover/focus the actual displayed **clock value** to reveal the **full local date and time**, including the existing meaningful offset/precision. Do not change display time or fabricate a finish timestamp if unknown. This is an especially useful pattern to preserve.
2. **Model cell:** normally just show the model name with no popup. When reliable evidence shows **linked subagents with differing models** (or another genuinely useful multi-model attribution), make the **model text** itself a conditional help target. Explain **main model and which linked subagents/other models participated**, including their recorded effort where available. Avoid generic `another model contributed` when the actual identities can be shown.
3. **Mark linked subagents with a small trailing `*` after the displayed main model name**, in both prompt tables when there is **positive evidence of linked subagent participation**, even if a subagent used the same model. The asterisk means **linked subagents participated**, **not merely 'several models'**. Do not conflate the current `has_additional_model` flag with confirmed subagent existence; prove the association using canonical causal ownership. A model-only change without a linked subagent must not receive this star. Provide an accessible explanation of the marker, not color alone. If the marker is useful, the adjacent model text/star may share one compact conditional detailed tooltip.
4. **Other cells** (e.g. Calls with a confirmed main/subagent split, a genuinely unusual context value, or trustworthy token-category detail) may get well-designed conditional tooltips if they add concrete facts absent from the cell. Skip trivial restatement, unprovable deductions and expensive re-acquisition.

**Do not** reintroduce per-row prompt-preview popups or the Mini row-icon clutter deliberately removed by FR000587.

## 5. Rich CCost breakdown on the **CCost (I + E) cell value** — major feature

When the user hovers/focuses an individual **prompt CCost value** in either Full Watch prompt table, offer a readable breakdown of **where the prompt's total CCost came from**. This is *different* from the column heading's explanation of `I + E`. The cell tooltip should answer: *What did the main prompt cost? What did each linked subagent cost? Which models/efforts and token categories account for it?*

**Desired structure (illustrative labels and layout, never hard-coded providers/models/amounts):**

```text
Main prompt — GPT-6.1 Sol · Extra High
• Input:          8 CCost
• Cached input:   2 CCost
• Cache write:    1 CCost
• Output:        14 CCost
Subtotal:        25 CCost

Subagent 1 — Terra 6.1 · Low
• Input:          3 CCost
• Cached input:   1 CCost
• Cache write:    0 CCost
• Output:         4 CCost
Subtotal:         8 CCost

Total CCost:     33
```

- Use **actual attributed data** for **main prompt and each distinct causally linked subagent**, including multiple subagents and differing models/effort. Present **Input, Cached input, Cache write, Output** as *CCost contributions*, not just percentages or raw token counts; optional trustworthy token counts can supplement, not replace, those costs. Show each subtotal and a coherent **overall prompt total**. Use current Credits/USD display settings and the same formatting semantics as the visible value.
- Be careful about **the two different I meanings**: `CCost (I + E)` in the existing header splits **first-request incoming-context cost vs other cost**, while the requested detailed **Input/Cached/Cache write/Output** lines break down charged token categories across main/linked work. **Do not equate the two decompositions**, silently double count cached tokens or reassign linked costs to the wrong scope.
- Derive this from **canonical source/analysis attribution** and stable immutable server-owned projections; a new small bounded read-only presentation projection is allowed if necessary. **Do not invent per-agent costs by distributing the aggregate total or inferring token categories from percentages**, scrape source private prompts or do browser-side repricing. Preserve original model IDs, effort attribution and concurrent/nested linked work correctly. A single agent with several model requests may legitimately have more than one model/effort: do not lie by assigning them all to the first model; group/split accurately where supported.
- Existing totals, component split `I + E`, reporting/valuation rules, observed-versus-unknown semantics and rounding are authoritative. Calculate and reconcile from **unrounded** values where available; a total may differ visually from the sum of individually rounded lines, so avoid claiming a false precise equality. Partial/unpriced data show **only genuine known lines** with compact meaningful qualification; never render fabricated zero or a misleading full breakdown. If an informative per-agent breakdown is unavailable, show the useful subset or omit the detailed tooltip rather than misleading the user.
- Keep the rich tooltip **readable and performant**: visual grouping and spacing, bounded number of displayed subagents/rows with an honest omitted-count/subtotal only if supported, viewport clamping/scroll for long text, no interactive controls inside `role="tooltip"`, no repeated heavy calculations per mouse movement, and no added persistent polling. No new pricing requests or model inference.
- Update focused analysis/projection/display and browser tests so **each agent's category amounts, subtotals, source scopes and total reconcile** across units, partial pricing, child models, nested/concurrent calls, corrections, Live/retained updates and historical rows.

## 6. Account Capacity: shorter tooltip and visible `(guesstimate)` provenance

- In **Full Watch account cards** (primary **and** secondary quotas), **CCost Today** and **Capacity** should both be meaningful direct hover/focus targets over **the label and its number**, after removing their `?` buttons. Include equivalent existing account/Quota surfaces where the same facts are displayed. Mini subscription help should move from the row's standalone `?` to the **relevant visible account/quota text** without turning the whole window into a trigger.
- **Shorten and restructure the Capacity tooltip.** The top explanatory prose should be **plain, brief and specific** (one or two short statements, optionally split by blank lines/bullets), not a wall of defensive text. **Preserve the valuable factual lower block**: actual quota/window, native Used/Remaining, source limit and resets when available. Arrange facts into scan-friendly named lines and modest section spacing. Do not remove the provider-native facts that make it useful.
- **Mark an inferred/guesstimated CCost Capacity prominently in visible text**: insert exactly a space then **`(guesstimate)` after the numeric capacity**, e.g. `Capacity: 1 000 (guesstimate)`. A **verified provider-reported directly comparable allowance/limit** displays normally, e.g. `Capacity: 7 000`, with **no marker**. This is deliberately one of the *few important qualifications that should be visible*, not hidden in a tooltip.
- Base this flag on actual **per-account, per-quota-window capacity provenance** (provider-native verified amount vs derived proxy, such as observed period CCost divided by a trustworthy usage fraction), not a blanket provider name, a rounded percentage, the magnitude of the number, or the presence of a unit. Retain exact canonical math, unavailable/`N/A` states and original quotas from FR000585. **Do not attach `(guesstimate)` to `N/A`, `?` or missing figures**, and do not imply that provider-native quota credits are actual billed Cost Guard CCost.
- Apply provenance consistently to all **surfaces that actually display the same estimated CCost Capacity** (Full Watch primary/secondary, Accounts where shown; Mini when Capacity is shown as text or described in help) and keep Credits/USD, Used/Remaining, theme and Live updates synchronized. A verified native limit should not suddenly become guessed when the display unit changes.
- This visible marker **does not replace** the tooltip's short method explanation for inferred capacities. Preserve real warning/severity colors, percentage bars and quota status; no new capacity formula is requested.

## 7. Split Watch session-summary Context and Total CCost into **two rows**

Under each session's prompt table/card in **Running Prompts and Earlier Prompts**, replace the current combined `Session Context / CCost:...` display with two clearly separated lines, preserving all underlying data:

```text
Context: 123K (existing context warning, when applicable)
Total CCost: 4 582
```

- **Exact visible labels:** `Context:` and `Total CCost:`; each colon must be followed by **one visible space before its value**. No `Session Context` label and no slash between the two measurements.
- **Context first**: place the same existing next-session-context estimate on row one, followed by the current parenthesized warning text when warranted. Keep the **warning triangle versus stop-sign/octagon icon**, severity logic, red coloring/outline, multiplier/cost impact and explanatory semantics **unchanged**, properly aligned with the Context line. Do not split away the warning or accidentally associate it with total session spending.
- **Total CCost second**: display the same existing *whole-session* CCost, with its honest partial/unavailable/retained status if applicable. Its useful help attaches to `Total CCost` label/value, not an extra standalone `?`. Keep this concept separate from **per-prompt CCost** in table cells.
- Maintain layout and readable spacing in Classic and Web light/dark, narrow/zoomed widths, active and historical cards, updates, loading and warning transitions. Don't change the session's measured context or attribution math.

## 8. Mini Watch: split hover help within the combined Session / (Total CCost) header

- In both Mini Watch tables, the first column visually combines **`Session`** and **`(Total CCost)`**. These are **two distinct help targets inside the same header**: hovering/focusing the **`Session` text** explains only the session name; hovering/focusing **`(Total CCost)`** explains only the whole-session cost. No help is triggered by dead space around the header.
- Preserve the existing combined column layout, title/cost alignment, ellipsis, sticky header, keyboard/touch access and the **text-only hitbox** from FR000589. A single tooltip explaining both at once is **not sufficient**. If FR000589 or another in-flight change already implemented the split, verify it and **do not duplicate the implementation**.
- No separate `?`, no new column and no per-row title duplication.

## Boundaries, implementation coordination and acceptance

**Affected owners (verify after preceding FRs merge):** shared `src/web/assets/help.js`, `app.css`, `mini.css`, `watch.js`, `mini.js`, `render.js`; existing Python causal/prompt/Watch projections for **real** per-agent cost and model/effort evidence, `application/quota_ccost.py` for derived-vs-native capacity provenance, Web DTO/display adapters, current `docs/web-beta.md` / `docs/web-mini-watch.md`, `development/architecture/modules/web-help.md`, focused Web regression/real PiP browser tests. Follow repository ownership boundaries, not guessed file paths. Preserve old completion records. No unrelated CLI, billing, model-selection, history/acquisition or OpenCode process changes.

**Acceptance criteria:**

1. No standalone tooltip `?` cues anywhere in Web Beta or Mini; useful explanations live on exact visible metric labels/values (including both `CCost Today` and `Capacity` words/numbers). Genuine data `?` markers remain, and no full-card/dead-space hover targets or dotted underlines return.
2. Hover opens after roughly **600 ms**, with shared policy across headers, actions, cards, cells and PiP; quick passes show no popup. Help cursor for passive targets is immediate; deliberate keyboard/tap help is prompt. Pointer exits, document/window exits, Escape, panel transfer, removed nodes and rerenders honor FR000587's correct lifecycle.
3. Model heading has two short bullet statements and **no** `Unlinked or unpriced work may be missing.`; Effort heading does **not** say `N/A — This setting is unavailable.`. Other help becomes concise, grouped and actionable rather than disclaimer-heavy, without concealing important uncertainty/provenance.
4. Started/Finished **cell time itself** reveals the full local date/time without a `?`; ordinary uninteresting cells remain unadorned. Dynamic in-cell help is selectively applied where meaningful.
5. Prompts with **confirmed linked subagent participation** show a trailing **`*`** after main model, regardless of whether linked models happen to match; no star otherwise. Conditional model help accurately shows the main model and supported linked model/effort details, and missing attributes are not invented.
6. Hovering a prompt **CCost cell value** gives a useful, readable **main/subagent** cost breakdown by **Input, Cached input, Cache write, Output**, with subtotals and coherent full-prompt total whenever underlying evidence supports it. Cross-unit, incomplete data, nested agents, multiple models and rounding are handled honestly; header `I + E` meaning stays unchanged.
7. Inferred numeric Capacity visibly reads **`<number> (guesstimate)`**; genuinely provider-sourced, directly comparable limits do not. Primary/secondary and other displayed-capacity contexts use the same provenance and remain correct on unit/quota-mode changes. Capacity tooltip leads with concise meaning and preserves well-spaced native factual details below.
8. Under every Full Watch prompt table, two rows show **`Context: <value> (warning)`** and **`Total CCost: <value>`** with spaces after colons, same values and unchanged warning icon/severity/threshold behavior and session cost state.
9. In both Mini tables, hovering just `Session` and just `(Total CCost)` opens **different** scoped explanations; column remains one column, with correct text-only target and keyboard/touch behavior. Do not regress title selection, layout or PiP bounds.
10. Targeted deterministic unit/DOM/browser tests and real Chromium/Document PiP pointer/focus flows cover all applicable Web themes, both Watch tables, active/historical cards, partial/missing cases, exact dates, multiple linked subagents, quotas with inferred/verified/unknown capacity, live updates, zoom/narrow views and correct accessibility. **No real model inference** is needed to validate this FR.

**Publication boundary:** one additional Ready FR, new permanent identity and identity watermark only. Implement the product changes later, through normal backlog execution.
