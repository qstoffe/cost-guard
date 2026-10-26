# FR 000460 — Make global Watch a recognizable, useful live CLI dashboard

## Owner observation

The current global `Live` Web view does not resemble CLI `Watch`: the browser shows multiple separate prompt tables and substantial surrounding prose, so it is hard to tell what is actively updating or which figures correspond to the live console. Code confirms `src/web/assets/render.js::renderLive` groups rows by session and calls `table(..., 'Live prompts', ...)` for **every session**, adding independent account-quota tables. The data pipeline may be sound; the primary problem is presentation and lifecycle clarity.

## Required behavior

- Present **one primary continuously updating Watch prompt table**, conceptually matching the CLI Watch view: same visible metric columns, prompts, session grouping/markers, running/completed/aborted/compacted state, newest/earlier distinction, cost/request/duration/context and tool/skill warnings. Group sessions using subtle inline section/divider rows or a cohesive nested presentation, **not a separate standalone full table per session**. Preserve all relevant data and canonical ordering.
- Compare identical shared Watch projections rather than comparing asynchronous real-world runs. Keep host-start run origin, run and Today totals, retained-row session subtotals, scope distinctions, latest-progress/running values and warning states. Never describe a retained-row subtotal as a complete historical session total or convert CCost into actual billing.
- Show live status and acquisition freshness prominently but compactly. Indicate that values are updating, idle, reconnecting, offline/stale, source unavailable, or terminally stopped; do not imply success or a running prompt just because the browser tab is open. Preserve accumulated valid rows during transient reconnection and resume coherently.
- Display Watch accounts/quota activity in a **compact supporting area** (structured cards/rows or expandable disclosure), with CLI-equivalent figures/semantic colors and no flood of disconnected account tables. Avoid losing independent account observations or hiding failure evidence.
- Keep user interaction stable during live updates: maintain scroll anchor/selection where feasible, avoid surprising focus jumps and avoid rebuilding independent filtering/pagination controls on each tick. Preserve complete session detail navigation, and the existing immutable Snapshot vs Live detail contract.
- Name the global navigation **Watch** per FR000440; retain `/#/live` URL compatibility. Styling follows FR000440 and display tokens FR000430; no second Watch engine, browser-side valuation, extra polling per tab or change to CLI.

## Acceptance

- Synthetic CLI Watch projection and Web Watch display comparison has equivalent rows, totals, warnings/status roles and ordering; the page has **one primary prompt table** even with multiple active sessions and supporting accounts.
- A real browser visibly updates running rows, handles start/idle/aborted/compaction, slow source, reconnect/replay gap, and server stop without duplicating rows or mislabeling old data as fresh. Verify scrolling, text selection, keyboard, narrow screen and light/dark.
- Keep existing SSE authorization, bounded replay, one host-owned acquisition loop and independent CLI Watch. Add appropriate Web rendering/lifecycle regressions and coordinate real-browser checks with pending FR000410.

Relevant owners: `src/web/assets/render.js`, `live.js`, `app.js`, `app.css`, `src/application/live_projection.py`, `src/presentation/watch.py`, `watch_activity.py`.