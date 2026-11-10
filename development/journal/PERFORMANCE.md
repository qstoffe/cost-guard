# Performance investigations

Source revision: 13ec8fee2821be77d35f6589242e9d5b6bd6e2a2
Checked revision: 13ec8fee2821be77d35f6589242e9d5b6bd6e2a2
Last checked: 2026-11-10
Status: current

## Summary

**NO_GAIN — milestone 120 (2026-11-10): no validated optimization identified.** Offline baselines cover Normal, Watch, CLI/compact-Web Token Mix and twelve-root cards. Existing shared guidance avoids repeated sampling when telemetry demands it. No candidate/product change, new speedup or whole-Web/installed-source recovery claim. Performance advances 80→120; ordinary count stays 120.

## Evidence

### Scope, owners and setup

Inventory: 1,250 selected text/config files (381 source/config, 346 test, 523 documentation), 343 binary/over-1-MiB exclusions, no exact duplicate groups; includes 269 `src/`, 344 `development/tests/` and 15 `development/tools/` files. Launcher extensions fall outside this selection; tracked paths were listed, not benchmarked. Size hotspots are not semantic findings. Full inventory: originating-session `scratch:/performance-inventory.json`; published summary below.

Representative source: report service/sampling/acquisition, context sample/guidance, Token Mix/cache/history-work/shared-evidence owners under `src/reports/`; `src/analysis/cache.py`, `src/analysis/context.py`, `src/cache/database.py`; Web coordinator/card workers/readers/guidance/cards under `src/watch/`; `src/application/session_detail.py`, `src/accounts/refresh_policy.py`, `src/sources/opencode_v2_transport.py` and `src/sources/opencode_tokens.py`. Runners: `development/tools/benchmark_large_month.py`, `development/tests/integration/benchmark_card_guidance.py` and `benchmark_v2_acquisition.py`; fixture: `development/tests/fixtures/synthetic_month.py`. Tests read, not rerun: `test_benchmark_large_month.py`, `test_step9_parity_performance.py`, `test_context_sample.py`, `test_web_token_mix.py`, and scale/page contracts in `test_web_session_detail.py`, under `development/tests/`.

Reachable costs and protected behavior:

- Normal orders the catalog and acquires enough eligible history for two latest-100 samples; unpriceable prompts, ties and touched old roots can deepen traversal. Account scope is separate. Fixtures have no accounts/availability network or V2 sampling-batch seam; they do not prove bracket amortization.
- Full Token Mix retains global deduplication/grouping. CLI reads/writes rich derived bundles; managed Web can reuse compact facts without repricing or rich writes, but still verifies membership/revisions and aggregates all shown requests. Neither reconstructs deleted history.
- Web separates card, account-history, detail and scalar-index lanes; HTTP pages never acquire history. Card readers isolate transport lifetimes; shared guidance uses one card-pool job, not per-tab samplers. Running roots stay fresh; changed scope/epoch, clock rollback and cancellation retire guidance.
- Loopback V2 GETs already pool connections with one stale-socket retry; SSE/cancellation have separate owners. Account cadence/deadline/retry owners are independent. No new network/provider/inference or monetary-cost measurements were made; unknown is not zero.

Windows 11 build 26300, AMD64 Family 25 Model 33, CPython 3.14.7. Sequential baseline processes use fixed synthetic UTC/time/pricing and fresh SQLite caches; warm phases reuse only their pair's cache. OS caches were not flushed; background load uncontrolled. Timings exclude fixture/database setup; no total-process, cross-date regression or cross-scenario scaling claim.

### Current Normal and CLI-neutral Watch baselines

Three repetitions of each unchanged command:

```text
py -3 development/tools/benchmark_large_month.py --roots 100 --prompts 50 --watch
py -3 development/tools/benchmark_large_month.py --roots 20 --prompts 50 --children 2 --today-roots 5 --running-roots 2 --watch
py -3 development/tools/benchmark_large_month.py --roots 1000 --prompts 20 --watch
```

