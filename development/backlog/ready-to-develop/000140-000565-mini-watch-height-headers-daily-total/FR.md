# FR 000565 — Mini Watch opening height, centered table headers and Total Today in the title bar

## Owner request and scope

**Owner-approved executable feature request, 2026-11-03.** Permanent identity **000565**, Ready priority **000140**, after the currently Ready FR000562–FR000564. Scope: **Web Beta → Mini Watch** (the floating Document Picture-in-Picture window launched from Watch), not the ordinary full-size Watch page.

The owner requests three small but visible Mini Watch refinements:

1. On opening, the **entire Mini Watch window must be at most 500 pixels high**, counting the window itself rather than merely the HTML content area.
2. **Center every column header's text** in the Mini Watch prompt table, while retaining sensible different alignment for data cells.
3. In the header, keep the clickable **Cost Guard · Watch** return-to-Watch action left-aligned and show a compact **Total Today** summary right-aligned: today's global CCost followed by today's prompt count, e.g. **Total Today 6 152 · 106 prompts**.

This is a focused visual/layout and existing-data-presentation request. Do not replace Mini Watch's live, per-prompt or account calculations.

## Inspected baseline and dependencies

Reviewed the current `qstoffe/cost-guard` main source on 2026-11-03.

- `src/web/assets/mini.js::Controller.toggle` currently calls `documentPictureInPicture.requestWindow({width: 560, height: 450})`. This is a *requested* browser content/window size, **not proof** that the fully rendered outer window, including browser/OS-managed Picture-in-Picture chrome, is no taller than 500 pixels on the owner's machine.
- `src/web/assets/mini.js::View` currently creates a single clickable `mini-summary` header containing `Cost Guard · Watch`, followed by connection health, a five-column per-prompt table, and primary-account quota rows.
- `src/web/assets/mini.css` currently gives all `.mini-prompt-table th` `text-align: left`, with sticky headings and individually scrollable content regions. The columns are **Session | # | CCost | Duration | CTX**.
- The full Web Watch already renders **Total Today** from the canonical `view.daily_usage.total` (formatted with `ReportView.display(..., 'known_ccost')`) and `view.daily_usage.prompt_count` in `src/web/assets/watch.js::daily`. Its `daily_state` and pricing/completeness flags express loading, partial, retrying and unavailable data. Reuse **these exact scoped values and meanings**, not a Mini-specific sum.
- Completed **FR000561** owns Mini Watch's per-prompt/status table design and primary account rows; completed **FR000543** owns the global all-local-day Total Today semantics. Preserve their behavior. Other Ready FRs currently concern the full Watch quota cards, historical report and token-mix parity; avoid conflating these scopes.

## 1. Cap the initially opened *whole* Mini Watch window at 500 pixels

- Opening Mini Watch via its Watch-page control should result in an **initial total outer window height no greater than 500 CSS pixels at normal 100% browser zoom/display scale** on supported desktop configurations, including any native PiP chrome/title/controls that contribute to visible window height. The existing 450px `requestWindow` option does **not** by itself satisfy verification.
- Inspect the **actual displayed outer geometry** in a real supported browser, and adjust the requested height (or supported post-open sizing) to fit within this cap if the browser adds chrome. Do not confuse `document.body` height, `innerHeight`, and the browser/OS-controlled outer boundary. Where OS/browser-enforced minimums or sizing restrictions prevent exact control, document the observed behavior and limitation rather than claiming compliance from a CSS declaration.
- Keep Mini Watch's current practical width/readability and allow a user to resize the window manually afterward; **the 500px cap is specifically for the state immediately after opening**, not a request to fight later native manual resizing. Reopening should again use the capped initial size.
- If prompts, quota rows, long titles or health warnings exceed the available vertical area, preserve the existing independent scrolling and readable sticky headers; do not clip data, introduce an unusable tiny viewport, hide provider warnings or increase the outer height to fit content. Avoid horizontal overflow or unintended changes to the main Watch page.

## 2. Center the five column-heading labels, not the entire table

