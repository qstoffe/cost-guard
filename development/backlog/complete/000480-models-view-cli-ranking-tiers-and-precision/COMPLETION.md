# Completion — FR 000480

Implemented 2026-10-27 in Cost Guard v80.97.

- Preserved CLI selectable/full-catalog membership, independent completed-priced
  sample and exact default server rank. No pricing, sampling, account or CLI changes.
- Aligned one-decimal multiplier/tier cells with > / ≥ K/M boundaries; no-sample
  relative cells stay blank, retaining promotional markers. Native published USD/M
  digits remain exact and explicitly separate from billing. Recent/superseded
  semantics, availability fallback/verified-empty states and notices remain visible.
- Added active catalog controls, complete wrapped long names, internal narrow-screen
  scrolling, exact numeric native-price sorting, stable ties/unknowns-last behavior
  and default-order restoration.

## Verification

Full suite: 110 files, zero failures. Working-tree package validation: zero failures,
four existing design-budget warnings. Headless Edge: 16 synthetic view cases across light/dark and
1200px/360px passed. Real-installation V2 probe completed Normal/all-models/sessions/date
alongside one live owner/two streams; cancelled deep history and closed owned workers,
without inference or shared OpenCode shutdown.

The initial suite overlapped temporary browser profiles and failed package-copy/hygiene
checks; rerunning the entire suite after browser completion passed unchanged.
[Detailed checks, receipt and proof limits](../../../architecture/governance/verification/models-display-parity.md).
Physical input, screenshot/contrast, assistive-technology and native macOS acceptance
remain unclaimed; real-source HTTP and synthetic browser evidence are separate.

## Knowledge and dependencies

No architecture-boundary changes. Updated affected module/code-map/display-parity
routes. Journal no-update: no new durable analysis/provider finding. Remaining Accounts,
host-status and report/detail FRs stay pending and intact; no new cross-FR dependencies
or external recovery artifacts are required. Selected FR bytes are preserved unchanged.
