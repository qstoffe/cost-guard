# FR 000603 — Mini Watch: compact Activity time before Earlier Sessions names

**Owner-approved Ready Feature Request, 2026-11-06.** Permanent identity **000603**; queue priority **000220** (after the existing Ready items, including FR000591 on Mini Watch fit/click sizing and FR000597/598/599). This is a **Mini Watch Earlier Sessions presentation change only**. The running/recent prompt table must remain unchanged.

## Owner request and visible result

In the compact Document Picture-in-Picture **Mini Watch**, the expandable **Earlier Sessions** table currently has **Session (Total CCost)** and **Ctx**. Add a narrow, separate **Activity** column as its **first** column, before the existing combined session-name/whole-session-cost cell. Use just a **24-hour local time in `HH:mm`** for every historical session with a known finish time; hovering/focusing the time shows the **full local date and time**. Do not show the full date in the ordinary table cell because the goal is to conserve space.

Required visible layout, **Earlier Sessions only**:

```text
Activity   Session      (Total CCost)        Ctx
-------------------------------------------------
22:41      Completed work A  (123)          85K
00:08      Completed work B  (456)          91K
```

The existing Session and (Total CCost) labels and values **remain in their shared existing column**, including the current ellipsized title, right-aligned visible total, partial/source notes and full-session vs prompt-cost meaning. Ctx remains the final column. No prompt-number, duration, status, sorting or extra columns are requested.

**Running/recently ended prompts must remain exactly the existing five columns**: Session (Total CCost), #, CCost, Duration, Ctx. Never add Activity to that table, its rows, its accessible structure or its default sizing assumptions.

## Time source and semantics

- **Activity means the time the historical session last finished its canonical representative prompt**, not the latest browser update, source refresh, first prompt start, currently running elapsed time or the OS clock. This is the existing authoritative *finished* timestamp used to select and display Earlier Sessions; do not invent a separate last-activity estimator or reorder the sessions.
- The current Live projection already exposes `history_cards[*].rows[*].prompt.completed_at_ms`, `display.finished_clock` and `display.finished_date_time`. **Reuse these existing server-prepared presentation tokens** for the representative historical row (the same row that drives earlier-session completion semantics), rather than reformatting UTC independently in Mini JavaScript or adding another backend fetch. The display uses Cost Guard's configured local timezone; on the current Swedish setup this is Europe/Stockholm. Do not mistake viewer UTC or the JavaScript runtime's unrelated timezone for the configured local wall clock.
- Visible time is exactly `HH:mm`, e.g. `08:05` or `23:47` — always zero-padded, 24-hour format, with **no seconds, date, AM/PM or offset in the cell**.
- On hover/focus (and existing touch/keyboard affordances) show the **full `YYYY-MM-DD HH:mm` with timezone offset** using the already provided `finished_date_time` token (e.g. `2026-11-06 00:08 +0100`). The offset differentiates repeated local hours at daylight-saving-time transitions. Reuse existing shared `ContextHelp` semantics (current approximately 600-ms pointer delay; accessible focus/touch support), not a browser-native `title`, new icon, row-wide hover target or permanent explanatory text.
- The **Activity header** may use the existing compact header help to explain that the time is the session's *latest supported finish*, and that the full local date is available on the value. Do not rename the column `Last Activity` or expand its width with a long label.
- If there is **no trustworthy finished timestamp** (including an eligible historical session with unknown ending or missing representative row), display a compact `—`/existing unknown-finish token. The tooltip/accessible description must **not pretend that the last observed activity is a known finish**. A short `Unknown finish time` accessible explanation is appropriate; do not fabricate zero or a current-time fallback. Preserve existing history membership, unknown-finish ordering and retained/partial evidence behavior.
- Do not change the selected newest-three history policy, oldest-to-newest display order, recently ended grace, running/history deduplication or the state transition when a session resumes. An updated authentic historical finish must update that same row and its tooltip; source retries must not advance the clock.

## Layout and technical constraints

- Maintain narrow intrinsic width for Activity (header and five-character clock), tabular numerals, **no wrapping** or overly generous fixed widths, and consistent heading/cell alignment.
- The session name/title receives the remaining elastic width; total CCost stays visible at its natural width, and Ctx stays readable. At normal Mini Watch width, **including the planned roughly 650-DIP opening width from FR000591**, the new column must not introduce unnecessary horizontal or vertical scrolling, truncate whole-session costs, or break the earlier expansion/collapse height calculation. When genuinely too narrow, preserve the existing accessible horizontal overflow behavior rather than squashing or hiding data.
- Implement the historical-only third column through the existing `src/web/assets/mini.js` table/row construction and `src/web/assets/mini.css` rather than changing the shared running table assumptions. In particular, account for the fact that historical Session moves from column index 0 to index 1: update historical row creation, draw/empty-row colspan, header help, CSS first-column selectors, focus semantics and accessibility without changing the running table's indices.
- No new acquisition, source scan, timer, persisted setting, schema extension, provider call, pricing valuation, Web route or Watch page redesign. The historical time tokens are already in the retained Live publication. Coordinate visually with whichever FR000591/FR000597 source has reached `main` when implemented, but **do not block on unrelated future items**.

## Acceptance and verification

1. Mini Watch **Earlier Sessions** expanded: heading order precisely **Activity | Session (Total CCost) | Ctx**; each genuine finished row shows the supported local `HH:mm` in the new first column. The running/recent prompt table remains **five columns and byte-for-byte equivalent displayed semantics**.
2. Value tooltip shows the correct **full date, local clock and offset**, no native duplicate; keyboard focus and touch reveal equivalent information. Header explains the finish-time meaning without widening the column.
3. Test multiple finished sessions crossing midnight, non-hour-aligned local times, Swedish DST fall-back with two different instants both displaying `02:30` but distinguishable full tooltips with `+0200` vs `+0100`, and unavailable/null completed timestamps displaying a truthful unknown. Use existing server `finished_clock`/`finished_date_time` tokens, not browser-derived or current time.
4. Preserve the newest up-to-three eligible history cards, oldest-to-newest order, retained/partial truth, running/history exclusion, live updates, key/DOM identity, and Earlier expand/collapse without misplaced row labels, missing Ctx or misaligned CCost. Empty/loading/unavailable history uses the **correct three-column span**.
5. Verify real layout at default nominal Mini width and narrow PiP conditions, Classic/Web light/dark, keyboard focus, zoom and when three Earlier rows expand, using focused DOM and real browser fixtures. Ensure that the added narrow Activity column doesn't cause unexpected scrollbars under FR000591's click-fit/collapse rules. Distinguish headless from untested physical desktop behavior.
6. Update `docs/web-mini-watch.md` and the existing relevant Mini tests (e.g. `development/tests/test_mini_watch.py`, `development/tests/integration/mini_watch.cjs`, `development/tests/fixtures/mini_sessions.cjs`, and `probe_mini_sessions.cjs` as applicable). Preserve no-change scope for full Watch, CCost/Ctx calculation, CLI and web settings. Run appropriate product/packaging checks only when implementing.

**Publication boundary:** create this Ready FR and increment `development/backlog/identity-state.json` high watermark from **602** to **603**. No implementation, tests, product source, release/version or completion state is changed by this FR authoring.
