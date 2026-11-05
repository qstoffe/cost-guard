# Completion — FR 000586

Implemented in v80.167, 2026-11-05.

## Delivered scope

- Both Full Watch prompt tables display zero I/E whenever the selected unit displays
  a numeric zero total, including existing calls, missing components and tiny USD
  rounding. Unknown totals remain unknown and partial markers remain; raw values,
  CLI/Sessions accounting and component calculations are unchanged.
- Card, active/Earlier, session-footer and daily initial/refresh/retry text stays
  quiet for brief operations. Neutral initial placeholders do not invent observed
  empty/zero data. Coherent daily/account/session values remain readable; existing
  publication wakeups show sustained 30-second guidance. Confirmed source/partial,
  provider/auth, pricing and global Live warnings remain actionable immediately.
- Confirmed successful focal prompts and titles share `--watch-success` during the
  existing grace. Unknown/aborted/error outcomes never imply success; resumption,
  concurrent cards, history eligibility/order and neutral Earlier titles remain intact.
- Current Web guide/header help, architecture module contract and test navigation
  updated. Reusable status/verification findings are in
  `development/journal/web/watch-polish.md`; no architecture boundary changed.
- Whole specification bundle preserved; ordinary progress advances 36→37 in the
  same delivery. No Mini, backend acquisition, polling, connection or pricing change.

## Actual verification

- Final Full product suite: **PASS**, 142 test files, zero failed files, 90.0 seconds.
- Working-tree validator: **PASS**, 11 checks, zero failures; six existing/advisory
  prose/module-design warnings. No hard cap raised and no ZIP/release created.
- Python/JavaScript regressions: prepared cost variants/raw parity, missing/positive/
  partial/zero totals, no/observed calls, units/repeat updates, initial/sustained/
  failed/recovered statuses, authoritative success/error/abort/unknown/resume,
  concurrent focal cards, Earlier transitions and stale SSE publication rejection.
- Hidden fresh-profile Chrome 156.0.8078.80: **PASS**, six Classic/Web light/Web dark
  × 1366/360px cases. Real DOM retained heights/figures, delayed/error recovery,
  zero-cost units, semantic row/title color equality/contrast >=4.5, focus/navigation,
  selection and Earlier disclosure, no page overflow.
  Evidence: `development/tests/evidence/watch-presentation/browser.json`.
- Real read-only V2 focused probe `probe_web_live.py --watch-cards --prompt-cost --daily`:
  **PASS**, prompt CLI/raw cost parity and component reconciliation (four calls),
  daily category reconciliation (651 requests/18 prompts, complete prices and
  explicitly incomplete prompt attribution), one owner/two advancing streams,
  preserved run origin, four one-row cards and bounded four pending captures.
  All owned workers closed; shared OpenCode untouched; no inference started.
  Shutdown interrupted independent history work; full-source completeness is not claimed.
- Final Full includes empty-card and route-entry blank/delayed assertions, typed
  source-retry health without false table-level interruption, and unchanged global
  warnings. Focused daily/quota reruns and the final six-case browser rerun also passed.
- Hosted browser smoke initially failed its obsolete expectation that the initial
  Watch result echoed the raw synthetic acquisition-state string. The causal test
  correction verifies actual SSE receipt, unchanged source-health DOM, blank initial
  content and virtual 30-second guidance instead; no application behavior was reverted.

## Failed ancillary check and explicit exception

The broader real-source command adding `--session-cost` **FAILED** at
`development/tests/integration/session_cost_observations.py:32`:
`assert reused.valued_requests == 0 and not reused.cache_written`.
Snapshot revision matching and cost/report parity assertions had succeeded.
Actual valuation/write values were not captured; cause and live-cache reuse
reliability remain unknown. Concurrency is a hypothesis, not a diagnosis.

**Decision Delegate** approved this FR-only verification exception: the unresolved
ancillary cache-reuse assertion need not block UI delivery once the focused live
probe passed (it did). No FR acceptance requirement or other applicable check was
waived. Backend/cache and the assertion were not changed or weakened. This is not
a cache-reuse PASS or user-authored waiver.

Browser evidence uses synthetic publications and virtual sustained delays; real
source evidence is a separate HTTP/SSE probe, not end-to-end real-account browser
paint. Physical desktop, actual screen-reader, Firefox/Safari and macOS acceptance
were not performed or claimed. No implementation remains for this FR; the ancillary
live-cache uncertainty is retained explicitly rather than reported as resolved.
