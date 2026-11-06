# Web AI Stats and historical re-entry

Source revision: 42cc45f624d7b9cda560e365e53a93cec36ff7bc
Checked revision: 42cc45f624d7b9cda560e365e53a93cec36ff7bc
Last checked: 2026-11-06
Status: current

## Summary

FR 000599's source/evidence is the revision above plus this delivery's diff.
AI Stats replaces the hourly-cost page, not canonical rate APIs or CLI/detail
semantics. Ten equal cards consume Python-prepared metrics and deterministic
original traits. Five periods share source coverage; month/all extend lazily.
`analysis/ai_stats.py` owns clipped time unions, event-time cost, local calendar/DST,
root averages/concurrency and stable records. `reports/ai_stats.py` owns compact
revision-/pricing-keyed evidence, with no prompt text or durable history authority.
`assets/cached-reports.js` shares only AI Stats/Token Mix's 15/5-minute cadence and
last-success re-entry bands. Over-hour entry withholds normal metrics; already-active
views keep accepted nodes through ordinary refresh, failure and navigation races.

## Evidence

Windows workstation, Python 3.14, real read-only V2 source; no inference, account
refresh or shared-service stop. Reproduce finite cold/warm acquisition with:

```text
py -3 development/tests/integration/probe_ai_stats.py --cold-and-warm
```

This uses an isolated disposable cache beneath session scratch and normal ReportJobs
limits. An initial 16-root prototype timed out at **120.026s**, returning no result;
repeated catalog brackets were the causal cost. Reusing the existing **64-root**
historical bound (source at most four concurrent reads) produced:

| Acquisition | Seconds | Actual work |
| --- | ---: | --- |
| Cold 30 days | 84.692 | 2698 roots, 54056 analyzed requests, 43 prepare batches, 44 catalog fetches/2156 pages, 42.297s child CPU; four covered periods |
| Warm 30 days | 3.452 | 2680 evidence hits, 18 active misses/hydrated roots, 283 analyzed requests |
| Lazy All time extension | 6.274 | 2741 roots, 2680 hits/61 misses, 62 hydrated including a concurrent correction, 2317 requests; five periods |
| Subsequent All time | 4.053 | 2722 hits/19 active misses, 731 analyzed requests |

The real installation changed during measurement; these are not immutable whole-
installation transactions, universal performance guarantees or hourly scan timings.
All final finite acquisitions completed inside the unchanged 120-second deadline.

Deterministic `test_ai_stats.py` covers independent metrics, event clipping, child vs
root concurrency, stable ties/clone dedup, zero/unknown/partial/provisional evidence,
Stockholm 7/9-hour DST nights, rolling/calendar edges, lazy 31-day month coverage,
archived/deleted roots, warm no-hydration/no-repricing reuse, pricing invalidation,
active evidence, optional-cache failure, display/scope allowlisting and actual
spawned finite-process output. Host tests prove concurrent/recent same-scope
coalescing, distinct scopes and unchanged observation clocks. The Node policy
matrix pins TTL, TTL+1, exactly one hour and one hour+1 millisecond.

Final Full: **151 files, zero failures, 97.5s**. The earlier full run failed two old
UI harness assumptions; their route/script fixtures were corrected, not waived.
Raw reports: `scratch:/full-tests.json` (old failure),
`scratch:/full-tests-final.json` (final pass).
Working-tree product validator: **11 passes, zero failures, six advisory warnings**
(existing Web guide/README/context/report-service/Watch/version-history categories).
No file caps or structure baselines changed.

