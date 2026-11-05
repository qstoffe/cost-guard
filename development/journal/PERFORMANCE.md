# Performance investigations

Source revision: bf3ae51d45184e8546b4d0d7af3c37d1a59fe11e
Checked revision: bf3ae51d45184e8546b4d0d7af3c37d1a59fe11e
Last checked: 2026-11-05
Status: current

## Summary

**NO_GAIN — current milestone-40 assessment (2026-11-05).** Normal comparison remains bounded by the latest up to 100 eligible prompts; explicit historical Token Mix remains deep. Repeated synthetic measurements establish the current baseline, not a runtime improvement. No shipped source changed. The developer benchmark's obsolete all-running-roots assertion was repaired without relaxing sampled-running cache bypass. This scheduled occurrence follows maintenance-state adoption; it does not reinterpret the older assessment with the same milestone label.

## Evidence

### Current coverage and setup

Whole-repository inventory at the revision above: 831 readable files (281 source/config, 245 tests, 305 documentation), 241 binary/over-1-MiB exclusions, no exact-byte duplicate groups. Areas include 208 `src/` files, 244 `development/tests/` files and 15 `development/tools/` files. The inventory covers tracked and nonignored text/config, excluding Git/runtime artifacts; its output stayed outside the clone. Metadata and historical evidence-file hotspots are triage, not proof of semantic duplication or runtime cost.

Representative source investigation: `src/reports/service.py`, `sampling.py`, `acquisition.py`, `token_mix_history.py`, `src/analysis/cache.py`, `src/cache/database.py`, `src/watch/acquisition.py`, `src/application/live.py`, `session_detail.py`, `src/accounts/refresh_policy.py`, `src/sources/opencode_v2_transport.py` and `src/web/assets/live.js`. Read contracts/tests: `test_step9_parity_performance.py`, `test_workload_mix.py`, `test_report_sampling.py`, `test_session_cost_cache.py` and the shared `fixtures/synthetic_month.py`. Existing product tests were read, not rerun or claimed as fresh PASS.

User-visible/high-frequency paths and material costs:

- Normal reports: root catalog/order, two independent priceable samples, revision-gated analysis/cache, model projection; account periods are a separate history scope. The synthetic provider has no accounts, so this is not Normal account-network latency.
- Historical Token Mix: all roots, disposable derived-cache I/O, deserialization and category/publisher valuation; analyzed snapshots are released per root, but total usage entries are retained for aggregation. Peak memory remains unmeasured.
- Watch/Web: bounded dashboard initialization, independent daily/history enrichment and active-root refresh; one Live publisher serves tabs, detail pages do not acquire source data, browser replay/probes are bounded. The runner exercises the CLI-neutral coordinator, not Web card workers, SSE throughput, browser paint or detail-page latency.
- External acquisition: V2 pools loopback GET connections with one stale-connection retry; account refresh owns cadence, deadlines and bounded retries. These are source-backed limits, not newly measured service latency. No model inference or new provider calls were started; monetary cost is unknown, not zero.

Windows 11 build 26300, AMD64 Family 25 Model 33, CPython 3.14.7. Three sequential fresh-process repetitions of each command:

```text
py -3 development/tools/benchmark_large_month.py --roots 100 --prompts 50 --watch
py -3 development/tools/benchmark_large_month.py --roots 20 --prompts 50 --children 2 --today-roots 5 --running-roots 2 --watch
py -3 development/tools/benchmark_large_month.py --roots 1000 --prompts 20 --watch
```

The runner constructs deterministic synthetic input, fixed UTC/time/pricing and fresh temporary report/Watch SQLite caches; warm phases reuse only their run's cache. OS caches were not flushed; workstation background load was uncontrolled. Medians below are seconds, not thresholds or total process durations. Scenario sizes differ, so no cross-scenario scaling ratio is claimed. Timing excludes fixture construction and initial database setup.

| Scenario | Report cold / warm | Watch usable cold / warm | Watch full cold / warm | Refresh cold / warm |
| --- | --- | --- | --- | --- |
| 100 roots x 50 prompts | .0374 / .0158 | .4945 / .1368 | .4958 / .1372 | .0011 / .0005 |
| 20 roots + 40 children x 50, 5 today / 2 running | .0967 / .0416 | .5472 / .1845 | .5890 / .2192 | .0215 / .0207 |
| 1,000 roots x 20 prompts | .0702 / .0213 | .3811 / .0771 | .3824 / .0782 | .0030 / .0026 |