Medians, seconds; cold / warm within each cell:

| Scenario | Normal | Watch usable | Watch full | Refresh |
| --- | --- | --- | --- | --- |
| 100 roots × 50 prompts | .0385 / .0165 | .5461 / .1466 | .5473 / .1471 | .0013 / .0005 |
| 20 roots + 40 children × 50; 5 today / 2 running | .1010 / .0430 | .5827 / .1981 | .6240 / .2343 | .0275 / .0297 |
| 1,000 roots × 20 prompts | .0692 / .0220 | .3748 / .0979 | .3768 / .0991 | .0035 / .0032 |

All nine runs exited zero with sampled-running/O(root) assertions satisfied and both sample counts 100. Normal cold hydrated 2/5/5 roots; warm zero, with 2/5/5 revision checks. Unsampled running roots do not force a full scan; Watch refreshes them independently. Not Web/browser/SSE/native or real-source latency.

### Current deep history and diagnostic profiles

Three alternating CLI/Web repetitions, each 100 roots × 50 prompts with its own fresh cache. Web enables `cache_token_mix_history` and `shared_web_evidence`, including end-of-scan membership/revision verification, not partial-history continuation or a full Web host.

| Existing path | Wall cold / warm (s) | Process CPU cold / warm (s) | Cache files after phase (bytes) |
| --- | --- | --- | --- |
| CLI deep | 2.0601 / .8626 | 1.1719 / .8438 | 21,807,104 |
| Web compact | .6546 / .1936 | .6094 / .1875 | 2,199,552 |

These existing paths have different execution/cache contracts: not a before/after gain or physical I/O measurement. All twelve uninstrumented full projected outputs matched SHA-256 `0d57b7105985dca688e67726094746526a21d700279eb6de0285fe85764c840b`, with 5,000 prompts/requests and no retained `service._analyzed` roots. Both paths hydrate 100/0 roots cold/warm. CLI performs 200/100 revision work items and one catalog read per phase; Web 500/200 including bulk checks and two catalog reads. Warm Web has 100 compact hits, no analysis/repricing. Its scalar revision counter alone is zero, not zero freshness work.

Separate single cProfile/tracemalloc pairs are diagnostics, not repeated timing/memory samples. CLI cold: SQLite commit .566 s and close .553 s self time; CLI warm: rich bundle reconstruction .539 s cumulative out of 1.210 s build wall. Web warm: shared grouping/projection .257 s cumulative and compact decode .094 s out of .424 s instrumented build wall. Inclusive times overlap. Traced Python build peaks, cold/warm: CLI **3,784,342 / 14,891,706 bytes**, Web **9,850,522 / 11,381,980 bytes**. They exclude fixture construction, native SQLite buffers, other processes/browser, and are not RSS or a general memory bound. Instrumented outputs matched the same digest.

Decision: retain mode-specific acquisition over one canonical projection. SQLite lifecycle/serialization and rich reconstruction are costs, not proof that pooling or routing CLI through Web cache is equivalent. Alternatives change concurrency, transactions, rollback, timeouts, freshness and cache reuse. No equivalent measured candidate or source optimization is retained.

### Card/guidance cohort: exercise the demanded work

Unchanged runner: twelve inactive V2-wire roots, batch two, three alternating trials, 60-second strategy budget:

```text
py -3 development/tests/integration/benchmark_card_guidance.py --roots 12 --trials 3 --batch-size 2 --seconds 60 --output <owned-scratch>/card-guidance-120.json
```

All six default trials observed 12/12 roots, with no failures or budget exhaustion, **but zero warning finalists and no shared producer**. `WireHistory` omits cache-read/write telemetry. `opencode_tokens.py` preserves those fields as unknown; the context estimator requires known I/C/W/O, so numeric guidance is correctly not demanded. The runner's non-null completion time alone is not numeric-guidance evidence.

