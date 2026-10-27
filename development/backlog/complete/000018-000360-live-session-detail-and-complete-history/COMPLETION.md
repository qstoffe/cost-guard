# Complete session Snapshot/Live detail

Delivered as Cost Guard v80.87 (2026-10-26). Original FR bytes are preserved; no attachments were present.

## Implementation

- `src/reports/session_history.py` retains canonical root-tree observations only in host memory, reuses shared report projection and freezes lifecycle/time for omitted rows. Source gaps are not deletion/completion proof. Snapshot and Live share eight detailed columns, canonical CCost/billing, token percentages, child contribution, partial data and report-execution duration.
- `src/application/session_detail.py` serializes acquisitions on the existing live owner, schedules one due session per turn and shares one history across tabs without extra account schedulers. Immutable captures and revision/anchor-aware 50-row pages expose every available row, with whole-report totals. Snapshot freezes all pages; Live entry requests authoritative observation. Identical running evidence advances the shared execution clock without full attribution/projection/valuation.
- `src/web/assets/session.js` retains canonical DOM row identities, explicit mode/observation/status, First/Previous/Next/Jump to latest, follow disabling, scroll anchors and deferred selected-row changes. No browser valuation, new runtime dependency, ledger or CLI redesign.
- Snapshot-local `src/analysis/prompt_index.py` removes quadratic repeated causal scans while retaining strict same-timestamp windows and provider filtering. Lifecycle fixture isolation removes unintended real integration access from deterministic tests.

## Verification and limits

Repository Full suite, working-tree validator and real read-only V2 probe are the delivery checks; final results are recorded in the PR. The real-source probe observed one acquisition/account owner, two SSE streams, reachable complete detail, consistent freeze and joined owned shutdown without stopping OpenCode or calling a model. Synthetic 100/1,000/10,000-prompt probes verify first/middle/latest access, bounded page payloads and DOM, full totals, stale cursors, stable revisions, snapshot/live transitions, running rows, compaction/omission, late child evidence, missing pricing and source reconnect. Existing report/Watch tests retain abort/error/background/context semantics.

The new asset VM exercises keyed rows, retained focus/selection, anchor requests, offline retention and mode/latest actions. It is not a physical browser, screen reader, CSS/resize or native macOS acceptance claim. Copy/selection spans the visible page, not unloaded pages. Admission bounds (16 observed session trees, 32 handles) are explicit busy states, never prompt limits; abandoned transport handles expire, not history. Missing catalog entries retain last-known reports and do not claim authoritative deletion. Already deleted, never observed history is unrecoverable. No new permanent gate, ZIP or packaged release.

## Knowledge and dependencies

Journal assessment: update the existing performance topic to retire the now-fixed quadratic causal-scan conclusion and retain reproducible scale evidence. Architecture assessment: update the Web owner/test route and code map; dependency direction remains Web → application → reports/analysis/domain, with no new external boundary. The earlier shared report/Web/live prerequisites and migration plan are preserved; remaining dedicated report coverage and Beta stabilization stay pending. No foreign changes, stashes or unfinished cross-FR evidence were incorporated or discarded.
