# Exact first-input Web Comparisons

Source revision: 519712251290c878aa829d591617d9f7242154c9
Checked revision: 519712251290c878aa829d591617d9f7242154c9
Last checked: 2026-11-06
Status: current

## Summary

The original implementation evidence below covers base
`fcd2e53ab2eb9dc0b22aa12a6fbdbba1d1ea51d8` plus FR 000606's feature diff.
The presentation follow-up covers the current source revision above plus
FR 000610's display-only diff; it does not revalidate unrelated architecture.
`src/analysis/input_identity.py` fingerprints complete ordered semantic first-input
parts, preserving case/whitespace. Recorded inline attachment bytes can prove
identity; filenames/paths/URLs cannot. Root-only normalized events exclude first
subtasks and synthetic inputs without promoting a later unsupported real input.

`src/reports/matched_runs.py` consumes canonical prompt attribution, unique physical
requests, reference valuation, historical context and execution boundaries. It
does not build a second accounting engine. Failed, aborted, partial/unpriced and
unknown-end rows remain explicit and cannot become unsupported ratio winners.

`src/reports/matched_inputs.py` indexes all recorded roots by revision and semantic
dependencies. Fingerprints and compact run statistics are private disposable
cache data; prompt text, titles and attachment payloads are not persisted by this
index. Existing derived bundles may be reused without creating new raw-prompt
analysis cache entries. Previews are ephemeral and warm checks hydrate at most
ten group representatives plus changed/noncacheable roots. Batches retain at most
128 root snapshots; V2 overlaps at most four source reads and preserves its
authoritative before/after catalog proof. Grouping is indexed, not pairwise.

The application exports an allowlist without fingerprints. Web retains keyed
groups/rows, all repeated runs, shared ContextHelp and prepared Credits/USD tokens.
Five-minute checks run only on the visible active online route, coalescing finite
jobs across tabs. Existing report-process limits remain 120 seconds and 8 MiB;
oversized/unavailable results are not silently truncated into complete evidence.
AI Stats reuses its own period acquisition for an optional eleventh card, never a
separate Comparisons archive scan. Unknown coverage omits the optional fact.

## FR 000610 presentation follow-up

Each group's existing safe ephemeral preview now begins with `Prompt 1:` using
`ReportView.text`, with an honest unavailable fallback. No backend identity,
fingerprint, preview length, privacy, acquisition, accounting or table column
changes were needed. FR 000609 had already added Comparisons' `#notice:empty`
`display:none` rule; this follow-up preserves it rather than duplicating CSS.

Current verification on Windows, 2026-11-06:

- Full suite: **153 test-file executions, zero failures, 103.0 seconds**.
  The focused matching file includes 17 tests, including short/truncated/compacted
  markup/privacy/attachment/unavailable previews and a different-first-input root
  whose later identical prompt must not join the true first-input pair.
- Package validator: **11 passes, zero failures**, six existing advisory/design
  budget warnings. No budgets or baselines changed.
- Extended hidden fresh-profile Chrome probe: **PASS**, 12 Classic/Web light/dark
  layouts at 360/1366/1920px. It checks zero empty-notice height/client rects,
  heading → one labeled preview → unchanged nine-column table, hostile text and
  all placeholders, no page overflow, meaningful notices/status/alerts, no matches,
  partial coverage, retained failure, quiet-refresh DOM/focus, paging and Back.
  Preview/status edge cases are synthetic UI injections; canonical preparation
  and first-input matching are separately covered by Python tests.
- Shared-loader hidden probe: **PASS**, 10 checks and 24 layouts, retaining initial
  observed progress, accessible state, quiet refresh, busy-slot recovery and cancel.
- Read-only real-installation finite scans: cold **83.026s**, warm **5.014s**, both
  completed with full observed coverage: **2,764 roots**, 599 excluded, 293 groups,
  10 displayed groups / 93 separate runs. Warm reused 2,745 compact entries and
  hydrated 28 roots. These are one installation's observations, not latency promises.
  No inference, source writes or shared-service stop occurred.

Evidence: `scratch:/full-tests.txt`, `scratch:/validation.txt`,
`scratch:/comparisons-browser.json`, `scratch:/report-loading/browser.json` and
`scratch:/comparisons-live.txt`. The integrated browser was disconnected. Initial
relative-output hidden-browser launches timed out before any page assertion;
resolving the output/profile path absolutely allowed the Chrome probe to run.
The probe now normalizes that path and includes browser stderr in CDP timeouts.
No test/requirement exceptions were requested. Physical desktop appearance,
screen-reader speech, non-Chromium engines and native macOS were not certified.

