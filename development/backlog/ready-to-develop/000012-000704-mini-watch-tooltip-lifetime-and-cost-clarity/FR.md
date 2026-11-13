# FR 000704 — Mini Watch: reliable hover lifetime and concise, source-backed tooltips

**Owner-approved Ready to Develop — 2026-11-13.** Permanent ID **000704**; queue priority **000012**, following existing priority 000011 / FR000703. **FR-only publication:** create this request and advance the permanent-ID watermark; do not implement product code, change other FRs, run product tests or paid inference, alter versions/releases, or change other backlog statuses in this authoring transaction.

## Purpose and scope

The owner wants a deliberate, compact tooltip pass **specifically in Mini Watch (Document Picture-in-Picture)**, plus a **shared Web tooltip-lifetime bug fix** that applies everywhere using the same hover controller. Do not redesign Full Watch/Accounts tooltips or change underlying accounting merely to achieve smaller Mini copy. Preserve keyboard/focus/touch help, correct source provenance, error and partial-usage semantics, historical session identity, existing session-cell help and the five-row Mini viewport.

**Highest priority inside this FR: fix hover tooltips spontaneously disappearing while the pointer remains stationary on the trigger.** The owner initially saw this over subscription/account labels, then reproduced the same symptom over several kinds of help. It is **not just an Accounts refresh bug**. The earlier opposite problem (a popup stranded after leaving Mini) must remain fixed.

### Existing work, overlaps and source-backed starting points

- **Completed FR000683** installed a shared open-only hover watchdog in `src/web/assets/help.js::ContextHelp.controller()`. Current source defines `HOVER_CHECK = 1000`, `HOVER_IDLE = 30000`; `pointerInteraction()` renews the idle deadline only on genuine pointer input, while `watchHover()` closes after deadline even when the pointer legitimately remains still and `:hover` remains true. This is a **specific code-supported candidate explanation**, not a captured real Windows pointer trace. Repair that lifecycle behavior; do not remove the shared watchdog or reintroduce stranded popovers. Completed FR000587 contains earlier hover/focus/pin safeguards.
- **Completed FR000699** already simplified Web quota Capacity help and added day-after-time reset formatting. This new FR is a **Mini-specific final copy contract**, not a reopening of global Accounts/Full Watch presentation. The remaining `Reset in` / `Reset at` content under a `Next reset:` heading, the missing special `tomorrow` token, and any repeated secondary Capacity/guesstimate help are in scope for Mini.
- **Ready FR000700 (priority 000008)** owns the *actual recursive main/child/grandchild CCost attribution*, distinct linked subagent records, completeness and correct cross-surface totals. **Do not overwrite or weaken FR000700.** This FR owns the narrower Mini-only final presentation: combine all contributing calls that share a supported **provider/model/effort group** for a succinct `Sub Agent N` line. Full Watch retains FR000700's more granular per-*individual-agent* help. Mini must consume that canonical repaired data and never implement a parallel, diverging price calculation. If the tooltip's required groups are unavailable before FR000700, implement/integrate after that prerequisite, not invent data.
- **Ready FR000703 (priority 000011)** owns last-good-value retention, stable rows and refresh behavior throughout Web/Mini. Do not undo that work or remount tooltip targets on every SSE update. Stable visible mouse targets and their tooltip lifetimes must remain compatible with FR000703.
- **Completed FR000694** sets effective-default effort tooltip evidence. Use the same truthful provider, executed/selected model and effort evidence; do not infer a missing effort/model version. Existing FR000698 Sessions model presentation is separate.
- Current candidate owners: `src/web/assets/help.js` (one Popover/document, hover/focus/pin, ARIA, watchdog), `src/web/assets/mini.js` (`View.table`, `sessionRow`, `rowHelp`, `promptDetails`, `drawCost`, `drawAccounts`, `drawSessions`), `src/web/assets/mini.css` and shared `src/web/assets/app.css`, `src/application/display.py::web_quota_reset`, `src/application/prompt_costs.py`, existing Live/prompt and session cost DTOs. Verify the installed service/actual DOM during implementation; these are code inspection leads, not claims of a completed runtime reproduction.

