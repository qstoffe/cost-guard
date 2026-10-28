# Test Health — milestone 35

Source/checked revision: `82f555e2ef9d3c0ee3586f067694f101d39d511b`.
Assessment date: 2026-10-28. Outcome: retain current test mechanisms; no source-backed harness rewrite justified.

## Scope and reproducibility

Installed `maintenance_evidence.py inventory --repo-root .` inspected tracked and nonignored untracked files before this report: 511 text/config entries (214 source/config, 131 documentation, 166 classified tests), 64 binary/over-1-MiB exclusions, zero exact-byte duplicate groups. Classification includes evidence JSON, not only executable tests. Exact-byte uniqueness does not establish semantic uniqueness. Full JSON was retained in current-owned scratch during assessment; this durable report does not depend on it.

AST inspection of every top-level `development/tests/test_*.py` and the literal registrations in `development/tools/run_tests.py` found 113 files: 109 Quick, four Full-only, no unregistered or nonexistent entries, 1,380 syntactic test methods. Eleven sibling-import statements represent ten distinct importer/module edges, unchanged from milestone 30. These are source counts, not executed coverage percentages. Reproduce by parsing `QUICK_PATTERNS`/`FULL_ONLY_PATTERNS`, comparing their union with the file inventory and counting `test_` function definitions and sibling-test `ImportFrom` nodes.

Read the milestone-30 assessment/journal, the intervening Git history and changed tests/fixtures, current runner/workflow, and representative source/test pairs across sources, cache, accounts, Watch, display and Web security. No private session transcripts, foreign scratch, credentials or raw application exports were accessed. Repository `AGENTS.md` and the legacy `development/MAINTAINER.md` referenced by the ordinary checkout do not exist at this remote revision; the actual development README/architecture route current ownership. No substitute legacy gate was invented.

## Critical risks, ownership and burden

Paths below are repository-relative. The table describes inspected contracts, not a claim that all tests were executed here.

| Risk | Inspected source and protection | Decision |
| --- | --- | --- |
| Startup retries must not wake CLI repeatedly or retry auth/schema failures | `src/sources/read_recovery.py`; `development/tests/test_connectivity_reliability.py`: virtual deadlines, exact attempts/waits, cache/CLI forbidden-call assertions | Keep deterministic failure/recovery cases; no model or actual installation needed. |
| Concurrent disposable cache remains rebuildable | `src/cache/database.py`; `development/tests/test_cache.py`: generations, WAL/busy timeout, bounded concurrent readers/writers and insert-only first sightings | Real temporary SQLite covers risks mocks would miss. |
| Account replacement must not resurrect stale credentials/quotas | `development/tests/test_openai_account_switch.py`: synthetic auth/DB bytes, acquisition generation and gated late response | Keep responsibility-owned account fixtures; no real OAuth needed. |
| Today totals survive deletion and incomplete refresh | `development/tests/test_watch_today_ccost.py`: independent Decimal reference, retained publication, correction and day rollover | Distinct temporal invariants, not redundant renderer snapshots. |
| Web/CLI parity must not become a shared mistaken oracle | `src/application/display.py`; `development/tests/test_web_remaining.py`, `fixtures/remaining_views.py` | Shared CLI parity is supplemented by explicit clock, rounded warning and unchanged raw Decimal expectations. Node checks actual JS consumption; browser smoke remains distinct. |
| Browser authorization and process/control isolation | `src/web/security.py`; `development/tests/test_web_runtime.py` | Retain expiring one-use bootstrap, checkout-scoped cookie/CSRF denial, bounded wire/control and owned-worker tests. Do not replace actual HTTP/worker evidence with DOM mocks. |
| Launcher syntax, discovery and actual console/native ownership | `src/windows_launcher.ps1`, `src/web/windows_launch.ps1`; `test_windows_launcher.py`, changed Watch launcher assertions and native CI adapter/probe | Some syntax assertions overlap across older tests. They are refactor-sensitive localized debt, not evidence to remove the only platform/process proof. |
| Local IDE cache exclusion must not weaken explicit-package validation | `development/tests/test_foundation.py`, `fixtures/package_copy.py`, `development/tools/validate_package.py` diff | New negatives retain explicit root `.vs` rejection, nested `.vs` validation and unrelated oversized/malformed paths. Do not suppress these after an unrelated README-cap failure. |

Runner ownership is unchanged: four isolated file workers; Quick 25 s / Full 240 s per file; selected profile/pattern defaults to one worker. Full-only owners cover session-detail scale, package mutations, public Diagnostics and parity/performance. JSON exports preserve named skips and unknown passed counts for failed files. The new Remaining file is explicitly admitted, not silently discovered. Reserved `integration/live/` contains no implemented model suite. Installed probes and physical UI acceptance remain conditional, not audit prerequisites.

