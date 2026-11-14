# Plain numeric table values — FR000706

2026-11-14; v81.50. Presentation policy only; no acquisition, valuation, cache
algorithm, canonical precision, sorting, attribution or completeness change.

## Audit and implementation

- `numbers.ccost_amount` no longer prefixes available reference amounts with `?`.
  Its existing `None` and unresolved-zero availability semantics stay unchanged.
  Native quota amounts use separate helpers; estimate/Capacity/Remaining rules
  and `~`/standalone `?` are not modified.
- Application amount tokens cover Full Watch running/earlier cards, session
  summaries, normal/session/date reports, subtotal/footer rows, incoming/extra
  costs and cost breakdown help. Mini/PiP consumes the same prepared values,
  including its existing independently guarded whole-session priced subtotal.
  The existing Mini compact detail groups and Full individual-agent breakdown
  consume the plain shared formatter.
- Explicit prefix producers in Watch run totals, category costs, historical
  model/publisher Token Mix totals and Comparisons are removed. Historical cost
  display tokens no longer replace `?` with `Partial `. Token Mix no longer needs
  a browser-only string-stripping exception.
- CLI report/Watch use the shared amount formatter and explicit Token Mix/footer
  producers. Known token-volume subtotals also drop the incomplete-number prefix;
  canonical exact totals/shares remain unavailable when telemetry is incomplete.
- Obsolete marker explanations are removed, not replaced by badges or per-value
  uncertainty decorations. Existing factual source/coverage explanations remain.
  General reference-valuation/not-billing help is retained.

## Verification and limits

- Formatter/projection matrix: complete and partial values have identical numeric
  presentation in Credits/USD across thirteen amount keys. Raw Decimal strings,
  completeness flags, tiny-positive USD rounding, genuine unknowns, supported zero
  and Comparisons source facts are checked separately.
- Existing focused regressions cover canonical source/pricing preservation,
  prompt/category breakdowns, Mini groups, Watch summaries/totals, native quota
  Capacity/Remaining and report/CLI parity. Superseded prefix expectations were
  updated; source/accounting assertions remain.
- `probe_web_help.cjs ... --numeric-tables` passes on hidden Chrome 157 with actual
  Document PiP. Canonical synthetic mixed/zero/unpriced fixtures are rendered in
  Full Watch, Mini prompt/session, Sessions catalog and detail/footer in both
  units, with focused cost help and replacement publications. The original
  unavailable-help probe has stale Mini selectors; the new scoped probe uses
  current separate columns and does not claim that old probe passed.
- The unpriced fixture includes a supported zero-cost compaction: Mini's existing
  whole-session priced-subtotal rule legitimately displays zero while its prompt
  and other unavailable cells show N/A. The probe preserves this distinction.
  Initial probe attempts exposed stale selectors/missing catalog setup and this
  independent zero rule; these were test assumptions, not product-policy changes.
- Existing `probe_token_mix.cjs` passes all five periods, model/publisher tables,
  both units, exact sorting, category cost help, partial/unpriced/empty states,
  three themes/four widths and replacement publication checks.
- Read-only real V2 `probe_web_live.py --numeric-tables`: 72 numeric display tokens,
  seven incomplete records, eight publications; one Live owner, two verified SSE
  streams and zero owned threads/processes after cleanup. It checks already
  observed cards, not global history completeness (history was still loading),
  private-incident reproduction, paid inference or physical desktop behavior.
  Earlier probe exits supplied no usable numeric proof; the final diagnostic run
  passed without touching the shared OpenCode service.
- Final Full: 198 groups, 2,435 tests, zero failures (163.0 seconds), four macOS
  checks skipped on Windows. Validator: zero failures, seven existing advisory
  warnings. Local macOS
  skips are not macOS certification. Browser fixtures are synthetic; physical
  input/assistive technology and exhaustive private history reconstruction are
  outside this presentation proof.

Runtime architecture boundaries are unchanged; the code map records the changed
presentation owners and reproducible checks.