## P0 — Fix premature hover tooltip disappearance without losing orphan cleanup

1. **A stationary real hover is not idle abandonment.** A tooltip opened by mouse hover must stay visible and readable while the actual pointer remains over its trigger or intentionally over the popup, **even with no pointer movement for 30, 60, 90+ seconds**. The current unconditional `now() >= hoverDeadline` close can violate this. Subscription quota refresh, label text updates, periodic SSE, changed numeric percentages, table row reconciliation, DOM styling and PiP refresh must not dismiss it if the actual relevant hovered target is still present and the tooltip remains applicable. Do not repeatedly restart the 600ms open delay while reading a tooltip.
2. **Retain the real safety watchdog.** Continue open-only, low-overhead periodic revalidation (about once a second or an equivalent bounded mechanism), plus normal leave/outside, document/PiP exit, blur, pagehide, removed-target and Escape handling. Recheck precise trigger/panel hover/hit-test truth, live DOM identity and related document state; allow deliberate transfer from trigger to popup. Missed `pointerleave` alone must not cause an indefinitely orphaned tooltip. The fix must not replace the watchdog with events only or create a second competing timer.
3. **Avoid false negatives and stale-signal assumptions.** Diagnose exactly which condition closes a stationary real hover: the 30-second lease, false `:hover`, hit-test/coordinate mismatch, node replacement, blur, another trigger or refresh. Use stable logical target identity and preserve the active tooltip over legitimate in-place content updates when possible. A genuinely changed/removed item must close or safely transfer, never show another item's help. Avoid treating a null/stale last-pointer position as definitive proof of departure.
4. **State the browser observability boundary truthfully.** If the browser supplies no exit events and retains falsely stale `:hover`, page JavaScript cannot in general distinguish a departed OS pointer from a genuinely stationary one with perfect certainty. Prefer avoiding **premature dismissal during confirmed stationary hover**, using trustworthy current pointer evidence/lifecycle events for orphan cleanup, and documenting any necessary bounded fallback for genuinely *inconclusive* state. Do not promise both mathematically impossible guarantees from a synthetic stale selector. No OS-wide mouse hook, always-on app poll, network request or new full-source acquisition.
5. **Lifecycle and accessibility stay correct.** One active watchdog at most per visible hover tooltip/document, no timer while closed/focus/pinned-only, no callbacks targeting a closed/reopened PiP. `aria-describedby` is attached/removed correctly. Keyboard-triggered focus and intentional pinned/touch popovers remain readable until normal dismissal, not subject to mouse idle expiry; do not leave a stranded popup when target/focus/document disappears.

## P1 — Subscription and header tooltip copy (Mini only)

1. **Subscription hover label:** exactly one primary **`Capacity: <amount>`** line and one **`Next reset: <human-readable schedule>`** line for the normal available state. Actual source-confirmed Capacity has no prefix; calculated/inferred Capacity starts with `~`. Preserve ordinary formatted Credit/USD precision already established by FR000699; do not emit long raw Decimals. No duplicate lower `Capacity`, standalone `Guesstimate`, `Unrounded calculation not verified provider`, formula/method essay, Monthly Capacity or repetitive caveat in **Mini's** tooltip. An unknown capacity/reset uses the established honest `N/A`/unknown state; real account errors/restrictions remain visible through their appropriate status/label surface rather than being silently suppressed.
2. **Next reset wording:** The `Next reset:` label already says what resets. Its value must **not repeat `Reset in` or `Reset at`**. Show useful remaining duration, then local `HH:mm`, then calendar qualification **after the clock**: `today` for the current local date, `tomorrow` for the next local date, the English weekday for subsequent dates within seven elapsed days, and `YYYY-MM-DD` beyond seven elapsed days. Examples: `Next reset: in 3 hours · 01:00 tomorrow`; `Next reset: in 2 days, 5 hours · 03:00 Monday`; `Next reset: in 20 days · 03:00 2026-12-03`. Examples are illustrative; choose dates/times consistently from one canonical clock and configured timezone, including DST. Preserve pending, expired, inactive-window and missing-deadline semantics. Prefer server-prepared localized tokens, not a duplicate client-side time calculation. Do not change CLI/Accounts/Full Watch reset copy unless shared code necessarily demands a safe general fix.
3. **Upper-left `Cost Guard · Watch` action:** its tooltip must contain exactly **`Return to Watch in the Existing Parent Tab`**, one line, no second sentence about a minimized window or browser return-to-tab. Keep the real action and accessible name consistent with the meaning (it returns to the existing parent browser tab, not a new one).
4. **Fit-height button:** its tooltip must be exactly **`Fit Mini Watch Height`**. Remove the explanations about row count, height/width and subscriptions; keep its existing action and accessibility.