- In the Mini Watch per-prompt table, **all five `th` labels** — **Session, #, CCost, Duration, CTX** — should be horizontally centered within their respective header cells.
- **Data cells keep semantic alignment:** the Session/title text is **left-aligned**; prompt number and numerical CCost, Duration and CTX values are **right-aligned**. This applies to active/running and recently ended prompt rows and does not depend on status colors.
- Preserve the existing column order, sensible widths, sticky header, per-prompt scope, long-name truncation/full-name accessibility, row outcome colors, tooltips, responsive layout, independent prompt scrolling and focus behavior. Do not apply global table alignment rules that change normal Web Watch tables or subscription rows.

## 3. Add right-justified Total Today beside the clickable title

- Change the top area into a **left/right-aligned single header row at its usual Mini Watch width**. The left element remains the current actionable **Cost Guard · Watch** label, which returns/focuses the existing owner Watch tab. The right element is a **non-clickable**, right-justified daily summary ending near the Mini window's right content edge.
- Preferred compact text: **`Total Today 6 152 · 106 prompts`**, i.e. label, **global CCost today first**, and **number of prompts today second** with readable spacing. Use the application's established numeric grouping, precision and selected Credits/USD display unit; avoid adding duplicated "CCost" or "Estimated" labels unless needed for the already-established unit/uncertainty semantics.
- **Use the same canonical `view.daily_usage.total` and `view.daily_usage.prompt_count` that full Watch's Total Today section uses.** Daily scope is the configured local calendar day across all included sessions/accounts/providers and earlier pre-Watch activity, not currently running prompt CCost, the visible five Mini prompt rows, per-account quota-period CCost or Watch-open duration. Do not sum visible rows, count attempts twice or issue a new data query to populate the header.
- Keep the display honest on first load, no observed activity (a real **0** is valid), incomplete pricing, missing daily data, retry/offline/stale data, midnight rollover and later source corrections. Unknown CCost must not be shown as 0; use concise existing loading/unavailable/partial conventions and an accessible hint if needed. Do not let a stale value appear to be a fresh daily observation.
- The existing `mini-summary` click target and the daily metrics must be **separate elements**: clicking or keyboard-activating the daily metric must not unexpectedly navigate to the main Watch tab. Preserve the clickable title's accessible label and focus ring.
- At narrower manually resized window widths, keep the summary visibly and accessibly legible without overlapping the title or creating horizontal scrolling. Compact wrapping or an intentional responsive two-line arrangement is acceptable only when needed; the normal opening width should show both left and right content comfortably on one row. Maintain Classic, Web light/dark themes and user Credits/USD changes live.

## Acceptance criteria and verification

1. **Initial window cap:** in a real browser capable of Document Picture-in-Picture, opening Mini Watch results in a measured **whole-window outer height ≤ 500px** at normal desktop scale, including browser chrome where measurable. Verify open, close, reopen, native close, manual resize then reopen, long account lists and health messages. Report browser/OS and measured actual outer geometry; source `height: 450` alone is not a PASS. Document any browser-owned exception honestly.
2. **Table alignment:** each of the five header labels is centered within its own header cell; Session row values stay left, and #/CCost/Duration/CTX values stay right. Check ordinary, running, successful, aborted/error, empty, long-name and narrow-window rows. Preserve sticky headings and scroll behavior.
3. **Header example:** at normal Mini opening width, the title is left and the daily summary is aligned to the right: **Cost Guard · Watch** … **Total Today 6 152 · 106 prompts** (with actual fixture values). Only the left title navigates. The summary does not obstruct native PiP/window controls.
4. **Canonical parity:** use a fixture including prior activity outside the displayed Mini rows and multiple sessions/providers. The Mini daily CCost and prompt count **exactly agree in meaning and value** with the full Watch Total Today for the same publication and selected CCost unit; do not double-count. Check Credits/USD switching, real zero, partial pricing, loading, source unavailable/retry/staleness, update corrections and local-day rollover.
5. **Regression:** extend the existing Mini Watch DOM/integration tests (`development/tests/integration/mini_watch.cjs`, `development/tests/test_mini_watch.py` or the current relevant successors) and the appropriate live-publication tests. Add an actual browser geometry check where supported; JS/CSS unit tests alone cannot establish outer-window sizing. Preserve one shared Live/SSE data owner, existing independent health/account scrolling, the main Watch view, accessible focus and browser-controlled PiP lifecycle.

**Non-goals:** new CCost accounting, different daily attribution, an additional data source or EventSource, changes to full Watch's layout, altered subscription quota usage, a native desktop window or enforcing a height restriction against the user's subsequent manual resize.
