# Architecture assessment — milestone 20

Source revision: 033cf10b4b787cc446eb12b6763de7c24393bef2
Checked revision: 033cf10b4b787cc446eb12b6763de7c24393bef2
Last checked: 2026-10-26
Status: current

## Summary

Whole-repository audit of coordination and local cohesion. **Runtime no-change:** sampled source shows distinct owners for host shutdown, finite reports, live acquisition, observed history and analysis. No demonstrated defect justifies combining those lifetimes.

Retire milestone-10's stale hypotheses: Web is implemented; the event pump has a bounded 1,024-item queue and overflow resync. Clarify existing host/report-worker/detail ownership in the overview. No runtime contract or gate changes; this is navigation correction, not runtime simplification.

Only development docs/native state change. Product suites, validator, version/release work, Diagnostics, UI, real-installation probes and model calls were skipped. Existing assertions characterize behavior statically, not as PASS receipts. Native delivery safety remains separate.

## Evidence

Reproduce at the source revision with installed `shared-repo/scripts/maintenance_evidence.py inventory --repo-root .` and `python development/tools/code_inventory.py --json`: read-only inventories, not product checks. Full JSON was retained in owned scratch; durable results/routes below survive cleanup.

Inventory: 412 text files (198 source/config, 136 test-related, 78 documentation), 26 binary/over-1-MiB exclusions, zero exact duplicates; Git/ignored runtime data excluded. AST: 171 runtime modules / 26,496 lines; 13 tools / 2,646 lines; 128 test-tree modules / 27,506 lines, including 17 fixtures / 1,388 lines counted once. All runtime purpose/size/import records inspected. Counts do not prove dead code, semantic duplication, coverage or cycles.

### Level 1: normal, failure and recovery routes

| Workflow | Observed owners and transitions | Simpler target considered / decision |
| --- | --- | --- |
| CLI report / Watch startup | `src/bootstrap.py:main` parses/validates before integration/cache work, composes ReportService, then dispatches reports or coordinator initialization/run. `src/reports/service.py:build` closes account work in finally. CLI retains direct report/Watch dispatch. | Routing CLI through HTTP or a Web process would add a lifecycle, not remove one. Keep direct composition and shared report semantics. |
| Web finite reports | `src/web/http.py` validates requests; `jobs.py:ReportJobs` admits four jobs/one process, retains sixteen results and drains at most 64 progress messages/turn. `run_report` creates an isolated ReportApplication; application/service.py rejects live/reused services. Deadline/cancellation closes only owned work; `run_owned_report` monitors exact parent loss. | Sharing live ReportService would couple cancellation/deep scans to acquisition. Keep process isolation; sentinel monitoring is not another analysis owner. |
| Web Live / outage | `src/web/host.py` owns HTTP, jobs and one `src/application/live.py` thread. It ticks `src/watch/acquisition.py:LiveAcquisition` through coordinator acquire_cycle. Retry retains frame/same selection and stops the pump; schema failure publishes failed; software fault stops host. | Per-tab acquisition/browser calculations multiply owners. Keep one live owner; CLI blocking waits and Web tick deadlines share initialize/poll/enrich, not scheduling. |
| Detail / retention / paging | `src/application/session_detail.py` fairly selects one due tree, acquires outside the lock on the live thread and returns detached 50-row pages. `src/reports/session_history.py` merges canonical evidence outside cache and freezes omitted rows' time/lifecycle. Snapshot freezes; Live refreshes. | Per-tab services/ledgers duplicate acquisition or confuse omissions with source truth. Sixteen trees/thirty-two handles bound admission, **not history bytes**. |
| Source consistency | V1 `load_session_snapshot` pins a SQLite read transaction. V2 `opencode_v2_snapshot.py:load_snapshots` brackets messages with authoritative catalog revisions and retries only unstable trees. Events remain hints. | Collapsing wire normalization, consistency and report policy would leak generation details into analysis. Keep adapter-local consistency and canonical domain. |
| Accounts / pricing / valuation | Account acquisition owns generation/deadline-pinned attempts; refresh_loop owns account-only scheduling/mailbox. Price catalog and independent metadata-health refresh stay separate. Analysis core/period index value canonical requests; quota observations never become billing/history. | A global source/quota/price scheduler or shared durable usage ledger would conflate validity windows and failure policies. Existing named owners are simpler than such an umbrella coordinator. |
| Shutdown / restart / security | Host signals stop then closes owned jobs/live/socket; GUI stays main-thread. `web/lifecycle.py` serializes restart and revalidates process identity. HTTP separates cookie/CSRF from private control; source guard stops, never reloads. | Keep launch transitions separate from host shutdown. No browser-disconnect shutdown/second manager; OpenCode and foreign processes are never targets. |

Characterization read under `development/tests/`: `test_web_live.py` outage/schema/overflow/fault assertions; `test_web_lifecycle.py` reused-PID refusal/parent-loss cleanup; `test_web_runtime.py` Host/Origin/CSRF denial; `test_web_session_detail.py` omission/outage/reconnect totals and frozen retained lifecycle; `test_account_acquisition.py` late-result rejection; `test_source_history_loading.py` changed-tree-only retries; `test_context_history_projection.py` missing-telemetry/reset continuity; `test_cache.py` independent generations. Inspected assertions, not execution receipts.

### Level 2: whole-repository cohesion

Source samples span every major area; AST records supplement them. This is not exhaustive line-by-line verification.

