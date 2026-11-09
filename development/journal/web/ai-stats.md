# AI Stats: fun-first numbers and resumable history

Source revision: 9b9fdf389d93d90a09bfa13e9b075b564d026961
Checked revision: 441b30a3aa6835a922598e32a5b9357bd062d8f7
Last checked: 2026-11-09
Status: current

## Comparable hourly rates — FR000655

Scoped delta against `791e0f45e6eeca1a3a184635ffcfdbe5c125ad3c` (2026-11-09):
the first retained card now shows Calendar average, Workday average and Active AI
average, all per hour. `application/ai_stats.py::rate_tokens` formats the existing
raw `active_rate` directly, never the rounded shift or capped legacy `Stat.value`.
Calendar/workday denominators, period membership, unioned elapsed activity and the
Stats-only best-effort policy are unchanged. Typed raw `robot_day`/`robot_period`
compatibility fields remain; their prepared card tokens are no longer emitted.

One safe plain-text title tooltip retains three short paragraphs in row order,
each ending with a compact formula. Reference-Credit active-intensity tiers retain
gentle snack/buffet jokes without salary/replacement claims. Idle and uncertain
inputs keep neutral copy; the browser's cold-failure help matches prepared idle
help. Existing ContextHelp, DOM identity and currency bindings own live refresh.
No acquisition, source, pricing, dependency, layout or other-card behavior changes.

Deterministic oracles cover 840 Credits / 7 dates / 5 workdays / 28 active hours =
5/21/30 CCost/h ($0.05/$0.21/$0.30 per hour), independent denominator changes,
100 Credits / two overlapping active hours = 50 CCost/h and one minute = 6000
CCost/h, raw Decimal-before-formatting, tier boundaries, zero active time,
no-workdays, all five periods and both units. The rates file is now explicitly
registered in Quick/Full so its regressions also run in the normal suite.

The integrated browser was disconnected. The existing hidden Edge probe is the
non-disruptive alternative; no physical desktop, screen-reader speech or real
touch-device proof is inferred. The historical FR000644 results do not prove this delta.

Current verification: Full **181 files, 2,217 passed, two macOS-only skips, zero
failures/errors, 133.9s**. Validator **11 passes, zero failures, seven existing
advisory warnings**, no budget increase. `scratch:/full-tests.log`,
`scratch:/full-tests.json`, `scratch:/validation.log`.

Hidden Edge **PASS, 17 checks, 72 state/theme/unit cases, nine layouts, 80 text
layouts, 1,350 contrast samples, zero runtime errors**. Three formula paragraphs
fit at 360/1280 widths, enlarged text/zoom and all themes/units; real keyboard,
hover, emulated touch, live focused help, Escape suppression, retained failures,
ten-card identity and production finite slices/two-tab association passed. Owned
browser/server exited cleanly. `scratch:/ai-stats-browser.json`.

Read-only real installation: four error-free completed requests, five periods ×
ten metrics; raw rate identities and both-unit active-rate tokens/formula help
checked. Cold30 **135.612s**, warm30 **5.054s**, All reuse **0s** (not a cold scan),
fresh warmAll **5.462s**. Disposable own cache, no OpenCode writes/stops. Timings
overlapped Full/browser checks and mutable source, not a paired performance claim.
`scratch:/ai-stats-live.jsonl`. No acceptance exception or deferral was needed.

## Historical first-card implementation — FR000644 (presentation superseded by FR000655)

Implementation delta from `a835c7881f368cb82fd1363e856183b1d45f7d45` (2026-11-09),
not a fresh audit of unchanged reports. `analysis/ai_stats_rates.py` computes
nominal local date/workday denominators and hypothetical shifts from the existing
period cost and unioned/bounded duration. `Stat.value` retains the original capped
active-hour rate for compatibility/traits; explicit raw `rates` retain the uncapped
active basis, calendar/workday averages, robot shift and workday-count projection.
All amounts are canonical reference Credits; only final application tokens use
`ccost_amount()` (100 Credits/$1). No browser division, source scan or price lookup
is added. Shared compact evidence/cache identities remain reusable.

Today is one date, rolling 7/30 use exactly 7/30 local slots ending today while
their cost membership remains trailing hours, month ends today, and All time starts
at the earliest positive included request/activity evidence. Gaps count; guessed
interval recovery never supplies an invented calendar beginning. Existing timezone,
`is_workday()` and configured SE/weekend-only calendar own eligibility. DST retains
nominal 24/8-hour divisors without changing measured work. No-workdays is distinct
from zero cost; zero active time keeps the other rows and a neutral zero robot.

