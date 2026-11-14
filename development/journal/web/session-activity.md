# Session-wide Tool Calls and Skills — FR000710

## Ownership and behavior

The old detail projection contained only report rows/metrics, so reading activity
from displayed rows or borrowing the last Watch card would silently omit history.
`application/session_activity.py` now projects the detail lane's existing canonical
snapshot, including all root assistant work and `ChildLinkIndex`'s qualified
recursive descendant windows. Shared Watch physical call IDs deduplicate repeated
parts; names, error/cancellation and custom-skill origin semantics stay shared.
No separate full-history source acquisition or browser-side tool counting was added.

`ActivityHistory` caches the safe projection by canonical snapshot identity, including
across owned child IPC. History and activity are captured together by the existing
begin/chunk/freeze revision. The authenticated `activity` action pages only detached
values from that capture, 25 terminal calls per response; no source command runs
on expansion. Watch retains its existing ten-failure/card-wide budget. Historical
aggregate counts have no such cap; every source-qualified safe call can be reached.
Absent source identity proof preserves the aggregate but explicitly counts
unavailable detail. Partial history and unknown skill origins remain labeled.

The presenter reuses Watch's keyed native details, summary fragments, invocation
nodes, safe text correction and logical indentation. Session Detail has exactly
two independent initially closed top-level panels. Calls in the table still means
model requests. Cancellation is inspectable but not relabeled as a failed error.
Invocation arguments use the existing allowlist/redactor and per-call text bound;
reason text uses only fixed recognized categories, never arbitrary error/output.
Root prompt numbers are shown where directly qualified; local prompt/agent opaque
identities identify other qualified owners without exposing prompts/titles.
Navigation/source invalidation clears private input and unrelated open choices.

## Verification (2026-11-14)

- Full bounded per-file suite: **200 groups passed**, four workers, 177.1 seconds.
  This run preceded the final public semantic-helper consolidation and HTTP
  negative assertions. Follow-up Full ran all 200 groups in 173.4 seconds:
  199 passed and one Skills cancellation regression failed. The shared helper
  had checked native error before the supported structured cancellation outcome.
  Restoring the original cancellation precedence repaired it; focused
  `test_watch_skills.py`, `test_watch_tool_activity.py` and
  `test_session_activity.py` all passed after repair. The latter includes
  untimed historical calls, latest-terminal deduplication and source-epoch scope
  isolation. The final same-revision history-reuse optimization also passed
  the existing client DOM/focus/transition test. No failing check is called PASS.
- Working-tree validator passed, with eight existing advisory budgets.
- Real read-only V2 installation/HTTP detail probe: one selected row; complete
  canonical activity; four terminal calls and four source-qualified safe details;
  aggregates reconciled; freeze stable; source guard unchanged; no owned workers
  remained. No inference, source/session mutation or shared OpenCode stop.
  Complementary history/account lane exceptions during probe shutdown do not
  establish whole-history/account success.
- Hidden Chrome 157 and Edge 157, fresh synthetic profiles, actual host/auth/DTO/assets:
  60 distinct failed reads across three root prompts including compaction plus a
  cancelled shell call; 25→50→61 record paging; unchanged five model requests;
  supported/unknown failure reasons and token redaction; live count growth and
  safe correction; stable native controls/input, open states, focus, selected text
  and scroll. Keyboard Space and trusted touch were exercised. Eight light/dark,
  360/1366-pixel, 100/150% layouts retained nesting/readable wrapping without page
  overflow. Switching sessions cleared old invocation content/open state.
  Evidence: `scratch:/session-activity-browser.json` and
  `scratch:/session-activity-edge.json`; these contain synthetic scalar/layout
  results, not private history. Chrome preceded helper consolidation; Edge
  followed it. The later cancellation repair restores existing shared semantics.
- Early browser attempts corrected an erroneous fixture expectation (the wrapper,
  child and continuation give three first-row model calls) and changed the CDP
  keyboard probe from an ineffective Enter event to native Space activation.
  The focused run then passed; these were not product PASS claims.
- Canonical regressions cover 300 failures, physical duplicates, repeated skills,
  safe cancellation versus failure, unknown reasons, nested descendants and
  excluded unrelated/late child work, wrong-source omissions, pinned revisions,
  freeze, unchanged-projection reuse and source invalidation. Authenticated detail
  HTTP tests cover paging, stale revisions and invalid boolean offsets.

## Limits

This is source-observed history, not recovery of absent private data. Unknown
skill origins cannot be reconstructed, and a missing safe reason is not invented.
The real probe is complementary installation evidence, not a reconstruction of
the owner's original private UI incident. No paid inference or live session
mutation was used, no release archive was produced, and no exceptions were taken.
