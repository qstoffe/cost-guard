# FR 000667 — Sessions: add a sortable CTX column with context-size help

**Owner-approved Ready Feature Request, 2026-11-10.** Permanent identity **000667**; Ready queue priority **001020**, following the existing Ready FRs. **FR-only publication:** add this file and atomically advance `development/backlog/identity-state.json` highWatermark **666 → 667** on `main`. Do not implement product code, run product tests, change version/release artifacts, or edit unrelated backlog items in this publication.

## Owner request and desired result

In the **Cost Guard Web → Sessions** page, the table listing all sessions currently offers **Last activity | Session name | Model | CCost | Prompts | Duration**. There is no context-size column. Add a **compact seventh column named exactly `CTX`**, with a useful hover/focus/touch heading tooltip describing what the context number means.

Make **CTX clickable/sortable like the existing metrics**. The owner explicitly wants it integrated with the newly completed Sessions **global heavy-metric sort and paged loading behavior (FR000664)**: no apparent dead click, no falsely sorted current page, and no unresponsive operation without progress/cancellation/recovery.

Suggested display placement: **after Duration**, preserving the six established columns and a one-line, compact Sessions catalog.

Illustrative examples (synthetic values, not observations):

| Session name | ... | Duration | CTX |
| --- | --- | --- | --- |
| Example A | ... | 08:20 | 172k |
| Example B | ... | 01:12 | 95k |
| Example C | ... | 00:30 | N/A |

### CTX meaning

- **Use a canonical session/root-scoped context-size value**, preferably the most recent *valid estimated incoming context for the session's next request*, matching the established **Mini Watch historical session-level Ctx** meaning where comparable. The table represents a **whole session**, not one arbitrarily selected historical prompt; never sum the context sizes of prompts, display the model's capacity limit, take a maximum without semantic justification, or present an old prompt's Ictx as the current session estimate.
- Define and document which canonical source, context epoch and revision supply this field for active, completed and archived sessions. Reuse the context estimator and projection's supported session-level semantics rather than calculating from formatted browser values. Confirm comparability with Full Watch/Mini; valid distinctions between running prompt-local and historical session-level estimates remain deliberate.
- Numeric display is concise, consistent with existing Cost Guard context formatting (e.g. `172k`), with honest `0` if proven and `N/A`/unavailable only if genuinely unsupported. **`Loading…` means source work is still pending**; retained or provisional data must not masquerade as a newly measured exact value.
- The **CTX header tooltip** should concisely explain that it is an **estimated session-level next incoming context in tokens**, not the model's remaining capacity or a sum of prompts, and that the column sorts the full catalog. Where useful, the value tooltip may disclose a precise supported figure and short freshness/estimate/unknown reason, using existing shared `ContextHelp` behavior; do not add noisy prompt details or unrelated cost narratives. The header must remain a working sort button for mouse, keyboard and touch.

## Existing implementation and boundaries

At authoring time:

- `src/web/assets/sessions.js` defines six headers and four metric-cell renderers; `src/application/session_catalog.py::SORTS` contains `activity, name, model, ccost, prompts, duration`. Therefore CTX is **not** currently sortable or rendered in the catalog.
- `src/reports/models.py::SessionUsageRow`, `src/reports/service.py::_session_rows()`, `src/reports/session_summary.py::session_summary()` and `src/application/projection.py` currently carry and project the catalog's scalar metrics, **but no CTX field**. Adding CTX requires a source-backed, serializable scalar value and its qualified display token, not just a seventh JavaScript cell.
- The established **Mini Watch** session-level value uses `card.session_summary.context.watch_next_context_tokens` for historical rows, sourced from the canonical Live/Watch context guidance. Investigate how to reuse its meaning without coupling the Sessions catalog to the PiP UI, triggering full Watch scans or depending on a Mini window being open.
- **Completed FR000664** owns global metric sort admission, whole-root scalar indexing, progress/Cancellation/Retry, request generations, cache reuse, stable 50-row paging and old-page epochs. Extend that **same implementation** for CTX; do not bypass or fork it.

## Acceptance criteria

1. **Seven correct columns:** Sessions catalog shows `Last activity | Session name | Model | CCost | Prompts | Duration | CTX` with `CTX` compact/intrinsically sized, aligned for numeric comparison, and consistent with Classic/Web light/dark, responsive widths and horizontal table panning. Only the session name remains the elastic/truncating column; no wrapped row, unintended extra vertical scrollbar or broken header/cell correspondence.
2. **Correct session context:** For a session with source-backed estimated next context of 172,000 tokens, CTX displays `172k` (using established source-prepared formatting), irrespective of which catalog page is open. Verify active/running, recently completed, older/archived, one-prompt and multi-prompt cases. A context update after a new prompt, tool call or compaction follows actual canonical evidence; it does not silently retain invalid data from a different epoch, source or root. Differentiate supported zero, pending, truly unavailable and retained/partial values.
3. **Global numeric sorting:** Clicking CTX sorts the **entire available root-session catalog** ascending/descending by **unrounded numeric context-token counts**, not lexicographic formatted strings (`95k` vs `172k`), not the current 50 rendered rows, and not context capacity or current prompt number. Use deterministic session-ID tie breaks; **genuinely known unknown values sort last in both directions**. An unindexed or stale root is **not** falsely treated as a final unknown.
4. **Heavy sort UX unchanged:** CTX participates in FR000664's exact requested/applied sort contract, cold scalar-index progress `indexed / available`, coherent 0–100% determinate bar, bounded failure/Retry, Cancel returning to the previous real sort/page/URL/focus/scroll, obsolete-response rejection and rapid warm-cache application without a spurious loader flash. Do not change global sort semantics for the six existing columns. Avoid a permanently blocked pending operation when an authoritative unavailable CTX is correctly known.
5. **Efficient bounded acquisition:** Extend/reuse existing session scalar summaries, revision-qualified cache, invalidation and source index scheduling. Existing Activity/Name and page navigation must not suddenly fetch/scan all 3,000+ session histories solely to **display** CTX; costly full-catalog CTX key qualification should occur only under the established global sort interest, subject to existing per-tick/source budgets. Do not add per-row browser HTTP fan-out, parallel unbounded transcript processing, a second indexer, paid model calls or new persistent personal history. If adding a cached CTX field requires schema/algorithm revision, invalidate/rebuild old disposable scalar-cache entries safely and preserve unrelated valid caches where possible.
6. **Stable tables and paging:** Keep exactly 50/page, correct total and page counts, stable pinned older-page membership/order, fast sorts after warm keys, quiet live updates, focus/selection/scroll and hover/focus help on retained row nodes. A newly observed session or changed CTX must update from the right source revision without mixing snapshots; restore/failure flows never render the previous sort as if CTX were already applied.
7. **Test the full path:** Extend `development/tests/test_web_session_catalog.py` for CTX source facts, indexed/pending/ready/retained/unavailable, caching, invalidation, full-catalog sort in both directions, unknown-last and exact boundary paging. Extend relevant `development/tests/integration/serve_web_sessions.py` fixture plus the existing Sessions browser/VM navigation tests for the seventh header, its tooltip/accessibility, cold progress/Cancel/Retry, 3,000+ synthetic roots, warm no-flash sort, keyboard/touch, narrow widths and themes. Validate canonical consistency with suitable Watch/Mini context fixtures; update Sessions documentation. Do the repository's standard implementation checks **when implementing**, not during this FR-only publication.

**End state:** Sessions visibly reports meaningful per-session **CTX** and offers a fully functional, responsive, source-correct **global CTX sort** using the same loading and cancellation workflow as the other heavy metrics.