A scratch-only adapter added known-zero `tokens.cache.read/write`, changing no product/runner. Six new trials asserted 12/12 roots, five numeric-guidance finalists, no failures/budget exhaustion, and producer execution with twelve-root sampling in all three shared trials.

| Existing strategy, complete telemetry | First rows median (s) | Cohort observed median (s) | Guidance ready median (s) | Sample-root work per run |
| --- | --- | --- | --- | --- |
| Per-card control | .2100 | .4367 | .4367 | 96 |
| Shared guidance | .0422 | .1465 | .2484 | 12 |

Existing behavior, not a delivered optimization/production speedup. One interpreter alternates fresh-cache strategies; allocator carryover, uncontrolled load and 20-ms ticks limit CPU/RSS/timing comparisons. At most three occupied/history slots were observed, not active-root fairness proof. Summed per-service `context_sample_peak_analysis_roots` values 8/1 are not concurrent peaks. In-memory wire traffic bypasses HTTP counters. No card numeric-value parity digest was captured: assertions prove exercised work/membership, not full semantic/browser/global Earlier acceptance.

### Reproduction, collection and delivery scope

[Sanitized raw samples, setup, source hashes, profiles and embedded probe sources](../architecture/governance/verification/performance-120-20261110.json) retain the baseline and complete-telemetry card evidence. The initial default-card observation is explicitly a summary reconstructed from returned output, not a full raw archive. Original files remain in originating-session `scratch:/performance-120.json`, `scratch:/card-guidance-120.json` and `scratch:/card-guidance-complete-120.json`.

In a new authorized worker, obtain its own scratch through the native helper; use native-injected scratch/session values, never manually replace them. Extract `baseline.probe_source` and `numeric_guidance.probe_source` from the published JSON into that owned scratch. Run from an explicit repository cwd, using those files and owned output paths:

```text
py -3 <owned-scratch>/performance_probe.py --output <owned-scratch>/performance-120.json
py -3 <owned-scratch>/guidance_probe.py --roots 12 --trials 3 --batch-size 2 --seconds 60 --output <owned-scratch>/card-guidance-complete-120.json
```

An optional inline-Python summary hit `SCRATCH_SESSION_BOUNDARY` before execution (unsupported environment-read syntax). Decision Delegate authorized one supported injected PowerShell packaging attempt, not a permission/test waiver. It succeeded without rerunning samples, alternate access, changed scratch identity or rebootstrap. No benchmark/product assertion failed.

Development-only evidence/docs/state activates no product suite, package validation, live/browser probe, version/release update or ZIP; none ran or is claimed PASS. GitHub checks/blockers are read at delivery. Responsibilities/flows are unchanged: no architecture update. Physical I/O, real-source/provider/whole-Web latency, total memory and monetary cost remain unknown. No requirement exception, proposal or held-work release.

Historical, not current baselines: [milestone 80](../architecture/governance/verification/performance-80-20261108.json) and [2026-11-05 milestone 40](../architecture/governance/verification/performance-40-20261105.json) retain original samples, limitations and collection repairs. Older observations remain in Git; none is a fresh regression ratio.

## Next investigations

Before connection/cache redesign, establish equivalent concurrent-owner, rollback/failure, revision/deletion and consumer-reuse contracts; profile warm allocations. Guidance claims need non-vacuous demand/producer assertions. Complete telemetry is a separate fixture, never a repair of unknown production counters. Whole-Web, installed V2/global Earlier, browser/native and numeric-parity proof remain separate.

## Rejected hypotheses

Do not expand Normal to all history, cache running roots, skip revisions, cap full detail to Watch rows, reprice on display ticks or add per-tab workers. Fewer cache bytes are not measured physical I/O/lower peaks; zero scalar checks are not zero bulk freshness work. Existing mode/strategy differences are not candidate gains. A non-null guidance completion time with zero finalists/producer is not exercised numeric guidance. Preserve unknown telemetry, source authority, transaction isolation and bounded cleanup; no speculative pooling for an invented gain.
