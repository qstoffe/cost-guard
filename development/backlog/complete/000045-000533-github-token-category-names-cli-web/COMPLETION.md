# FR 000533 completion

Implemented in v80.114 (2026-10-30), with the verification exceptions below.
The whole specification bundle was moved intact; its body was not rewritten.

## Delivered

- Shared Python display vocabulary: **Input / Cached input / Cache write / Output**,
  including explicit I/C/W/O expansions. CLI Normal, model/publisher history,
  all-model reference prices, Watch and prompt/session/date detail use the names.
- Additive application display metadata supplies the same labels/legend to Web
  Overview, Models/all catalog, historical model/publisher tables, Watch and
  Snapshot/Live session detail. Combined percentage cells use `Token Mix %`;
  compact prices/run totals have adjacent or accessible expansions.
- Raw fields/order, source adapters, acquisition, normalization, pricing/fallback,
  counts, shares, per-category CCost, samples, sorting, totals and persisted schemas
  are unchanged. Separate tests preserve observed zero, missing telemetry,
  published Cache write prices without observations and Not applicable rates.
- README/help/reference text and current golden expectations were updated. Current
  synthetic CLI text at 80/120/160 columns replaces stale embedded README images;
  historical binary assets remain. Prompt/Watch grids keep existing numeric minimum
  widths, documented in the text captures; renamed mix cells wrap and narrow
  historical tables use labeled rows without clipping numeric cells.
- Architecture presentation-owner facts and `development/journal/token-categories.md`
  document the shared boundary and limitations; no new analytics layer was needed.

## Actual verification

- Final `development/tools/run_tests.py --suite full`: **117 files, 116 passed,
  1 failed**; 1424 test cases reported, 2 built-in symlink-privilege skips. The
  suite is **not PASS overall**. The failing file is described below.
- All vocabulary/telemetry tests, model/publisher numeric correspondence,
  CLI-width cases and shipped-JS deterministic DOM checks passed, including
  Overview, Models/all catalog, history, date/range, Watch and session detail.
- `development/tools/validate_package.py --working-tree --json`: **PASS**,
  zero failures, four design-budget warnings; hard caps, version consistency,
  Python compatibility/import and architecture boundaries passed.
- `git diff --check`: passed. No live provider/model calls, OpenCode writes,
  runtime installation, execution-policy changes or Web promotion were performed.

Evidence stays outside this task payload:
`development/tests/evidence/fr000533-full-final.json`, `fr000533-package.json`,
the earlier quick/full reports, and `development/tests/fixtures/token-categories/`.
`integration/capture_token_categories.py` reproduces synthetic CLI text, not
browser/OS screenshots. Older failed runs retain their actual outcomes.

## Decision Delegate exceptions and uncertainty

1. **Real browser checks unperformed.** The authorized bounded headless check
   could not import Playwright (`ModuleNotFoundError`). No browser was launched
   or installed and no broader discovery was attempted. Decision Delegate
   authorized completion for this display-only change using passing deterministic
   DOM coverage and static responsive-CSS inspection instead. Actual desktop/360px
   light/dark rendering, clipping/wrapping and browser accessibility remain
   unverified—not PASS; no physical-device or assistive-technology proof is claimed.
2. **FAIL—execution-policy blocked.** Four `powershell.exe` subcases in
   `test_launcher_feedback.py` failed with script-disabled `SecurityError` /
   `UnauthorizedAccess`, exit 1 instead of 9009/17: missing Python and report,
   Watch and Diagnostics exit propagation. Corresponding `pwsh` cases passed.
   Decision Delegate authorized this narrowly identified unrelated exception,
   conditional on all other required tests and the validator passing. Intended
   Windows PowerShell behavior in this environment remains unverified; no
   assertions, launcher implementation or policy were changed to hide it.
3. Decision Delegate permitted minimal meaning-preserving recent changelog
   compaction under the unchanged byte cap, retaining all versions/dates and
   behavioral limitations, and current synthetic-text README examples in place
   of obsolete screenshot labels. No backlog history pruning/audit was performed.

The implementation is delivered; the browser acceptance scope and policy-blocked
launcher behavior remain outstanding verification work, not missing token logic.