Only the retained first card gets three labeled accessible groups. Existing grid,
trait and title ContextHelp remain; Python prepares all unit variants and math help.
Focused heading/card identity and unit bindings survive updates. Other nine metrics,
matched facts, Watch, CLI and canonical valuation are unchanged.

Deterministic coverage: 840/7 dates/5 workdays/28 active hours yields 5, 21 and 240
Credits; changing active time alone to 7h yields a 960-Credit robot. Christmas SE
versus weekend-only changes W=4/5 and workday/period projections, not the shift.
Tests also cover morning Today, weekend/holiday zero workdays, DST/year/month edges,
exact rolling cost boundaries, local All-time gaps/request beginnings, overlap,
broken/zero duration, both unit tokens and configuration through warm evidence.

Read-only real-installation cold/warm probe completed four requests, all five
periods × ten metrics, with all rate identities and both-unit tokens checked:
cold30 **116.184s**, warm30 **6.114s**, All reuse **0s** (not a cold scan), fresh
warmAll **5.512s**. No job/result errors. It used a disposable owned cache and did
not stop or write OpenCode. Mutable-source timings overlapped Full tests and are
not a paired performance comparison. Evidence: `scratch:/ai-stats-live.jsonl`.

Full: **179 files, zero failures, 123.6s**. Validator: **11 passes, zero failures,
seven existing advisory warnings**, no budget increase. Later targeted checks cover
the final exact active-hour help formatting (Stats/recovery/resume all passed).
Evidence: `scratch:/full-tests.log`.
Final hidden Edge browser probe: **PASS, 16 checks, 72 state/theme/unit cases,
9 layouts, 80 text layouts, 1,350 contrast samples; zero runtime errors**. It checks
the three-way example, independent faster robot, no-workdays, ten stable cards,
both units and focused help, actual text/clipping geometry at 360/520/1280 widths,
100–200% text and 125% zoom, Classic/Web light/dark, keyboard/touch/Escape, session
links, retained failure/update behavior and production finite slices/two-tab reuse.
Owned browser/host processes exited cleanly. Evidence:
`scratch:/ai-stats-browser-final.json`. An initial probe found a fixture period
selection mismatch after the new Today case; correcting that harness state preserved
the product assertions and the full rerun passed.
The integrated desktop browser was disconnected; hidden Chromium is the
non-disruptive browser route. No physical touch, native desktop or actual
screen-reader speech is claimed, and no permission/acceptance exception is inferred.

## Earlier fun-first implementation

FR000633 implementation delta against the revision above, not a fresh audit of
unchanged reports. The owner deliberately replaced conservative AI Stats-only
calculation/presentation: ten finite numbers and playful traits in every period,
with no evidence caveats, badges or hidden explanations. Canonical Watch, Sessions,
CLI, Token Mix, Comparisons, valuation and execution-duration contracts stay strict.
No source writes, paid inference, new service or persisted prompt text are added.

Owners: `src/analysis/ai_stats.py` calculates Stats; `src/reports/ai_stats.py` and
`ai_stats_evidence.py` acquire/checkpoint/project; `src/application/ai_stats.py`
prepares both units; `src/web/stats_jobs.py` schedules bounded slices;
`assets/ai-stats.js`, `app.js` and `cached-reports.js` retain/render fun results.
Responsibilities/dependencies are unchanged; CODE_MAP changes are navigation-only.

### Stats-only heuristic rules

- `fun-1` unions reliable measured intervals first and clips to period/observation.
  Broken known-start intervals use the next root-local timestamp, capped at four
  hours, or one minute if absent. Running unknown ends use observation, capped at
  four hours. Missing starts use a real request timestamp with a bounded supplied
  duration or preceding one minute. No timestamp means no invented date.
- Request-only activity gets one-minute preceding pulses. Broken histories may
  fill uncovered request timestamps; complete measured histories do not gain time
  from requests at their edge. Union/dedup, half-open concurrency, selected-local
  calendar/DST splitting and stable record ties remain. Winners/links use real roots.
- Valid finite nonnegative known cost up to $1e9/request wins. Missing prices use
  pooled known same-model cost/token (capped $.001/token), otherwise $.000003/token.
  Missing input/output assumes 250/1,000 tokens; cached/write assumes zero. Guessed
  tokens cap at ten million and supplement at $10/request. Known cost is retained.
  Pending time-only activity gets $.003/root; fully empty known tokens stay zero.
