# FR 000596 — Web Token Mix

Implemented for v80.178 (2026-11-06), against main base
`904c9aea9a5f0e682437b74d7f66d3d5a6d813ff`.

## Delivered behavior

- One actual total-token heading and four-category summary, followed by exactly
  two uncapped 13-column model/publisher tables. Full single-line names and metrics
  pan horizontally; the document scrolls vertically. All headings sort independently
  by exact integer, rational share or Decimal values, with unknowns last.
- Shared text-only contextual help, prepared Credits/USD tokens and explicit
  Partial/N/A replace the old report shell, filters/pager and question-mark clutter.
- An intentional bounded first load enables quiet approximately-five-minute checks
  only on the active visible page. Slow/failed updates retain usable values and
  actual observation provenance. Whole-payload validation and keyed reconciliation
  preserve independent sorts, unit, row identity, focus and scroll/pan.
- Web-only compact revision-keyed request facts reuse canonical per-request category
  valuations. Changed/new/late roots refresh, deleted roots drop out, catalog changes
  invalidate pricing and availability changes regroup without repricing. Active or
  unstable roots are not persisted. Batched cache I/O and bounded observed source
  batches preserve the private finite-job deadline/cancel/parent-loss protections.
  Concurrent/recent tab jobs coalesce; heavy work stays outside Live. CLI semantics
  and other views are unchanged.

## Verification

- `py -3 development/tools/run_tests.py --suite full`: PASS, 149 files, 96.5s,
  including the newly registered focused Token Mix file.
- Focused final cache regressions: 10 tests PASS (11.436s), including cross-root
  clone deduplication, >500-key unchanged reuse without hydration/repricing,
  changed/new/deleted/late usage, active/empty/zero scope and optional cache failures.
  Served-HTTP/DOM tests additionally cover partial/huge values, units, navigation,
  visibility, one slow update, failure retention and malformed payload rejection.
- `py -3 development/tools/validate_package.py --working-tree`: PASS, 11 checks,
  zero failures; six advisory prose/design-budget warnings remain. No cap increased.
- Read-only installed V2 history: both fresh-cache cold and warm production jobs
  completed within the unchanged 120s limit, in 88.075s / 4.255s. Of 2728 roots,
  warm reuse hit 2709 and reanalyzed only 19 unstable roots (707 requests). Child
  CPU was 44.906s / 2.984s; both results had 12 model and 3 publisher rows.
  Detailed numeric/source counts are in `development/journal/web/token-mix.md`.
- Hidden Chromium with shipped authenticated HTTP/CSP/assets: virtual-overdue
  campaign PASS across nine theme/width layouts, 65 rows per table, all 26 headings
  both ways, exact independent expectations, unknown-last, help/Escape, units,
  navigation reuse and slow coherent replacement retaining focus/scroll/nonzero pan.
- Final real-wall-clock Chromium campaign: PASS, refresh after **300034ms**, with
  the same matrix and a slow coherent replacement preserving all tested anchors.
  Sanitized synthetic evidence: `scratch:/token-mix-browser-wall-clock.json`.

## Limits and decisions

No requirement/test exception was requested or granted. Browser fixtures are
synthetic, not physical desktop, screen-reader or macOS acceptance. Real V2 timing
is installation/load dependent, not a universal success guarantee for every history;
timeout/revision failures retain the prior usable result. No model inference,
shared OpenCode stop, new dependency, tag, Release or release ZIP was used.
Current main remains the supported distribution.
