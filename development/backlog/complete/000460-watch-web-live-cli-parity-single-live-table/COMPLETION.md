# FR 000460 completion — Web Watch single live table

Implemented in v80.95 (2026-10-27).

- One persistent primary prompt table, canonical CLI ordering, six recognizable CLI columns
  plus supporting activity/context detail. Inline session dividers link to full detail and
  label retained-row subtotals honestly; filters/pages do not change Run/Today totals.
- Latest Watch model and observation-time running duration are exported independently of
  frozen prompt metrics. Running/abort/compaction, context/tool/skill warnings, partial prices,
  run origin, independent account observations and complete Snapshot/Live detail remain intact.
- Compact account cards replace disconnected quota tables; failures remain visible.
- Controls, page, unchanged row identities and visible-row scroll anchors survive updates.
  Selected/focused prompt content defers replacement; connection/source/terminal states retain
  valid rows without presenting old running observations as fresh lifecycle proof.
- Watch navigation and legacy live URL, SSE authorization/replay, one host acquisition owner,
  independent CLI, server-side valuation and account cadence are unchanged.

## Verification

- Full isolated repository suite: 108 test files, zero failures. Package validator: zero
  failures; four existing advisory size warnings. No ZIP or live-model test.
- Identical shared Watch projection compared through CLI table cells and rendered Web DOM,
  including cost/calls/running-duration/context; deterministic client tests cover duplicates,
  replay gap, row identities, selected text, stable filtering/paging and terminal retention.
- Actual installed Edge headless rendered fixtures passed at 1200px/light and 360px/dark:
  one table/two sessions, layout/selection/focus/scroll/page stability, abort/compaction/idle,
  slow/unavailable source, offline/reconnect/replay gap/stop without duplicate rows.
- Independent read-only real V2 probe passed with one acquisition owner/two HTTP streams,
  preserved run origin, detail freeze, four finite report scopes, cancelled deep history
  and joined shutdown. Shared OpenCode untouched.
- Evidence and limitations: [Web Watch verification](../../../tests/evidence/web-watch/README.md).
  The desktop browser pane was disconnected. Headless fixture transport is not real-source
  browser SSE integration or physical/screen-reader/macOS acceptance. Existing FR 000410
  HTTP/hosted browser checks remain independent; no claimed new platform certification.

## Knowledge and dependencies

Architecture boundaries: no change. Updated the Web module's source/test routes for the new
presenter and Watch-specific display projection. Journal learning: **no-update**; no new
reusable operational finding beyond those owner facts. No unfinished cross-FR dependency or
external recovery artifact is required for this change; the selected FR bytes are preserved.
Pending neighboring view/host FRs remain unmodified.