- Zero denominators produce zero, not null. Rates cap at $1e9; prepared numeric
  displays clamp to 1e12 and percentages to 100. These are fun-page rules, not a
  change to canonical telemetry, CCost or global `None`/`source_complete` meaning.

### Acquisition, cache and presentation

All five rows publish from usable slices before complete coverage. Changed roots
may retain this observation's usable Stats facts but lose newer-revision proof;
deleted roots are removed. Actual `ai_stats_work` remaining/readiness stays truthful.
No private progress of 100 means a partial scan finished. Six nonadvancing slices or
nonbusy checkpoint failure settle a usable snapshot; BUSY retries back off. Existing
256-root slices, 64-root batches, maximum-four V2 reads, 100,000-root/250,000-fact
limits and finite-process/cancellation/security ownership remain.

Stats compact algorithm is `ai-stats-evidence-5-fun-1`; coverage remains version 2.
Projection/browser policy `fun-1` rejects old conservative retained results without
invalidating unaffected shared evidence. Private reason/status/source diagnostic
facts survive, but prepared display emits only value/trait. State, explanation,
interval and technical-history-summary DOM are removed, not CSS-hidden. Warm
updates retain cards; a never-successful cold failure gets ten playful zeros and no
invented session links. Optional matched facts retain their independent eligibility.

## Evidence

Reproduce on a local workstation with disposable own caches:

```text
py -3 development/tools/run_tests.py --suite full
py -3 development/tools/validate_package.py --working-tree
node development/tests/integration/probe_ai_stats.cjs <headless-browser> <output-json>
py -3 development/tests/integration/benchmark_ai_stats.py --baseline 9b9fdf389d93d90a09bfa13e9b075b564d026961 --sliced
py -3 development/tests/integration/probe_ai_stats.py --cold-and-warm --budget-seconds 600
```

Focused tests cover mixed missing starts/ends/tokens/prices, running/old/incomplete
roots, all five periods/both units, empty/extreme inputs, healthy formulas, DST,
ties/dedup, early slices, revision churn, bounded stalls and checkpoint recovery.
`test_web_dispatch.py` preserves strict rejection/omission for Token Mix/Comparisons
while asserting the deliberate Stats exception. Single-pipe mock dispatch disables
speculative background admission; real process/production probes are separate.

Initial read-only observation covered **2,980 roots**. Final post-sharing probe:
four complete/error-free requests, five periods × ten values; cold30 **129.005s/12
slices**, warm30 **6.774s/1 slice**, All reuse **0s** (not a new cold scan), fresh
warmAll **6.216s/1 slice**. Private missing-duration/price/running reasons survived.
These mutable-source timings overlapped other tests: acquisition/population proof,
not paired speedup or browser paint. `scratch:/ai-stats-live-delivery.jsonl`.

Final post-sharing Full: **174 files, zero failures, 124.1s**, four isolated workers.
Validator: **11 passes, zero failures, seven existing warnings**, no raised budgets.
Follow-up focused Stats/recovery/resume/Token Mix: **62 tests passed**; focused
Stats/recovery/resume after sharing: **51 tests passed**.

Hidden Edge complete probe: **PASS, 16 checks, 54 canonical state/theme/unit cases,
9 layouts, 80 enlarged-text layouts, 1,350 contrast samples, zero runtime errors**.
Actual HTTP/assets, hover/focus/touch help, keyboard/session links, retained warm
refresh, cold-failure zeros and all five periods/units were exercised. Production
two-tab fixture: 7 days ready at 2/24 roots; 12 finite children/exactly 24 hydrations;
original broad goal resumed without another selection. All owned host/browser/
worker resources closed cleanly. Post-sharing rerun passed the same full probe:
`scratch:/ai-stats-browser-delivery.json`.

Profiling identified repeated local-day boundary construction as the largest
Stats-local self-time consumer. Boundaries now reuse one calculation-local entry
per calendar day, preserving timezone/DST behavior; a disjoint spring-transition/
next-day regression pins actual night/day totals. Healthy costs skip unused rate
pooling, and aligned request/value sequences avoid repeated rich-entry hashing.
No persistent cache, new dependencies, canonical analysis change or heuristic
change is involved. The benchmark now waits on explicit selected-scope readiness
and applies the same sliced settings to both capable builders; earlier current-only
sliced timings were not a like-for-like latency comparison.

The Delegate did not accept the initial residual cold CPU regression (about 68%
for 30 days and 44% for All time). It directed one bounded preparation-sharing
repair before reconsideration: `StatsObservation` now reuses unclipped intervals/
flags and request deduplication only for exactly identical ordered root populations
within one projection. Every period still clips timestamps, pools fallback rates,
evaluates completeness and calculates matched facts independently. No persistent
cache, cross-slice invalidation or reduced publication frequency was introduced.

