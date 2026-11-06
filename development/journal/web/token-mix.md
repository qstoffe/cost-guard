# Web historical Token Mix

Source revision: 904c9aea9a5f0e682437b74d7f66d3d5a6d813ff
Checked revision: 904c9aea9a5f0e682437b74d7f66d3d5a6d813ff
Last checked: 2026-11-06
Status: current

## Summary

FR 000596's delivery diff adds a dedicated retained Web view and Web-only compact
history acceleration. The source revision above is its inspected base, not a claim
that the old main already contains the implementation. CLI acquisition remains
unchanged; both paths share canonical clone deduplication, availability filtering,
model/publisher grouping and per-request model/tier valuation.

One total-volume heading and compact four-category summary precede exactly two
13-column tables. Shares compare exact integer ratios; costs compare Decimal wire
strings. Prepared display tokens keep units and readable Partial/N/A independent of
sort keys. Keyed reconciliation, whole-payload validation and one active-visible
five-minute timer retain usable results during refresh/failure. Jobs coalesce
in-flight and recent checks without inventing a new observation timestamp.

## Evidence

Reproduce deterministic coverage with
`py -3 -m unittest development.tests.test_web_token_mix development.tests.test_web_remaining development.tests.test_web_views -v`.
The cache tests cover CLI equality, children, cross-root clone fingerprints, unknown
prices/telemetry, huge exact counts, zero/empty scope, active-root misses, optional
cache errors/corruption, changed/new/deleted roots, price invalidation and
availability-only regrouping. A stable 520-root warm run forbids both source
hydration and canonical repricing, exercising the >500-key SQLite read boundary.
The served-HTTP Node fixture covers hidden/inactive deferral, one slow refresh,
failed-refresh observation retention, units and persistent DOM identity. Full now
includes the focused Token Mix test file rather than silently omitting it.

Real installed V2 history is measured read-only with
`py -3 development/tests/integration/probe_token_mix_baseline.py --cold-and-warm`.
Each run uses production isolated ReportJobs, the unchanged 120-second deadline
and its own temporary empty cache; output is numeric timing/counts, not history
content. The original uncached Web path timed out at 120.058s after 374/2727 roots.
Earlier 16-root/per-root-connection candidates also timed out. The completed
64-root/bulk-SQL candidate initially completed in 96.937s cold and 4.206s warm.
The final repeated run over 2728 roots measured:

| Observation | Empty-cache cold | Warm incremental |
| --- | ---: | ---: |
| Parent elapsed seconds | 88.075 | 4.255 |
| Child elapsed seconds | 87.740 | 3.913 |
| Child CPU seconds | 44.906 | 2.984 |
| Compact cache hits / misses | 0 / 2728 | 2709 / 19 |
| Canonically valued requests | 55284 | 707 |
| Full catalogs / pages | 44 / 2112 | 2 / 96 |
| Message operations / pages | 2799 / 5080 | 22 / 53 |

Both completed with 12 model and 3 publisher rows. Nineteen unstable roots were
not cached: the warm measurement is not a claim of zero work on active history.
Live source churn/load changes timings; this is not a universal 120-second SLA.
The separate stable fixture proves the no-hydration/no-repricing path causally.

Hidden real Chromium proof uses
`node development/tests/integration/probe_token_mix.cjs <verified-browser-executable> <existing-scratch-output.json> --wall-clock`.
It uses an isolated profile and synthetic 65-row/model-and-publisher history served
through shipped authenticated HTTP/CSP/assets. It checks 360/1366/1920 widths across
Classic/light/dark, uncapped single-line rows, horizontal-only panning, all 26
headings in both directions with independent integer/rational expectations,
keyboard help, units, return navigation and a real five-minute slow replacement.
The virtual-overdue browser campaign passed all nine layouts, all 26 headings,
units/help/navigation and coherent replacement with real nonzero horizontal pan,
focus, scroll and row identity retained. The sanitized wall-clock outcome is
retained in task completion evidence, not inferred from the timer being installed.
The corrected final wall-clock campaign passed the same layout/sort/help/unit/
navigation/retention assertions, with its actual refresh starting after 300034ms.
Owned synthetic evidence: `scratch:/token-mix-browser-wall-clock.json`.
Earlier acquisition races and a null-progress fixture failed; they are not browser
PASS evidence. An initial wall-clock run reached its valid cadence but then failed
an invalid expectation: the fixture's small raw cost change rounded to the same
display text. The corrected fixture crosses a display-rounding boundary rather
than weakening the replacement/anchor assertion.

## Next investigations

Keep the initial deep scan bounded: much larger or continuously changing histories
can still exceed the existing job deadline or source revision-retry bound. Cache
loss is safe but makes the next capture cold. More cross-machine performance and
physical/assistive/macOS acceptance remain unmeasured; synthetic Chromium layout
is not native desktop or screen-reader proof. No new inference, account polling,
shared OpenCode stop, dependency or release archive is involved.

## Rejected hypotheses

- A periodic full CLI-style scan is not an adequate freshness implementation: the
  established 491-second historical CLI observation exceeds the Web deadline.
- Smaller source batches alone did not suffice; repeated catalogs and independent
  SQLite connections dominated. Bounded observed batches plus bulk cache I/O were
  necessary for the measured candidate.
- Aggregating tokens then applying one representative price is invalid. Compact
  facts store canonical per-request category valuations; regrouping never invents
  a new price engine or durable history ledger.
- A raw usage change need not change rounded text. Browser replacement fixtures
  must deliberately cross a display boundary if they assert visible text changes.
