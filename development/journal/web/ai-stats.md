# Web AI Stats and historical re-entry

Source revision: 558eabfd31c727b1df6ef599d33b71de15956348
Checked revision: 558eabfd31c727b1df6ef599d33b71de15956348
Last checked: 2026-11-06
Status: current

## Summary

FR000611 observes the base above plus its delivery diff. The shared Overview/Fun
Facts detail track is content-sized, with wrapping and equal sibling heights within
each responsive grid row. Keyed card/link identity, metrics and acquisition are unchanged.
AI Stats replaces the hourly-cost page, not canonical rate APIs or CLI/detail
semantics. Ten baseline cards consume Python-prepared metrics and deterministic
original traits. Five periods share source coverage; month/all extend lazily.
`analysis/ai_stats.py` owns clipped time unions, event-time cost, local calendar/DST,
root averages/concurrency and stable records. `reports/ai_stats.py` owns compact
revision-/pricing-keyed evidence, with no prompt text or durable history authority.
`assets/cached-reports.js` shares only AI Stats/Token Mix's 15/5-minute cadence and
last-success re-entry bands. Over-hour entry withholds normal metrics; already-active
views keep accepted nodes through ordinary refresh, failure and navigation races.

## Evidence

### FR000611: clipping remediation and current verification

Reproduce with an explicit installed Chrome/Edge executable and absolute JSON output:

```text
node development/tests/integration/probe_ai_stats.cjs <browser-executable> <output-json>
```

Hidden Chromium used a disposable profile, shipped authenticated HTTP/CSP/assets
and canonical synthetic reports. Integrated browsing returned `browser.disconnected`;
no visible desktop, personal profile or shared OS input was used. Pre-fix CSS
reproduced a **22.5px detail track minus 7.5px margins = 15px element**, versus
**23.25px line-height / 20px text ranges**. Both session links and Busiest Day date
exceeded their hidden clipping rectangle despite fitting outer cards.

Final browser: **PASS, 10 checks, 9 normal layouts and 80 text layouts**. The focused
`development/tests/integration/probe_ai_stats_layout.cjs` companion checks actual
text ranges, clipping ancestors, separate rows, within-row equal heights and page
overflow. Classic/Web light/dark at 360/1366/1920px; 100/125/150/200% root text sizing;
Arial/Georgia; Credits/USD; short/long/unbroken session names, month/day date text,
large values, N/A, empty details, partial/unknown status and long traits; all five
periods and both optional matched-card labels are covered. Actual Tab focus, visible
unclipped outline, retained focused link during update, pointer hit/hover/click and
Enter preserve the canonical destination. Existing AX, safe literal hostile titles,
touch/help, retained cards and refresh-lifecycle checks still run. This is synthetic
rendered UI, not real-source browser painting or physical-device/speech/other-engine proof.

Local Full: **153 files, zero failures, 105.5s**. Working-tree validator: **11 passes,
zero failures, six existing advisory warnings** in the categories recorded below.
No caps or structure baselines changed. Evidence: `scratch:/ai-stats-before.json`,
`scratch:/ai-stats-final.json`, `scratch:/full-tests.json`.

The real read-only V2 probe shown below used production ReportJobs and an isolated
disposable cache, with no inference, account refresh or shared-service stop:

| Attempt | Result | Seconds | Coverage |
| --- | --- | ---: | --- |
| Cold 30 days | **FAILED: report_timeout** | 120.029 | zero periods; progress 2688/2725 roots |
| Warm 30 days | complete | 9.003 | four periods |
| All-time extension | complete | 10.212 | five periods |
| Warm All time | complete | 5.165 | five periods |

**Decision Delegate approved an FR000611-only exception to successful cold live
acquisition:** this probe does not exercise the changed CSS; direct rendered evidence
establishes the clipping fix. No further cold retry, backend repair or deadline
increase was required. Full tests, validation and protected Git delivery were not
waived. Cold-acquisition reliability and timing variance remain unresolved; concurrent
Full testing is a possible influence, not an established cause. Exit zero and warm
success do not turn the cold failure into PASS. No On Hold or owner decision was needed.

**Documentation exception, Decision Delegate, FR000611 only:** the knowledge helper
read this leaf, but apply failed before writes with `INDEX_LIMIT` because existing
ancestor indexes exceed eight routes; the Web index also uses a backticked route to
this leaf rather than a helper-recognized link. The delegate authorized a targeted
ordinary patch, not index restructuring, new routes, size-limit changes or a helper
PASS/full ancestor validation claim. Architecture needs no update for this CSS-only
change. This leaf remains within 12 KiB.

### Historical FR000599 evidence and exceptions only

The following observations use `42cc45f624d7b9cda560e365e53a93cec36ff7bc` plus
FR000599's delivery diff, not current FR000611 performance or inherited exceptions.

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

`test_ai_stats.py` covers canonical accounting, DST/period edges, uncertainty,
revision-aware reuse and actual spawned finite-process output. Host and Node
tests independently cover scope coalescing, observation clocks and re-entry bands.
Historical Full corrected two stale route/script fixture assumptions rather than
waiving them. Validator advisory categories were Web guide, README, context,
report service, Watch coordinator and version history; no caps/baselines changed.

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

Cold acquisition still can time out on this installation. Investigate its unchanged
catalog/hydration costs when performance is in scope; timing variance is not yet
attributed to concurrent testing or another proven cause.

Investigate the combined Node-launched production-process fixture if it becomes
necessary for another task; preserve independent real-process proof meanwhile.
The whole-app help audit needs a modern synthetic Sessions runtime before it can
truthfully audit its later routes; its current failed run is not product failure.
Cold source discovery/catalog brackets remain measurable dominant costs. Physical
assistive-tech/device/engine behavior remains unverified, not a hidden PASS.
Oversized legacy architecture docs need separately scoped consolidation, not budget
inflation during a feature's ownership update.

## Rejected hypotheses

- A card's `scrollHeight <= clientHeight` proves its text is readable: false; the
  inner detail can clip glyph height. Content-sized rows and wrapping fix the cause
  without JS-measured heights, negative margins or stacking hacks.
- More polling or extending the finite deadline: does not fix repeated catalog I/O;
  the existing 64-root batching bound was sufficient on the observed installation.
- Fresh HTTP/timer/page visit means fresh history: false; acquisition clocks drive
  re-entry, and failures/cancellation never advance the last-success timestamp.
- Immediate browser fixture success proves process/coalescing: false; the production
  process and mutable real installation have separate evidence above.
- Every over-hour view should blank: false; withholding is entry/inactive-scope-only,
  not a disruptive active-page timer.
