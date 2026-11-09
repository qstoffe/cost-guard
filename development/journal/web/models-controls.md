# Models source controls, filters and value help — FR000656

2026-11-09; v81.5, based on `a12ec872a4305423215f0a55cf649780c3cd3d15`.
Scoped implementation/verification, not a whole-Web or pricing audit.

## Ownership and semantics

- Keep the existing independent `BenchmarkLane`, finite worker, complete Harbor
  4.0 validation and separate atomic last-good cache. Empty-body authenticated
  `POST /api/models/benchmark/refresh` records coalesced forced demand; the host
  still owns actual acquisition, budgets, cancellation and normal 24-hour freshness.
  Failed reads retain the original data/date, without price/report refresh.
- `application/benchmark.py` admits only unique exact publisher/version identities
  against the retained GitHub catalog, including the existing Claude prefix
  equivalence and qualified publisher URL. It exports canonical names and existing
  availability/supersession flags. Raw Harbor configurations remain in the snapshot;
  clients/efforts are never merged. Both the denominator and available effort list
  come from the entire validated edition, not the eligible or visible intersection.
- `benchmark.js` owns five independent sortable tracks, local Copilot/effort choices,
  a native keyboard/touch details multiselect and targeted intrinsic value help.
  Default All admits new source efforts; a chosen subset does not. Empty selection
  remains empty; missing effort has its own truthful option. Section/card decoration
  is removed; only Solved stretches. Shared toolbar CSS supplies both source rows.
- The frozen report exports the exact published native USD tier text and actual
  pooled comparison shares/count. Application display balances percentages to
  100%; browser help does not use the broader Token Mix report or sorting fallback.
  Promotion facts remain in the price block. Source rates/tiers, token eligibility,
  reference ratios, valuation and CLI semantics are unchanged.
- Both fetched dates use `format_local_timestamp` with the same report-configured
  timezone. HTTP never invokes upstream I/O; row-value help never fetches anything.

## Executed evidence

- Local Full runner: **181 isolated file entries**, 179 initially passed; two failed
  only on the old Models heading/source-toolbar expectation. Their causal updates
  passed `test_web_overview` and `test_web_views` (three tests). This does not claim
  that the original Full invocation was all-green.
- Current focused regression group: **52 tests passed** across Models, workload mix,
  display, Harbor/HTTP/manual lane, overview/views and pricing refresh. Coverage
  includes unique/version/publisher joins, all checkbox combinations, full-source
  denominator/options, absent/zero/partial/tiny costs, exact tiny native rates,
  one/multiple tiers and boundaries, promotions/refresh, empty/short/99/100/121
  histories with a maximum actual 100 sample, and truthful missing distribution.
- Hidden installed Chrome layout probe: six light/dark cases at 360/1366/1920,
  Classic/Web and 100/125% zoom, all PASS. Five headers, no outer card/frame,
  document vertical scrolling, narrow horizontal pan, no clipped values, independent
  sorts, High/zero filters, native dismissal and intrinsic value-help targets.
  Artifact: `scratch:/evidence/models-chrome.json`.
- Authenticated Chrome controlled-source browser probe: PASS, **12 interaction
  checks and 247 layout records**, including 240 toolbar combinations over five
  widths, Classic/Web light/dark, 100/125/150/200% text scaling and normal/refreshing/
  long-error/unavailable states. Native keyboard/touch value help, text selection,
  Escape, effort zero/High-only, independent choices, fresh-cache forced Harbor
  refresh/coalescing/failure/last-good/recovery and independent price refresh pass.
  Artifact: `scratch:/evidence/models-refresh-chrome.json`.
- Final authenticated Edge controlled-source probe: PASS, **12 interaction checks
  and 247 layout records**, covering the final effort-focus restoration/menu bounds
  and refreshed GitHub rate help (`Input $10`, `Output $40`) with the same Token Mix.
  The matrix includes the same 240 width/theme/text-scale/status combinations.
  Artifact: `scratch:/evidence/models-refresh-edge.json`. Its inspected benchmark
  screenshot shows the unboxed section, separated headings, compact first four
  tracks and Solved alone filling the remaining width in the High-only state.
- Real workstation `probe_web_live.py --benchmark --benchmark-cold`: PASS. **35**
  real Harbor rows, **27** exact matched rows, **29** GitHub reference rows; actual
  **100** completed priceable comparison prompts with verified 100%-summing help.
  Source efforts: high/low/max/medium/none/xhigh, not a hardcoded choice list.
  Successful fetch `1794260726302`; forced fresh-cache fetch `1794260728160`.
  Full-source denominator, canonical join/availability, configured-local date and
  unchanged retained GitHub pricing snapshot verified. One V2 Live owner/two streams,
  no model calls, no owned threads/processes at exit; shared OpenCode untouched.
- Initial browser helper's native Enter event omitted text and did not toggle the
  native details summary. Supplying the real Enter/Space text sequence repaired the
  probe, not product behavior. Initial HTTP fixture lacked lifecycle observations;
  correcting that fixture and its actual CSRF header resolved its setup failures.
- Final `validate_package.py --working-tree`: **0 failures, 11 passes**, version
  consistency **v81.5**, with seven existing advisory size warnings. Layout/hygiene,
  UTF-8, file budgets, Python 3.11 syntax, compile/import and layer checks pass;
  no cap or baseline was raised. `git diff --check` reported no whitespace errors.

## Verification limits

Integrated browser DOM/layout read succeeded; screenshot capture explicitly required
a visible desktop tab despite focus and was unavailable. No visible-desktop action
or permission escalation was needed: hidden browser geometry/input evidence was
adequate. Controlled browser jobs do not establish production process concurrency;
real finite spawn/cache tests and the real-source host probe provide separate proof.
No physical desktop, assistive screen-reader or native macOS acceptance is claimed.
No new waiver, dependency, inference, tag, ZIP, GitHub Release or unrelated work.
Remote checks and merge truth belong to the delivery PR.
