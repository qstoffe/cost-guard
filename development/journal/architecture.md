# Architecture assessment — milestone 10

Source revision: b2850feffd227ee5e502bd40d9a0266fdd49ba86
Checked revision: b2850feffd227ee5e502bd40d9a0266fdd49ba86
Last checked: 2026-10-26
Status: current

## Summary

Scheduled whole-repository architecture audit, independently considering orchestration and local cohesion. Runtime **no-change** is justified by the sampled source: lifecycle, acquisition, semantic analysis and presentation have distinct state owners. No demonstrated coordination defect warrants a rewrite this cycle. The overview's old one-way data pipeline hid direct Watch dispatch and retry ownership; replace it with a source-backed call/consumption map and describe the existing conditional delivery flow. This is navigation improvement, not runtime simplification or proof of behavioral parity.

Journal: retain this baseline and route without refreshing older findings. Architecture: update overview; no module responsibility moved. All delivered paths are under development. No product tests, validator, release/version work, Diagnostics, live installation probes or model inference were run. No new validation gate is created.

## Evidence

Reproduce with installed `shared-repo/scripts/maintenance_evidence.py inventory --repo-root .` and `python development/tools/code_inventory.py --json` at the source revision above. These inspect local files/AST without importing the product. Maintenance inventory: 340 text files (157 source/config, 120 test-related, 63 documentation), 17 binary/over-1-MiB exclusions, zero exact-byte duplicate groups. Git internals and ignored runtime material are excluded; no credential/session exports were read. AST inventory: 138 runtime modules / 23,086 lines; 12 development tools / 2,541 lines; 112 test-tree Python modules / 24,017 lines, including 16 fixture modules / 1,341 lines counted once. Sizes and static imports are triage, not executed coverage, dead-code proof or runtime-cycle proof.

### Level 1: normal, failure and recovery routes

| Workflow | Source trace and state authority | Simpler alternative and decision |
| --- | --- | --- |
| Startup / one-shot | `cost-guard.py` installs the minimal runtime guard before bootstrap import. `src/bootstrap.py:main` parses CLI and validates configuration before selecting sources/cache/providers. `src/reports/service.py` dispatches report modes; `acquisition.py` owns root hydration/cache reuse; `analysis/core.py` composes canonical analysis; renderers consume projections. | Making bootstrap own report acquisition would move decisions out of their use case and duplicate Watch's shared seam. Retain the composition root; correct the misleading diagram instead. |
| Initial discovery vs report read retry | `src/sources/selection.py` selects exactly one generation, with metadata-only best-effort migration evidence. `src/sources/read_recovery.py` has a shared finite report readiness budget; auth/schema failures are not readiness retries. `bootstrap.py` separately owns preselection Watch waiting. | One universal retry loop would conflate selection, short report deadlines and persistent Watch recovery. Keep separate policy owners; no new retry adapter. |
| Watch normal / outage / shutdown | `src/watch/coordinator.py:poll_once` selects changed/relevant roots, stages hydration, then updates blocks, retained accounting and projections. `_advance` owns waits/polls/rendering. `_recover_source` stops its event pump, retains the displayed frame, retries only the selected source and uses fresh snapshots; initialization failure discards partial initialization. `run_forever` finally closes owned work. | A global scheduler spanning source, quota and rendering would erase their deliberately independent cadences. Watch's orchestration remains one coordinator, not several competing runtime state machines. Its 754 lines alone do not establish incoherence. |
| Consistent source acquisition | V1 owns read-only SQLite/catalog/revisions. `src/sources/opencode_v2_snapshot.py:load_snapshots` brackets message acquisition with catalog revisions, retries changed trees and keeps stable neighbors. `opencode_v2_transport.py` owns pooled idempotent GET stale-socket recovery and cancellable SSE; no shared service stop. | Folding wire normalization into reports or treating SSE as history would weaken authoritative snapshot consistency. Retain adapter-owned translation and consistency. |
| Capacity independent of source liveness | `src/accounts/acquisition.py` owns credential-generation-pinned attempts, expired lanes and results. `refresh_loop.py` owns account-only scheduling/coalesced mailbox. `src/watch/account_refresh.py` owns main-thread publication and successful-seen timestamps; `watch/accounts.py` owns stale/expiry display policy. | Completion, observation validity and display age differ. Merging into source polling would couple quota stalls/events to acquisition. Retain these seams. |
| Retained accounting vs current source/cache | `src/reports/history.py` tracks revision-proven history and publishes a completed scope which can extend beyond today for usable quota windows. `src/watch/today_ccost.py` retains current-local-day observations across deletions, publishes finite batches and rolls over at midnight. `analysis/period_ccost.py` indexes valuation; `cache/database.py` owns only disposable WAL persistence. | Rolling scope, daily retention and cache differ; shared `reconcile_usage` already merges telemetry. Do not add a durable ledger. |

Normal/failure expectations were characterized by reading existing deterministic fixtures/assertions, not executing them: `test_source_history_loading.py` covers V1/V2 parity, changed-tree retry and consistency brackets; `test_watch_source_recovery.py` covers preserved frames, same-source recovery, schema termination and forbidden subprocess/reselection; `test_account_acquisition.py` covers changed/removed credentials, broken-storage fail-closed behavior and bounded work. `test_cache.py` checks generation independence/rebuild/concurrent access. `test_runtime_errors.py` seeds secret-bearing exceptions and checks sanitized fatal evidence. These are source-backed protections, **not current PASS receipts**.

