# FR 000672 — Mini Watch: compact relative Activity age labels

**Owner-approved minor Ready Feature Request, 2026-11-10.** Permanent identity **000672**, Ready priority **001070**, following the current Ready queue. **FR-only publication:** add this file and increment `development/backlog/identity-state.json` highWatermark **671 → 672** in the same documentation-only `main` commit. No product changes, tests, releases or unrelated backlog edits during publication.

## Goal and display contract

In **Cost Guard Web → Mini Watch**, the **Activity** cell currently shows the configured-local clock time of a running prompt's **start**, or of an ended prompt's supported **finish**. Preserve the existing clock for recent activity, and use an abbreviated elapsed age for older activity.

**Every abbreviated unit must be lowercase**, matching the compact styling elsewhere: `h` = hours, `d` = days, **`m` = months (not minutes)**, `y` = years. Always use **one space followed by `ago`**: `13h ago`, `1d ago`, `1m ago`, `1y ago`. Never use capital D/M/Y.

Apply these rules in order, with integer **floor** (truncate fractions, never round to nearest or use ceiling):

1. **Clock `HH:mm`:** When the event is **on today's configured-local calendar date OR strictly less than 12 elapsed hours ago**, retain the existing clock value. A prompt from yesterday at 23:59 therefore keeps `HH:mm` during the first 12 hours after its event, even after crossing midnight. Today's prompt retains `HH:mm` even if it is 20+ hours old.
2. **Hours:** Once neither clock condition holds, for ages from **12h to under 24h** show floored hours: `12h ago`, `13h ago`, … `23h ago`.
3. **Days:** From **24h to under 30 elapsed days** show floored elapsed days: `1d ago` for [24h,48h), `2d ago` for [48h,72h), etc.
4. **Months:** From **30 elapsed days up to under 365 elapsed days**, show floored **30-day elapsed-time buckets**: `1m ago` starting at day 30, `2m ago` at day 60, and `12m ago` for days 360–364. Use fixed 30-day buckets, not varying calendar-month lengths.
5. **Years:** At **365 elapsed days or more**, switch to floored **365-day elapsed-time buckets**: `1y ago` at day 365, `2y ago` at day 730, etc.

Examples below are synthetic, not real user-session traces:

| Case | Visible Activity |
| --- | --- |
| Same local calendar day, even 20 hours earlier | `HH:mm` |
| Previous day, age 11h 59m | `HH:mm` |
| Previous day, exactly 12h | `12h ago` |
| Previous day, 13h 55m | `13h ago` |
| Other date, 23h 59m | `23h ago` |
| 24h to under 48h | `1d ago` |
| Exactly 48h | `2d ago` |
| Exactly 30 days | `1m ago` |
| Exactly 60 days | `2m ago` |
| Exactly 365 days | `1y ago` |

**Do not filter out old history.** The owner explicitly rejects a limit at 100 days. Keep showing all otherwise eligible running and historical rows, filling the established up-to-five historical session slots even with very old sessions. This FR changes presentation only, not membership, history ranking, acquisition or visibility caps.

## Existing code and coordination

- In `src/web/assets/mini.js::View.drawSessions()`, Activity already uses `prompt.at_ms` (running/execution-unverified) or `prompt.completed_at_ms` (ended) to choose the established server-prepared `prompt.display.clock` or `finished_clock`. Calculate relative age from **that exact absolute timestamp**, not from a formatted clock, last poll, a newer prompt or a source observation timestamp.
- The existing `MiniWatch.Controller` presentation loop calls `render()` every **5 seconds** while the PiP is open. Recompute relative-age labels on this already existing timer so the display crosses 12h/24h/30d/365d thresholds even without an SSE/Live event. **Do not add** another timer, browser fetch, source scan or data owner.
- The **calendar-day condition must follow Cost Guard's configured timezone**, not necessarily the browser/OS timezone. Use existing prepared local date/time or a safe narrow timezone-aware helper. Elapsed time is an **absolute difference in milliseconds**, independent of DST. Check fall-back repeated clock hours and spring-forward transitions; do not mistake a timezone offset change for an elapsed hour.
- Keep existing **full Activity value tooltip** giving configured-local exact date, time and UTC offset when the visible value is relative. Preserve focused/hover/touch help and the truthful `—` / unknown-time state where no supported event timestamp exists. Never fabricate `0h ago` for missing times or negative `ago` for future/inconsistent source time. Adjust the **Activity header help** to explain the rule succinctly.
- **Compatibility with Ready FR000671:** it adds a passive `▶` preceding Activity only for genuinely running prompts. Preserve the prefix with whichever format is currently valid (`▶ 12:34` or `▶ 13h ago`); remove it at completion/abort/error. No icon for historical, terminal or execution-unverified data. Do not implement/rewrite FR000671 during this FR's backlog publication.
- Keep the five-column table, established colors/status, keys, accessible row meaning, and Mini window width/height policy. Age tokens must remain on one line and fit compactly without unnecessary native resizing, wrapping, clipping or changing unrelated CCost/Total/Ctx behavior.

## Acceptance criteria at implementation time

1. Synthetic fixed-clock boundary tests cover **same day OR age under 12h**, exact 12h, local midnight, 23:59:59→24:00:00, 47:59:59→48:00:00, 29d→30d, 59d→60d, 364d→365d and 729d→730d. Assert **floor** and consistent **lowercase `h/d/m/y`** with exactly one space before `ago`.
2. Verify timezone mismatch (configured vs browser), DST transitions including repeated 02:30 with differing UTC offsets, and genuine missing/future time. Both clock and relative Activity values preserve the full date/offset tooltip.
3. Keep even 100+ day or multi-year old eligible sessions in Earlier without losing any of the normally selected historical rows. Test running, green finished-grace, red aborted/error, neutral history and resumed sessions.
4. Without new source updates, advance a synthetic clock across an age threshold while the same Mini PiP remains open. Its existing 5-second render updates the label on the **same DOM row** without changing session membership or creating new fetches/timers; focused help stays correct.
5. Verify format and alignment with/without the FR000671 play icon in narrow/wide PiP, Classic/Web light/dark, keyboard/touch and zoom, with no unnecessary width growth.
6. Extend existing relevant tests (`development/tests/integration/probe_mini_activity.cjs`, Mini session fixtures and focused browser/VM tests). Update `docs/web-mini-watch.md` when implementing. Run product checks **during implementation**, not while publishing the FR.

**End state:** Same-day or under-12-hour Activity uses `HH:mm`; older activity uses concise lowercase `13h ago`, `1d ago`, `1m ago`, `1y ago` with exact-date help, no age exclusion and no new polling.