## P2 — Table header tooltips (Mini only)

The table remains **Activity | Session | CCost | Total | Ctx**. Replace only the specified headings' help, without new icons, extraneous definitions or changes to main Web pages.

| Heading | Exact intended help |
| --- | --- |
| **Activity** | Two separate bullet lines: `• For a running prompt, shows when it started.` and `• For a finished prompt, shows when it finished.` These describe the row's currently represented prompt, not the whole session's original creation date. |
| **Session** | Preserve current help and all Session **cell** tooltips unchanged. |
| **CCost** | `Reference cost of this session's latest represented prompt, including attributed linked subagent calls.` (The row may be running or finished; use its actual representative prompt.) |
| **Total** | **Keep current sentence unchanged:** `The entire session’s reference cost, including attributed linked subagents.` |
| **Ctx** | `Estimated context for this session, in tokens.` No explanatory paragraphs about Next Ctx/Δ Ctx under the heading. |

## P3 — Table value tooltips and source-backed cost groups (Mini only)

### Activity value

On a row's Activity **value**, show only `YYYY-MM-DD HH:mm` in the app's configured local time. For a running row this is the representative prompt's **start**, for a finished row its **known finish**. Remove the `+0100`/`+0200` UTC offset and any timezone suffix from this **Mini tooltip only**; do not alter authoritative timestamps, backend UTC storage, DST comparison, other screens' accessible timestamps, or the visible compact Activity cell. Unknown finish must remain unknown, not invented. `src/application/display.py` already has a local `date_time` token without offset; use an appropriate scope-qualified/start-vs-finish equivalent instead of globally changing unrelated `start_date_time`/`finished_date_time` contracts.

### Prompt CCost value

**Replace** the current verbose Mini prompt CCost tooltip with the following ordered, compact content. The spacing is intentional; within each group the model and its CCost occupy consecutive lines, with exactly one blank line **between** groups. Example values/model names are synthetic:

~~~text
Prompt #3
Main Model: provider-a/model-main — high
Main Model CCost: 120 Credits

Sub Agent 1: provider-b/model-child — medium
Sub Agent 1 CCost: 80 Credits

Sub Agent 2: provider-c/model-child — default (high)
Sub Agent 2 CCost: 20 Credits

Duration: 1m 23s
~~~

- Preserve actual `Prompt #N` order number. Exactly one **Main Model** group when one main provider/model/effort is used. If multiple truly distinct main combinations contributed, show `Main Model 1`, `Main Model 2`, etc. with their corresponding cost lines rather than falsely crediting just one main model.
- Every `Sub Agent N` is a **distinct Mini presentation group by supported provider + model + effort**. Aggregate the source-attributed cost of *all calls* by child/grandchild agents using that same combination into that group's cost; otherwise show separate numbered groups. This is intentionally **different from FR000700's Full Watch per-individual-agent breakdown**. Retain source-backed individual subagent identities in the underlying data for auditing. Stable, deterministic ordering avoids numbering jumping on refresh.
- Every displayed model label uses `provider/model — effort`, with correctly qualified selected/default-effort evidence and distinct provider/model versions. Do **not** print a separate `Effort:` paragraph. A model switch or changed effort must not hide earlier contributions; no guessed model, unproven child execution or fabricated CCost.
- Show `Main Model CCost:` / `Sub Agent N CCost:` in the currently selected Credits or USD presentation unit. Sum canonical **unrounded physical request values exactly once**, then format group totals by normal unit rules. Group subtotals reconcile to the prompt's shown CCost according to existing partial/completeness policy; independent rounding may differ by a display unit. If unknown/unpriceable/missing-attribution evidence prevents a complete value, keep the corresponding cost line honest (`N/A` / visible `?` partial as appropriate) and preserve the original cell's honesty, never substitute `0` or label an incomplete total complete merely for cleanliness.
- Then one blank line and **`Duration: <value>`** at the bottom. While the represented prompt is genuinely running, **color only the live Duration value yellow** using the existing safe `ContextHelp.runningDuration` behavior; otherwise ordinary text. Keep legitimate running updates without closing hover help.
- Remove the other existing Mini prompt CCost tooltip content: separate `Calls`, `Effort`, `Linked subagents`, `Multiple models contributed`, generic `Estimated attribution`/`Partial pricing` prose and inherited verbose full breakdown/technical explanation. Relevant unknowns are represented by the affected model/cost values rather than fabricated certainty. The separate **Session cell** help is not changed.