## Original implementation evidence

Reproduce deterministic checks with `py -3 development/tools/run_tests.py --suite
full` and `py -3 development/tools/validate_package.py --working-tree`. The focused
`development/tests/test_matched_inputs.py` is registered in both Quick and Full;
it covers exact identities, native V1/V2 normalization parity, causal children,
later-prompt isolation, cache corruption and pricing/algorithm invalidation,
501-run groups, stable paging/recency, status qualifications, AI Stats reuse,
allowlisted DTOs and actual spawned finite-job cancellation/coalescing.

Final Full: **152 test-file executions, zero failures, 93.4 seconds**; the focused
15-test file also passed independently. Validator: **11 passes, zero failures**,
six existing advisory/design-size warnings (Web guide, README, version history,
context, report service and Watch coordinator); no budget was raised. Full evidence:
`scratch:/full-tests-delivery.txt`.

Hidden UI reproduction: `node
development/tests/integration/probe_comparisons.cjs <Edge executable>
<owned JSON output>`. Shipped authenticated HTTP/assets/CSP use canonical synthetic
reports, not real private prompts. The strengthened probe passed nine Classic/Web
light/dark layouts at 360/1366/1920 pixels: ten unframed groups, 30 separate linked
rows, exact headers, safe hostile titles, numeric alignment, horizontal narrow
tables without document overflow, AX column headers, real CDP mouse hover,
Escape, emulated touch, keyboard help, unit changes without acquisition, retained
DOM/focus, Previous/Next, Sessions links/Back, the eleventh AI Stats card and
visible/in-flight/hidden/inactive cadence. No uncaught product errors occurred.
Evidence: `scratch:/browser-comparisons-delivery.json`.

Real-installation reproduction: `py -3
development/tests/integration/probe_comparisons.py`. It uses the configured real V2
source and owned disposable cache, emits numeric metrics only, performs two finite
jobs, then closes its own resources. No model inference, provider paid calls,
source writes or shared-service stop occurred.

- Initial cold observation: 87.682 seconds followed by a source-revision conflict;
  warm result: 5.571 seconds with partial coverage. This was not a cold PASS.
- A subsequent 32-root-batch cold attempt reached the 120-second deadline; its
  recovery pass finished in 30.922 seconds using already written compact entries.
  Catalog-bracket amplification, not analysis CPU, dominated that cold attempt.
- After bounded 128-root batching, cold and warm jobs both returned usable results
  in **79.451 / 4.660 seconds**. They checked **2,757 roots**, excluded 599, found
  293 groups and displayed 10 groups / 87 individual runs. The warm pass reused
  **2,737 compact entries**, with 20 misses and 29 root hydrations, rather than
  rehydrating the archive. Warm source metrics showed four full catalog fetches.
- Both final live results explicitly reported **partial coverage** because the
  active source changed during acquisition. Job completion is not a claim of
  atomic/full-history completeness. Complete no-match behavior is deterministic
  fixture evidence, not a claim about this active real installation.

Live evidence: `scratch:/live-comparisons-batched.txt`. These are observations on
one installation, not guaranteed latency or controlled before/after benchmarks.
The integrated browser was disconnected; hidden fresh-profile Edge was used.
This proves synthetic browser behavior and separately real finite acquisition,
not physical desktop appearance, assistive-technology behavior or macOS native UI.

## Next investigations

Retain truthful partial coverage under active-source churn. A future quiescent
installation measurement could establish complete real-source coverage; the
current evidence must not be relabelled complete. Very large history remains
bounded by the existing finite-job deadline/result budget, not a new unlimited
scan or a permanently running background worker.

## Rejected hypotheses

- Session title, preview text, attachment location and same model/effort are not
  input identities; matching those would create false comparisons.
- More small batches do not necessarily improve responsiveness: with V2 catalog
  bracketing, 32-root batches caused repeated full listings and a cold timeout.
  Increasing only the fixed batch bound preserves revision proof/concurrency.
- A strengthened browser probe initially dereferenced an absent tooltip in its
  own predicate; the null-safe predicate was repaired, not the assertion removed.
- Newly registered cache regressions initially expected per-service counters,
  but fresh services deliberately shared source-owned acquisition metrics. They
  now assert independent per-operation deltas; the cache outputs already matched.
- Equal first input does not prove equal tools/repository/instructions/context,
  answer quality or intrinsic model superiority. No such benchmark is claimed.
