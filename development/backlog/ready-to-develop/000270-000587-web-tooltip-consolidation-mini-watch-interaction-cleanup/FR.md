# FR 000587 — Web tooltips: declutter Mini Watch, consolidate full Watch help, and sharpen copy

## Owner request and backlog decision

**Owner-approved executable Feature Request, updated 2026-11-05.** Permanent identity **000587**; Ready priority **000270**, after current Ready FR000586 (000260). This is a **selective second UX/content pass** across Cost Guard Web Beta, with **mandatory Mini Watch and full Watch changes**. Publish this FR only; **do not implement source, tests, user docs, version, or release changes while authoring it**.

Completed **FR000582** was a good step forward: the shared custom tooltips are fast and attractive, column-heading help is useful, and full Watch's **CCost (I + E)** explanation is an especially good model of concise text with intentional whitespace. The rollout was nevertheless too indiscriminate: too many question-mark cues, overlapping explanations, needless internal freshness details and some help that adds no value. **Keep what works; remove or consolidate low-value help and apply real UX judgment throughout the Web UI.** This is not a mandate to remove all tooltips or replace the shared component.

**Owner clarification superseding the original FR000587 proposal:** In **Mini Watch**, do **not** add one new table-level `?` per table. Instead, eliminate ordinary row/header-area `?` clutter and use the existing **column headers themselves** as the primary explanation surface. The only deliberate exceptions are the return-to-Watch action tooltip and **at most one optional, useful quota-detail `?` per subscription**.

## 1. Mini Watch: strict, minimal tooltip policy — mandatory

### 1.1 Keep column-header tooltips, make them genuinely useful

- **Keep hover/focus/touch help on the actual column headings** in *both* the current/running prompt table and expanded *Earlier Sessions* table. These are helpful even when space is tight, without requiring an extra visible `?`.
- **The combined `Session` / `Total CCost` header requires a proper two-part explanation.** It displays *two distinct concepts inside one column* and must not be explained as one dense sentence. Separate the sections with **a blank line**. Example format (final English copy may be polished for correctness/compactness):

  ```text
  Session — The name of the session.

  Total CCost — Estimated cost of the entire session, including
  earlier prompts and linked subagents. Not your bill.
  ```

  Apply consistently to both Mini tables and account for FR000583's planned parenthesized **`(Total CCost)`** header. **Do not confuse the session total with the running table's separate per-prompt `CCost` column.**
- The other header help — `#`, `CCost`, `Duration`, `Ctx` — should likewise be **short, accurately scoped, and easy to scan**, with the difference between active-prompt next context and Earlier Sessions' last valid session next context kept correct. Avoid unnecessary diagnostics and paragraph-like copy. A one-line concept does not need blank lines just for decoration.
- The column header should remain a semantic, accessible help target without an extra question-mark control, extra table column or disruptive layout change. Preserve copy/selection, sticky headers, scrolling, narrow layouts, unit changes and theme support.

### 1.2 Remove the default question-mark clutter throughout Mini Watch

**Remove all routine stand-alone Mini Watch `?` cues other than the optional per-subscription quota cue described below.** In particular:

- Remove **both adjacent upper-right/header `?` cues**, including the `CCost Today` explanation `?` and the header-wide `Update status and observation times` `?`. `CCost Today` should remain self-explanatory in visible text; do not relocate these into another header question mark.
- Remove row `?` beside **session names/session totals**, **prompt `#`/status**, and **Earlier Sessions `Ctx`**. The table headings explain the metrics; meaningful running/completed/failed states remain readable/accessible without an extra hover log beside every cell.
- **Do not replace these with a new general table-level `?`**, multiple help icons on the table corner, or invisible duplicate help on normal table values. Keep the Mini visually quiet.
- **Earlier Sessions toggle gets no tooltip at all**, expanded or collapsed. Its label/action is self-explanatory; deleting the tooltip also eliminates that particular stuck-tooltip bug. Preserve correct disclosure/ARIA state, click/tap/keyboard activation and its layout behavior (including FR000583).
- A long/truncated session title should remain intact in the underlying text and accessible naming/navigation. Do not reintroduce unconditional per-row `?` solely to repeat the full title or internal source states. Use the existing selectable/accessible session presentation; do not sacrifice accessibility just to remove the icon.
- Retain **visible, actionable** connection/authorization/host/source warnings and meaningful unknown/partial/stale indications where necessary; removal of redundant tooltip chrome is not permission to hide genuine errors or misrepresent retained information as live.

### 1.3 Keep **Cost Guard · Watch** return-to-tab tooltip, fix its stuck state

The top-left **Cost Guard · Watch** action is a useful exception **without a question-mark icon**. Keep a short tooltip conveying how to return to the original Watch tab, including the browser's native **Return to Tab** control if the Mini PiP remains minimized.

**Bug fix:** when this button is activated by pointer click, touch, Enter or Space, its tooltip must **disappear immediately**, not remain onscreen as the return action occurs. No immediate reopening from stationary hover/focus, window focus changes or live rerenders; help can reappear on a *new intentional* pointer/focus interaction. Preserve real return-to-tab action, accessible button name, and browser-owned PiP behavior.

