# Web AI Stats: resumable coverage and historical re-entry

Source baseline: d381d399f401c24302fa559eb62ec68e33aba4e7
Checked scope: FR000614 implementation delta, with FR000615 lifetime override below; not a whole-module audit
Last checked: 2026-11-06
Status: implementation verified; scoped coverage/performance/documentation exceptions

## Contracts and causal findings

Owners: `reports/ai_stats.py` acquisition, `ai_stats_evidence.py` compact facts/bounds,
`web/stats_jobs.py` logical identity/priority/liveness, `jobs.py` finite process/IPC.
FR000609 loader, FR000612 metric reasons, ten cards/matched fact, calendar/DST and
independent 15/5-minute AI Stats/Token Mix freshness/re-entry remain canonical.

The original 120-second error proves a finite job deadline, not the owner's exact
slow source operation. Current source metadata has no authoritative event-time
exclusion capability. An inactive root with old metadata can contain recent requests;
an unknown old execution end may overlap newer windows. `test_ai_stats_resume.py`
pins that counterexample against the complete canonical calculation. Metadata is
priority only; every unknown root remains potentially relevant to every period.

**Decision Delegate coverage exception:** requirements 5/6 and acceptance 2's
unconditional earlier independent completion are conditional on validated evidence.
Cold/invalidated archives may require complete verification before even Today/7 days
is coherent. This is not unconditional acceptance-2 PASS, metadata exclusion or
permission for labels-only switching. Stable known ends can prove broader-only work;
active, running, pending, incomplete or unknown-ended roots cannot be excluded.

AI Stats alone can exceed 120 logical seconds: each child keeps that watchdog,
256 missing roots, 64-root batches, maximum-four V2 reads. Each slice verifies fresh
membership/revisions; volatile facts refresh before publication. Fixed source/
pricing/algorithm-keyed per-root checkpoints contain no prompts/session text.
Resource/stall/storage errors terminate honestly. FR000615 supersedes the earlier
15-second interest expiry and user-facing cancellation: one host-owned logical job
retains at most five validated requested scopes. Explicit selection prioritizes the
next missing slice, then earlier goals resume without another user action or polling
interest. Checkpoints, finite child watchdogs, internal cancellation/shutdown and
other deadlines/queue/result/parent-loss/read-only bounds remain. Current lifetime
verification and limits: [shared report loading](report-loading.md).

## Reproducible verification

```text
py -3 development/tools/run_tests.py --suite full
py -3 development/tools/validate_package.py --working-tree
node development/tests/integration/probe_ai_stats.cjs <browser-executable> <output-json>
py -3 development/tests/integration/benchmark_ai_stats.py --baseline d381d399f401c24302fa559eb62ec68e33aba4e7 --sliced
py -3 development/tests/integration/probe_ai_stats.py --cold-and-warm
```

Local Full: **154 files, zero failures, 102.0s; 1,812 passed, one platform skip**
(`zsh/PTY unavailable`, native macOS CI owns execution). Fifteen resume cases cover
coverage/priority, cache/revision/active changes, storage/resources, reuse and stalls.
Virtual **200 seconds/five children** avoids real idle; actual spawned coverage
2/4/6/8/9 ends without a child. Browser Attempt crosses virtual600 seconds while
normal120 expiry and existing runtime/Watch/Models/Comparisons boundaries remain.

Final hidden Edge: **14 checks/9 layouts, 80 enlarged-text layouts, 1,350 color samples,
16 canonical state/unit cases, no runtime errors**; shipped authenticated HTTP/assets/
CSP, disposable profiles, no desktop effects. Production two-tab/process case:
**7 days coherent at4/24 roots**, wide incomplete; returning30 uses **12 finite
children/exactly24 hydrations**, no active child. Ready rows need no extra worker;
direct tests pin missing-root repricing priority. Other UI cases use immediate jobs.

Failed fixture hypotheses: Node→Python→console spawning stalled an unrelated Normal
child, leaving Stats queued, not failing acquisition. The existing verified
`pythonw.exe` child pattern fixed this; Stats-only rejects unrelated requests.
Another assertion wrongly demanded an extra 7-day child despite an already coherent
row. It now checks logical ownership; focus/coverage/exact hydration checks remain.

