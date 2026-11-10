# FR 000671 — Mini Watch: show a play symbol before Activity time only for running prompts

**Owner-approved minor Ready Feature Request, 2026-11-10.** Permanent identity **000671**; Ready priority **001060**, following the existing queue. **FR-only publication:** add this one FR and atomically advance `development/backlog/identity-state.json` highWatermark **670 → 671** in one direct-`main` documentation commit. Do not implement product code, run product tests, or modify releases, versions or unrelated backlog files during authoring.

## Requested UI change

In **Cost Guard Web → Mini Watch** (Document Picture-in-Picture), put a small, simple, right-pointing **play triangle `▶`** immediately **before the existing Activity start time** for a **genuinely running prompt**, with a little spacing:

```text
Activity
▶ 12:34     (running prompt)
  12:34     (completed/aborted/ended prompt)
```

The icon is **a passive running-status indicator**, not a play/pause control. Prefer a plain text/Unicode glyph (or equivalently compact existing local presentation), without an icon package, animation, button or tooltip of its own. Keep the existing time, row color, layout, and Activity hover/focus/touch help.

## Exact visibility and lifecycle

1. Show `▶` **only for the prompt that is actually in progress**, using the established canonical `prompt.in_progress` and verified lifecycle status. Do not equate membership in the running selection with proven execution: `execution_unverified`, aborted, errored, completed or historical-only prompts must **not** acquire a false play symbol.
2. **Remove it immediately on a real terminal transition**, including success (green terminal grace), abort/failure (red grace), and subsequent normal/white history. No symbol persists because the same keyed row stays mounted or because a stale presentation update arrives. If a new prompt actually starts in the same session, show the symbol on its own running Activity cell, but not on the old terminal prompt.
3. The symbol precedes the existing **start time** while running; when finished, Activity uses the established **finish time**. Unknown time (e.g. `—`) retains truthful existing behavior; no invented time or repeated start/finish label.
4. Keep `▶` visually compact and aligned with the time, ideally using existing room inside Activity. **Do not widen the table/PiP unnecessarily**, change the five-column layout, force a new minimum native window width, change automatic Fit-on-open measurements just to accommodate this symbol, or cause time wrapping/clipping at narrow widths. If a few pixels are genuinely necessary, make the smallest responsive adjustment consistent with existing metric-column sizing.
5. Keep the visual decoration accessible without duplicating status: the row already has an outcome label such as `Running` in its `aria-label`. If the triangle is a separate element, mark it decorative for assistive technology. Preserve the time cell's existing full local date/offset help, focus, hover and touch behavior; do not introduce an independent focus stop.

## Verified existing implementation (not yet modified)

- `src/web/assets/mini.js::View.sessionRow()` creates the existing Activity `span.mini-activity`; `View.drawSessions()` sets its text from `prompt.display.clock` for running or `finished_clock` for ended rows, and applies `mini-running`, `mini-success`, `mini-error` or neutral styling based on prompt lifecycle.
- `src/web/assets/mini.css` already has compact, nowrap tabular Activity styling and color rules for running/success/error. Reuse this presentation rather than adding a new status column or restructuring row selection.
- The existing `running` selection in Mini also covers execution-unverified states, but the row does not mark those unverified outcomes as genuine running. Use the **verified running status** for the new icon.

## Acceptance and checks at implementation time

- For a current verified `in_progress` prompt with `12:34` Activity, display **`▶ 12:34`**. On `completed_successfully`, `aborted` or `has_error`, the symbol disappears in that very update, while correct success/error color and the existing terminal Activity time remain. It stays absent as the terminal highlight expires and in historical-only rows.
- Test execution-unverified, unknown start/finish, multiple simultaneous running sessions, active-to-terminal transition, rapid next prompt in the same session, a different session inheriting/reusing a row, source correction and repeated SSE/timer updates. No wrong retained `▶` or false running signal.
- Verify Mini's column width, sticky header/time alignment, selection, Activity tooltip/keyboard focus, Classic/Web light/dark and narrow/zoomed PiP; no extra control, animation or unnecessary window resizing.
- Extend existing focused Mini fixtures/browser regression tests (e.g. `development/tests/fixtures/mini_sessions.cjs`, `development/tests/integration/mini_watch.cjs` and relevant `probe_mini_sessions.cjs`) and update `docs/web-mini-watch.md` if needed. Run applicable checks **when implementing**, not in this documentation-only commit.

**End state:** A small `▶` before Activity immediately identifies genuinely running Mini Watch prompts and disappears as soon as the prompt is no longer running, without changing how the rest of Mini Watch behaves.
