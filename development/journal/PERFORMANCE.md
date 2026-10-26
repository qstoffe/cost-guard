# Performance investigations

Source revision: 07c14d21fcbc32ab5b194a5afc85c8cb4ae25cbd
Checked revision: 07c14d21fcbc32ab5b194a5afc85c8cb4ae25cbd
Last checked: 2026-10-26
Status: current

## Summary

Milestone-20 audit: **NO_GAIN / no runtime change**. Nine fresh-process synthetic benchmark runs confirm bounded sampling and stable reuse in the measured scenarios; they do not establish production latency, complete billing parity or a before/after improvement. Current measurements and limitations are below. Older findings retain their original scope.

FR 000360 scale work supersedes the old "quadratic but not dominant" causal-scan conclusion for long session detail. `src/analysis/prompt_index.py` now indexes assistant parents, synthetic prompt windows and provider-filtered prior entries once per snapshot. Strict timestamp windows and source ordering are preserved. Shared detail acquisition reuses unchanged analysis/valuation and advances only report execution time for identical running evidence. The older measurements below retain their original revisions/scopes, not current performance guarantees.

The authoritative baseline was the locally delivered v80.33 filesystem, including all earlier uncommitted work, copied before editing. No Git restore, dependency, cache-generation change or remote operation was used. v80.32/v80.33 ownership splits, growth ratchets and the code map remain; this pass targets execution speed, Watch robustness, Diagnostics relevance and test cost without a second analysis path.

## Evidence

### Milestone-20 performance audit (2026-10-26)

Whole-repository metadata inventory: 412 inventoried files (198 source/config,
136 tests, 78 documentation), 26 binary/over-1-MiB exclusions, no exact-byte
duplicate groups. Inventory includes tracked/nonignored files, not Git internals,
runtime credentials or another checkout. Large owners include Watch coordinator,
analysis context/causal, report service and both source generations. Metadata is
not proof of semantic duplication or dead code.

Representative source investigation followed the architecture routes through
report sampling/acquisition, analysis prompt indexes/cache, Watch live cadence,
Web composition, V2 transport and account refresh policy. Existing history-loading,
step9 parity/performance and Web-detail tests were read for behavior contracts,
not executed or claimed as new passes. Normal reports require independent eligible
100-prompt samples; the benchmark does not exhaust its nominal month. Running roots
must bypass stable caches. One shared live acquisition owner and bounded refresh
policy remain preferable to per-tab workers, skipped revision checks or parallel
hydration without live evidence.

Reproduction: Windows 11 build 26300, AMD64, CPython 3.14.7; base revision above.
Run each command three times in a new process, sequentially, without profiling:

```text
py -3 development/tools/benchmark_large_month.py --roots 100 --prompts 50 --watch
py -3 development/tools/benchmark_large_month.py --roots 20 --prompts 50 --children 2 --today-roots 5 --running-roots 2 --watch
py -3 development/tools/benchmark_large_month.py --roots 1000 --prompts 20 --watch
```

Each run constructs deterministic input and fresh temporary report/Watch SQLite
caches; warm phases reuse only their own run's cache. UTC and fixed synthetic
pricing/time come from the runner. OS/filesystem cache was not flushed; background
workstation load was uncontrolled. Wall times below are medians in seconds, not
thresholds, total process duration or cross-scenario scaling ratios. The 1,000-root
case has fewer prompts per hydrated root than the 100-root case.

| Scenario (nominal prompts) | Report cold / warm | Watch usable cold / warm | Watch full cold / warm | Refresh cold / warm |
| --- | --- | --- | --- | --- |
| 100 roots x 50 (5,000) | .0405 / .0204 | .5451 / .1522 | .5461 / .1526 | .0013 / .0006 |
| 20 roots + 40 children x 50 (3,000), 5 today / 2 running | .1178 / .0463 | .6382 / .2157 | .6832 / .2534 | .0225 / .0274 |
| 1,000 roots x 20 (20,000) | .0761 / .0244 | .4068 / .1054 | .4083 / .1070 | .0034 / .0031 |

All nine runner exits were successful. Every warm report had zero additional
hydrations and no more than O(root) revision checks; both sample counts were 100.
Idle Watch startup hydrated 20 roots cold / 2 warm, with zero refresh hydrations.
Active Watch startup hydrated 20 cold / 4 warm, with 2 refresh hydrations in both
phases. Today began Pending. Cold and warm are different cache states, not baseline
and candidate implementations; no equivalence digest or improvement is asserted.

