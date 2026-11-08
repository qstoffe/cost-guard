# Performance investigations

Source revision: c110fe568c41abb18b9e386f20a3c2f456f956e7
Checked revision: c110fe568c41abb18b9e386f20a3c2f456f956e7
Last checked: 2026-11-08
Status: current

## Summary

**NO_GAIN — milestone 80 (2026-11-08).** Offline baselines cover bounded Normal, Watch reuse and deep Token Mix. Existing Web compact hits avoid warm hydration/repricing; CLI reconstructs richer derived bundles. No candidate optimization, whole-Web acceptance, source/tool/version change or ordinary-count increment. Only performance milestone 80 advances.

## Evidence

### Current coverage and setup

Whole-repository inventory: 1,083 readable files (351 source/config, 322 test, 410 documentation), 284 binary/over-1-MiB exclusions, no exact duplicates. Includes 254 `src/`, 320 `development/tests/`, 15 `development/tools/` files; tracked plus nonignored text/config, excluding Git/runtime artifacts. Full inventory: originating-session `scratch:/performance-inventory.json`; summary published below. Historical evidence JSON size hotspots are not runtime/semantic findings.

Representative source investigation: `src/reports/service.py`, `src/reports/sampling.py`, `src/reports/acquisition.py`, `src/reports/token_mix_history.py`, `src/reports/token_mix_cache.py`, `src/reports/history_work.py`, `src/analysis/cache.py`, `src/cache/database.py`, `src/watch/web_coordinator.py`, `src/application/session_detail.py`, `src/accounts/refresh_policy.py` and the GET owner in `src/sources/opencode_v2_transport.py`. Runner/fixture and critical contracts were inspected in `development/tools/benchmark_large_month.py`, `development/tests/fixtures/synthetic_month.py`, `development/tests/test_benchmark_large_month.py`, `development/tests/test_step9_parity_performance.py`, `development/tests/test_web_token_mix.py` and `development/tests/test_web_session_detail.py`. Existing unit tests were read, not rerun or claimed as fresh PASS.

User-visible/high-frequency paths and material costs:

- Normal: full root catalog/order, two independent samples of up to 100 eligible prompts, revision-keyed analysis and model projection. Unpriceable/tied/recently touched history can require more roots; this is not a universal five-root bound. Account periods have a separate history scope; synthetic runs have no accounts or model-availability network.
- Explicit Token Mix: complete root population, clone deduplication, category/publisher grouping and retained aggregate entries. CLI releases analyzed roots but reads rich derived bundles. Managed Web uses compact facts, current membership/revision brackets and no rich derived writes. Both still aggregate all shown requests; neither reconstructs deleted history.
- Watch/Web: CLI-neutral startup/enrichment/refresh is timed, not Web's separate card/history/detail/index lanes, finite jobs, SSE, browser or native lifecycle. HTTP detail pages serialize bounded rows without source acquisition.
- External costs: V2 pools loopback GETs with one stale-connection retry; account refresh has cadence/deadline/retry owners. No newly measured network/provider latency, model inference or new provider calls. Monetary cost is unknown, not zero.

Windows 11 build 26300, AMD64 Family 25 Model 33, CPython 3.14.7. Three sequential fresh-process repetitions of each unchanged repository command:

```text
py -3 development/tools/benchmark_large_month.py --roots 100 --prompts 50 --watch
py -3 development/tools/benchmark_large_month.py --roots 20 --prompts 50 --children 2 --today-roots 5 --running-roots 2 --watch
py -3 development/tools/benchmark_large_month.py --roots 1000 --prompts 20 --watch
```

Fixed synthetic input, UTC/time/pricing, fresh temporary SQLite caches; warm phases reuse only their run's cache. OS caches not flushed; background load uncontrolled. Medians in seconds exclude fixture/database setup, not thresholds or total process durations. No cross-scenario scaling or cross-date regression ratio is claimed.

| Scenario | Report cold / warm | Watch usable cold / warm | Watch full cold / warm | Refresh cold / warm |
| --- | --- | --- | --- | --- |
| 100 roots x 50 prompts | .0432 / .0174 | .6159 / .1567 | .6171 / .1571 | .0014 / .0006 |
| 20 roots + 40 children x 50, 5 today / 2 running | .1099 / .0414 | .6174 / .2035 | .6584 / .2394 | .0260 / .0268 |
| 1,000 roots x 20 prompts | .0872 / .0218 | .4603 / .0847 | .4616 / .0858 | .0030 / .0027 |

All nine runs exited zero, with both report sample counts 100. Cold Normal hydrations were 2/5/5 respectively; warm hydrations were all zero, with 2/5/5 revision checks. The two running child-scenario roots are old/outside Normal's sample; Watch independently hydrates both per refresh. Watch cold initialization hydrated 20 roots per scenario, warm initialization 2/4/2, subsequent refresh 0/2/0. Runner assertions retain sampled-running bypass and the broad O(root) revision bound; the fixture has no V2 batch-sampling seam, so it does not prove bracket-amortization performance.

### Deep history, profiling and decision

The new offline probe alternates existing CLI deep and compact Web paths for three repetitions each, 100 roots x 50 prompts, with independent fresh caches. Web enables `cache_token_mix_history` and `shared_web_evidence`, including end-of-scan membership/revision verification; it is not a full Web host or partial-history continuation test.

| Existing path | Wall cold / warm (s) | Process CPU cold / warm (s) | Cache files after each phase (bytes) |
| --- | --- | --- | --- |
| CLI deep | 1.9670 / .7901 | 1.2500 / .7969 | 21,807,104 |
| Web compact | .6601 / .2145 | .6563 / .1875 | 2,199,552 |

