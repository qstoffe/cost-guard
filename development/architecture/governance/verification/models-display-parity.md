# Models display parity — FR 000480

Checked 2026-10-27 against implementation based on `ac6079864fc54934581bb25c97c7de0a34b772a6`.

## Ownership and regressions

The CLI and Web consume the same canonical comparison projection. No price formula,
membership, availability acquisition, completed-prompt cutoff or account mutation changes.
The existing shared display tokens retain one-decimal `x`, tier direction and K/M bounds.
Models now aligns base multipliers, keeps fallback relative cells blank, distinguishes
native reference rates from billing, and exposes active selectable/full-catalog controls.
Exact native rate strings supply numeric vector sort keys; rounded/visible cells never
establish order. Unknowns stay last in either direction, equal values stay stable, and
the third heading click or CLI default order button restores the supplied server order.

`test_web_models.py` and `integration/web_models.cjs` compare the same reports with the
terminal: selectable/full membership and default ranking, values that round to `8.0x`,
promotion/recent/superseded roles, >200K and ≥1M tiers, fallback and verified-empty
availability, absent prices, complete long names, filtering and exact deep-decimal sorting.
`test_web_overview.py`, `test_web_display.py` and HTTP-backed `test_web_views.py` retain
neighboring view/notice/sort coverage.

## Observed checks

- Full bounded suite: 110 test files, zero failures (44.6 seconds).
- Working-tree package validation: 11 passes, zero failures; four existing design-budget warnings.
- Explicit headless Edge: all four 1200px/360px × light/dark cases passed, each testing
  selectable/full catalogs with and without a priced sample (16 view cases).
  Measured base-ratio right alignment, complete long-name filtering, name/numeric
  alignment, internal horizontal scrolling, no document overflow and sort restoration.
  Receipt: [synthetic browser observations](models-browser.json).
- Read-only real-installation `probe_web_live.py --reports`: V2, one live owner,
  two streams, four retained rows, three accounts; Normal/all-models/sessions/date
  completed; deep history cancelled. Run origin/live owner preserved; owned workers
  closed; shared OpenCode untouched. No inference was requested.

The first full-suite attempt overlapped the browser's temporary profile, causing
directory-hygiene/package-copy failures. After the browser finished and removed its
profile, the complete suite passed unchanged. Probes and package-copy checks must run
sequentially. The browser probe explicitly serves UTF-8 so arrows/thresholds exercise
the production encoding rather than a fixture-default character set.

## Limits and knowledge assessment

Headless synthetic DOM/layout is not physical mouse, screenshot, contrast measurement,
screen-reader or native macOS acceptance. Real-source HTTP proof is separate from
synthetic browser rendering; no claim of combined live-history browser acceptance.
No architecture-boundary change. Existing module/code-map/parity routes were updated;
journal no-update: no new analysis/provider knowledge or invalidated historical finding.
