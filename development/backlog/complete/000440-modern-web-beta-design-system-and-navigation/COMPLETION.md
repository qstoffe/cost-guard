# Completion — FR 000440

## Outcome

Implemented in v80.93 (2026-10-27): a shared, local-only responsive light/dark design system, clearer main navigation and modern table/control surfaces. Global **Watch** uses `/#/watch`; legacy `/#/live` is replaced in its current history entry. Session Snapshot/Live remains distinct. Original FR bytes are unchanged.

Implementation candidate: [0f1734ba43829b2092a0177673f42d3843e399b7](https://github.com/qstoffe/cost-guard/commit/0f1734ba43829b2092a0177673f42d3843e399b7).

## Changes and alternatives

- Shared tokens define spacing, surfaces, typography, semantic color, radii and restrained depth. System light/dark and reduced-motion preferences require no theme storage, external fonts, CDN, Node build or new product dependency.
- Navigation, focus/hover/active states, responsive action areas, filters, sort indicators, sticky headings, numeric alignment and locally scrolling table panels retain visible/selectable data and textual status meaning. Static definitions alone move into native details; no report fields or rows are removed.
- Chose `history.replaceState` rather than pushing a redirect entry so legacy bookmarks/reloads preserve useful Back/Forward behavior. Canonical Watch and session `/live` remain separate routes.
- No changes to CLI, account editing/login, report semantics/DTOs/limits, auth/bootstrap, acquisition, run origin or host lifecycle. Separate page-specific parity FRs remain pending; this does not pre-implement their information layouts.

## Evidence and tests

- Full suite: **107/107 files PASS**, zero failures, 42.8s. Initial old-footer assertion failure was repaired to pin the intentional Watch naming, then the full suite reran successfully.
- Package validator: **PASS**, zero failures, four existing design-budget warnings. No hard caps or assertions were weakened.
- [Offline synthetic before/after gallery](../../../architecture/governance/verification/web-design/index.html), twenty actual Edge screenshots and [review/evidence details](../../../architecture/governance/verification/web-design.md). Five required views, both themes, 360px and 1440px; canonical table content matches before/after. Reviewed evidence hashes are outside this immutable bundle.
- Actual Edge checks confirm no after-preview page overflow, focus outline, sticky-heading style and reduced-motion behavior. VM integration covers canonical/legacy Watch, reload and session Live distinction; the optional hosted Chromium smoke also exercises real Back/Forward, dark/narrow/focus/reduced-motion behavior.
- Real V2 live/detail probe: **PASS**, one engine/account owner, two streams, preserved origin and frozen detail. Owned work closed; shared OpenCode untouched. No model inference.

The exploratory broader report probe did **not** pass: normal report hit the existing `result_too_large` bound after 1,853 history candidates; later report modes were not reached. This is recorded separately, not converted to success or repaired by expanding the 8 MiB policy. Normal-report acceptance on this installation's full history remains unproved.

## Assessments and limits

Journal: **no-update**; no new reusable debugging conclusion. Architecture boundaries: **no-update**; existing asset/router/render ownership remains intact. User docs/version/history and focused visual evidence are updated in this delivery. Native nextState/retention are preserved exactly; there are no completed bundles to prune.

Physical keyboard/mouse, screen-reader, high-DPI and native macOS acceptance and subjective owner sign-off are not claimed. The captures use synthetic data, not user sessions or accounts. Optional hosted browser execution is not implied by local fixture capture results. No release ZIP, tag or GitHub Release was created.
