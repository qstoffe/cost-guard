# FR 000666 completion

Implemented in v81.16, 2026-11-10.

Mini preserves the previously displayed same-session Ctx only during a canonical,
source-validated new-prompt handoff. Exact predecessor ID/raw tokens, active history,
fresh complete capture and compatible context qualify it. Fresh values replace it
immediately, including equal formatted numbers. Help explicitly identifies previous
context pending refresh; Δ Ctx stays current-prompt-specific.

Compaction, context/model boundaries, incompatible known models, unsupported current
requests, execution uncertainty, authoritative invalidation, source/host changes and
row removal cannot revive old values. Historical-only values need matching prompt
context and later source validation. First/new Mini remains honest without prior
displayed context. No estimator, Full Watch, cost, layout, geometry or acquisition
change, browser storage, refresh request, paid inference or release archive.

## Verification

- Local Full: 181 bounded groups, zero failures, 142.6 s; final focused Mini: 13 tests,
  zero failures after fixture and late-publication adjustments.
- Package validator: 11 passes, zero failures, seven existing advisory warnings.
- Real headless Edge 157 Document PiP: source → capture → Live/SSE → PiP
  `172k → 172k → 175k`, repeated/timer draws, focus/AX provenance, prompt-local Δ,
  fresh/late evidence, tool continuation, genuine invalidation and fresh Mini.
- Read-only real V2: one supported running context, advancing verified streams;
  zero live handoffs observed, zero owned workers after close, OpenCode untouched.
  This does not reproduce the owner's private incident or certify Earlier history.

The original task and attachments are retained intact. No acceptance exceptions or
deferred scope. Physical desktop/window behavior was not retested; native headless
PiP covers this presentation change without changing geometry.

Architecture/code map, user guide, release metadata/history and ordinary progress
updated. See [journal evidence and fixture-repair history](../../../journal/web/mini-watch.md#same-session-ctx-handoff-fr000666).
