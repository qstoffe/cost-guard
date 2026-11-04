# FR 000583 — Mini Watch: resize on Earlier Sessions, parenthesize session CCost, and silence transient Watch refresh labels

## Owner request and backlog decision

**Owner-approved executable feature request, 2026-11-04.** Permanent identity **000583**; Ready priority **000230**, after the existing Ready FR000582 (000220).

The owner requests three focused presentation improvements in **Cost Guard Web Beta**:

1. **Mini Watch / Earlier Sessions:** on explicit expansion, grow the *existing* Document Picture-in-Picture (PiP) window **only when expanding Earlier Sessions introduces a new vertical session scrollbar**, if the browser supports it. On collapse, try to restore the window's **pre-expansion dimensions** so the window does not keep occupying extra space.
2. **Mini Watch / both session tables:** retain FR000578's left/right alignment and flexible truncation, but remove the visible pipe. Display **`(Total CCost)`** at the right of the first-column header and **`(<session total>)`** at the right of each session cell.
3. **Full Web Watch / Running Prompts:** remove brief, blinking **Refreshing/Retrying prompt refresh** messages and **`(refreshing; retained total)`** text. Ordinary fast refresh should keep valid existing figures visible quietly; a real sustained failure must still be truthfully communicated.

This FR is an approved backlog entry **only**. Do not implement source, tests, docs or release changes in the authoring session.

## 1. Mini Watch: event-driven window sizing for Earlier Sessions

### Intended user experience

- A fresh Mini window initially opens with its **existing placement/size rules** (normally 560 × 250 screen DIPs) and Earlier Sessions collapsed.
- **Click/tap or keyboard-activate** Earlier Sessions. Compare the session region **before and after disclosure**. If it previously had **no vertical scrollbar**, and expansion **would introduce one solely because the extra Earlier Sessions rows do not fit**, attempt to grow the *currently open* PiP window **vertically only** just enough to show the session table content without that new vertical scrollbar. Retain a modest safety margin where needed for headers/borders.
- If opening Earlier Sessions already fits, **do not resize**. If there was already a vertical scrollbar before expansion, **do not automatically enlarge** on this rule. Horizontal scrollbar/panning on a narrow width alone is not a reason to grow the window.
- On collapsing Earlier Sessions **after a successful automatic enlargement**, attempt to return to the **exact dimensions immediately before that expansion**. Prefer this predictable pre-expansion size over calculating a new minimal window size. If no automatic enlargement occurred, don't resize on collapse.
- The request is **one user-triggered adjustment per disclosure transition**, not continuous content-driven auto-fitting during every Live/SSE update. New data, a refresh, incoming history, day changes or ordinary re-renders must never repeatedly resize or move the window.
- Protect the user's manual window choices: do **not** shrink to stale stored dimensions if the user resized the PiP manually between expansion and collapse. Treat manual resize as user intent and clear/reconcile pending auto-restore. Use only ephemeral state for the current PiP opening; no new persisted geometry/configuration or stealth browser-storage write.
- Do **not** change the width or force a new native window position. Do not close/reopen PiP to fake resizing, disrupt focus, move the main browser, or override the native window controls. If the OS/browser clamps the requested height, keep usable scrollbars and don't enter a repeated attempt loop.
- **Earlier Sessions remains a normal accessible disclosure**, starts collapsed, preserves its state through routine updates and shares one vertical sessions viewport. Subscription/account scrolling remains independent. Preserve sticky table headings, row ellipses, full metric values, focus/keyboard/touch and normal browser PiP close/reopen behavior.

### Technical feasibility and required proof

**This is plausible but browser-dependent.** Chrome's Document Picture-in-Picture guidance explicitly supports calling the PiP Window's `resizeBy()` / `resizeTo()` since **Chrome 121**, and states both require **a user gesture**: https://developer.chrome.com/docs/web-platform/document-picture-in-picture#resize_the_pip_window . The actual **Earlier Sessions activation** provides the necessary user gesture if the measurement and resize attempt occur directly in the trusted click/keyboard event; an unrelated timer, SSE event or asynchronous later continuation cannot be assumed to retain activation.