Physical devices, real screen-reader speech and non-Chromium paint remain unverified;
AX names/keyboard/touch/help and computed contrast/layout are checked. No paid
inference, source writes, shared OpenCode stop, ZIP, tag or packaged Release.

Evidence: `scratch:/fr614-full-final.json`, `scratch:/ai-stats-browser-final.json`.
Final validator: **11 passes, zero failures, six existing advisory warnings**
(Web guide, README, context, report service, Watch coordinator, version history).
No cap, structure baseline or permanent gate was raised.

## Performance: measured work, not a universal speedup

Fixed Python 3.14/Windows synthetic history: 12 and **2,700 roots × 20 = 54,000 requests**;
7 days/30 days/All time; cold/warm/1% changed, separate disposable caches. Baseline is
read by exact `git show`, never checkout/reset. Selected canonical period hashes
compare all metric/reason/matched fields. The old 7-day UI acquired 30 days, so that
actual historical path is the comparator. Direct-builder measurements exclude
process/IPC; `--sliced` uses fresh services/production scan/256-root settings but
still excludes OS process startup/IPC. Actual spawned evidence is separate.

Paired direct-builder run before the final lazy-read repair (seconds):

| Scope | Cold baseline/current | Warm baseline/current | 1% changed baseline/current |
| --- | ---: | ---: | ---: |
| 7 days | 45.274 / 9.529 | 4.009 / 3.285 | 4.279 / 3.766 |
| 30 days | 52.257 / 10.023 | 4.092 / 4.397 | 4.174 / 4.578 |
| All time | 51.626 / 10.649 | 4.979 / 5.627 | 5.437 / 5.051 |

All 18 selected-period comparisons passed. Cold hydrates 2,700 roots, warm zero,
changed exactly 27. Small cold improves .212–.226s to .044–.048s; warm .0136–.0168s
versus .0119–.0184s, changed .0405–.043s versus .0216–.027s. Removing duplicate
full-analysis persistence and bulk-writing compact facts explains eliminated work;
approximately fivefold **direct cold-builder** improvement is not an end-to-end claim.
An earlier prototype projected all five rows on every selection and materially hurt
warm 7/30-day work; computing only ready selected/contained periods removed that waste.

Bounded warm diagnostic, including production settings, found 87 read connections
(43 stable, 43 transient, one proofs), 5,400 JSON loads. Connection entry cost only
86–95ms; transient/proofs roughly 90ms. Final verification was about 6ms, not an
explanation for the entire residual slowdown. Canonical projection and decoding
dominate; allocation/GC time can shift between JSON/decoding stages. The small repair
reads transient facts only after stable misses and proofs only for still-missing
roots: warm **43 connections, 2,700 JSON loads, zero transient/proof reads**, unchanged
64-root raw-payload bounds, zero hydration/repricing. No global pool or archive-wide
raw-payload retention was introduced.

Diagnostic warm30/all production4.207/5.401→4.403/5.406s, direct4.531/5.280→
**4.717/5.777s**, instrumented4.951/5.338→5.009/5.511s. Some overlapped a browser
fixture: removed reads, **not latency improvement or precise percentages**.

**Decision Delegate performance exception:** after investigation, accept residual
large-history warm 30-day/All-time and changed-30-day slowdown under requirements
10–11, rather than disproportionate cache redesign. This superseded its initial
"investigate, not waived yet" decision. Nonregression is not PASS; the exception
does not cover correctness, unrelated responsiveness, materially worse new evidence
or removing freshness/resource protection. The cold/work reduction and resumability
justify this scoped trade-off. No universal warm improvement is claimed.

Direct evidence: `scratch:/benchmark-ai-stats-verified.jsonl`;
diagnostics: `scratch:/profile-stats-warm-before.jsonl`, `scratch:/profile-stats-warm-after.jsonl`.

### Final production-settings matrix and real source

