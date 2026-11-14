# FR000710 completion — 2026-11-14

Implemented in v81.54: Session Detail now has independent, initially collapsed
Tool Calls and Skills sections over the full source-observed root history,
compaction and causally linked recursive child work. Physical call deduplication,
tool groups, outcomes, confirmed custom skills and safe invocation formatting
reuse Watch semantics/presentation.

Each red failed/cancelled group opens to distinct source-qualified calls with
bounded redacted arguments, recorded final status/outcome, qualified owner
identification and a fixed safe failure reason or explicit unavailability.
Complete aggregate counts are independent of the 25-record Load more pages.
Partial history, unknown skill origins and missing safe detail remain explicit.
History and activity share the detail lane's canonical snapshot and pinned
revision; unchanged snapshots reuse the safe projection. Stable native controls
preserve open state/focus/selection; invalidation and navigation clear private text.
Existing model Calls, history table, costs/context and sanitized export remain.

## Verification and limits

- Full suite: all 200 groups initially passed. Post-helper-consolidation Full:
  199 passed, one cancellation-precedence regression failed and was repaired;
  affected Skills, tool-activity and session-activity groups then passed.
- Working-tree validator: PASS for v81.54, eight existing advisory budgets.
- Rendered hidden Chrome/Edge: paging beyond ten failures, source corrections,
  stable DOM/open state/focus/selection/scroll, redaction, keyboard Space, touch,
  light/dark/narrow/zoom and navigation checks passed.
- Read-only real V2/HTTP detail probe reconciled four terminal calls/four safe
  details, complete history and frozen revisions; source guard unchanged,
  owned workers closed, shared OpenCode untouched.
- No inference, live-session mutation, raw-output view, new private-history scan,
  ZIP or release publication. Missing historical proof/reasons are not recovered
  or invented. No approved exceptions/exclusions were needed.

See [journal and precise verification chronology](../../../journal/web/session-activity.md)
and [architecture/code map](../../../architecture/modules/CODE_MAP.md).
