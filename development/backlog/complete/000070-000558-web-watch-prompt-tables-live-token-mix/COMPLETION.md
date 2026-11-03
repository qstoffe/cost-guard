# FR 000558 completion — v80.138, 2026-11-03

Implemented both Watch tables' ten-column order, HH:mm/full-date disclosure,
Duration second, canonical #N with preview-only ellipsis, Calls, observed per-prompt
I/C/W/O Token Mix %, and hover/focus/click header explanations. Expanded nonempty
history is unframed with one theme-aware divider; existing activity/context/lifecycle,
display units and keyed DOM behavior remain intact.

Canonical capture already computes running mix. The card export now carries it;
accepted usage/corrections update cumulatively without extra acquisition or JS math.
Zero/missing/incomplete telemetry remains unknown. CLI/Reports are unchanged.

## Verified

- Full: **132 test files pass**, zero failures, 72.5s, Windows/Python 3.14.7.
  Initial two outdated summary-DOM fixture failures were repaired and rerun.
- Package: **11 checks pass**, zero failures; six advisory prose/design warnings.
- Headless Edge 156.0.4314.58: **nine cases pass**, Classic/light/dark ×
  1920×1080, 1366×768, 360×800; real pointer/focus/Escape help, selection/DOM reuse,
  local clocks/ordinals, unframed/divided history and horizontal overflow.
- Native fake V2 capture and actual LiveConnection→Watch DOM prove cumulative
  `100/0/0/0` → `25/75/0/0` → `20/60/0/20`, correction/coverage changes,
  child/model/reasoning attribution, stale-event rejection/reconnect and terminal freeze.
- Fresh real-source repeat passes: V2, one owner/two verified advancing SSE streams,
  five known mix rows, one row/card/four capture slots, detail/freeze and tracked-worker
  shutdown. The first whole probe failed on an in-flight account-quota daemon;
  the unchanged repeat after Full passed. No lifecycle/configuration/assertion workaround.

## Scoped exception and remaining uncertainty

**Decision Delegate**, not owner, authorized only completed-partial telemetry parity:
Web shows N/A where the existing CLI may show numeric shares. This preserves honest
Web coverage while CLI changes remain out of scope. The CLI discrepancy is unresolved;
no fully-known/zero/live parity or other test requirement was waived. A separate
conditional shutdown exception was not needed because the repeat passed.

Neither twelve-second real-source observation captured a natural usage/mix change;
real-source timing/browser integration, physical touch/screen readers/macOS/native
fullscreen remain unverified. Resource observations exclude Claude metadata helpers;
zero tracked multiprocessing children is not proof of zero owned OS processes.
No inference, login, visible desktop action or shared OpenCode stop was performed.

Architecture/current guide/code map and
[journal with detailed evidence](../../../journal/web/watch-prompt-tables.md) updated.
The intact FR bundle uses next available Complete ordinal 000070; merged progress
advances ordinary count 8→9 only. No ZIP/tag/GitHub Release is produced.