All nine collected runs exited zero, with both report sample counts 100. Cold Normal reports hydrated 2/5/5 roots respectively; every warm Normal report hydrated zero. Their warm revision checks were 2/5/5, not the full catalog. The two running roots in the child scenario are old and outside Normal's sample; Watch independently hydrates both on each refresh. Watch cold initialization hydrated 20 roots in each scenario; warm initialization hydrated 2/4/2 and subsequent refresh 0/2/0. The unchanged benchmark's broad O(root) check remains satisfied; these fixtures do not prove all catalogs always require only five checks.

### Deep history, profiling and decision

An independent 100-root x 50-prompt Token Mix probe ran three times with separate fresh caches, using the same fixture/config/prices/time. Cold/warm median wall time: **2.0642 / .7023 s**; process CPU: **1.0938 / .7031 s**. Cold wall ranged 1.9856–2.8556 s, warm .6994–.7039 s: storage/background noise is material, so no small timing gain is claimed. Every run retained 5,000 prompts/calls, cold/warm hydrations 100/0 and revision checks 200/100. Deep scans released `service._analyzed`; this is not a peak-memory bound. Full projection SHA-256 matched across all six cold/warm outputs: `a40b21f2d6071af0f9fe8a0cb667567968d0bf5aecc54c757ebdf6624b969365`.

[Current sanitized raw samples, setup, file hashes, profiles and executable `deep_probe`](../architecture/governance/verification/performance-40-20261105.json) retain reproduction evidence. From the repository root, the embedded deep probe can be reproduced with:

```text
py -3 -c "import json; exec(json.load(open('development/architecture/governance/verification/performance-40-20261105.json', encoding='utf-8'))['deep_probe'])"
```

Separate cProfile runs are diagnostic, not equivalent uninstrumented timing samples. Normal 1,000 x 20 observed 789,436 calls, .8554 s profiler total; fixture construction consumed .6695 s cumulative, while two report builds consumed .1592 s. Deep cold+warm observed 4,605,257 calls, 3.7773 s profiler total; builds consumed 3.5652 s cumulative, including 301 SQLite closes (.5704 s self), commits (.3703 s self) and 100 cache bundle reconstructions (.4961 s cumulative). Inclusive/profile totals overlap and are not additive; subprocess setup/imports are not product report cost.

The simpler current target is retained: bounded Normal sampling plus disposable revision-keyed cache, not a second comparison-history engine. Deep cache connection/deserialization work is observable, but shrinking that scan changes semantics and pooling/batching changes thread, transaction, rollback, busy-timeout and error ownership. This synthetic profile alone does not establish an equivalent safe production redesign or measured candidate gain. No speculative wrapper/pool or paid-provider benchmark was introduced. **NO_GAIN** means completed assessment with no runtime optimization, not an inconclusive claimed improvement.

### Benchmark repair and verification

The exploratory active/children command exited 1: the old runner expected both running roots to hydrate on warm Normal, even though neither was sampled. That failed assertion is retained as failure evidence, not PASS. The runner now derives visited roots from public `report_source_revisions()` and counts the fixture's active roots within that set; it still rejects missing sampled-running hydration or extra stable-root hydration. Production acquisition is unchanged.

`py -3 -m unittest development.tests.test_benchmark_large_month -v` passed one test with three independent fresh-cache cases (4 roots x 60 prompts; 0/1/4 running roots). Exactly two roots are sampled, with expected warm hydrations 0/0/2, covering idle reuse, old-running exclusion and sampled-running bypass. The nine report/Watch runs and three deep runs also passed their stated assertions. No local full product suite, validator, version bump, ZIP or live installation/browser probe was run: all delivery edits are development-only. Normal remote PR checks are reported in the PR, not anticipated here. No requirement/test exception was requested. Architecture responsibilities/flows are unchanged; no diagram/module-contract update is needed. Watch/Normal CPU, peak memory, installed-service/browser latency and monetary cost remain unknown.

### Historical findings and scope (not current baselines)

