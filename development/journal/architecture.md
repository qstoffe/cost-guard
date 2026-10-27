# Architecture assessment — milestone 30

Source revision: e25cf3b63a5ffe73e20787a96c9c1ee38f356c1a
Checked revision: e25cf3b63a5ffe73e20787a96c9c1ee38f356c1a
Last checked: 2026-10-28
Status: current

## Summary

Fresh whole-repository audit at milestone 30. **Runtime no-change** at both levels: sampled coordination/internals show no overlapping state machine or semantic duplication warranting replacement. This is not exhaustive correctness. Clarify the map's finite-report versus shared Live/detail lifetimes and recovery; retain module boundaries.

Only development knowledge and the exact native maintenance transaction change. Product tests, validators, release/version changes, Diagnostics, real-installation probes, browser/native UI and model calls are intentionally not run for this development-only delivery. Inspected assertions are characterization evidence, not fresh PASS receipts. No runtime, parity, performance or complexity gain is claimed.

## Evidence

Reproduce against the source revision with installed `shared-repo/scripts/maintenance_evidence.py inventory --repo-root .` and `python development/tools/code_inventory.py --json`. Both are read-only metadata/AST inventories, not product gates. Complete outputs were retained in owned scratch during investigation; these counts and exact source routes survive cleanup.

Inventory: 485 text/config files: 214 source-or-config, 160 test-related, 111 documentation; 61 binary/over-1-MiB exclusions; zero exact-byte duplicate groups. Git metadata and ignored runtime artifacts are excluded. AST: 174 runtime Python modules / 26,810 lines; 14 development tools / 2,803 lines; 148 test-tree modules / 29,646 lines, including 19 fixture modules / 1,474 lines counted once. All runtime purpose/import/largest-routine records were inspected. Ten historical test-to-test import edges remain; no new coupling is introduced. Counts alone establish neither runtime cycles, dead code, meaningful duplication nor executed coverage.

### Level 1 — end-to-end normal, failure and recovery ownership

| Workflow / inspected source | Observed ownership and simpler alternative considered |
| --- | --- |
| `src/bootstrap.py:main`, `src/config.py:load_configuration` | CLI parses and validates defaults/overrides before source/cache/network composition. Reports build then render; Watch initializes and runs its own coordinator. Finally closes account work/progress. Routing CLI through Web would add a server lifetime and alter recovery; retain direct dispatch. |
| `src/web/host.py:_serve`, `src/web/jobs.py:tick`, `run_owned_report`, `src/application/service.py:execute` | Host owns jobs/socket/shutdown; finite workers own fresh services, deadlines and cancellation. Result/progress draining is capped at 64 messages per turn. Exact parent sentinel prevents orphaned acquisition. Reusing Live's mutable service would couple deep scans/cancellation to Live; keep process isolation. |
| `src/application/live.py:_run`, `src/watch/acquisition.py:tick`, `src/watch/coordinator.py:acquire_cycle` | One live thread drives Watch acquisition and detail. Hints are bounded and only request authoritative refresh. Retry retains frame, same source and run start; nonretryable schema stops the driver; unexpected fault stops host. CLI blocking waits and Web tick deadlines are scheduling adapters, not competing analysis owners. A universal retry coordinator would conflate those policies. |
| `src/application/session_detail.py:tick/page`, `src/reports/session_history.py:acquire` | HTTP leases enqueue/read; one live thread acquires one due tree fairly, outside lock. Snapshot freezes captures; 50-row pages detach projections. Retained omissions freeze lifecycle/time; unchanged running evidence advances duration without revaluation until lifecycle deadline. Combining this with disposable cache would misrepresent retained evidence as current complete authority. |
| `src/sources/opencode_v1.py:load_session_snapshot`, `src/sources/opencode_v2_snapshot.py:load_snapshots` | V1 pins a read transaction. V2 brackets message acquisition by catalog revisions and retries changed trees only. Wire normalization stays adapter-local; events never establish usage or completion. Combining adapters with report policy leaks generation-specific state. |
| `src/accounts/acquisition.py:poll/close`, `src/accounts/refresh_loop.py:tick`, `src/pricing/github_copilot.py:get_catalog` | Acquisition rejects expired/generation-obsolete results; account-only clock owns scheduling/publication mailbox. Pricing and release-metadata health/backoff are separate. Source, quota, price, billing and historical attribution have different validity windows; a shared scheduler/ledger is not a simpler authority. |
| `src/web/lifecycle.py:launch`, `src/web/host.py:stop/run_gui`, native adapters | Launcher serializes intentional restart and checks birth/current-image identity before accepting readiness. Host signals shutdown and closes owned work/socket; GUI remains main-thread. Browser failure does not restart host. Merging launcher arbitration into host would hide pre-host ownership checks. No UI code was invoked. |

### Level 2 — substantial modules and local cohesion

Representative source was read across every major area, supplemented by whole-runtime AST records; this is not line-by-line verification of every module.

