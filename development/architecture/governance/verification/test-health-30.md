# Test Health — milestone 30

Source/checked revision: `ebacf2cde20a2ee1db2168569e00fa43c87f27bb`.
Assessment date: 2026-10-28. Outcome: retain current mechanisms; no product/test-runner refactor justified by inspected evidence.

## Scope and investigation

Installed `maintenance_evidence.py inventory --repo-root .` examined tracked and nonignored untracked files: 485 text/config entries (214 source/config, 111 documentation, 160 classified tests), excluding 61 binary/over-1-MiB entries. No exact-byte duplicate groups; neither that result nor file size proves semantic uniqueness. Full inventory remained in owned scratch; this report retains decision-relevant evidence without depending on it.

AST inspection of all top-level `development/tests/test_*.py` and `development/tools/run_tests.py` found 112 registered files, 108 Quick and four Full-only, no missing/unregistered files and 1,370 syntactic test methods. Eleven sibling-import statements still represent ten distinct importer/module edges, unchanged since milestone 25. Counts include source syntax, not executed coverage. Full-only owners remain session detail, foundation/package mutation, public Diagnostics and parity/performance. Runner: four isolated workers, Quick 25 s / Full 240 s per file; JSON retains failures, named skips and unknown passed counts for incomplete files. Profiles/patterns default to one worker.

Whole-repository sampling inspected source and corresponding tests, not only recent Web changes:

| Risk/owner | Inspected protection and burden decision |
| --- | --- |
| Source readiness: `src/sources/read_recovery.py` | `test_connectivity_reliability.py`: virtual deadline/attempt counts, exact waits, no repeated CLI wake or cache on failed startup, auth/schema failures not retried. Retain independent negative expectations. |
| Account generations and metadata: `src/accounts/refresh_policy.py`, transport boundary | `test_openai_account_switch.py`: isolated synthetic credential DB, byte-preserving reads, gated late response and old-generation removal; `test_claude_transport.py`: synthetic child, exactly initialize/get_usage, privacy allowlist, bounded timeout/reaping. No real login or paid call needed. |
| Valuation and display: `src/analysis/valuation.py`, `src/application/display.py` contract | `test_web_display.py`: independent Decimal/null/rounding goldens plus CLI parity and JS consumption. `test_web_accounts.py` and `fixtures/account_views.py`: known/zero/unknown/unlimited quotas and private canaries. Sharing expectations with production is not the sole oracle. |
| Cache: `src/cache/database.py` | `test_cache.py`: disposable rebuild, generation coexistence, WAL/busy timeout, bounded reader/writer and insert-only first-sighting concurrency. Isolated real SQLite tests retain risks mocks would miss. |
| Watch observations/retention | `src/watch/session_retention.py`, `test_watch_today_ccost.py`: current-day observations survive source deletion; incomplete refresh retains last complete value and atomically accepts correction. Responsibility-owned fixtures remain appropriate. |
| Sessions scope/paging | `test_session_list_pages.py`: 0/1/100/1,001 roots, independent ordering, <=50 hydration per page, total/CLI parity, archive/partial state and catalog drift/rebinding rejection. Internal `_analyzed` assertion protects acquisition work bounds, not just cosmetic shape. |
| Web authentication/control: `src/web/security.py`, HTTP/jobs | `test_web_runtime.py`: actual loopback requests, cookie/bootstrap/CSRF/wire denials, spawn-worker cleanup, 130-message burst and bounded drain. Synthetic raw-peer race still asserts response bytes and propagates unrelated errors. |
| Transport freshness/terminal: `src/web/assets/live.js` | `test_web_connection.py` plus `integration/web_connection.cjs`: deterministic clock, one watchdog/stream, retained stale values, source-versus-HTTP state, terminal/auth/identity stop. Distinct Python empty-read/terminal-close race assertion; separate real Chromium network/SSE proof. |
| Legacy pricing fixture coupling | `test_model_pricing_presentation.py` imports `pricing_markdown` from `test_step6_pricing_accounts.py`; inspected definition is synthetic pricing-table data. Known localized debt, not evidence that test removal or a generic fixture framework improves outcomes. |

The prior journal, milestone-25 report, recent completion reports and Git changes since `94de154a6c3f15a97d3a03980bc090505cd2f2e7` supplied bounded historical context. No private session transcripts/raw exports were loaded. `integration/live/` is reserved, not an implemented model suite. Installed workstation probes remain opt-in, not automatic audit requirements.