### Total CCost value — NEW tooltip

Attach an actual tooltip to the **Total** value (currently only an accessible label, no `ContextHelp.value`). Use **the same group layout and spacing as Prompt CCost**, but for the **entire root/session tree**, not the latest prompt; do **not** put a `Prompt #N` heading on a whole-session total:

~~~text
Session Model 1: provider-a/model-main — high
Session Model 1 CCost: 300 Credits

Session Model 2: provider-b/model-main — medium
Session Model 2 CCost: 40 Credits

Sub Agent 1: provider-c/model-child — high
Sub Agent 1 CCost: 80 Credits

Duration: 7m 14s
~~~

- Number **Session Model 1, 2, ...** for distinct main/root-session provider/model/effort combinations across **all** applicable prompts and root-session model requests (including correctly attributed compaction/other root work, not just the focal prompt). Separately number **Sub Agent 1, 2, ...** by distinct child model/effort combination over the root's full recursively linked subagent work, with all eligible calls for the combination grouped once. A single-model session with no child work shows just `Session Model 1`, its cost and supported Duration.
- Do not count the same child cost under both Session Model and Sub Agent, and do not exclude genuine unassigned-but-root-owned work from the Total. Full-session canonical CCost, source coverage/partialness and all other consumers remain authoritative. If some costs cannot be allocated confidently, retain explicit partial/N/A truth in the appropriate cost line or existing value state; never fabricate a balancing group or silently drop a physical request.
- `Duration` here refers to **source-supported session elapsed/active duration**, not the focal prompt's duration. Mark it yellow only while the session is genuinely running, using the shared safe Duration emphasis. If authoritative session duration cannot be derived, show `N/A` rather than a false precise number. No explanatory cost boilerplate, duplicate whole-total paragraph, Calls or linked-subagent counts.

### Ctx value — warn only after a price threshold is actually exceeded

- **Remove the normal per-cell Ctx tooltip entirely.** No Next Ctx/Δ Ctx/general context or approaching-price paragraphs, including for a valid non-warning estimate, `N/A` or a pending retained estimate. Keep Ctx numeric value, the Ctx **header** help and normal accessibility semantics.
- Only when the **canonical, source-qualified context price warning has `severity == exceeded`** for that actual session/context generation show its Ctx value in **the same red `--error` color** as Full Watch's *exceeded* price-threshold warning. Do not color approaching (`severity == approaching`), normal, unavailable, stale, invalidated or mismatched-context Ctx in Mini. No yellow/orange approaching stage and no tooltip at all for that stage. Do not use display-rounded Ctx digits to invent a severity.
- For **exceeded** only, attach a short warning tooltip such as `Price threshold >200k exceeded · 2.4x more expensive`, sourced from the existing threshold value and supported price multiplier. If the multiplier is genuinely unavailable, report the exceeded threshold succinctly without inventing an `Nx` amount. Revert to neutral text and no warning tooltip immediately when the source revision/context/model changes or the severity is no longer exceeded. Keep keyboard/focus/touch access to the meaningful exceeded warning.

