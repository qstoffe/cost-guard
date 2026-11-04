# Watch session summary and incremental CCost

FR 000572 · 2026-11-04 · v80.152. Baseline: `780a54ed6676ec711d0a07d63b6d174fd7501b12`.

## Ownership and invalidation

- Full Watch uses canonical first-request `incoming_context_tokens` as ECTX before
  Δ Ctx. The old Context-cell icon/update branch and standalone warning DTO/footer
  are removed. Session Context and its inline warning come from one latest valid
  continuation per session, shared by concurrent cards and independent of row ECTX.
- `analysis/session_cost.py` reuses `trace_entries`, `unique_usage` and
  `comparison_cost`; it does not rebuild prompt reports. The generation-2 SQLite
  `session-ccost-v1` namespace persists an unrounded aggregate plus minimal hashed
  request identity/fingerprint/amount contributions. Source instance/generation/root,
  attribution/aggregation version and reference catalog semantics isolate entries.
- Every changed snapshot reconciles actual membership/fingerprints, including
  corrections, late children, compaction, provisional usage and authoritative
  deletion. Changed/removed values amend the old aggregate; replay is idempotent.
  Revision changes are checkpoints, not evidence that an old total is correct.
  Partial source brackets never overwrite complete persisted checkpoints.
- One separate, fairly admitted background future owns totals. Row publication,
  lifecycle, daily/accounts, SSE cadence and other sessions do not wait for it.
  Accepted fresh snapshots are reused for periodic reference-catalog checks without
  history hydration. Production aggregate resources do not select another source or
  initialize/write schema metadata. A catalog refresh may use its normal pricing
  cache; unchanged aggregate checks do not write session cache state.
- Stable totals survive visible capture eviction, browser/tab membership changes and
  a fresh process. Loading is localized to an unknown first total; retained/stale,
  partial-source, unpriced and optional-cache failure states remain distinct.
  No prompt text, tokens, source paths or credentials enter the new namespace.

## Deterministic work evidence

`test_session_cost_cache.py` instruments actual canonical contribution valuation
calls and repository writes, not just a displayed work counter:

| Scenario | Checked requests | Valued requests | Session-cache write |
| --- | ---: | ---: | --- |
| Initial long session | 2000 | 2000 | yes |
| One new prompt/request | 2001 | 1 | yes |
| No-op refresh | 2001 | 0 | no |
| History/input reordering | 2001 | 0 | no |
| Fresh SQLite repository | 2001 | 0 | no |
| Fresh Python process, same persisted cache | 2001 | 0 | no |

Independent fixture arithmetic checks the total, while a separate complete-session
report checks corrected root/child/compaction/running coverage. Further cases cover
partial-to-complete pricing, unknown versus zero, source/catalog/algorithm isolation,
cache lock/corruption errors, bounded occupied-worker behavior, concurrent cards,
re-entry without presentation-side work, superseded generations and pricing-only
refresh with no source hydration. The new test module is included in Quick and Full.

This is incremental **valuation and aggregate arithmetic**, not a constant-time source
delta API: authoritative snapshots and persisted contribution payloads are still
linearly checked to detect historical corrections/deletions. Existing row capture's
canonical analysis remains separate; no general source-acquisition speedup is claimed.

## Rendered and real-installation evidence

- `probe_watch_cards.cjs`: Chrome 156.0.8078.80 headless, 12 combinations of
  classic/light/dark and 2560/1920/1366/360px. Exact ten headings, ECTX header
  hover/focus/click help, inline approaching/exceeded/cleared guidance, full-line
  severity inheritance, focus-safe invalidation, Credits/USD, wrapping/no overflow,
  table pan, history, activity and account alignment passed. Screenshots/structured
  results were retained during work at `scratch:/browser-evidence-delivery/`.
- The separate `probe_watch_summary.cjs` passed all nine classic/light/dark ×
  1920/1366/360px cases, including warning transitions and account track alignment.
  Its obsolete assertion requiring three account cards side by side at 1366px
  initially failed; the corrected assertion preserves established responsive caps:
  three cards at 1920px, two plus wrapping at 1366px, and stacking at 360px.
  No production layout was changed to satisfy this legacy probe.
- `probe_web_live.py --watch-cards --session-cost --daily`: real V2 read-only capture
  matched a stable four-request session to independent full history. A fresh
  repository revalued zero requests and wrote no session-cache state. The final
  observed daily group had 931 requests / 24 initiating prompts, complete prices
  and explicitly incomplete prompt attribution; category costs reconciled.
- One live owner served two streams with advancing instance-bound IDs and preserved
  run origin. First card rows appeared at 3.370s; owned cleanup completed at 10.637s
  with no cleanup failures and zero remaining owned threads/processes. Shared
  OpenCode was untouched; no model inference was started. Phase instrumentation
  recorded one history-read error during shutdown; it does not invalidate the
  already-published daily evidence or establish its original cause.

## Verification history and limits

The first Full run caught an obsolete JS column-order assertion, corrected to the
new ten-column contract. A subsequent concurrent Full run failed the existing
PowerShell PATH-fallback discovery test; that file passed in isolation, and all 139
files passed in a two-worker Full rerun (156.2s). The final production revision
`330712dc1572b01777dd53583b9b58bd12ded5da` passed all 139 files in 160.0s;
the subsequent legacy-probe-only correction passed its nine rendered cases.
No launcher behavior/assertion was weakened, and no requirement/test exception was
granted. Final results are recorded in the completed specification's `COMPLETION.md`.

The initial real-source probe exposed a probe-only publication race (internal cost
completed before the HTTP snapshot carried it); the probe now waits for a published
cost. Subsequent real-source runs passed. Browser evidence is headless DOM/layout,
not physical-desktop, native shell or actual assistive-technology acceptance. No
Mini Watch, CLI, Sessions-page UI or global daily/account accounting redesign is
claimed. Existing advisory prose/module design-budget warnings remain; no hard cap
was raised and no release ZIP was built.