| Area / source candidates | Local assessment and no-change rationale |
| --- | --- |
| Entry/config/domain: `src/bootstrap.py`, `src/config.py:load_configuration`, `src/domain/session_tree.py` | Startup validates shipped defaults independently; topology separates best-effort metadata mapping from valid detail targets. No justified generic startup/topology abstraction. |
| Source adapters: `src/sources/opencode_v1.py`, `opencode_v2_snapshot.py`, `src/watch/observers.py` | Different storage snapshots share canonical results, not storage mechanics. Pump has bounded queue/overflow marker; dropping hints forces authoritative resync. Long V2 wire translation remains a hotspot, not evidence of duplicate valuation. |
| Accounts: `src/accounts/acquisition.py:poll/close`, `refresh_loop.py:close`, `simple_http_mapping.py` | Generation/deadline handling belongs to acquisition; bounded declarative mapping rejects unsupported/deep schemas and keeps billing separate from quotas. No executable user expressions or need for universal mapping helpers. |
| Pricing: `src/pricing/github_copilot.py:get_catalog`, `catalog.py:estimate`, metadata/import inventory | Pricing refresh and release-date health have different evidence/backoff. Monetary fallback is explicitly not CCost. Keep semantic catalog separate from concrete document parsing; fresh upstream support is not established here. |
| Analysis: `src/analysis/core.py`, `causal.py:build_prompt_records`, `context.py`, `period_ccost.py` | Timeline/index reuse serves canonical attribution and context epochs; historical completion and current continuation eligibility differ intentionally. Prefix-sum period valuation shares unique usage. No observed duplicate orchestration to replace; long context/causal routines remain characterization candidates, not line-count refactors. |
| Cache: `src/cache/database.py:connect`, repository/import inventory | Disposable generation-named WAL state closes/commits/rolls back per connection. It is not SessionHistory's retained evidence owner. Merging those would weaken source authority. |
| Reports: `src/reports/service.py:build`, `acquisition.py`, `session_history.py` | Service dispatch, revision-keyed hydration and process-local retained detail have coherent responsibilities. `SessionHistory` deliberately bypasses derived cache for merged observations. No extra report framework or cosmetic split justified. |
| Watch: coordinator acquire_cycle/recovery/close, `acquisition.py`, `observers.py` | CLI and Web share acquisition operations, not terminal waiting. Tick deadlines vs blocking terminal waits explain two adapters; retained run/Today/detail scopes differ. No second billing implementation demonstrated. |
| Application: `src/application/service.py`, `live.py`, `session_detail.py` | Isolated finite services, one live worker and shared detail admission have distinct lifetimes. Projection boundary excludes raw integration payloads; no Web import needed. |
| Web/security/lifecycle/assets: `src/web/host.py`, `http.py`, `jobs.py`, `events.py`, `security.py`, `lifecycle.py`, `assets/live.js` | Fixed routing/admission, process work, publications/replay and launcher identity each have a specific owner. Client ordering/gap resync consumes full state, never calculates totals or restarts host. Separate modules avoid an omniscient host. |
| Native adapters: `src/web/native_windows.py`, `native_macos.py` | Similar small adapters preserve different native event loops and system browser APIs. Extracting a generic tray framework would hide main-thread/ABI requirements without removing meaningful policy. Read only, never invoked; native macOS proof remains pending. |
| Presentation/faults/tools: `src/presentation/report.py:render`, `watch_screen.py`, `src/runtime_errors.py:recoverable`, `development/tools/collect_diagnostics.py:main`, `run_tests.py:main` | Output consumes projections; screen geometry stays local. Sanitized faults and diagnostic bundle publication are distinct from runtime acquisition. Runner remains bounded per file; no new test fixture dependency or validation gate introduced. |

Runtime owners/handoffs/dependencies are unchanged. No performance/parity/complexity gain or replacement mechanism is claimed; no new negative fixture applies.

## Next investigations

Web/bounded-pump findings supersede milestone-10 notes. Under relevant shipped changes, characterize slow-detail starvation/cancellation (shared live thread), sustained overflow/resync, retained-history memory and slow-provider shutdown. Admission limits are not byte limits; no latency/memory measurement or current outage demonstrated.

Native macOS acceptance remains pending in the Web contract/docs/web-beta.md. Layout/accessibility, physical suspend, soak, upstream compatibility and executed parity remain unmeasured. Static assertions/historical probes are not fresh PASS. Obtain failure/duration evidence before rewriting long routines or legacy test coupling.

Deliver architecture/20's native state, retaining identity/completed bundles. No FR move/pruning. Confirmed default read-back/native delivery establish completion.

## Rejected hypotheses

- Web remains unimplemented or the event queue remains unbounded: rejected by current host/application/acquisition source and Queue(maxsize=1024) plus overflow resync. Historical audit text is not fresh evidence.
- One universal retry/scheduler is simpler: rejected because short report budgets, CLI blocking recovery, Web tick cadence and account-only refresh differ in lifetime and policy; shared acquisition already exists.
- Every retained dictionary is a duplicate ledger: rejected because source/cache, current-day/run totals and observed session history have distinct authority/retention contracts.
- Static counts, large files, exact-duplicate absence or test names prove architectural health/refactor need: rejected; source semantics and measured failures are required.
- Similar native adapters require a generic framework: rejected absent meaningful policy reduction across different event loops/ABIs.
- A scheduled development-only audit must rerun product suites or bump version: rejected by the active workflow. No product PASS, new gate or runtime improvement is fabricated.