### Level 2: whole-tree triage and local cohesion

All 138 runtime module purposes/import/routine records were inspected in the AST inventory; representative source and tests were read across every major area below. This is a sampled semantic audit, not an exhaustive line-by-line proof of every adapter or test.

| Area | Representative source / test inspection | Decision |
| --- | --- | --- |
| Entry/config/launchers | `cost-guard.py`, `src/bootstrap.py`, `config.py`, `windows_launcher.ps1`, `macos/Cost Guard.command`; `test_runtime_errors.py` | Configuration-before-I/O and process-guard/launcher handoff stay coherent. Shell launchers were read, never invoked. |
| Domain/cache | `src/domain/session_tree.py`, domain module inventory; `src/cache/database.py`, `src/analysis/cache.py`; `test_cache.py` | Topology is metadata, not causal usage. Cache keys include explicit semantic dependencies and source provenance; no runtime-to-development ownership needed. |
| Sources | `src/sources/selection.py`, V1 adapter, V2 snapshot/transport/read recovery, errors; `test_source_history_loading.py`, `test_watch_source_recovery.py` | Distinct wire/normalization/acquisition responsibilities; generation differences stop before reports. V2 union-compatibility hotspot is translation, not duplicate analysis. |
| Accounts | Acquisition/refresh loop, `simple_http_mapping.py`, credential/discovery routes; `test_account_acquisition.py` | Mapping primitives have explicit bounds, not executable user expressions. Provider-specific adapters and generation-pinned acquisition are separate responsibilities. No source change justified from size alone. |
| Pricing | `src/pricing/github_copilot.py` parser, promotion retention/expiry, catalog fetch; catalog/metadata inventory; `test_context_history_projection.py` pricing fixtures | Price validity, release-date health/backoff and model availability have different evidence. Keep provider-neutral catalog vs concrete document parsing. No claimed fresh upstream compatibility. |
| Analysis | `src/analysis/core.py`, `causal.py` prompt timeline/child work, `context.py` epoch/live-anchor logic, `period_ccost.py`; `test_context_history_projection.py` | Long routines (prompt record 191, compaction 156, live context 119 lines) encode distinct provenance/termination/epoch cases. No demonstrated repeated orchestration or removable dead branch; retain rather than extract a chain of cosmetic wrappers. |
| Reports | `src/reports/service.py`, `acquisition.py`, `history.py`; source-history fixture/tests | Service delegates scopes/cache/projection; acquisition and history have named owners. Largest service routine is its 47-line constructor, despite 671-line module size. Do not split by line count. |
| Watch | Coordinator normal/recovery/close, observers, account reconciliation, Today retention; `test_watch_source_recovery.py` | Tracker, run totals, Today and account observations intentionally differ in scope/lifetime. No second billing implementation demonstrated. Event hints remain non-authoritative. |
| Presentation | `src/presentation/report.py`, `watch.py`, `watch_screen.py`; context projection and runtime tests | Layout/terminal state consumes projections; no source/provider acquisition. The 139-line report block renderer remains a local formatting hotspot, not a global orchestration defect. |
| Development tools/tests | `development/tools/collect_diagnostics.py`, `run_tests.py`, inventory/code map, journal Test Health; shared fixtures used by representative tests | Diagnostics isolates observations/sanitizes failure data; bounded per-file runner stays separate from product runtime. Historical 10 test-import debt edges remain known, not new audit work or grounds to remove unique cases. |

Runtime owners, dependencies and workers are unchanged; no runtime complexity/performance gain or executed parity is claimed. Only documentation changed; no replacement mechanism or new negative fixture applies.

## Next investigations

Pending web work remains unimplemented; preserve report/Watch distinctions. Under a relevant product change, measure event arrival/backlog during slow hydration: `LiveEventPump` currently uses an unbounded hint queue, unlike the account mailbox. No event-rate/memory experiment was performed here; bounded coalescing would need characterization of resync/software-fault ordering, cancellation and lost-hint recovery before replacement. This is an unmeasured robustness risk, not a demonstrated current outage or proof that every queue is bounded.

Inspect actual failure/duration evidence before changing long causal/context/renderer routines or the known fixture coupling. Current test execution/parity, upstream quota support, native macOS behavior and performance remain unmeasured. Historical journal claims retain their original limits. No live or paid check can be inferred from this audit.

Deliver exact native architecture/10 state; retain identity and every pending bundle. No FR move or retention deletion. Only merged-default verification and native delivery establish completion.

## Rejected hypotheses

- A linear source-to-report-to-Watch diagram describes dispatch: rejected by direct bootstrap Watch construction and shared ReportService calls.
- One retry/state machine is simpler: rejected because readiness deadlines, persistent selected-source recovery, account acquisition and stale display are different observable policies.
- Long files, static imports or zero exact duplicates prove either a required refactor or architectural health: rejected; source semantics and measured failure matter.
- Similar retention dictionaries justify a shared durable ledger: rejected; different period/publication/lifetime contracts and disposable source authority must survive.
- A scheduled documentation/state-only delivery must rerun Full or bump the product version: rejected by the active development-only workflow. No historical result is republished as current PASS.