| Area / inspected candidates | Decision and rationale |
| --- | --- |
| Entry/config/domain: bootstrap, config, `src/domain/session_tree.py:root_by_session` | Defaults validate independently. Topology tolerates missing parents/cycles without creating valid report roots. Pure canonical records remain separate from integration selection. No generic startup/topology layer justified. |
| Sources: V1/V2 snapshot acquisition, transport/wire import records, Watch acquisition | Storage consistency, raw wire translation and canonical normalization remain distinct. Long wire conversion is a candidate for focused characterization, not proof of duplicate cost logic. Keep generation details below reports. |
| Accounts: acquisition/refresh loop, `src/accounts/simple_http_mapping.py:_component` | Declarative mapping distinguishes missing/invalid/native units, billing components and quota fractions. Late results cannot replace timeout observations. Discovery, worker validity and publication are separate responsibilities, not redundant retry states. |
| Pricing: `src/pricing/catalog.py:estimate`, Copilot get_catalog and metadata imports | Monetary billing fallback explicitly differs from reference CCost. Fresh prices do not prove healthy release dates. Keep provider-neutral catalog separate from upstream parsing/metadata recovery. No upstream compatibility was measured. |
| Analysis: `src/analysis/core.py:analyze_snapshot`, `causal.py:build_prompt_records`, `context.py:watch_context_state` | Shared timeline feeds prompt attribution; context epochs deliberately distinguish historical completion, active anchors, compaction and provisional estimates. Combining historical and live branches would erase real distinctions. Long routines remain investigation candidates, not refactoring-by-line-count. |
| Cache/reports: `src/cache/database.py:connect`, `src/reports/acquisition.py:prepare`, service/history | Cache connection owns commit/rollback/close. Batch hydration gates stable revision hits; detail forces snapshots when needed. Retained SessionHistory bypasses persistent derived cache. No duplicate authoritative history store demonstrated. |
| Watch: acquire_cycle, acquisition tick, tracker/retention/Today import records | One caller owns mutable acquisition. Row visibility, run totals and daily retained CCost have different scopes. Rendering never becomes acquisition/recovery owner. No evidence for one all-purpose retained dictionary. |
| Application/display: execute, session_detail, `src/application/display.py:with_display/metric_tokens` | Finite service ownership and immutable allowlists isolate transports. Display tokens preserve raw numeric fields and skip opaque external-label maps. Extracting display primitives into a new framework would add indirection without removing policy. |
| Web/assets/security: host/jobs/lifecycle/security, `src/web/assets/live.js`, `reports.js` | Client stream checks instance/sequence, bounded replay-gap resync and terminal/auth stop; never calculates canonical totals or starts host. Route filters are distinct from acquisition scopes. Fixed host/security/lifecycle owners remain preferable to an omniscient HTTP coordinator. |
| Native launchers: `src/web/native_windows.py:run`, `native_macos.py:run`, launch lifecycle | Similar small adapters expose platform-specific GUI readiness and event-loop contracts. A generic tray abstraction would hide ABI/main-thread constraints. Read-only source review; macOS desktop acceptance remains pending. |
| Presentation/faults/development tooling: `src/presentation/watch_screen.py:publish`, `src/runtime_errors.py:recoverable`, Diagnostics and runner main | Buffered geometry decisions do not own usage. Fault-report failure preserves original defect. Diagnostics collects and publishes separate evidence; runner bounds files/processes/timeouts. No universal helper, new gate or cross-test fixture needed. |

### Characterization assertions inspected (not executed)

Under `development/tests/`: `test_web_live.py` outage retains rows/run start, retries same source and schema becomes terminal; overflow remains at most 1,024 queued hints and requires resync. `test_web_runtime.py` progress burst drains 64 then 64 then result, and Host/Origin/CSRF negative requests return 403. `test_web_session_detail.py` omitted running rows retain duration, timestamp and nonterminal status; unchanged running evidence advances only duration while reanalysis/revaluation are forbidden. `test_account_acquisition.py` a result completed after its deadline yields timeout/no quotas even when main was busy. `test_source_history_loading.py` retries changed tree twice versus stable neighbor once. `test_web_models.py` verified-empty and unverified fallback retain different membership/warnings. These characterize the authority boundaries that a future replacement must preserve, not current suite outcomes.

No runtime owners, handoffs, dependencies or behavior mechanisms changed, so no new replacement/negative fixture or before/after runtime measurement applies. Navigation clarification is the only architectural artifact change. Native verify/Git read-back protect delivery separately.

## Next investigations

Prioritize measured evidence for slow detail on the shared Live thread, retained-history bytes, slow-provider shutdown and sustained hint overflow before redesign. Sixteen retained trees/thirty-two leases bound admission, not history memory. This audit did not measure latency, memory, upstream compatibility, accessibility, physical suspend or soak; it establishes no current outage. Native macOS Finder/Gatekeeper acceptance stays pending. Pending FRs 000510/000520 remain selected by a later independent invocation, not implemented or reprioritized here.

Historical AGENTS routes named removed files; actual clone inventory resolved the routes. The old journal exceeded the helper's 12-KiB read limit by 29 bytes: shorten obsolete delivery text, reread hashes, consolidate. No helper or limit was weakened.

## Rejected hypotheses

- Milestone-20 notes/counts prove current architecture: rejected; fresh inventory, source and assertions are required.
- One universal source/quota/report scheduler, per-tab services or one durable ledger are simpler: rejected by distinct cancellation, validity and authority contracts and an existing shared acquisition seam.
- Exact-duplicate absence, large routines or AST edges prove architectural health/need for a rewrite: rejected; inspect semantics and measure alleged failure first.
- Similar native adapters require a generic framework: rejected absent policy reduction across different event loops/ABIs.
- Development-only audit must run product tests/version/release checks: rejected by the active workflow. No invented PASS, improvement, gate or runtime proof.