Hidden Chromium with disposable profile, shipped HTTP/CSP/assets and canonical
synthetic datasets: `probe_ai_stats.cjs` **PASS, 8 checks / 9 layouts**. Covers
automatic/alias navigation, exact periods/ten cards, literal hostile record titles,
Classic/Web light/dark at 360/1366/1920px, equal geometry/no overflow, coverage/unit
reuse, lazy All time, all ten AX names, actual CDP Tab/Shift-Tab and Enter/Space,
touch activation, help/Escape, in-flight navigation/cancel/retry, both routes'
quiet/over-hour entry/failure/provenance and independent browser documents.
`probe_token_mix.cjs` also passed its four checks/nine layouts: exact two 13-column
tables, all 26 sorts, explicit first load, retained quiet update/focus/panning.
Logical evidence: `scratch:/ai-stats-browser.json`,
`scratch:/token-mix-browser-final.json`. First CDP Enter attempt omitted native key
codes/text; adding the same event fields as established probes fixed activation.
The updated Sessions browser probe also passed nine checks, preserving retired
Reports navigation, catalog/detail, local-time/DST and neighboring table behavior
(`scratch:/web-sessions-final.json`).

An extra full `probe_web_help.cjs` attempt **failed** before AI Stats: at `#/sessions`
it expected `#result th:first-child .help-label`, but the actual page said
`Live session source unavailable.` The `serve_mini_watch.py --help-audit` fixture
has immediate jobs/manual Watch publications but no `host.live` catalog/detail
runtime. HTTP correctly reports that missing capability. Later routes were not
audited in that run. Decision Delegate authorized leaving this optional whole-app
fixture gap unresolved for FR000599 only, relying on the focused passing help/AX,
shared deterministic help and separate modern Sessions checks. Assertions remain;
neither all ten tooltip interactions nor full-audit success is claimed by AX names.

**Proof split and Decision Delegate-authorized exception:** the integrated browser
was disconnected. Hidden UI uses immediate canonical `AIStatsJobs`, not production
spawning/coalescing. A Node→Python→ReportJobs fixture's initial Models child stayed
running; the combined harness remains unresolved. Separate actual spawned-process
tests and real-source probes establish those boundaries instead. Decision Delegate
approved this split and waived actual screen-reader speech testing for this FR;
native physical device/font and non-Chromium runs are not additional merge gates.
Required hidden touch, Tab/activation, all-ten AX and navigation/cancel checks did
run and pass. None of this claims physical/speech/non-Chromium acceptance.

**Documentation exception, Decision Delegate:** existing OVERVIEW/web/reports/code-map
files were already 15948/55260/17663/34456 bytes. `repository_knowledge.py read`
returned `KNOWLEDGE_LIMIT` before any write (existing-file 12 KiB bound). Targeted
ordinary patches replace affected ownership/navigation/freshness facts; unrelated
architecture restructuring and changing helper limits were not justified. Delegate
authorized this narrow size/helper exception. Existing oversized documents remain
outside full helper validation; no helper PASS or whole-document revalidation is
claimed. This bounded leaf retains actual base-plus-diff provenance. Product Full,
validator, acceptance/security and protected Git delivery are not waived.

## Next investigations

Investigate the combined Node-launched production-process fixture if it becomes
necessary for another task; preserve independent real-process proof meanwhile.
The whole-app help audit needs a modern synthetic Sessions runtime before it can
truthfully audit its later routes; its current failed run is not product failure.
Cold source discovery/catalog brackets remain measurable dominant costs. Physical
assistive-tech/device/engine behavior remains unverified, not a hidden PASS.
Oversized legacy architecture docs need separately scoped consolidation, not budget
inflation during a feature's ownership update.

## Rejected hypotheses

- More polling or extending the finite deadline: does not fix repeated catalog I/O;
  the existing 64-root batching bound was sufficient on the observed installation.
- Fresh HTTP/timer/page visit means fresh history: false; acquisition clocks drive
  re-entry, and failures/cancellation never advance the last-success timestamp.
- Immediate browser fixture success proves process/coalescing: false; the production
  process and mutable real installation have separate evidence above.
- Every over-hour view should blank: false; withholding is entry/inactive-scope-only,
  not a disruptive active-page timer.
