# Test Health — milestone 25

Source/checked revision: `94de154a6c3f15a97d3a03980bc090505cd2f2e7`
Assessment date: 2026-10-27. Outcome: retain current test mechanisms; no product or harness changes justified by this sample.

## Scope and inventory

Installed `maintenance_evidence.py inventory --repo-root .` examined Git-tracked and nonignored untracked text/config: 453 files (212 source/config, 98 documentation, 143 classified as tests), no exact-byte duplicate groups. It excluded 57 binary-or-over-1-MiB entries and runtime artifacts. These categories include fixtures and integration scripts; they are not executed test counts. Full local inventory was retained during investigation; this report preserves the decision-relevant sanitized results independently of disposable scratch.

AST inspection of all top-level `development/tests/test_*.py` and the explicit runner registry found 108 files: 104 Quick and four Full-only, with neither missing nor unregistered files. There are 1,358 syntactic test methods, not an executed/discovered assertion count. Eleven sibling-test import statements represent ten distinct importer/module edges (runtime_errors imports watch_lifecycle twice). This remains localized legacy fixture coupling, not eleven independent regressions or evidence of measured growth against the earlier ten-edge audit.

Ownership: `development/tools/run_tests.py` isolates files in subprocesses, four suite workers, Quick 25-second / Full 240-second file bounds. Foundation/package mutation, Diagnostics, parity/performance and session-detail work remain Full-only. Node VM fixtures live under `development/tests/integration/`; `integration/live/` is reserved, not an implemented model test suite. `.github/workflows/web-beta.yml` owns public-hosted Python 3.11/Node 22 Windows x64 and macOS ARM64/Intel regression, native and Chromium phases. Its path filter excludes this documentation/state delivery. No new mandatory gate is introduced.

## Source-backed risk sample

Paths below are repository-relative. This is representative whole-repository sampling, not exhaustive coverage proof.

| Source owner | Test owner / evidence inspected | Unique risk retained |
| --- | --- | --- |
| `src/sources/read_recovery.py` | `development/tests/test_connectivity_reliability.py` | Virtual clock bounds retries/deadline; asserts exact waits, no cache initialization and no repeated CLI wake |
| `src/accounts/claude_transport.py` | `development/tests/test_claude_transport.py` | Real isolated synthetic child/control protocol, exactly initialize/get_usage, no user/model prompt or persistence, privacy allowlist, auth/shape/method distinction, timeout and owned cleanup |
| `src/analysis/valuation.py`, application projections | `development/tests/test_application_reports.py` | Decimal/null and billing/reference separation; parity is complementary to independent expected values, not their replacement |
| Cache repository/database | `development/tests/test_cache.py` | Disposable rebuild, coexisting generations, WAL, concurrent first-sighting/writes with bounded joins |
| `src/watch/today_ccost.py` | `development/tests/test_watch_today_ccost.py` | Deleted rows do not erase current-day observation; corrections retain last complete publication; responsibility-owned synthetic inputs |
| `src/application/display.py` | `development/tests/test_web_display.py` | Independent rounding/raw-value goldens, unknown versus zero, tiers/precision, plus CLI parity and separate JS token-consumption check |
| `src/web/security.py`, HTTP/job owners | `development/tests/test_web_runtime.py` | One-use bootstrap, cookie scope, origin/CSRF denial, wire limits, bounded queue/control progress, owned cancellation |
| Runtime error boundary | `development/tests/test_runtime_errors.py` | Private exception canaries, fatal versus recoverable faults, thread hooks and reporter-failure behavior; sibling-fixture debt does not make these redundant |

## Available outcomes and causal assessment

Read-only GitHub API inspection of the eight latest workflow runs and all jobs of [run 40421018674](https://github.com/qstoffe/cost-guard/actions/runs/40421018674), source `be6c8511b26a71030628fe0d7e8202961ad2582e`, verified three successful jobs. Full-suite-plus-validator step intervals were Windows 98 s, macOS ARM64 192 s, Intel 218 s; native steps 10/11/13 s and rendered-browser steps 11/11/11 s respectively. These are coarse GitHub step timestamps including orchestration, not per-file timings, controlled comparisons or measured speedups. Two earlier cancelled candidates in the eight-run sample are not failures or PASS; workflow concurrency cancels superseded runs, but individual cancellation intent was not investigated.

At the initial query, latest-main [run 40422673710](https://github.com/qstoffe/cost-guard/actions/runs/40422673710) at this audit's source was in progress, not PASS. The prior journal records known, already repaired fixture inflation, native setup/timing, platform path and socket-close failures; source inspection does not establish a fresh recurrence. No raw logs or private historical sessions were loaded. No per-file current-run timings, provider cost or historical paid fanout were measured. Prior green revisions do not prove current product/desktop acceptance.

## Decision and delivery

Keep explicit admission, isolated files and responsibility-owned fixtures. Replacing them with monolithic discovery would lose file cleanup/deadline attribution without measured benefit. Merging CLI parity, fixed expected-value tests, VM consumption and actual Chromium smoke would conflate distinct risks. No substantial avoidable cross-file harness complexity was demonstrated; no wrapper, timeout increase, coverage deletion or speculative refactor is warranted.

Before/after mechanisms, worker count, deadlines, test files and gate fanout are unchanged; performance gain is **not measured**, not zero or claimed. Product tests, validators, live probes/model calls, mutation canaries and release/version work were deliberately not run for this development-only audit. No mechanism replacement therefore needs seeded-failure equivalence proof. Native Git/selection/retention verification remains required.

Journal: consolidate current counts, provenance and limits in `development/journal/test-health.md`; existing INDEX route suffices. Architecture: **no-update**; no responsibility, dependency, gate trigger or flow changes. Stage the native exact milestone-25 maintenance nextState and unchanged identity high watermark; no ordinary FR is completed by this audit.

Remaining investigations: obtain per-file failure/duration evidence before retuning VM/Quick bounds; migrate legacy sibling fixtures when their owning behavior actually changes; retain separate consumer desktop/Finder/Gatekeeper/accessibility/soak proof. Pending ordinary FRs remain pending and byte-identical.
