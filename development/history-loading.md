# Mode-aware history acquisition

## Scopes and correctness

`reports/history.py` declares range/root/limit requirements and owns the incremental source-backed Watch day scope. `reports/acquisition.py` coordinates shared source snapshots and exact revision/config/algorithm/pricing-gated analysis; it contains no billing or generation-specific interpretation. `sampling.py` retains both independent latest-100 samples, priceability, whole-tree activity and equal-time cutoff ties.

| Mode | Required history |
| --- | --- |
| Normal / All Models | Latest 100 eligible completed comparison prompts and separate latest 100 eligible Token Mix prompts, possibly inspecting more than 100. Availability only filters Normal's catalog. |
| Sessions N | Exactly the requested newest N roots by whole-tree activity; `all` is intentionally unbounded. |
| Session detail | Requested root/descendants. A displayed threshold-price warning independently requires the same bounded report sample. |
| Date/range | Every tree with potentially contributing activity since the range start; request/event boundaries establish attribution, not root creation dates. |
| `--token-mix` | Entire available history, never Watch/dashboard limits. |
| Watch dashboard | Startup baseline (20 roots or configured Earlier count), every active/uncertain liveness candidate regardless of age, then relevant changed/observed roots. Row caps never gate discovery/accounting. |
| Watch Today | Available completions since configured-local midnight across all roots, including archived roots and old parents with current child work; independent of dashboard/session scope. |

Catalog timestamps select candidates, not usage or completion truth. V1 catalogs include payload-free message/part row activity when the session clock is stale. A separate status-only liveness query checks latest messages/live tool flags; V1 has no native active registry, so old flags cannot be age-filtered. V2 uses the supported native active registry; unknown/legacy active state fails open. Neither liveness candidate selection nor native idle proves a prompt's end: canonical analysis does.

Native quota capacity, resets, Pace and account status need no month-history scan. Watch does not render historical account billing/attribution/month projection fields. Its visible daily total is separate. Context threshold multipliers are a genuine historical consumer: only an actual threshold requests the existing exact comparison sample (15-minute reuse), not month accounting. Other notices use catalog/provider metadata.

## Startup, refresh and recovery

Interactive startup skips the unrendered V1→V2 migration-gap probe, acquires catalog/revisions, required dashboard roots and Earlier representatives, then renders. Reports retain migration notices and may reuse a complete catalog acquired within two seconds during selection; Watch polls always enumerate authoritatively. Even daily revision reads wait until after the usable frame. `Today: Pending` hides incomplete values. The main thread enriches at most four daily roots per step; no new worker or concurrent analyzer exists. Account completions publish between steps and source polls retain their cadence. A slow source tree can still delay one timeout-bounded step.

Daily accounting reuses exact stable bundle revisions and only reanalyzes changed/uncacheable roots. It flattens the source-backed daily scope once per completed plan, not after every slice. The retained process tracker reconciles request/step identities and shared clone de-duplication, preserves observations after deletion, and filters exact completion timestamps. Midnight cancels old plans and clears the old day's observations; the new configured-local boundary uses timezone/DST rules, never a fixed 24-hour subtraction. Restart cannot reconstruct deleted, unobserved data; cache is not a ledger.

Changed unrelated old trees do not hydrate the dashboard. Native active/proven running roots refresh authoritatively even with unchanged cheap revisions. Catalog discovery/revision checks still detect new roots/children, removals and missed hints. Resync rereads observed roots plus relevant changes, not arbitrary historical snapshots. Scoped Watch still observes catalog metadata for its independent global Today metric. Source errors preserve their classifications and existing recovery; enrichment software faults remain fatal rather than becoming a misleading zero.

V2 builds one root/child index per complete catalog, memoizes tree revisions, and shares before/after catalogs across a required snapshot batch. Every returned tree must have equal authoritative revisions around its own message reads. Only unstable trees retry, with at most two fresh attempts after any reused-bracket miss. Events invalidate reusable catalog/index hints. No undocumented per-session revision endpoint or remote mutation is used. V1 batch revision queries bound SQLite parameters, not the number of roots, and remain payload-free.

Analysis cache compatibility includes model identities, display aliases, currencies and exact native rates/tiers plus config/algorithm/source revision. Retrieval times, document revision labels and presentation-only model metadata are not estimator semantics. Stable warm hits are not rewritten; running/incomplete bundles remain unpersisted.

## Numeric diagnostics and reproducible benchmarks

`domain/acquisition.py` exposes only fixed mode/generation labels, counts and timings. Source adapters count logical full catalog acquisitions, catalog pages, revision checks/calculations, message operations/pages and hydrated roots. Cache reads/hits/misses/writes, analytical prompts/requests and dashboard/day candidates are distinct. Timings separate catalog, revisions, liveness, cache reads, hydration, analysis, accounting, projection and rendering. Inclusive orchestration timings are not additive. First-usable/full-population readiness and actual first/full rendering are separate; provider quota acquisition remains independently measured by account diagnostics.

`diagnostic_watch.py` exercises staged startup, bounded enrichment, one unchanged poll and status projection, with in-memory renders; no titles, prompts, IDs, model names, credentials or payloads leave it. An existing source instance's counters are cumulative, so use before/after snapshots to isolate a diagnostic run. Benchmark Watch phases reset their numeric metrics and use a separate disposable cache from report sampling.

```text
python development/tools/benchmark_large_month.py --roots 1000 --prompts 20 --watch
python development/tools/benchmark_large_month.py --roots 1000 --children 2 --prompts 10 --today-roots 3 --running-roots 4 --watch
python development/tools/run_tests.py --pattern test_history_loading.py
python development/tools/run_tests.py --pattern test_source_history_loading.py
```

One workstation observation, 1,000 month roots × 20 prompts with no current-day usage: pre-change Watch cold startup hydrated 1,000 roots in 15.95 s; warm startup hydrated two in 4.15 s. Afterward staged cold readiness was 0.45 s with 20 hydrations (full daily completion 0.45 s), warm readiness 0.11 s with two, and unchanged refresh hydrated none. Normal reports still hydrated five roots to obtain 100 prompts and zero on warm reuse. These elapsed values are observations, not load-sensitive test thresholds or universal latency promises.

The fake current V2 service verifies 1,000 root revisions need one catalog/index (not 1,000 index constructions); four snapshot hydrations share one additional catalog with authoritative before/after equality. Pagination, transitional project lists, source parity, unstable-tree retry and live/reconnect tests remain deterministic. Catalog discovery and metadata/liveness proofs may still scale with total available history where the source lacks a trustworthy delta API; the optimization does not promise constant-time discovery or omit uncertain active roots.

A post-change read-only live V2 smoke (not a before/after comparison) observed 418 roots/427 sessions, 18 daily candidates and three running rows. First usable/full daily dashboard readiness was 3.97/4.53 s cold and 0.57/0.90 s warm. A real context-price warning legitimately needed a 51-root eligible comparison sample: cold work remained hydration/catalog/projection-I/O dominated, with only 56 ms of analytical processing. Warm analysis wrote no derived cache entries. This smoke used no account providers, so it proves neither provider freshness nor exhaustive manual accounting parity; deterministic fixtures cover the accounting boundaries.
