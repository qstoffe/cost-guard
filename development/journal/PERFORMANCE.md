# Performance investigations

Source revision: 1b0fd64375bfc10c6653dda86dea41e2d0c1eb88
Checked revision: 1b0fd64375bfc10c6653dda86dea41e2d0c1eb88
Last checked: 2026-10-29
Status: current

## Summary

FR 000534 (2026-10-29) deliberately restores global latest-up-to-100 comparison sampling; ordinary model lists and tier warnings no longer acquire deep model/publisher comparison samples. Historical Token Mix remains deep and explicit. The milestone-40 observations below describe the superseded policy, not current latency or an equivalent-work speedup. Running roots still require authoritative hydration; revision checks are unchanged.

## Evidence

### Milestone-40 assessment

Whole-repository inventory at the source revision: 539 readable files (219 source/config, 172 tests, 148 documentation), 64 binary/over-1-MiB exclusions, no exact-byte duplicate groups. One source/config entry is the empty local inventory output created by redirection; it is not product code. Tracked and nonignored files were inventoried, not Git internals, credentials or other checkouts. Metadata is triage, not proof of semantic duplication/dead code.

Representative investigation covered `src/reports/service.py`, `sampling.py`, `comparison_history.py`, `token_mix_history.py`, `src/cache/database.py`, `src/watch/acquisition.py`, `src/application/live.py`, `src/accounts/refresh_policy.py`, `src/sources/opencode_v2_transport.py`, browser session paging and the existing step9/workload-mix tests. Test files were read for contracts, not executed as new passes. The global sample remains bounded; model/publisher evidence scans older roots, releases deep snapshots and uses revision/dependency-keyed compact caches. Deletion/revision checks, noncacheable running work, one shared Live owner, bounded account retries and loopback-only pooled transport remain required.

Reproduction: Windows 11 build 26300, AMD64, CPython 3.14.7; three sequential fresh-process repetitions of each command:

```text
py -3 development/tools/benchmark_large_month.py --roots 100 --prompts 50 --watch
py -3 development/tools/benchmark_large_month.py --roots 20 --prompts 50 --children 2 --today-roots 5 --running-roots 2 --watch
py -3 development/tools/benchmark_large_month.py --roots 1000 --prompts 20 --watch
```

The runner constructs deterministic synthetic input, fixed UTC/time/pricing and fresh temporary report/Watch SQLite caches; warm phases reuse only their run's cache. OS caches were not flushed; workstation background load was uncontrolled. Medians below are seconds, not thresholds or total process durations. Scenario sizes differ, so no cross-scenario scaling ratio is claimed.

| Scenario | Report cold / warm | Watch usable cold / warm | Watch full cold / warm | Refresh cold / warm |
| --- | --- | --- | --- | --- |
| 100 roots x 50 prompts | 3.0544 / .0390 | .7443 / .2137 | .7460 / .2144 | .0019 / .0009 |
| 20 roots + 40 children x 50, 5 today / 2 running | .5680 / .0640 | .5191 / .1884 | .5597 / .2240 | .0204 / .0200 |
| 1,000 roots x 20 prompts | 32.9626 / .0628 | .5247 / .1248 | .5269 / .1258 | .0049 / .0029 |

All nine completed runs exited zero. Both report sample counts were 100. Cold reports hydrated every root; warm idle reports hydrated zero and the active scenario hydrated exactly its two running roots. Existing O(root) revision-check assertions also passed. The former unconditional zero-hydration assertion failed the active case correctly at the source layer but incorrectly labelled the behavior a benchmark failure; only that development assertion changed. The first collection hit its 120-second shell budget and was discarded; a bounded 600-second collection with per-process 180-second limits completed and retained each result immediately. An interrupted profile attempt is not PASS; a subsequent fresh profile completed.

A separate `py -3 -m cProfile -o performance-40.prof development/tools/benchmark_large_month.py --roots 100 --prompts 50` run (without Watch) observed 2,707,112 calls, 4.730 seconds profiler total. `comparison_samples` consumed 4.339 seconds cumulative; 407 SQLite connections spent 1.172 seconds closing and .931 seconds committing. Inclusive timings overlap and are not additive. Instrumented timings are not comparable to unprofiled wall medians. The profile implicates transaction lifecycle in this synthetic cold workload, not a proven production root cause. Pooling/batching would change thread/transaction/error ownership and needs concurrent-reader/writer, rollback, busy-timeout and recovery characterization first. Removing the historical scan or skipping revisions would violate current evidence semantics, not optimize equivalent work.