The current `src/web/assets/mini.js` disclosure listener only flips `this.earlier.hidden` and `aria-expanded`; the PiP is opened with `documentPictureInPicture.requestWindow({width: 560, height: 250, ...})`. The current `src/web/assets/mini.css` also caps `.mini-prompts` at **`max-height: 10.8rem`**, with `overflow: auto` and constrained flex sizing. **Merely enlarging the native window may not remove its scrollbar**: implement a bounded layout mode that can actually use the added vertical space when history is expanded, while leaving the normal compact/collapsed layout, independent account scroll and manual resize behavior intact.

Plan for safe measurement of natural/required session content height versus existing viewport, CSS height constraints, header/other regions and the actual post-resize `innerHeight`/`outerHeight` (screen-DIP/CSS scaling differences). Record the **pre-expansion outer bounds** and the actually achieved auto-resized bounds. Never assume a successful `resizeTo` call means the size changed; verify with the window's resize event/measured bounds and avoid resize-observer loops.

Check Chrome **and supported Edge/Chromium** in an actual Document PiP browser environment, including keyboard activation. Where window resize is unsupported, refused by user-activation policy, or clamped by the work area/OS, **fall back silently to the existing scrollable sessions region**; there must be no fake success or broken disclosure. Position is browser-owned and may move as a side effect of native constraints; do not assert exact coordinates that JavaScript cannot guarantee.

Compatibility with **Settings → Mini Watch placement** (Default/Remember last/Standard) is mandatory: the user's existing selected placement mode controls initial opening, not temporary disclosure expansion. A collapse that restores the pre-expand size must not erase a manual choice or alter the persistent mode. Don't introduce a separate auto-resize setting for this FR.

## 2. Mini Watch: replace pipe suffix with parentheses, preserve alignment

The recently implemented FR000578 aligns session title/heading left and total-cost suffix right *inside one physical first column*, e.g. `Session    | Total CCost` and `Short name    | 328`. The owner likes the alignment but not the pipe.

**New exact visible treatment (both Running Prompts and expanded Earlier Sessions):**

```text
Session                           (Total CCost)
A very long session title th…             (4582)
Short name                                  (328)
```

- Display the left header label **`Session`** and the nonshrinking right suffix **`(Total CCost)`**. Do not include `|` or `/` as an alternative separator.
- For each first-column cell, display the actual session title left and its whole-session cost **in parentheses** at the far right, e.g. **`(328)`**, with the existing Credits/USD and truthful `N/A`, zero, partial and Loading formats.
- **Keep the current exact alignment behavior**: one physical first column, two internal independently aligned regions; short session titles stay left, right-hand suffix stays at the right edge; long titles alone get end-ellipsis. Never reserve a separate header-width physical cost column or truncate the suffix/cost.
- Preserve complete title/meaning in accessible focus/hover tooltip, the distinction between *whole-session* cost and the separate per-prompt CCost column, the existing row/grid sizing/scrolling, themed surfaces and tooltip UX (coordinate with queued **FR000579** and **FR000582**). Update descriptive prose and tests that currently expect a pipe.
- Do not alter displayed account/CCost Today, model, context (including the queued `Ctx` casing of **FR000581**), Duration, prompt number or histories.

## 3. Full Watch: no fleeting Refreshing text in Running Prompts

A short-lived refresh status currently flashes on/under running prompt cards. **Remove this visible flicker entirely** during routine refresh, while retaining actual last known measurements.

Current code inspection identifies **two likely visible sources** in `src/web/assets/watch.js`:

- `Card.update()`: `this.message` can show **`Retrying prompt refresh; retained contents are not current.`** when `value.state === 'retrying'`.
- `Card.drawSummary()`: the session-cost suffix can show **`(refreshing; retained total)`** when `session_summary.state === 'refreshing'`.