A separate instrumented 1,000-root run (`py -3 -m cProfile -o <owned scratch file>`
followed by the third command's script/arguments) reported 1,303,120 calls,
1.674 seconds profiler total. `CacheDatabase.connect` had 214 context-manager
invocations and .499 seconds cumulative; fixture construction itself took .734
seconds. Inclusive profile timings overlap and must not be added or compared with
unprofiled wall samples. Cache I/O is a candidate, not proven production waste:
short-lived connections explicitly commit/rollback/close and configure busy timeout,
WAL-related behavior and thread ownership. Connection pooling or transaction
batching requires concurrent owner/error/recovery characterization first. No extra
layer or speculative optimization was retained.

[Sanitized raw benchmark evidence](../architecture/governance/verification/performance-20.json)
preserves all nine samples, numeric acquisition counters, setup and inventory
summary. No provider/model calls or real-installation probes were made. CPU time,
peak memory, production service/network latency and monetary cost were not measured.
No product tests, validator, version bump, release or ZIP: this delivery changes
only development knowledge/evidence and the exact native maintenance transaction.
Architecture boundaries are unchanged, so no diagram/module-contract update.

Remaining investigation: characterize SQLite lifecycle under concurrent report/live
owners and actual installed workload before batching or pooling. Long-detail,
source hydration, browser rendering and native platform observations below remain
separate scopes; this audit neither renews their historical PASS claims nor closes
their outstanding verification limits.

### Earlier long-session evidence

On Windows/Python 3.14, `py -3 development/tools/run_tests.py --pattern test_web_session_detail.py --file-timeout 300` initially took 191.4 seconds; its scale test passed but a fixture-revision collision failed parity. Profiling the scale method (`py -3 -m cProfile -s cumulative -m unittest development.tests.test_web_session_detail.SessionDetailTests.test_scale_all_rows_totals_bounded_pages_and_unchanged_work`) showed 724M calls/292.5 seconds instrumented: causal record construction, prompt-parent windows and repeated root entry scans dominated. After indexing, the same scale workload plus repaired parity/retention tests took 5.9 seconds uninstrumented. Expanded HTTP/asset/provenance tests later took 7–8 seconds. These are single-run workload observations, not universal timing guarantees or an isolated microbenchmark; profile overhead and later fixture additions prevent a precise speedup ratio.

Reproduce with `development/tests/test_web_session_detail.py` against the checked source. It constructs 100/1,000/10,000-prompt histories, appends one prompt, checks first/middle/latest identities/full totals/bounded payloads and asserts timer-only/stable-revision work counters. A running-evidence test rejects calls to full analysis/projection on unchanged normalized evidence. Strict same-timestamp window equivalence is checked against the existing public algorithm. Full (104 files) and a real read-only V2 `development/tests/integration/probe_web_live.py --detail` passed; the latter observed one acquisition/account owner, two streams, complete pages and consistent freeze. No UI, model or shared-service stop.

### Historical hot spots and fixes

| Hot spot (live V2 data, 60 roots) | Owner and fix | Effect |
| --- | --- | --- |
| ~26 ms per V2 request opening a fresh connection | `opencode_v2_transport.py`: bounded pool of keep-alive loopback connections, one retry on a service-closed idle socket | ~0.3 ms overhead per request |
| 0.5M regex calls resolving model identities | `PricingCatalog` memoizes identity/closest resolution per immutable instance | resolution leaves the profile |
| Two full catalog listings per snapshot | `opencode_v2.py` reuses a <=2 s old complete catalog as the before-bracket; mismatch retries fresh | consistency proof unchanged |
| Watch startup hydrating 20 mostly idle roots | `watch_root_latest_prompt_ms`: only stable cached analysis (never running work) with nothing since start is skipped unless chosen as `[Earlier]` | 6.2 s → 0.65 s |
| Resync hydrating all history roots | `_changed_roots`: hydrated + changed + hinted roots | 13 s → 1.4 s |
| Sequential availability/Claude helper waits | `AvailabilityPrefetch`; Claude helper stopped on a non-daemon cleanup thread | report 2.1 s → 0.65 s |
| Watch discovery network reads on the main thread | `WatchModelDiscovery` check worker; main thread applies results | no poll stalls |

Parallel message hydration was measured and rejected: the local service serializes responses (20 roots: 736 ms sequential vs 597 ms with 8 threads), not worth the complexity.

Post-v80.36 behavior-neutral cleanup (median of 5, captured live snapshots analyzed offline):

| Hot spot | Owner and fix | Effect |
| --- | --- | --- |
| Trace entries, sorted prompt events and active compaction re-derived per prompt (quadratic per root) | `causal.py`: one `_RootTimeline` per `build_prompt_records` pass | 74 live roots 252 → 92 ms; largest root 60 → 12 ms; synthetic 500-prompt root 1.72 → 0.23 s |
| Cache store deep-converted nested entries with `asdict` only to discard them | `analysis/cache.py`: flat field copies; nested values serialized once | 74 live bundles 90 → 31 ms; byte-identical JSON |

Analysis records (2,528 across fixtures/live variants), cache JSON and Watch rows/markers over replayed live snapshots hashed identically before and after. Watch's per-second status path (≈2 ms for 20 hydrated 200-prompt roots) was measured and left unchanged.

Post-v80.46 cleanup (captured live month, 6,279 requests, min of 40 runs, three alternating rounds): a changed Watch poll spent most of its ~65–90 ms rebuilding local month/today CCost. `billing_request_fingerprint` packs its six IEEE-754 values in one `struct` call (14–16 → 10–12 ms) and `comparison_cost` formats each UTC day once (37–39 → 22–25 ms); `accounts_quota_projection` 67–70 → 43–47 ms. Fingerprints, de-duplicated entries, comparison costs, the quota projection and epoch/midnight edge cases hashed identically before and after. Decimal valuation itself is unchanged.

Post-v80.53 cleanup (synthetic active-context root, median of 5): `prompt_effort` rescanned every session message per prompt, and `PromptRowProjector` built `ContextEpochs`/`ContextHistory` twice. One `prompt_replies` index and one shared epochs instance cut `build_prompt_block` 0.76 → 0.26 s at 2,000 prompts (1,000: 0.25 → 0.12 s; 250: 39 → 33 ms) with identical projection hashes.

### Historical behavioral evidence

Baseline (v80.33 copy) and current trees rendered the same live data against one shared cache: Watch initial frame and token mix, and normal, all-models, sessions, session-detail and date reports were byte-identical. New regressions cover pooled transport reuse/retry/bounded idle sockets, overlapping discovery checks, the stuck Claude helper not delaying answers, Watch resync scope, and the numbers-only Diagnostics Watch smoke.

### Historical tests and tools

Full runs concurrently with its slowest files first (151 s → 32 s). Validator-negative checks call their owning check on a package copy instead of the whole validator subprocess; the dedicated release-builder module was retired with local archive generation in v80.51. The validator parses each file once per run. Fake V2 services, the V1 database and package copies are fixtures; test-to-test edges fell from 43 to 33. Fake services now drop keep-alive sockets on stop, matching a real process exit.

Post-v80.40 cleanup: report-service, availability/rendering, quota-rendering, account and config-package setup moved into responsibility-owned fixtures, so tests no longer borrow `CompactReportTests.service` as an unbound method; test-to-test edges fell from 33 to 18, and post-v80.46 snapshot/threshold/warning fixtures to 10. Measured, unchanged: 80 live roots (largest 34 prompt events/487 messages) analyze in 54 ms total, 9.7 ms worst root; Watch tool observation runs only for the latest running prompt (~0.3 ms average per call). Per-prompt causal scans are quadratic only on synthetic 500+-prompt roots (500: 0.22 s, 1,000: 0.88 s), far beyond observed live sizes.

## Next investigations

The former repeated causal-scan hot spot is resolved for root prompts; child/task traversal and source hydration remain workload-sensitive and were not made incremental here. Measure real long-history acquisition under account load before adding concurrency. Earlier Watch quota projection duplication (~0.15 s in its historical live sample) still needs proof that discovery cannot change comparison pricing between projections before removal. Real browser resize/scroll/selection and assistive-technology checks remain separate from VM results.

## Rejected hypotheses

Do not solve long detail by imposing Watch's row cap, rebuilding all prices on display ticks or introducing per-tab account/Watch workers. The scale profile identified shared causal lookups, not a browser billing problem. Preserve the historically rejected parallel hydration experiment above: its measured local-service benefit did not justify complexity. No durable history ledger or source mutation is needed for process-local observed retention.

### Live-proof limits

Live checks were read-only: headless report/Watch probes and Diagnostics against the shared V2 service, never stopping it. No interactive terminal/UI, native macOS, sleep/wake or Ctrl+C session was exercised.
