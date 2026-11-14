# FR 000706 completion

Implemented in v81.50 (2026-11-14).

Numeric CCost no longer carries an uncertainty question-mark prefix in shared
Web/CLI report, Watch, Mini/PiP, session/detail, Comparisons and Token Mix display
tokens, totals and breakdown help, in Credits or USD. Known token-volume numeric
subtotals follow the same plain-value policy. No replacement badge/label is added.
Canonical Decimal amounts, pricing, attribution, source/completeness evidence,
sorting and unknown/unavailable rules are preserved. Quota, Capacity, Remaining,
native balances and their estimate/unknown indicators are unchanged.

Verification:

- Local Full: 198 groups, 2,435 tests, zero failures, 163.0 seconds; four
  native macOS checks skipped on Windows, not certified locally. Focused matrix covers thirteen amount keys, partial/
  complete equivalence, canonical preservation, Comparisons, category totals,
  Watch run totals, unknowns, supported zeros and tiny-positive USD rounding.
- Working-tree validator: zero failures; seven existing advisory warnings.
- Hidden Chrome 157: current Full Watch, Mini Document PiP, Sessions/detail/footer
  mixed/zero/unavailable values and numeric cost help pass in Credits/USD.
- Existing full Token Mix browser matrix passes periods, category help,
  model/publisher sorting, unknowns, unit changes and replacement publications.
- Real read-only V2 probe checks 72 numeric tokens across eight publications and
  seven incomplete records; one owner, two verified SSE streams, clean owned
  shutdown. Shared OpenCode is untouched; no paid inference.

[Audit, ownership and evidence limits](../../../journal/web/numeric-table-values.md)
include the preserved Mini supported-zero-compaction distinction and repaired
probe assumptions. Real global history was still loading: this is not exhaustive
private-history proof, a private-incident reproduction, physical desktop input
or local macOS certification. No acceptance scope was deferred or waived.

Affected architecture navigation and current user docs are updated. Maintenance
progress advances to ordinary count 151 only when merged to default.