The implementation must reproduce the user's observed flash and check both pathways (plus any equivalent prompt-card refresh message) rather than guessing just one. Requirements:

1. When a valid previous prompt/session observation is present, keep the previous values visible and stable while a new read/aggregation runs, with **no temporary `Refreshing`, `Retrying prompt refresh`, spinner, badge, placeholder or line-height shift** in the Running Prompts area. Publish revised values when coherent data arrives.
2. Do not show **`(refreshing; retained total)`** beside already known session CCost during routine update. Avoid transient visible updates of the equivalent status in Earlier Prompts cards if the same component shares that path.
3. **Do not lie about source health.** A persistent real source failure, expired authorization, missing evidence, genuinely partial/unavailable observation or lengthy outage must still have clear, appropriately delayed/meaningful status via the existing app's health/connection treatment. A normal quick refresh is not a warning. If a real source read fails and old values are retained, preserve truthful stale/failure help or visible guidance once warranted; do not just claim that old data is live.
4. No change to actual prompt lifecycle/terminal grace, timing, source states, CCost caching/valuation, SSE behavior, interval, ownership, server API semantics, token/context/warning figures or the existing user's data.
5. Coordinate with queued **FR000580**'s reworked `Session Context / CCost` summary and **FR000582**'s simplified help; the finished UI must not reintroduce noisy refresh copy while applying either design.

## Acceptance and regression checks

1. **Mini disclosure sizing:** with no session scrollbar while collapsed and an expanded 1–3 Earlier Sessions set that would overflow, supported Chrome/Edge Document PiP attempts an immediate **height-only** increase from the user's actual current size. After a successful resize, all session rows fit without the new vertical scrollbar where screen space allows. Verify both regular pointer click and keyboard activation, and measure actual before/after PiP outer/inner geometry, not merely CSS client sizes.
2. **No unnecessary resizing:** if expansion already fits, or the region was already vertically scrollable, the native window stays its original size. Horizontal-only overflow never triggers height expansion. Routine SSE updates and account changes never trigger a window resize.
3. **Restore:** collapsing after auto-expansion returns near/exactly to the pre-expansion bounds (within browser-controlled rounding/clamps); no spurious shrink if it didn't expand. Manual user resize while expanded wins, so collapsing doesn't override the user's choice. Repeated expand/collapse does not accumulate rounding drift or oscillation.
4. **Graceful fallback:** simulate a blocked resize, unsupported method, missing user activation, OS work-area clamping and short display: disclosure still works, the existing independent session scrollbar remains usable and sticky headings/values are readable; no reopen or error loop. Document any platform-specific limits based on actual evidence.
5. **Parentheses:** both Mini tables show `Session` left / `(Total CCost)` right, and titles left / `(<whole-session value>)` right. Zero, N/A, partial pricing and long title values are covered; no visible pipe or slash, no loss of ellipsis/accessible full title, no extra table column or layout regression.
6. **Quiet Watch:** repeatedly exercise a running card through routine prompt refresh, revaluation and an existing session cost becoming `refreshing`. The displayed CCost remains stable; no `Refreshing` or `Retrying prompt refresh` copy flashes or causes height changes. A sustained true outage/missing data remains discoverable by the correct existing health/availability surface.
7. **Cross-view/theme and documentation:** regression-check Classic, Web light/dark, unit changes and normal/narrow PiP; manual vs standard/remember-last placement; opening/closing Earlier Sessions, pagination-like history entry, active prompts, focus, keyboard/touch; no extra SSE, provider call, background history scan or persisted browser geometry. Update current `docs/web-mini-watch.md` and `docs/web-beta.md`, plus focused integration/real-browser evidence after implementation. Preserve historical completed FR artifacts.

**Out of scope:** changing the default 560×250 DIP opening size, auto-growing Mini for arbitrary live content, allowing the app to set arbitrary PiP screen position, implementing a custom window manager, removing genuine error states, changing metrics or pricing, changing CLI, and implementation/version/release work in this authoring session.
