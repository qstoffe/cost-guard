# Web Watch terminal reconciliation

2026-11-02 · FR 000546 · v80.125

## Reproduced mechanisms

Canonical current-V2 HTTP fixtures, through actual isolated CardWorkers capture,
retention, WatchCards and immutable export, reproduced three defects:

- A child previously observed active disappears from a complete source tree.
  Retaining that session object made a freshly persisted quota terminal stay
  running in Web, while the fresh report correctly stopped it.
- An idle terminal omitted on a later refresh removed the same assistant's
  normalized terminal evidence and resurrected that attempt.
- Delayed same-generation rows/totals replaced a newer terminal capture.

The same fixtures also showed that the card export omitted the normalized quota
cause. It now exports that allowlisted cause and the page displays it.

## Ownership and guardrails

V1 transaction/V2 complete pagination plus revision brackets certify snapshot
completeness. Shared observed-history analysis keeps retained usage but uses
the fresh complete tree for lifecycle. Absent data from an unproven partial read
does not establish an end; the retained card is partial/unavailable and omitted
rows do not advance their last-observed clock. Persisted ends stay on assistant
identities, not a prompt-wide terminal lock: real later attempts/tools/children
and background work remain possible. Session detail reuses the same owner.

Complete zero-call/compaction reclassification keeps observed Web history without
claiming success or fabricating a source end. Observation grace starts once,
separately from execution; final activity counts survive without live indicators.
The shared adaptive cadence, bounded workers and 60-second continuation grace
are unchanged. Mini Watch is not implemented here; it must consume this same
server-owned card lifecycle rather than adding an age/quota heuristic.

## Evidence and limits

The new regression file covers missing/zero/positive usage, cold/repeated
reconstruction, terminal grace/history, partial/outage/recovery, reclassification,
retained active children, delayed publications and legitimate subsequent work.
Existing card tests cover concurrent focals and old generations. Actual check
results are recorded in the task completion, not inferred from this test route.

A read-only real V2 installation probe published cards/full totals, shared two
SSE streams on one live owner and verified Session detail/freeze. Owned workers
closed; the shared OpenCode service was not stopped. This does not reproduce the
owner's historical quota incident: no affected session/snapshot/version was
provided, so its exact cause remains unknown. No inference, model switch,
production prompt intervention or quota-based termination was performed.
