# FR 000510 — Remaining Web report and detail presentation

## Outcome

Implemented in v80.100 (2026-10-28); protected PR delivery is required before this
candidate is considered delivered. [Implementation candidate](https://github.com/qstoffe/cost-guard/commit/d6694ba67a5c1fd9ad1c9444150b5b2673906da0).

- Shared display tokens now supply configured-local prompt clocks, Next Ictx
  guidance, CLI historical mix category cells and exact aggregate-cost sort keys.
- Session summaries use shared CCost/money/duration formatting and truthful child
  breakdowns; clear Freeze/Follow controls, optional provenance and contextual
  warnings retain complete revision-aware pages, all-history totals and stable IDs.
- Date/range explanations use inclusive configured-local calendar dates rather
  than epoch milliseconds; historical Token Mix matches CLI table columns and
  total placement while keeping explicit capture/progress/cancellation.
- Added deterministic CLI/DOM tests, an explicit synthetic browser fixture and
  the [owner-facing matrix](../../../architecture/governance/verification/remaining-web-parity.md)
  for all requested views, with reviewed synthetic screenshots outside this bundle.

## Choices and preserved behavior

Formatting belongs in the existing application display seam; neither a browser
calculator nor a new acquisition/history owner was introduced. Optional details
replace repeated implementation prose. Horizontal table scrolling is intentional
on narrow screens; primary lifecycle/warning text remains visible.

CLI valuation/analysis, source ownership, account acquisition, history retention,
authentication, standalone host lifecycle and no-browser-storage behavior remain
unchanged. The selected FR and attachments were moved without edits. Repository
knowledge/routes were updated in place; journal assessment: **no-update** because
the owner documentation and focused evidence contain the reusable facts.

## Verification and limitations

- Full suite: 113 isolated files, 1,373 passing tests, zero failures/errors/skips.
  Package validation: zero failures, four design-budget warnings.
- User-approved OpenCode built-in browser: complete 120-row detail, 50-row DOM,
  first/middle/latest pages, constant whole-session totals, mode-specific running
  labels, retained selected row/cell identity and narrow 360px layout inspected.
- History navigation admitted zero scan jobs; explicit capture showed progress,
  cancellation marked that synthetic finite job cancelled, and a second explicit
  job displayed the canonical historical result. Browser storage stayed empty.
- Ordinary-installation read-only Web Diagnostics: `not_observed`, no snapshot;
  this is **not** live-installation readiness or real-provider browser proof.
  No inference, provider probes, shared-service stop or automatic restart.
- Native macOS, physical-input, screen-reader and dark visual acceptance were not
  run. Partial/empty/missing/retained combinations retain deterministic coverage,
  not a claim that every combination has a browser screenshot. See the matrix.

## Repairs and follow-up

Full-suite checks caught and repaired a compaction-preview regression and restored
the established inclusive-range label while removing epoch prose. An exploratory
wildcard `--pattern` run timed out because it was treated as one file-sized unit;
the supported isolated Full suite then passed. Any runner UX proposal is deferred,
not implemented cross-scope. Hidden Review-pane screenshot failures were recorded
as limitations, not substituted with invented captures. No permanent release gate
or platform certification was added.