[Sanitized raw samples and setup](../architecture/governance/verification/performance-40.json) retain all nine runs, source identity, counters, inventory summary and profile aggregates. No candidate runtime implementation or equivalence digest exists: cold/warm are cache states, not before/after implementations. CPU time, peak memory, installed-service/browser latency and monetary cost are unknown. No provider/model calls, live installation probes, product tests, validator, version bump or ZIP were performed; all delivered edits are under development. Architecture responsibilities/flows are unchanged: no diagram/module-contract update.

### Historical findings and scope

- Milestone-20 (2026-10-26, revision `07c14d21fcbc32ab5b194a5afc85c8cb4ae25cbd`): NO_GAIN, nine successful synthetic runs. Normal reports then sampled bounded recent history; 100 x 50 cold/warm report medians were .0405/.0204 seconds, 1,000 x 20 .0761/.0244. These are different semantics, not a regression ratio. [Original samples](../architecture/governance/verification/performance-20.json) preserve setup and acquisition counters. Cache connection lifecycle was already a candidate, not established production waste.
- FR 000360 indexed assistant parents, synthetic prompt windows and provider-filtered prior entries in `src/analysis/prompt_index.py`. A historical 10,000-prompt detail profile observed 724M calls/292.5 seconds instrumented; repaired scale/parity tests later took 5.9 seconds uninstrumented, then 7–8 seconds with expanded tests. Different instrumentation/fixtures prohibit a precise speedup ratio. `development/tests/test_web_session_detail.py` retains complete totals, bounded pages, stable-work counters and strict timestamp semantics. Running evidence reuses analysis only when unchanged.
- Historical live V2 observations identified fresh-connection overhead (~26 ms/request before keep-alive pooling), repeated model resolution, duplicated catalog reads and broad Watch hydration. Existing pooling/retry, immutable-catalog memoization, bounded catalog reuse, revision-keyed idle-root skips and hinted resync addressed those owners. Live timings are not renewed guarantees. Parallel hydration was rejected: 20 roots measured 736 ms sequential versus 597 ms with eight threads on a serializing service, insufficient benefit for the complexity.
- Historical v80.36 offline replay: one causal `_RootTimeline` reduced 74-root analysis 252 to 92 ms; flat cache serialization reduced 90 to 31 ms with byte-identical JSON. Analysis records (2,528 across variants), cache and Watch output hashes matched. Historical Watch status (~2 ms for 20 hydrated roots) was left unchanged.
- Historical v80.46 captured-month workload (6,279 requests, minimum of 40 runs, three alternating rounds): packed billing fingerprints 14–16 to 10–12 ms, per-day formatting 37–39 to 22–25 ms, quota projection 67–70 to 43–47 ms. Fingerprints, entries, costs and epoch/midnight behavior hashed identically; Decimal valuation was unchanged.
- Historical v80.53 synthetic 2,000-prompt projection: reply indexing and shared context epochs reduced median .76 to .26 seconds (five repetitions), identical hashes. Earlier small-live-root observations do not justify quadratic work on large histories.
- Historical v80.33 filesystem-copy parity covered normal/all-model/session/date reports, Watch and token mix on shared captured input. Historical full/live checks and launcher/terminal/macOS observations retain their original dates/scopes; none is a fresh milestone-40 PASS. Test-runner concurrency, focused validator-negative checks and owner fixtures previously reduced test cost/coupling; no new suite redesign is claimed here.

## Next investigations

Measure the restored bounded comparison scope independently from deep historical Token Mix before reusing old cache-I/O conclusions. Characterize concurrent report/Live owners and transaction failures before changing connection lifetime or batching. Measure source hydration and child/task traversal separately. Watch quota projection duplication requires proof that discovery cannot change comparison pricing between projections. Browser resize/scroll/selection, assistive technology, native macOS, sleep/wake and interactive Ctrl+C remain separate proof scopes. No cross-repository proposal was published; follow-up is retained here, not a new FR.

## Rejected hypotheses

The milestone-40 rejection of removing comparison evidence applied to its then-required model-specific policy; FR 000534 explicitly reverses that policy, not historical Token Mix. Do not cache running roots, skip source revisions, impose Watch row caps on full detail, rebuild prices on display ticks or add per-tab account/Watch workers. Do not retain speculative pooling/concurrency wrappers for an invented gain. Synthetic wall measurements are not production latency, billing parity, CPU/memory savings or provider cost evidence. Transaction isolation, rollback/close behavior and source authority remain required.