**Source pointers:** `src/web/assets/mini.js::View` attaches help to `this.summary` and `this.earlierToggle`; `src/web/assets/help.js::ContextHelp.attach()` currently shows rather than dismisses help on action clicks. Remove the Earlier binding; fix action dismissal robustly for the retained return button and inspect similar action-vs-passive behavior elsewhere. Preserve existing hover/focus/Escape/touch-pin behavior for **passive** help cues.

### 1.4 Subscription quota: the *only optional Mini `?`*, and it must earn its space

A **single `?` beside each subscription/account row** may be worthwhile **if it exposes useful information not already visible**. It should not exist just to repeat the row or show `Last quota update`.

- Prefer to show **which quota is currently represented on the compact row** (primary quota label/period and native Used/Remaining orientation), then, **when available**, the account's **secondary quotas** with their own names, periods, limits/usage/remaining and relevant reset/availability notes. This is a substantive reason to keep the cue when a subscription has multiple quotas.
- Separate **Primary quota** and **Additional quotas** with a blank line; give each secondary quota its own compact line/group. Include a short distinction between native quota and the reference **CCost used in the period** where necessary. Show only values actually provided by the existing account view; no inferred quota capacities, made-up percentages, arbitrary new account polling or other new source acquisition.
- Prefer useful actual data over a long disclaimer stack. Include actionable restricted/unavailable/partial/retained notes only when relevant. **Do not show internal timestamp logs, raw observation source enums or `Last quota update`.**
- If an account exposes nothing beyond what its row already says, the implementer may omit its optional `?`; **never add several `?` to one subscription**. No new tooltips on progress bars solely to restate usage.

## 2. Full Web Watch: concrete consolidation and placement fixes — mandatory

### 2.1 Remove prompt-preview question marks from both prompt tables

In both **Running Prompts** and **Earlier Prompts**, **remove the per-row `?` next to the prompt preview** that reveals the complete prompt text.

- The owner considers full prompt text low-value in this compact live-monitoring context. An especially poor case is a short, entirely visible preview whose `?` simply repeats the same text.
- **Prefer removing this cue altogether**, not merely conditionally hiding it when the preview fits. Preserve the existing visible preview, truncation behavior, readable/accessible prompt identification, and ordinary navigation; no surprise full-text popup.
- Source pointer: `src/web/assets/watch.js::Card.update()` builds `watch-prompt-preview` and calls `ContextHelp.beside(label, prompt.preview ...)`. Audit Running and Earlier rows.

### 2.2 Move the daily summary help to the far right and explain the *whole card*

The full Watch daily overview above the subscription cards displays **CCost Today, today's prompt count, and Token Mix %**. Today its `?` is inserted beside the **prompt count, between the metrics**, and explains only the number of prompts. This placement and narrow subject are confusing.

- **Remove the mid-card prompt-count `?`. Replace with one purposeful help cue at the **far right of the entire daily summary/card** (adapt responsive placement only as needed to avoid overlap). Its scope is the **whole daily summary**, not merely prompt count.
- Use compact, clear, visually separated lines covering **CCost Today** (reference estimate, not billing), **today's prompt count** (daily scope, not just visible running rows), and **Token Mix %** (token-share breakdown, not cost). Give Token Mix a brief plain-language explanation, with **I/C/W/O** definitions only to the extent genuinely useful; avoid repeating the full dense table-header tooltip or dumping internals. Example structure, not mandated copy:

  ```text
  CCost Today — Estimated reference cost for today's prompts.
  Prompts — Count of prompts with model activity today.

  Token Mix % — How tokens are split between input,
  reused input, cache write and output.
  ```
- The same cue should work on mouse, keyboard and touch, remain right-aligned in the intended layout, and not cause clipping or unstable reflow at narrow/zoomed widths. Retain accurate daily scope, categories, partial/unknown reporting and underlying data. Source pointer: `src/web/assets/watch.js::daily()`, current `ContextHelp.beside(count, ...)`.

### 2.3 Look for other full Watch help that repeats itself or sits in the wrong place

Perform a purposeful audit of other **Running/Earlier column heads, row icons, session summary, account/subscription cards and quota/reset cues**. Keep a cue if it explains a non-obvious metric, meaningful price warning, actual date, quota scope or otherwise valuable detail. Remove, consolidate or reposition cues that:

- duplicate visible text or nearby column-header help;
- put a help icon between unrelated values or next to the wrong subject;
- repeatedly explain the same disclaimer or offer little more than a trivially longer copy of a visible field;
- make a small/dense card harder to scan.

The implementer should exercise independent UX judgment and record major **kept / removed / consolidated / repositioned** choices. This audit does **not** authorize removing important warnings, useful full local timestamps, native quota reset information or accurate metric caveats just to minimize the icon count.

## 3. Across Web: strip internal freshness logs and rewrite remaining tooltips