CLI wall ranges: cold 1.9234–2.1120 s, warm .7334–.8127 s; Web: cold .6531–.6948 s, warm .2066–.2227 s. These paths have different cache/bracketing contracts: the table is not a before/after improvement or billing comparison. Cache file size is not physical bytes read/written.

Every run retained 5,000 prompts/calls, released `service._analyzed`, and hydrated 100/0 roots cold/warm. CLI performed 200/100 per-root revision checks and one catalog read per phase. Web performed 500/200 revision work items (including bulk checks) and two catalog reads per phase; warm Web had 100 compact hits, no analysis or repricing. Its scalar `revision_count` alone is 300/0 and excludes bulk work: zero there does not mean no freshness checks. All 12 full projected JSON outputs matched SHA-256 `ac6f9f4e30469c355143292230897ecc43d91fa5f0770f2de7805f8ac5e0744b`.

[Sanitized raw samples, setup, source hashes, profiles, inventory summary and executable `probe_source`](../architecture/governance/verification/performance-80-20261108.json) retain reproduction evidence. Original samples remain in originating-session `scratch:/performance-80.json`. To reproduce, extract `probe_source` from that JSON to a Python file in an existing owned scratch directory, set `OPENCODE_TOOLKIT_SESSION_SCRATCH` to that directory, and run from this repository root:

```text
py -3 <owned-scratch>/performance_probe.py --output <owned-scratch>/performance-80.json
```

Separate single-run cProfile and tracemalloc passes are diagnostics, not timing samples or repeated memory measurements. CLI cold had .552 s SQLite-close and .462 s commit self time; warm rich-bundle reconstruction consumed .520 s cumulative out of a 1.212 s instrumented build. Web warm shared grouping/projection consumed .247 s cumulative out of .396 s, with compact decode .081 s. Inclusive times overlap and are not additive. These observations do not attribute real-source latency.

Traced Python build peaks: CLI cold/warm **3,784,422 / 14,810,442 bytes**, Web **9,810,221 / 11,381,980 bytes**. Releasing analyzed roots does not guarantee lower warm peaks; precise causes remain unestablished. Single samples exclude fixture construction, native SQLite buffers, child/browser memory: not RSS, total-memory bounds or an optimization claim. Instrumented outputs matched the same hash.

Decision: retain bounded Normal and mode-specific acquisition over one canonical Token Mix projection. CLI serialization/connection lifecycle is observable cost; Web already avoids rich writes. A blanket switch/pool changes cache reuse, revision brackets, threads/transactions, rollback, busy-timeout and failure ownership. No equivalent candidate redesign was established; no speculative wrapper or source optimization is retained. **NO_GAIN** completes this assessment, not separate live/Web recovery requirements.

### Verification and collection repair

The first scratch deep probe failed with `AttributeError`: it used nonexistent `TokenMix.prompt_count`. Source inspection identified the existing `sample_size` field; only the scratch probe was corrected. The failure remains in published evidence, not PASS. All nine already-successful report/Watch samples were retained without rerun; the corrected six deep runs and four diagnostic runs exited zero. No repository runner/assertion or product code was changed.

No local full/quick product suite, package validator, version bump, ZIP, installed-service or browser probe was run: edits are development-only evidence/docs/state. This is the selected workflow's normal scope, not a requirement/test exception. Normal GitHub checks/blockers are read at delivery and reported in the PR. Architecture responsibilities/flows are unchanged; no diagram/module-contract update is needed. Normal/Watch CPU, physical I/O, total peak memory, real account latency, installed V2/whole-Web latency and monetary cost remain unknown.

### Historical findings and scope (not current baselines)

- [2026-11-05 milestone-40 samples/profile](../architecture/governance/verification/performance-40-20261105.json): NO_GAIN; repaired obsolete unsampled-running expectation. Historical results, not fresh PASS.
- [Milestone-20](../architecture/governance/verification/performance-20.json) and [older milestone-40](../architecture/governance/verification/performance-40.json) retain original semantics/failed attempts. FR 000534 restored bounded Normal; old deep-comparison timings are not equivalent gains.
- Older causal/cache/quota/context improvements remain in Git, not current ratios. Inspected detail tests retain 100/1,000/10,000-row totals, bounded pages and revision reuse; not executed here.

## Next investigations

Before changing CLI connection lifetime or adopting compact evidence, characterize concurrent report/Live owners, cache-consumer reuse, transaction failures and fresh revision/deletion behavior on equivalent inputs. Investigate warm allocation peaks with object/allocation evidence rather than assuming cache hits are cheaper in every resource. Whole-Web scheduling, real V2 hydration/bracket cost, browser interaction, assistive technology and native lifecycle need their own existing scoped evidence. No new FR, proposal implementation or cross-repository work was published; these limits do not release held work or declare pending recovery complete.

## Rejected hypotheses

Do not expand Normal to all history to satisfy obsolete assertions, cache running roots, skip revisions, cap full detail to Watch rows, rebuild prices on display ticks or add per-tab workers. Zero scalar revision calls are not zero bulk freshness work; fewer cache bytes are not measured physical I/O or lower cold peak memory. Existing CLI/Web mode differences are not a candidate speedup, and synthetic wall/CPU/Python-allocation samples are not production latency, billing or whole-process savings. Retain transaction isolation, rollback/close behavior and source authority; no speculative pooling/concurrency wrapper for an invented gain.
