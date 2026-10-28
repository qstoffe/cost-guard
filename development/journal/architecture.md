# Architecture assessment — milestone 40

Source revision: a27d5fede5d07a7a2e992691b34790b6017cd780
Checked revision: a27d5fede5d07a7a2e992691b34790b6017cd780
Last checked: 2026-10-28
Status: current

## Summary

Fresh two-level review supports **runtime no-change**, not a claim of exhaustive correctness. No evidenced overlapping orchestrator or local semantic duplication justifies a replacement. Correct stale analysis/navigation facts for publisher-aware sampling and job-local CCost display. Preserve isolated finite reports, one Live/detail driver, independent quota refresh and source-specific snapshot consistency.

This scheduled delivery changes development knowledge/maps and exact native state only. Product tests, validators, version/release changes, Diagnostics, installed-service probes, browser/native UI and model evaluations were not run. Assertions below were read, not executed. No runtime parity, speed, memory or complexity improvement is claimed.

## Evidence

Reproduce at the revision above: installed `shared-repo/scripts/maintenance_evidence.py inventory --repo-root .` and `py -3 development/tools/code_inventory.py --json`. Full metadata/AST outputs were retained in current owned scratch during investigation; the durable summary and source routes below survive cleanup. These are read-only inventories, not product validation gates.

Inventory: 537 text/config records (218 source-or-config, 147 documentation, 172 test), 64 binary/over-1-MiB exclusions, zero exact-byte duplicate groups. Scope is tracked plus nonignored untracked, excluding Git/runtime artifacts. AST: 178 runtime Python modules / 27,420 lines; 14 development tools / 2,810 lines; 159 test-tree modules / 31,294 lines, including 20 fixture modules / 1,517 lines. All runtime purpose/largest-routine records were reviewed; representative source/assertions were then read across the major areas below. Counts do not prove dead code, semantic duplication, cycles or executed coverage. Binary images, private runtime data and platform UI were not inspected as functional evidence.

### Level 1 — normal / failure / recovery red thread

| Source owners inspected | Observed authority and simpler alternative considered |
| --- | --- |
| `src/bootstrap.py:main`, CLI/config routes | Parse/validate configuration before selecting source, initializing cache and creating providers. Reports build/render directly; Watch owns its coordinator; finally closes account/progress work. Routing CLI through Web would add host lifetime rather than remove policy. |
| `src/web/host.py:_serve/close/run_gui`, `src/web/jobs.py:tick/run_owned_report/close`, `src/application/service.py:execute` | Host owns stop/socket/owned work; finite workers get fresh report services, bounded deadlines and exact parent-sentinel cleanup. A 64-message drain prevents progress backpressure without starving control. Invalid/busy/foreign-service requests fail without closing foreign work. Sharing Live's mutable service would mix cancellation and deep scans with Live. |
| `src/application/live.py:_run`, `src/watch/acquisition.py:tick`, `src/watch/coordinator.py:acquire_cycle/close` | One thread drives Watch and due detail. Bounded hints request authoritative acquisition. Outage retains frame, observation time and same-source recovery; terminal schema ends driver; unexpected fault stops host. CLI waits versus Web ticks remain scheduling adapters, not duplicate valuation. |
| `src/application/session_detail.py:tick/page`, `src/reports/session_history.py:acquire` | Leases only request/read. Shared driver fairly acquires outside lease lock; immutable capture and 50-row projection detach HTTP pages. Omissions freeze lifecycle/duration, identical running evidence advances clock without revaluation. Combining retention with derived cache would blur observed versus complete source evidence. |
| `src/sources/opencode_v1.py:load_session_snapshot`, `src/sources/opencode_v2_snapshot.py:load_snapshots` | V1 pins one SQLite read transaction; V2 brackets message reads with per-tree revisions and retries unstable trees only. A common raw snapshot implementation would hide different consistency proofs. No fallback to another source or event-derived usage. |
| `src/accounts/acquisition.py:poll/close`, `src/accounts/refresh_loop.py:tick`, `src/pricing/github_copilot.py:get_catalog` | Deadline/attempt identity rejects late quota results; discovery precedes draining; mailbox separates publication. Pricing and metadata health have independent freshness. Universal retry/state ownership would collapse genuinely different validity windows. |
| `src/web/lifecycle.py:launch`, native adapters `run`, `src/web/assets/live.js` | Launcher locks restart and checks birth/current-image identity; GUI owns main thread/readiness; browser failure leaves managed host. Client enforces instance/sequence, replay-gap resync and auth/terminal stop without starting a host or valuing usage. Moving arbitration into host loses pre-host ownership. Source inspection only, not UI proof. |

### Level 2 — local cohesion across substantial areas

