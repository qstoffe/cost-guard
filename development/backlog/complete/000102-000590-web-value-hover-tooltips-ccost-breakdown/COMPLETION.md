# Completion — FR 000590

Implemented 2026-11-05 as Cost Guard **v80.171**.

## Delivered behavior

- All standalone Web/Mini help cues removed; useful help uses intrinsic visible text,
  immediate passive help cursor, deliberate keyboard/tap access and preserved selection/actions.
- One 600ms hover-opening policy, separate 150ms exit grace, pending cancellation and
  preserved focus/pinned/document ownership; long help stays within CSS-zoomed viewports.
- Concise Model/Effort help, exact clock targets, positively linked-agent model stars,
  conditional actual model/effort and Calls detail in both Full Watch tables.
- Canonical request/session/model/effort category costs, per-group/per-agent subtotals,
  full prompt total and Credits/USD variants; bounded 24-group export with honest omitted
  cost/calls, unavailable telemetry/pricing and linked agents without usage. No aggregate
  distribution, browser repricing, new acquisition or changes to I+E/CLI totals.
- Per-window inferred numeric Capacity has `(guesstimate)` across displayed surfaces;
  native comparable and unknown limits do not. Native factual details remain.
- Context/warning first and Total CCost second, unchanged severity/math; distinct Mini
  Session and Total CCost help within the existing one column.

## Verification

- Local Full suite: **144 files, zero failures, 89.4s**, four isolated workers. The new
  eight-test cost-detail file is explicitly registered in both Quick and Full.
- Working-tree validator: **11 checks passed**, zero failures; six existing advisory
  documentation/design-budget warnings, no raised cap/baseline. `git diff --check` clean.
- Actual owned headless Chrome 156.0.8078.80 and Document PiP: shared help, broad Mini
  suite and 12-case full Watch suite passed. Themes, narrow/zoom, hitboxes, accessibility
  structure/input, delay/lifecycle, rich cost bounds, units, quota provenance, warnings,
  selection and live/retained transitions covered; rich screenshots inspected.
- Read-only real V2 installation: prompt raw CLI/I+E/category parity, daily reconciliation,
  one owner/two streams/three accounts, advancing sequence and stable run origin passed.
  All owned workers closed, no cleanup failures, no model inference or shared-service stop.

## Limits and retained knowledge

Real sampled prompt had no linked agents; deterministic canonical fixtures cover nested/
concurrent/same-model and multi-effort agents. Daily prompt attribution was incomplete
despite complete cost; a transient history failure recovered before coherent publication.
Headless checks do not establish physical desktop/native blur, screen-reader, macOS or
other-engine behavior. Injected blur proves its handler only; immediate synthetic report
jobs are UI, not finite-process lifecycle evidence. **No verification exceptions**.

Current contracts: `development/architecture/modules/web-help.md`, `reports.md`,
`CODE_MAP.md`. Evidence/repairs/limits: `development/journal/web/contextual-help.md`
and `development/architecture/governance/verification/web-help-590.json`.
Current Web/Mini/account docs, README and version history updated. No release ZIP, tag
or GitHub Release generated; supported distribution remains current `main`.