- Milestone-20 (2026-10-26, revision `07c14d21fcbc32ab5b194a5afc85c8cb4ae25cbd`): NO_GAIN, nine successful synthetic runs. Normal reports then sampled bounded recent history; 100 x 50 cold/warm report medians were .0405/.0204 seconds, 1,000 x 20 .0761/.0244. These are different semantics, not a regression ratio. [Original samples](../architecture/governance/verification/performance-20.json) preserve setup and acquisition counters. Cache connection lifecycle was already a candidate, not established production waste.
- Older milestone-40 (2026-10-28, revision `76d9054556da384d8cb888b16699ece5f1b2d984`): the then-required deep model/publisher comparison scan produced 100 x 50 cold/warm medians 3.0544/.0390 s and 1,000 x 20 32.9626/.0628 s. [Original samples and profile](../architecture/governance/verification/performance-40.json) retain the nine runs and older benchmark repair. Its initial 120-second collection and interrupted profile were discarded; a bounded 600-second collection with per-process 180-second limits and a subsequent fresh profile completed. FR 000534 deliberately restored bounded global sampling on 2026-10-29; those old timings are neither current latency nor an equivalent-work speedup. The later architecture assessment removed the unreachable comparison-profile/cache engine, not historical Token Mix.
- FR 000360 indexed assistant parents, synthetic prompt windows and provider-filtered prior entries in `src/analysis/prompt_index.py`. A historical 10,000-prompt detail profile observed 724M calls/292.5 seconds instrumented; repaired scale/parity tests later took 5.9 seconds uninstrumented, then 7–8 seconds with expanded tests. Different instrumentation/fixtures prohibit a precise speedup ratio. `development/tests/test_web_session_detail.py` retains complete totals, bounded pages, stable-work counters and strict timestamp semantics. Running evidence reuses analysis only when unchanged.
- Historical live V2 observations identified fresh-connection overhead (~26 ms/request before keep-alive pooling), repeated model resolution, duplicated catalog reads and broad Watch hydration. Existing pooling/retry, immutable-catalog memoization, bounded catalog reuse, revision-keyed idle-root skips and hinted resync addressed those owners. Live timings are not renewed guarantees. Parallel hydration was rejected: 20 roots measured 736 ms sequential versus 597 ms with eight threads on a serializing service, insufficient benefit for the complexity.
- Historical v80.36 offline replay: one causal `_RootTimeline` reduced 74-root analysis 252 to 92 ms; flat cache serialization reduced 90 to 31 ms with byte-identical JSON. Analysis records (2,528 across variants), cache and Watch output hashes matched. Historical Watch status (~2 ms for 20 hydrated roots) was left unchanged.
- Historical v80.46 captured-month workload (6,279 requests, minimum of 40 runs, three alternating rounds): packed billing fingerprints 14–16 to 10–12 ms, per-day formatting 37–39 to 22–25 ms, quota projection 67–70 to 43–47 ms. Fingerprints, entries, costs and epoch/midnight behavior hashed identically; Decimal valuation was unchanged.
- Historical v80.53 synthetic 2,000-prompt projection: reply indexing and shared context epochs reduced median .76 to .26 seconds (five repetitions), identical hashes. Earlier small-live-root observations do not justify quadratic work on large histories.
- Historical v80.33 filesystem-copy parity covered normal/all-model/session/date reports, Watch and token mix on shared captured input. Historical full/live checks and launcher/terminal/macOS observations retain their original dates/scopes; none is a fresh milestone-40 PASS. Test-runner concurrency, focused validator-negative checks and owner fixtures previously reduced test cost/coupling; no new suite redesign is claimed here.

## Next investigations

Current Normal/deep baselines are now separated above. Before changing connection lifetime or batching, characterize concurrent report/Live owners, transaction failures and fresh revision/deletion behavior on equivalent input. Measure source hydration and child/task traversal separately; deep deserialization/peak-memory work needs its own evidence. Watch quota projection duplication requires proof that discovery cannot change comparison pricing between projections. Browser resize/scroll/selection, assistive technology, native macOS, sleep/wake and interactive Ctrl+C remain separate proof scopes. No cross-repository proposal or new FR was published; these are investigation limits, not newly approved work.

## Rejected hypotheses

The older milestone-40 rejection of removing comparison evidence applied to its then-required model-specific policy; FR 000534 explicitly reverses that policy, not historical Token Mix. Do not expand Normal to all history merely to satisfy an obsolete benchmark assertion, cache running roots, skip source revisions, impose Watch row caps on full detail, rebuild prices on display ticks or add per-tab account/Watch workers. Do not retain speculative pooling/concurrency wrappers for an invented gain. Synthetic wall measurements are not production latency, billing parity, CPU/memory savings or provider cost evidence. Transaction isolation, rollback/close behavior and source authority remain required.