| Area / representative source inspected | Decision |
| --- | --- |
| Domain/config/entry: `src/domain/session_tree.py:root_by_session`, bootstrap; config/CLI AST routes | Canonical topology tolerates missing parents/cycles without inventing valid roots; startup stays explicit. No new generic topology/startup layer. |
| Sources: V1 snapshot, V2 snapshot and wire/transport/import records | Keep storage proof, compatibility parsing and canonical normalization separate from report policy. Large wire conversion alone is not evidence for another split. |
| Accounts: acquisition/refresh loop, `src/accounts/simple_http_mapping.py:_component` | Missing/invalid/native units and independent billing/quota meanings remain explicit. Worker validity, scheduling and publication are distinct, not redundant retries. |
| Pricing: catalog `estimate/reference_category_valuation`, Copilot catalog, publisher/metadata routes | Native monetary fallback is separate from reference category value; fresh prices do not prove healthy release dates. Keep upstream parsing below provider-neutral catalog. |
| Analysis: `core.py:analyze_snapshot`, `causal.py:build_prompt_records`, `context.py:watch_context_state`, `valuation.py:unique_usage/comparison_cost`, `workload_mix.py` | Causal timeline, historical versus active context, clone fingerprints and weighted profiles encode different contracts. Own-model/publisher/global sampling is not the independent running dashboard mix. Correct old common-100-prompt documentation, not source semantics. |
| Cache/reports: database `connect`, acquisition `prepare`, session history, token-mix history | Transactions own commit/rollback/close. Revision hits avoid hydration; detail forces required snapshots; deep history releases hydrated roots. Historical publisher grouping reuses shown requests, not comparison priors. Retained history intentionally bypasses persistent derived cache. |
| Watch: acquire-cycle, `src/watch/token_mix.py:observe`, tracker/Today/retention AST routes | Observation ledger preserves known fields and replaces aggregate message entries with steps. Visible rows, run totals and daily retention have distinct scopes; merging dictionaries would erase invariants. |
| Application/display: execute/detail, `src/application/display.py:metric_tokens/with_display`, `src/numbers.py` | Immutable allowlisted export and ContextVar-scoped unit formatting avoid cross-job leakage without changing raw Decimal CCost. Replacing with global mutable unit or browser-side conversion is less isolated. Update analysis map. |
| Presentation: `src/presentation/watch_screen.py:publish`, `quota_migration.py:eligible`, report/Watch AST routes | Buffered geometry/overflow rendering owns no usage. Time-bounded migration notice is isolated presentation state, not quota acquisition. No universal presentation/state helper. |
| Web/native/faults/tooling: host/jobs/lifecycle/security, native run, `runtime_errors.py:recoverable`, runner/Diagnostics main | Security bootstrap exchange is single-use/bounded. Native loops retain platform ABI/readiness differences. Fault-report failure preserves original defect; runner bounds per-file work; Diagnostics independently collects. No generic tray framework or new gate warranted. |

### Characterization / negative assertions inspected, not executed

- `development/tests/test_web_live.py:test_source_outage_retains_active_frame_and_recovers_same_selection`: same rows during outage, one retry window, same run start on recovery, terminal schema.
- `development/tests/test_account_acquisition.py:test_timeout_keeps_worker_slot_and_late_response_cannot_overwrite`: timeout publication does not free blocked worker capacity or let late data replace current evidence.
- `development/tests/test_workload_mix.py`: mixed-prompt exclusion, same-publisher-only weights, 0/40/90/100 evidence, and historical publisher reconciliation/availability filtering protect distinct sample scopes.
- `development/tests/test_ccost_display_unit.py`: raw totals/order unchanged across report modes; nested exception reset and concurrent credits/USD exports; native quotas, billing residuals, rates and relative prices unchanged.

No production mechanism or responsibility changed, so no replacement negative fixture, executed parity baseline or before/after handoff reduction applies. Global owners/handoffs and local source remain identical; only map precision changes. Native verify and fresh Git/PR truth independently protect this development delivery.

## Next investigations

Measure slow-detail impact on the shared Live thread, retained-history bytes, provider shutdown latency and sustained event overflow before designing replacements. Admission counts bound trees/leases, not history bytes. Cold comparison history may traverse many roots; no latency/memory/soak was measured. Desktop reconnect/suspend and macOS Finder/Gatekeeper acceptance remain unproven by this audit. Current pending feature requests remain unmodified; this maintenance does not implement them or create a speculative suggestion.

Tool limits: combined knowledge read exceeded 32 KiB; split exact map/journal reads succeeded. Knowledge apply rejected CRLF metadata matching; LF-normalized planned content passed without changing the installed helper. A source-print command hit Windows console encoding on an arrow; reran with Python UTF-8 mode. No permission/limit/assertion was weakened. No remote service fault or paid model work occurred; cost is unmeasured.

## Rejected hypotheses

- Earlier milestone notes/counts prove current health: rejected; fresh inventory, source and assertions were inspected.
- A universal report/Live/quota scheduler or durable ledger is simpler: rejected by distinct isolation, freshness, retention and cancellation contracts.
- Large routines or zero byte-duplicate groups justify a rewrite or prove no semantic duplication: rejected; source-backed risk is required.
- Model publisher equals account route, all mixes share one 100-observed-prompt window, or USD display changes valuation: contradicted by source and inspected assertions.
- Development-only maintenance should run product tests/version work, launch UI or claim fresh PASS: rejected by active scope. No suggestion publication or external access was needed.