## Fresh available outcomes

Read-only API inspection sampled the eight latest Web Beta workflow runs: five success, three cancelled. Cancellation is not PASS or an established product regression; individual cancellation intent was not investigated. Paginated jobs and Checks annotations of latest main [run 40601136981](https://github.com/qstoffe/cost-guard/actions/runs/40601136981), source `e25cf3b63a5ffe73e20787a96c9c1ee38f356c1a`, establish:

| Hosted platform | Full registered suite | Regression phase seconds | Native step seconds | Browser phase seconds |
| --- | --- | ---: | ---: | ---: |
| Windows 2025 x64 | 112 files; 1,370 passed; 0 skipped/failures/errors | 107.20 | 10 | 9.38 |
| macOS 15 ARM64 | 112 files; 1,365 passed; 5 skipped; 0 failures/errors | 201.45 | 14 | 10.33 |
| macOS 15 Intel | 112 files; 1,365 passed; 5 skipped; 0 failures/errors | 214.00 | 14 | 10.50 |

Regression/browser durations come from structured phase annotations; native durations are coarse GitHub step timestamps. Regression includes Full plus validator, not per-file suite time. All three jobs' regression, native and rendered-browser steps succeeded. Both Mac skip lists identify the same five Windows-specific shell/discovery/paired-GUI-interpreter tests, not missing Node or silently skipped shared behavior. Windows suite annotation marks passed counts complete. The only intervening commit to this audit base changes architecture/journal/maintenance metadata, not product, tests or CI; this is historical verified CI evidence, not a new candidate run.

FR 000500's completion report records repaired malformed-request/lifecycle fixture assumptions and a CI browser expectation obsolete for its finite-report-only host. Current `ci_browser_web.py` now distinguishes STARTING/source pending and SOURCE UNAVAILABLE from HTTP connectivity; `web_connection.cjs` independently asserts the same distinction. This is a fixture assumption repair, not permission to treat a dead source as connected or weaken terminal/SSE assertions. The successful subsequent hosted run corroborates recovery. Earlier cancelled candidates are not invented failures.

Workflow ownership remains `.github/workflows/web-beta.yml` -> `development/tools/ci_web_beta.py`: public standard GitHub-hosted runners only, Python 3.11/Node 22, bounded regression/native/browser phases, sanitized summaries, no paid/self-hosted fallback. Path filters exclude this report/journal/state-only delivery. Native/browser evidence retains its explicit synthetic-entry and headless limitations. Physical clicks, default-browser behavior, accessibility, actual suspend/soak and consumer Finder/Gatekeeper acceptance remain NOT VERIFIED here.

## Decision, alternatives and delivery

Keep isolated file admission, bounded subprocesses and responsibility-owned fixtures. Four newly registered files since milestone 25 protect paging, model/account view consumption and connection freshness; their unique behavior does not justify merging them just to reduce counts. A monolithic discovery process would lose timeout/cleanup attribution; a universal DOM wrapper would conflate VM token-consumption with actual Chromium transport/rendering. No substantial avoidable orchestration or repeated current setup failure was demonstrated. Known ten-edge legacy fixture coupling and tighter Quick outer/VM child deadlines remain targeted follow-ups, not authority to loosen gates.

Before/after: unchanged 112 files, workers, deadlines, setup layers, risk mechanisms and gate fanout. No speedup measured; paid-cost/fanout and per-file durations unknown. No mechanism replaced, so no seeded-failure equivalence run is claimed or needed. Product tests, validators, live/browser/native probes, model calls and version/release work were NOT RUN for this development-only delivery. Source/AST inventory and existing remote evidence are assessment operations, not a product PASS claim for this candidate.

Consolidate current counts/provenance/causal lesson in `development/journal/test-health.md`; existing INDEX route suffices. Architecture: **no-update**, unchanged responsibilities/dependencies/flow. Deliver exact native test-health/30 maintenance state with ordinaryCount/completion watermark 30 and identity high watermark 520 unchanged; no FR moves or completed bundle additions. Both pending specifications remain byte-identical. PR link is recorded in the merge commit/native delivery receipt.

Follow-ups: obtain per-file timings before retuning bounds; move sibling-test fixture data into its owner when relevant behavior changes; keep physical/platform acceptance distinct. Checks also report an upload-artifact@v5 Node-runtime deprecation warning: no failed job or source-backed need for a speculative workflow change; deferred for a dedicated compatibility assessment, not published as a cross-repository suggestion.
