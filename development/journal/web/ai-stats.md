# AI Stats: loading, sampled responses and resumable history

Source revision: a6d4c606fc0ac4f8c62dceeb03844b6a46671b55
Checked revision: a6d4c606fc0ac4f8c62dceeb03844b6a46671b55
Last checked: 2026-11-12
Status: current

## Summary

FR000689 scoped delta; historical measurements retain their scope, not a fresh audit.
Current [reports contract](../../architecture/modules/reports.md#web-ai-stats-acquisition-and-accounting).

**Pending means exactly one `Loading…` text node in each of twelve stable cards,
including queued, deferred, failed and interrupted attempts. A real blocker is
page-level, never a card label. Ready values appear atomically; matching ready
same-source/same-period values survive refresh.** Never invent failed-acquisition
zeros or relax schema/source checks. All ready cards remain playful best effort,
not accounting evidence or a scientific benchmark. No Pause/Retry/Refresh action.

Owners/tests: [CODE_MAP](../../architecture/modules/CODE_MAP.md). Boundaries retained;
no extra scan, inference or source write.

## Loading-only and supervised recovery — FR000689

### Confirmed defects and repair

- `View.update` produced `Counting paused.` on cold failures/interruption; all pending
  interiors, including accessibility, now follow the invariant above.
- `app.js::show` hid cold errors (`state.result == null`); cold/background errors now
  reach the separate existing actionable `role=status` notice.
- `stats_jobs.accept` called exhausted/nonbusy-checkpoint **unready** work complete;
  dispatcher accepted row presence and assigned 900s cadence despite browser rejection.
  Now typed retryable checkpoint/no-progress failure, scoped-ready publications only;
  persistent blockers have page-level feedback while demand stays pending.
- BUSY/LOCKED beyond six nonadvancing slices keeps the same job/scan/observation and
  bounded backoff, so unlocking can resume its checkpoints. Nonbusy write failure
  and no-progress use host-supervised bounded retry, never false readiness.
- Prior Stats policies regenerate using the shared policy and existing compact
  invalidation; unrelated reports/native history are not deleted/reset.
- Incomplete finished publications wait5s before rediscovery, not fake success/hot-loop.
  Admission/result/catch/finally are attempt-qualified; retired failures cannot mutate
  replacements. Healthy admission clears waiting feedback; leases promote demand.

### Historical incident attribution

**Owner's exact earlier failed attempt: NOT VERIFIED.** The ordinary checkout's exact
derived product directory had no `instance.json`, `diagnostics.json` or `lifecycle.log`;
its logs inventory held only recovery artifacts. Delegate directed the latter two
checks: missing instance metadata alone was insufficient. No unrelated private search.

Initial baseline invalid: this worker edited runtime; SourceGuard stopped the host
(cancelled jobs/no fault), not incident/outage evidence. Later replays froze runtime.

### Verification status

- Full: all 185 groups ran, 184 passed; foundation's version oracle raced a version
  edit. Its rerun passed that assertion; a validator subprocess timed out under load,
  then passed isolated (5.650s). All tests passed across runs, not one green Full.
  Focused resume/dispatch 74 tests and lifetime VM pass; validator 11 pass/7 advisories.
- Headless Edge matrix passed 19 checks/160 pending combinations. Enhanced matrix
  covered six operational codes but hit its parent deadline during final slices;
  separate production-slice rerun passed: narrow at 2/24 roots, 12 children, exactly
  24 hydrations, broad goal completed, no active child/host fault/HTTP threads.
- Frozen fixed-live failed its 540s readiness condition: connected healthy host,
  unchanged source guard, Stats still running after ten slices. Cause unproved.
  Warmed traced replay passed Stats/Token Mix in 48.045/16.152s (partial source).
  Tightened replay passed in 47.759/20.791s: actual visible interest/90s lease → queued
  admission → running → complete, 3164/3164 roots, `fun-3-responses`, strict valid,
  default30 ready/12 cards; five scopes ready. Stats acquired; Mix partial.
  Simulated browser faults automatically recovered over real results, retaining
  last-good DOM; cold faults had Loading/page notice. Clean owned exits/no errors.
  Evidence: `scratch:/fixed-live.json`,
  `scratch:/traced-live.json`, `scratch:/verified-live.json`, `scratch:/final-slices.json`.
- **Decision Delegate** authorized the minor historical-attribution exception to
  acceptance7: original failure/cache state, cold-upgrade timing and causal replay
  NOT VERIFIED; failed540s unresolved. Frozen warm successes prove current recovery,
  not historical cause; new-state instrumentation cannot restore absent records.
  No Suggestion/hold; no cold/schema/security waiver.

## Evidence

Reproduce on a local workstation, with owned disposable browser profiles/caches:

```text
py -3 development/tools/run_tests.py --suite full
py -3 development/tools/validate_package.py --working-tree
node development/tests/integration/probe_ai_stats.cjs <headless-browser> <output-json>
node development/tests/integration/probe_ai_stats.cjs <headless-browser> <output-json> --live-history
py -3 development/tests/integration/probe_ai_stats.py --cold-and-warm --budget-seconds 600
py -3 development/tests/integration/benchmark_ai_stats.py --baseline <historical-revision> --sliced
```

Probes own host/children; no OpenCode stop/write. Export aggregates/codes/provenance;
managed chain, standalone timing and synthetic faults differ. Warm is not cold;
freeze runtime/version.

### Documentation method

After pre-write `KNOWLEDGE_LIMIT`, foreground **Decision Delegate** authorized direct
consolidation ≤12,288 bytes and surgical reports/CODE_MAP edits, preserving provenance.
No helper/limit/diagram change, helper PASS or test waiver. Old exceptions stay scoped.

## Sampled response podium — FR000685

Historical delta against `f9ee34f59c1106df88dd01c7907344a7bccc373d`, 2026-11-12.
Policy `fun-3-responses`: Top 3 weighted model/effort response-output tok/s replaces
only Token Consumption Rate. Other metrics/matched facts retain owners; sparse,
partial or estimated ready observations never become N/A.

V2 2.2.7 OpenAPI and released tag
[`fedc6f208aa2bd54c1019227214568083f6380ad`](https://github.com/anomalyco/opencode/tree/fedc6f208aa2bd54c1019227214568083f6380ad)
were traced through runner/step, publish-llm-event and message-updater: stream drains
before awaiting tools, which can overlap it. Released linkage, not a binary audit.

Prefer independent step pairs, then assistant created→valid same-response streamed;
otherwise completion clipped at native tool start. Multiple steps need independent
pairs, not multiplied message intervals. Completion membership, canonical clone dedup
and reasoning-once output remain. Queue/TTFT/network/setup and fallback clipping bias
this round-trip proxy, never pure decoding speed. V1 can use the broader fallback.

Per-root/model and final period/model samples each retain ≤32: newest eight, then
lowest call-identity-hash 24. Final period filters precede selection; future/as-of
bounds reject stale reuse. Identity is source/session/message/step/parent/order, not
array index or root container. Algorithm `ai-stats-evidence-6-response-stream` affects
Stats only; shared compact usage and coverage v3 remain independently reusable.
The foreground Delegate approved these hierarchical caps and historical-window bias
as design interpretation, not a quality/test waiver. One sensible timed call can race.

Historical owned-cache cold30 **145.768s/13 slices**, warm30/All **8.539/9.048s**,
payload **432,456–432,476 bytes** versus pre-change **136.074/7.527/6.875s** and
**428,527–428,561 bytes**. Mutable-source concurrency prevents paired speed claims.
Live preceded final endpoint preference; focused tests checked it. ≤32/child timing
samples had median stream/tool deltas **1–187ms**, tail **4,287ms**, completion−stream
up to **211,932ms**, with native tool ends on either side.

Fixed 12/512-root ×20-call benchmark, 7/30/all, cold/warm/1%-changed: 18 old-ten-metric
signatures matched, hydration **512/0/5**, slices **2/1/1**. Base/current 512-root cold
**2.35–2.49/2.83–2.96s**, warm **0.61–0.71/1.21–1.24s**, changed
**0.70–0.73/1.04–1.12s**. Current view **26,069 bytes**; old size unmeasured. Profiling
removed repeated hash/sort overhead; initial **310s cold/20–26s warm** was not final.
Delegate accepted residual cost for the new statistic with unchanged hydration/slices
and formulas, bounded sampling and ~4KB payload growth: not zero-cost/future-regression
PASS. Full **185/0 failed/143.5s**, validator **11/0/7**, Edge **19 checks**.
Historical evidence: `scratch:/ai-stats-optimized.jsonl`,
`scratch:/ai-stats-benchmark-optimized.jsonl`, `scratch:/ai-stats-browser-final.json`.

## Observed token traffic and ready card shells — FR000682

Historical delta against `431ef684b3e6c654fefc718d29c4adf00ca310b8`, 2026-11-12:
reasoning-once observed traffic/exact totals, currency-independent help, coverage v3
and source-qualified shells. Unknowns are not cost-derived tokens. FR000689 supersedes
old terminal labels. Generation speed was explicitly omitted for absent token timing;
FR000685 later uses a broader proxy.

Historical Full **185/0 failed/150s**, validator **11/0/7**, Edge **18 checks**.
Fixed hydration **512/0/5**, slices **2/1/1**, view **19,862→26,684 bytes**;
real cold30 **188.200s/13 slices**, warm30/All **8.078/7.928s**. Timings were noisy,
not a speedup claim; no acceptance exception. Full prior measurement table remains
in Git at this note's source revision and `scratch:/ai-stats-benchmark.jsonl`.

## Comparable hourly rates — FR000655

Against `791e0f45e6eeca1a3a184635ffcfdbe5c125ad3c`, 2026-11-09: raw Decimal
calendar/workday/active rates, not rounded shifts/capped Stat.value. Three help formulas:
840 Credits/7 dates/5 workdays/28 active hours = **5/21/30 CCost/h**; 100 Credits/two
overlapping hours = **50/h**, one minute = **6000/h**. DST/zero/units/focus stay covered.
Historical Full **181/0 failed/133.9s**, validator **11/0/7**, Edge **17 checks**;
real cold/warm30/All **135.612/5.054/5.462s** (not paired). No acceptance exception.

## Three perspectives on the first card — FR000644

Historical delta against `a835c7881f368cb82fd1363e856183b1d45f7d45`, 2026-11-09;
shift UI is superseded by FR000655. Local nominal 24/8-hour denominators reuse
`quota_pace.is_workday`/unioned activity; 100 Credits=$1. Rolling/calendar/All/DST
membership stays distinct. Historical Full **179/0 failed**, validator **11/0/7**,
Edge **16 checks**; old shift formulas are not current hourly display.

## Earlier fun-first implementation

FR000633 against `9b9fdf389d93d90a09bfa13e9b075b564d026961` changed bounded
Stats-only heuristics, never canonical accounting/source records. Git retains the
constants/old tables. Cold-failure zeros/unready-success settling are superseded.
Observation-local sharing retains independent period clipping/pooling; 120 mixed
cases, six large signatures and 18 old-builder comparisons matched. Hydration
**2700/0/27**, 11 cold slices. After directed repair Delegate accepted residual cold
CPU **28%/14.6%/12.3%** for early figures, not future/source/retention waivers or
scope-ready paint proof. Full **174/0 failed**, validator **11/0/7**, Edge **16 checks**.

## Next investigations

Historical attribution, physical desktop/touch, screen-reader speech, non-Chromium
and aggregate job memory remain unproved; hidden DOM/AX is not those outcomes.
No inferred authority for model calls/destructive cache or source repair.

## Rejected hypotheses

- A string rename alone fixes liveness, or failed acquisition means empty: false.
- Missing instance metadata proves no historical diagnostics: false; check exact paths.
- Source-edit probe shutdown reproduces the owner's private incident: false.
- Streamed proves pure decoding speed: false; the podium uses a broader proxy.
- Today's formulas in an old comparator prove parity: false; load historical formulas.
- Stats estimates certify canonical missing ends: false; accounting/security stay strict.
