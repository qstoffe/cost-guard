# Completion — FR 000572

2026-11-04 · v80.152 · implementation baseline
`780a54ed6676ec711d0a07d63b6d174fd7501b12`, integrated main
`1a746e6ee4a735e1cde80115604fecdaa91a8c18` (v80.151).

## Implemented scope

- Active and Earlier full Watch tables use canonical first-request ECTX immediately
  before Δ Ctx, retain ten columns, and explain estimates/unknown values in accessible
  header help rather than visible approximation decoration.
- One session-scoped Context · CCost line replaces the old Context-cell treatment
  and warning footer. Canonical approaching/exceeded guidance retains inline price
  impact details; exceeded severity colors the entire line. Concurrent cards share
  the latest valid continuation and full root-tree total.
- The existing disposable SQLite infrastructure persists minimal hashed contribution
  identities, unrounded values and aggregate completeness. Only added/changed
  contributions are revalued; corrections/deletions reconcile without double counting.
  Source, algorithm and pricing identities prevent stale cross-source/catalog reuse.
- One independent bounded background lane shares totals without delaying rows,
  accounts or lifecycle publication. Retention, process restart, pricing-only checks,
  partial/unpriced states and optional-cache failure have focused regression coverage.
- Current Watch docs, architecture/CODE_MAP, journal and release metadata are updated.
  Original FR payload moved intact; ordinary progress advances from 22 to 23 only
  when this change reaches main. Mini Watch, CLI, Sessions UI and global accounting
  remain outside this change. No release ZIP, tag or GitHub Release was generated.

## Verification

- Final production revision `330712dc1572b01777dd53583b9b58bd12ded5da`:
  **Full: 139 files, zero failures, 160.0s**, two isolated workers.
- Package working-tree validation: **11 passes, zero failures**; six existing
  advisory prose/design warnings, no hard-cap increase.
- Main Chrome 156.0.8078.80 headless probe: **12 passing cases**, classic/light/dark
  × 2560/1920/1366/360px, exact columns, ECTX help, warning transitions/colors,
  focus-safe clearing, Credits/USD, wrapping, table pan, activity/history/accounts.
- Separate legacy summary probe: **nine passing cases**, classic/light/dark ×
  1920/1366/360px; rerun after its responsive assertion correction.
- Read-only real-installation Watch/session-cost/daily probe: **PASS**. Stable V2
  session matched independent full-report valuation; fresh repository revalued zero
  requests with no session-cache write. Daily category costs reconciled, while prompt
  attribution remained explicitly incomplete. One owner/two streams, preserved run
  origin, no owned cleanup failures or remaining workers; shared OpenCode untouched.
- Long-session regression: 2000 initial valuations; one added request requires one
  valuation; no-op/reorder/fresh repository/fresh Python process require zero
  valuations and zero session-cache writes. Canonical correction/deletion/late-child,
  compaction, concurrent-card, re-entry and cache-failure cases pass.

[Design, measured work and verification history](../../../journal/web/watch-session-summary.md).
GitHub checks and final merge state are recorded by PR #155 rather than claimed
in advance here. No test exception or waiver has been granted.

## Limits and investigated failures

Snapshots/fingerprints are still checked linearly for historical corrections; this
is incremental valuation/aggregate arithmetic, not constant-time source acquisition.
Headless DOM/layout evidence is not physical-desktop or actual screen-reader proof;
no model inference was started. A shutdown history-read error has no proven original
cause and does not establish failed published cost reconciliation.

An obsolete JS column-order assertion was updated for the requested contract. One
four-worker Full run failed existing PowerShell PATH-fallback discovery; the file
passed independently and subsequent complete two-worker runs passed without launcher
or assertion weakening. A real-source probe publication race was fixed in the probe
by waiting for the HTTP-published cost. The older browser probe's incorrect demand
for three cards at 1366px was corrected to the existing responsive two-plus-wrap
layout; no product CSS was changed for that assertion.