- Remove developer-style default help such as **`Last prompt update`**, **`Last quota update`**, **`Last daily observation`**, `Connection: … / Source: … / prompts: …` and equivalent continually ticking observation timestamps/status dumps. Inspect all applicable Web/Mini surfaces, especially `src/web/assets/mini.js::View.update(), drawDaily(), drawPrompts(), drawHistory(), drawSession(), drawAccounts()`. Don't move the same noise into a different tooltip.
- Keep **user-meaningful** status: live versus retained/not current, partial pricing and real N/A, estimated context, unavailable/blocked quota, lost authorization, and true failure warnings. A visible error is not made optional just because its internal details are removed. **Actual user dates** (prompt start/finish, quota reset) are valuable and not equivalent to observation/polling timestamps.
- Rewrite long remaining explanatory text into crisp plain English: lead with the user question answered; use **one sentence** for a simple idea, or **short named lines and occasional blank lines** to separate multiple concepts. Preserve the especially good **CCost (I + E)** formatting style and the quick custom help component from FR000582. Avoid generic dense paragraphs, internal jargon and redundant disclaimers; don't force extra blank lines into single-sentence help.
- Review all tooltip-bearing Web views, not solely literal occurrences of `ContextHelp` or these named examples. Prefer consistent semantic placement and scope to mechanical deletion; keep valuable column headings. Retain the accurate distinction between prompt/session/day CCost, native quota, model/subagents, input/next context, token shares and real vs partial/unknown values.
- Reuse the **one existing contextual-help system** and preserve accessible hover/focus/touch/keyboard semantics. No new second tooltip framework, avoid duplicate native `title` help, and don't turn selectable data into help-only controls.

## Acceptance criteria and verification

1. **Mini visual policy:** no header `?` for CCost Today or observation times; no row `?` beside Session, prompt `#`, status or Earlier Ctx; no table-level substitute `?`; no tooltip on Earlier Sessions. The only optional stand-alone Mini `?` is at most **one per subscription**, where useful. Column-heading and Cost Guard · Watch action help continue to work.
2. **Mini combined heading:** Session / (Total CCost) tooltip clearly has **two labeled explanations separated by a blank line**, in both Mini tables, with accurate whole-session versus per-prompt CCost scope. Other Mini column-head tooltips are concise, accurate and readable.
3. **Return-to-Watch bug:** hover/focus then activate Cost Guard · Watch by mouse, touch and keyboard. The action works and its tooltip dismisses immediately; stationary pointer/focus, tab switching and Mini Live updates do not reopen it until deliberate new help interaction. Earlier Sessions expands/collapses with no help popover to stick.
4. **Subscription value:** when secondary quotas exist in current view data, the optional account cue explains **primary versus secondary** quotas and real period/usage/reset details concisely, with readable spacing. Multiple quotas are not conflated or fabricated; when no added information exists, omitting the cue is acceptable. No raw `Last quota update`.
5. **Full Watch prompt table:** per-row full-prompt-preview `?` is absent in both Running and Earlier rows, regardless of preview length. Visible preview, accessibility, row state, truncation/selection and navigation remain correct.
6. **Daily card:** exactly one intentional daily-summary `?` at the **far-right**, not between prompt count and Token Mix. It explains CCost Today, prompt count and Token Mix with concise, human-readable grouping. Check layout at normal/narrow/zoomed widths.
7. **Whole-app UX audit:** assess remaining tooltips for unnecessary/duplicative/poorly positioned `?`, adjust actual problem cases, record the rationale for the key dispositions, and make dense copy shorter with purposeful whitespace. Preserve helpful table-header guidance and FR000582's fast custom tooltip behavior.
8. **Correctness and regressions:** remove internal `Last prompt update`, `Last quota update`, `Last daily observation`/equivalent logs from default help without losing actionable outages, exact real user timestamps, resets, partial/estimated/unknown semantics, accessible labels or accurate CCost/token/quota scope. Test both Mini tables, multiple prompts, subscriptions with zero/one/multiple quota periods, long session names, live rerenders, collapsed/expanded Earlier, actual Document PiP, mouse/touch/keyboard, Escape, focus and pointer transfer, Classic/Web light/dark, CCost units, viewport clamping, selection, sticky headers, and no native title duplication.
9. Add focused deterministic/browser regressions (notably `development/tests/integration/web_help.cjs`, `probe_web_help.cjs`, `probe_mini_sessions.cjs` and relevant Watch tests) and update `development/architecture/modules/web-help.md` and current Web/Mini user docs when implementing. Verify in the actual browser/PiP where the interaction was observed.

**Relationship to other work:** build on completed **FR000582** while narrowing its tooltip density. Coordinate with Ready **FR000583** (Mini resize and the parenthesized Session/Total CCost header), **FR000585** (quota presentation/period capacity), and **FR000586** (quiet transient full Watch statuses). Review current source after preceding Ready tasks land; this FR's explicit UX policy remains the owner's intended outcome.

**Out of scope:** new account/source polling, cost calculation or attribution changes, rewriting quota semantics, CLI changes, hiding real errors, custom PiP window chrome, a new global help framework, and product implementation/version/release work in this authoring session.