`.github/workflows/web-beta.yml` owns the three public standard hosted runners, Python 3.11/Node 22, full regression/validator, native adapters and separate real Chromium smoke. Its path filters exclude this report/journal/state delivery. No paid/self-hosted fallback, broad new gate or automatic self-review was introduced.

## Fresh remote outcomes and causal classification

Read-only GitHub API inspection sampled five latest workflow runs: one successful, two cancelled, one failed and one queued (no conclusion at observation). Cancellation/queue are not PASS or demonstrated product failures. Paginated job evidence and Checks annotations were retrieved through the installed Git/GCM transport; no raw-log access workaround was used.

- [Run 40735661619](https://github.com/qstoffe/cost-guard/actions/runs/40735661619), source `227d2ad8ce3be3e8dd39d0f1a04e0a30f724e0ae`: Windows regression failed; both Mac jobs succeeded. Windows annotation explicitly names `README.md: 32771 > 32768 bytes`, three failures in `test_foundation.py`, zero errors, and incomplete known-passed counts. Its native/browser phases passed independently and do not rescue failed regression. The `.vs` test was one victim of the shared invalid package baseline, not evidence that the exclusion fixture itself was wrong.
- Current README source normalizes to 32,142 LF bytes / 32,533 CRLF bytes, below the unchanged 32,768-byte cap. Inspection of the intervening README diff confirms shortening alongside launcher renaming, not a raised budget. This is a local byte calculation, not a validator run.
- [Run 40737349402](https://github.com/qstoffe/cost-guard/actions/runs/40737349402), candidate `f8edc0c9a4db7a7132f13cce93955df746f6aacf`: all three hosted regression/native/browser jobs succeeded. Windows Checks reports 113 files, 1,380 tests passed, zero skipped/failures/errors, complete passed count; regression including validator 131.17 s. Coarse job-step intervals for regression/native/browser were Windows 133/12/13 s, ARM64 Mac 200/10/9 s and Intel Mac 249/15/16 s. These intervals include orchestration and are not per-file timings or a controlled comparison.
- [Run 40738339004](https://github.com/qstoffe/cost-guard/actions/runs/40738339004) targets this audit's exact main base; API status was queued with no conclusion. No PASS is claimed for it. Successful prior candidate evidence remains revision-specific, not a new audit-candidate test run.

Current source plus subsequent successful hosted evidence supports classifying the observed cap failure as repaired baseline/checkout-format drift, not a current `.vs` product regression or reason to weaken package negatives. Distinct attempts were inspected as separate revision evidence, not summed as one successful logical test. The Node upload-artifact deprecation warning remains a warning, not an auth/test failure.

## Alternatives, before/after and delivery

Keep isolated admission, responsibility-owned fixtures and bounded orchestration. Monolithic discovery would lose per-file timeout/cleanup attribution; a generic browser framework would conflate VM projection contracts and real network/native behavior. New Remaining tests protect actual display/raw-value/JS parity; deleting them to restore the previous count loses a unique risk. No repeated current setup failure or substantial avoidable harness coordination was established. Historical static launcher shape overlap and ten sibling-import edges remain targeted debt; move data to its owner when a relevant refactor justifies it rather than add compatibility layers now.

Before/after mechanisms, worker/deadline counts, registrations, setup layers and gate fanout are unchanged by this audit. No speedup measured; per-file durations and paid-cost/fanout remain unknown. No mechanism replaced, so no seeded-failure equivalence run is claimed. Product tests, validator, live/browser/native probes, model calls and version/release work were **NOT RUN** for this development-only delivery. Existing CI is supporting historical evidence, not invented candidate PASS.

Journal update consolidates current inventory and this causal classification in `development/journal/test-health.md`; its existing INDEX route suffices. Architecture: **no-update**, unchanged responsibilities/dependencies/flow. Exact native `test-health/35` maintenance transaction is delivered with ordinary/completion count 35 and identity high watermark 530 unchanged. No FR is invented or moved; all seven pending specifications and 35 completed bundles remain intact. PR/merge identities are retained by Git/native delivery.

Remaining work: get per-file timings before deadline tuning; address localized fixture/syntax coupling when its owner changes; keep physical console input, default-browser, accessibility, Finder/Gatekeeper and soak/suspend acceptance distinct from hosted synthetic/headless evidence. No new suggestion was published; no unimplemented current defect was established by this audit.