## Verification / acceptance (implementation worker)

1. **Real stationary pointer and orphan regressions are both mandatory.** In actual Chromium/Edge **Document PiP** and standard Web/Full Watch shared help, open subscription, Activity, CCost, Total, Ctx-exceeded and generic tooltips. Keep the actual pointer stationary on the trigger **well beyond 30 seconds** (e.g. 60–120 seconds), through several UI refreshes and changing subscription/row values: never auto-close for inactivity alone. Also simulate missed pointerleave/document exit with a genuine hover/hit-test transition away; the shared watchdog must still dismiss abandoned help. Exercise physical Windows PiP→browser chrome/other application if available and report any OS-only test **NOT RUN** honestly. Test stale `:hover` contradictions without falsely claiming JavaScript can know absent OS cursor position.
2. **Tooltip lifecycle matrix:** delayed opening, trigger↔tooltip transfer, no event after pointer exit, trigger removal/replacement, stable keyed row refresh, rapidly switching targets, scroll/resize/zoom, close/reopen PiP, backdrop/blur/pagehide, Escape, pointer focus vs keyboard focus, touch pin and multiple Web documents. Assert no repeated unexpected closes, no permanently stranded popup where current browser state reveals departure, no timer leaks, no ARIA orphaning, no background polling while closed and no additional API calls on hover.
3. **All exact Mini help text:** the two-line subscription normal case and formatted capacity `~`, `Next reset` without redundant reset wording; **today/tomorrow/weekday/date** including DST, deadline absence and greater-than-seven-day boundary; exact header action/Fit strings; two separate Activity bullets; CCost/Total/Ctx header strings. Preserve Session help; verify locale-independent intended English copy and screen-reader focus/tap affordances.
4. **Activity and Ctx state matrix:** actual running start vs finished completion in local `YYYY-MM-DD HH:mm` without offset, unknown finish, date/zone change. For Ctx check no value help or warning in normal/approaching/unavailable/pending cases, red font + short threshold/`Nx more expensive` popup only when **exceeded**, no stale red state after threshold/model/session/compaction change. Compare same canonical threshold and red token against Full Watch.
5. **CCost/Total truthful scope:** main-only, single/multiple main models, one and multiple subagent model/effort groups, several individual children sharing one group, nested descendants, model/effort changes, interrupted or failed child, missing execution evidence, supported vs missing prices, partial costs, reused child/de-duplication, compactions/out-of-prompt root work, source generation/cache changes and both Credits/USD. Assert that the actual Mini cost groups reconcile from **the same underlying FR000700-corrected canonical physical requests** and that Total includes all eligible session work, not just latest prompt. No extra Calls/Effort/Multiple models/Linked subagents paragraphs. Duration is yellow only for genuinely running prompts/sessions.
6. **Rendered and non-regression checks:** actual visible Mini PiP at narrow widths/125% zoom, light/dark themes, selected cost units, 0–5 session rows and retained Live refresh, panel positioning/line breaks, no new horizontal overflow or incorrect height adjustment. Confirm shared Full Watch/Accounts tooltip *copy* unchanged, except genuine shared lifetime bug fix; FR000699 quota math, FR000700 per-agent Full Watch breakdown, FR000703 stable last-known refresh and native text/provenance remain intact.
7. Use existing `development/tests/integration/web_help.cjs`, `probe_web_help.cjs`, `probe_mini_help.cjs`, Mini DOM/browser tests, and relevant `development/tests/test_web_display.py`, context-warning, prompt-cost/recursive-attribution and session-summary fixtures. Add focused cases for this new Mini presentation. State which checks actually passed, failed or were not run; do not declare the customer's intermittent real Windows symptom proved fixed solely from a virtual selector test.

**Done means:** Mini Watch tooltips are short, exactly organized as requested, and show accurate source-backed main/subagent and session-level reference CCost without extra prose. A genuinely stationary pointer never loses its tooltip to the shared watchdog, while genuinely abandoned help is dismissed where supported browser evidence reveals departure. The existing richer Full Watch/Accounts semantics and FR000700/FR000703 work remain intact.