Final fresh-service sliced matrix (same fixed source, seconds baseline/current):

| Scope | Cold | Warm | 1% changed |
| --- | ---: | ---: | ---: |
| 7 days | 51.308 / 26.636 | 4.471 / 4.453 | 4.454 / 4.400 |
| 30 days | 50.980 / 27.023 | 5.010 / 5.560 | 5.277 / 5.528 |
| All time | 55.031 / 28.297 | 5.865 / 6.433 | 6.711 / 6.052 |

All 18 parity checks passed. Cold: 11 slices, exactly 2,700 hydrations/54,000 requests;
warm zero, changed 27 hydrations in one slice. Small cold .201–.203s/.055–.060s,
warm .015–.018s/.014–.020s, changed .035–.040s/.025–.037s. Cold sliced work is
about 1.9× faster, not the direct-builder 5× claim. Repeated bounded restoration
costs 13–14s; 22 catalog calls/59,400 revision checks versus baseline 1/8,100.
Warm 30/all remains slower under the scoped exception, not nonregression PASS.
Evidence: `scratch:/benchmark-ai-stats-sliced-final.jsonl`.

Final isolated-cache read-only V2 probe: cold30 **94.936s/12 children**, warm30
**5.233s**, All extension **6.861s**, warmAll **6.200s**, no terminal errors.
Cold totals: 2,815 hydrations/58,486 analyzed requests (includes volatile refresh,
not unique records), 75 catalog fetches/3,750 pages, 49.547s child CPU; worker87.790s,
queue7.132s, serialization10.902ms/2,532,595 bytes across slices, not one result.
Maximum own-child working set321,089,536 bytes, not aggregate logical-job memory.
Nested stage totals seconds: catalog24.396, snapshots51.715, restore9.780,
analysis1.991, evidence4.101, writes1.213, verification4.704, projection2.884;
not additive. Warm30/All hydrate19/20 volatile roots. Completed acquisition retains
partial/unavailable reasons: running-executions, unknown-duration, unpriced-requests.
Historical d381 real cold91.474s/2,726 roots and warm30/All3.601/4.309s are nonpaired
mutable-source observations, not a frozen speed comparison or incident diagnosis.
**Current Decision Delegate final-readback acceptance:** these final synthetic/live
costs fit the existing scoped performance exception; proceed without more redesign.
Nonregression/end-to-end speedup remain unproved; no correctness/freshness waiver.
Evidence: `scratch:/ai-stats-live-final.jsonl`.

## Documentation decision and retained historical lessons

The knowledge helper failed before writes with **KNOWLEDGE_LIMIT**: current module
documents exceed 12 KiB. A new **Decision Delegate** exception for FR000614 permits
contextual AI Stats patches only to reports/web modules, the CODE_MAP owner/test row,
and this consolidated leaf **≤12,288 UTF-8 bytes**. Legacy ancestors exceed eight
routes and use a backticked AI Stats route; CODE_MAP is outside helper grammar.
No inherited FR000612 exception, unrelated consolidation/cap change or helper PASS.
Module overages and routing debt remain; checked claims are scoped to this delta.

Historical observations are context, not renewed acceptance or inherited exceptions:

- FR000599: 16-root prototype exceeded 120s from repeated catalog brackets; 64-root
  V2 cold **84.692s**, 2,698 roots/54,056 requests, 44 catalog calls/2,156 pages,
  42.297s child CPU. Immediate UI jobs did not prove spawning; combined Models/help
  fixtures had gaps. Current Stats process proof is independent.
- FR000611: a 15px inner region clipped 20px text despite outer fit. Content-sized
  tracks fixed it. Cold timed out120.029s; its CSS-only exception does not carry forward.
- FR000612: selected nested label contrast1.0 became minimum5.81 via inherited/atomic
  colors. Returned evidence, not spinners/zero, owns metric states. Unknown old timing
  affected recent windows without identifying an exact native record.
- HTTP/navigation/timers never prove freshness. One-hour withholding is re-entry,
  not active-page blanking. Deleted history/the exact incident remain unavailable.
