# Historical report recovery — FR000678

## Reproduced cause (2026-11-11)

Read-only local V2 acquisition enumerated 3,120 roots and completed source reads,
then both Token Mix and AI Stats returned `internal_error` rather than a report.
Sanitized exception frames identified `ValueError` in
`token_mix_cache.py::decode`, reached from freshly generated Token Mix facts and
`StatsAcquisition._batch` → `ai_stats_evidence.decoded`. No private source rows,
prompts, titles, session IDs or credentials are retained here.

Identity admission requires semantic version 3 for both moving family aliases
and opaque Claude Agent catalog candidates. The encoder marked only the former.
An unresolved opaque candidate therefore failed its own encode/decode roundtrip,
even with a brand-new disposable cache. This is a demonstrated software defect,
not evidence of source disconnection or lost history. The owner's approximate
43% UI observation was a useful lead, not proof of a specific cache exception;
the isolated cold reproduction reached history analysis before rejection.

The fix uses the same identity admission predicate for marker emission. It does
not loosen decoding, invent a release/price, change recorded history, bump the
global cache generation or discard unaffected entries. Previous affected facts
rebuild lazily; exact resolved releases and unrelated warm roots remain reusable.

## Independent lifecycle defects and changes

- AI Stats manufactured ten zero cards after failed/interrupted acquisition.
  Only valid source-backed empty/best-effort results now render zero-style cards;
  failure without a matching result stays report status.
- A managed lookup with no result/job during host backoff ended the browser
  attempt. No-result failed pages then had no automatic lookup timer. The two
  historical routes now keep using the existing host lookup/poll lifetime, never
  set explicit `retry:true`, and recheck relevant recovery even from a cold error.
  AI Stats no longer gives up after three transient readiness failures.
- Untyped child interruption/start failures were treated as terminal. They now
  use existing capped host backoff. Typed access/resource/protocol blockers remain
  diagnosable; demonstrated source-readiness recovery rechecks access blockers.
- Cache connection faults have small typed cause codes, and Token Mix checkpoint
  contention distinguishes SQLite BUSY/LOCKED from other unavailable persistence.
  Contention uses short backoff; unavailable persistence uses slower capped checks.
- Missing refresh publications do not erase accepted matching historical data.
  AI Stats incomplete refresh slices cannot overwrite a prior same-period result.
  Both report routes hide Retry/Refresh and redundant toolbar space in all states.
  Models, Comparisons and independent Sessions-detail controls retain their scope.

## Verification

Deterministic coverage includes opaque resolved/unresolved selections, cold and
warm facts, previous semantic markers, one-entry corruption/repair, 3,217 roots /
6,434 requests, real SQLite writer contention/release, continuation/parking,
source readiness/access recovery, typed terminal errors, host backoff without
explicit Retry, cold browser failure and retained provenance.

Initial real AI Stats probe: five scopes returned after 13 slices in 152.269s;
warm refresh completed in one slice in 6.565s (3,098 compact hits, 22 changing roots).
All five rate formulas/display contracts passed. Partial/unpriced/running evidence
remains qualified, not a claim of complete or billed cost.

The first fixed Token Mix cold probe exceeded its old 130s observation budget
while still advancing (2,881 hydrated roots at 120.680s), not a product timeout.
The probe now has an explicit 1–1,800s bound (600s default), matching the existing
AI Stats observation approach. Product work/resource limits are unchanged.

Final Full/validator/browser/live outcomes will be recorded before delivery.
No inference, source writes/deletion, shared-service restart, visible desktop
interaction, physical-device acceptance or screen-reader speech is claimed.