Sharing diagnostic: **120 mixed-input five-period parity cases** and six fixed
large-history all-period signatures match the saved pre-sharing fun implementation.
30-day cold projection fell **24.19→18.11s**, CPU **49.58→43.77s**; 7-day warm
projection **3.86→2.77s**, CPU **6.28→5.31s**. Workload overlap limits causal claims.
`scratch:/sharing-diagnostic.jsonl` retains the bounded driver/results.

Final historical-builder/formula benchmark: **18 selected-period parity comparisons
passed**, 12/2,700 roots × 20 requests, three scopes, cold/warm/1% changed. Both
builders use fresh services/256-root slices; hydrations remain **2,700/0/27**, with
11 cold slices. First numeric results: **1.10–1.44s vs 31.70–32.64s**. Large-history
seconds below are baseline/current, not ceilings:

| Scope | Cold wall | Cold CPU | Warm wall | Changed wall |
| --- | ---: | ---: | ---: | ---: |
| 7 days | 32.27/39.89 | 30.41/38.94 | 4.83/4.27 | 4.67/4.44 |
| 30 days | 31.70/35.85 | 30.80/35.28 | 5.56/4.61 | 5.60/5.06 |
| All | 32.64/36.08 | 31.28/35.14 | 6.02/4.15 | 6.45/4.60 |

`scratch:/ai-stats-benchmark-delivery.jsonl`. Historical builder/formulas use current
shared dependencies, not a complete old runtime. Baseline partly overlapped other
checks; exact causal percentages and real-source comparative overhead are unproved.

**Current Decision Delegate performance exception:** after the directed repair and
parity proof, the foreground Delegate accepted criterion 6's measured residual cold
completion CPU increase (**28%/14.6%/12.3%**) for earlier numeric publication, unchanged
scanning and improved warm/changed measurements. This is not a blanket nonregression
PASS or guaranteed ceiling. No extra scanning, warm regression, stall, retention/
period leakage, other-report or future-change waiver; Full/validator/CI remain required.

### Historical findings and scoped decisions

FR000619's earlier 2,787-root observation recovered measured time but intentionally
left 4–5 unavailable and 3–5 partial cards; FR000633 supersedes that accepted policy.
Its native compaction finding remains valid: explicit completed-part `time.end` can
recover canonical timing; creation time/status/summary alone cannot prove an end.
Canonical compaction normalization is not changed here.

Earlier FR000614/FR000615/FR000617 lifecycle and FR000619 performance/documentation
exceptions grant no present waiver.

**Current Decision Delegate documentation-method exception:** the legacy knowledge
helper rejected the requested read with `KNOWLEDGE_LIMIT` before writes because
existing leaves exceeded 12KiB. The foreground read-only Delegate authorized direct
patching for this FR only: consolidate this leaf to <=12,288 UTF-8 bytes, surgically
update the AI Stats section/table in `architecture/modules/reports.md`, and change
only its CODE_MAP row/scoped provenance. Preserve unrelated provenance; no helper
changes, raised limits, whole-module audit, diagram rewrite or helper PASS. No
product/test waiver was granted by that documentation decision; the separate cold
performance decision above is narrowly scoped. The FR separately owns user docs.

## Next investigations

Physical-device rendering, screen-reader speech, non-Chromium paint and aggregate
job memory remain unproved. Integrated browser was disconnected; no integrated PASS.
These are evidence limits, not new task gates.

## Rejected hypotheses

- A CSS-hidden badge or replacing nulls with ten indiscriminate zeros is not the
  requested repair: Stats must actually use available time/cost and compute ratios.
- Complete scan coverage is not a prerequisite for entertaining numeric results;
  conversely early rows are not proof of complete scanning. Benchmarks/probes must
  wait on explicit scope readiness when measuring completed acquisition.
- The retained-card browser test must keep its accepted result during a real warm
  refresh, not delete that result before expecting it to remain visible.
- The Token Mix browser fixture omitted `source.observed_at_ms`; the production
  retention guard correctly withheld it. Supply the canonical observation in that
  fixture, rather than weakening Token Mix admission to accommodate invalid data.
- Importing today's formulas into the historical builder makes parity vacuous.
  The fixed-history comparator loads both historical builder and historical analysis,
  with current shared dependencies, not a whole historical runtime.
- Canonical missing ends remain unknown. Stats-only guessed intervals cannot be
  promoted into billing/history proof, invented dates, records or source mutations.
