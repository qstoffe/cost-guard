# Architecture assessment — milestone 60

Source revision: 302784d150a8bd7b7ac203dfc6cfba88a6ea54cd
Checked revision: 20ab74d5927e6d5dbe1f81701cd8448cbb79f1aa
Last checked: 2026-11-06
Status: current

## Summary

**Completed two-level static assessment: independently justified global NO_CHANGE and local runtime NO_CHANGE.** No material orchestration defect or local refactor with demonstrated net benefit was established. This is not a blanket health/correctness/security/performance claim. The overview consolidates runtime owners and delivery/CI activation. Runtime modules, state machines and dependencies are unchanged; no measured gain or parity test is claimed.

Only Architecture 30 → 60 advances on merge. Ordinary count 60, last ordinary identity, other methods and Session Learning deferral stay unchanged. Checked revision adds backlog authoring only. No FR implementation/move, version change or automatic proposal.

## Evidence

### Inventory and reproducibility

At the source revision: **953 text/config records** (324 source-or-config, 359 documentation, 270 test), **265 binary/over-1-MiB exclusions**, **zero exact-byte duplicate groups**. Scope: Git tracked plus nonignored untracked text/config excluding runtime artifacts. Largest text hotspots are historical development verification JSON, not proof of product complexity. Reproduce with installed `shared-repo/scripts/maintenance_evidence.py inventory --repo-root .`.

`py -3 development/tools/code_inventory.py --json` AST-parses without imports: **212 runtime modules / 32,002 lines**, tools 15 / 2,961, test tree 238 / 44,663, nested fixtures 38 / 2,911 (not additive). All runtime purpose/import records were reviewed, then substantial areas source-sampled; JavaScript/platform/tooling was read separately. Seven legacy test-to-test edges remain bounded debt. Only two package markers lack static test paths. Imports are **not executed coverage**; size is not a quality score.

Temporary metadata: `scratch:/architecture-60-inventory.json`, `scratch:/architecture-60-ast.json`; this summary survives cleanup. No prompts/accounts/auth/runtime history read or exported. Counts describe the original baseline, not later backlog additions or performance.

### Level 1 — end-to-end authority, normal/failure/recovery

| Source trace inspected | Ownership / simpler target compared |
| --- | --- |
| `src/bootstrap.py`, `cli.py`, `config.py:load_configuration/validated_values`, `runtime_errors.py:run` | Parse/validate precedes source/cache/provider work; direct CLI reports close owned accounts/progress. Watch owns waiting/retry. Routing CLI through Web would add host/HTTP/browser lifetime rather than remove decisions. Sanitized unexpected faults remain distinct from invalid config/source failure. |
| `src/web/host.py`, `jobs.py`, `src/application/service.py` | Host owns HTTP/jobs/Live. Fresh finite processes: 4 pending/16 records, 120s deadline, 8MiB result, bounded progress, parent sentinel and owned cancellation. Foreign/Live rejection must not close another service. Sharing one service couples deep scans/cancellation to Live. |
| `src/application/live.py`, `src/watch/acquisition.py`, `coordinator.py`, `web_coordinator.py` | One driver calls initialize/poll/enrich. Outage retains frame, discards partial startup, retries same generation and stops on unsupported/persistent unreadability. Hints/HTTP health never establish completion. CLI wait/Web ticks adapt shared acquisition; a universal scheduler couples different lifetimes. |
| Web coordinator, `src/watch/session_costs.py`, Web `composition.py` | Four card workers plus separate account-history/detail/scalar-index lanes use isolated resources; late daily results are day-checked; owned transports cancel before joins. Session-cost reconciliation uses existing snapshots and source-free cache/catalog resources. Combining lanes risks head-of-line blocking/shared cancellation; no evidenced net simplification. |
| `src/reports/acquisition.py`, `src/sources/selection.py`, `opencode_v1.py:load_session_snapshot`, `opencode_v2_snapshot.py`, V2 transport | One selected generation, never merged histories. V1 pins a read transaction; V2 brackets full trees and allows at most two fresh consistency attempts. Hints/cached metadata are not usage. Loopback/proxy-free GET, one stale-idle retry, SSE and socket cancellation have distinct contracts; a common raw adapter hides their proofs. |
| `src/accounts/acquisition.py`, `refresh_loop.py`, `simple_http_mapping.py`, pricing `github_copilot.py` | Attempt/deadline/account identity rejects late observations; timeout retains occupied lane. Independent account mailbox/cadence is not source retry. Fail-soft catalog cache versus strict explicit refresh and optional metadata freshness are intentionally different. Universal retry/expiry would erase valid distinctions. |
| Web `http.py`, `security.py`, `lifecycle.py`, native adapters; browser `app.js`, `live.js`, `report-loading.js`, `cached-reports.js`, `session.js`, `sessions.js`, Mini sample | Loopback/Host/Origin/session/CSRF, pre-host process proof, host close and native handoff have separate owners. Browser sequence/gap resync and finite attempts consume detached values; routes never acquire. Mini owns layout, not source. A global browser/native machine conflates authority; no desktop proof inferred. |

**Global decision:** preserve the modular monolith/lifetime boundaries. Navigation costs isolate real state/cancellation/consistency differences, not duplicate decisions. Map repair is not runtime redesign.

### Level 2 — all substantial areas

Counts are baseline runtime modules; test routes not explicitly read below are navigation only.

| Area | Representative implementation / local decision |
| --- | --- |
| Root/entry (10) | Bootstrap/CLI/config/fault root and Windows launcher; early validation, unit scope and minimal fault boundary remain cohesive. No generic lifecycle wrapper. |
| Domain (9) | `src/domain/models.py` snapshot/price/quota contracts plus complete purpose/import records. Evidence, native termination, unknown values, valuation and quota identity stay distinct; no transport imports. |
| Sources (24) | Selection, V1 normalization/snapshot, V2 consistency/transport/wire. Native formats stop at snapshots; no generation branch above adapters. |
| Accounts (20) | Acquisition/refresh/mapping; partial/null/units/capacity/billing and publication identity stay explicit. Shared mapping engine does not merge provider semantics. |
| Pricing (10) | Copilot catalog/fallback/metadata and catalog/identity purpose routes. Reference valuation, billed cost, model availability and metadata freshness are different facts. |
| Analysis (26) | Full `core.py`, `valuation.py`, `input_identity.py`, `matched_runs.py`; causal prompt/context routines. Single child/terminal/context owners; size alone does not justify splits. Ordered first-input identity rejects external references; preview is never identity. |
| Cache (6) | Full `database.py` and other purpose/dependency records. Short connections commit/rollback/close; reconstructible acceleration is not durable source/observed-history state. No schema/ledger added. |
| Reports (22) | Full service/acquisition, matched-inputs/matched-runs, AI Stats/Token Mix cache. Populations/privacy/retention differ; AI Stats reuses facts/projection, not a second identity scan/valuation. No evidenced common-cache benefit. |
| Watch (24) | Coordinators/acquisition and session-cost lane, tracker/retention/tool purpose routes. Visible rows, retained observations, run/Today totals and session baselines have different scopes. Combining their dictionaries would lose contracts, not remove duplicate truth. |
| Application (15) | Finite/Live, full session catalog/detail. Exact sorting waits for complete scalar coverage; fair bounded admissions/backoff/epochs differ from revision-pinned rich history. HTTP lease is admission, not history ownership. |
| Presentation (19) | Full `watch_screen.py`, report prompt renderer and bootstrap consumption. Buffered geometry/style consumes projections, not acquisition. Small compatibility entrypoints were noticed, not assumed dead from size. |
| Web (27 plus assets/native) | Host/jobs/security/lifecycle and browser routes above; Settings atomic allowlist and Mini sample. Independent route/attempt/connection/layout lifetimes do not establish value in a generic client framework. CSS/native layout not exhaustively audited. |
| Development / platform | Inventory tool, bounded test runner, Diagnostics collector, Windows/macOS shell wrappers and CI dispatch/workflow. Per-file test isolation, privacy-allowlisted diagnostics, hosted-only native CI and real desktop probes have separate triggers. No dependency, gate, model call, archive or launcher change. |

**Local decision:** no unsupported deletion, helper split or forced fixture migration. Seven test-import edges/large routines remain follow-ups when responsibilities change, not accepted growth or fabricated gain.

### Tests read and verification actually performed

Read full `development/tests/test_application_reports.py`, `test_matched_inputs.py`, `test_watch_source_recovery.py`, `test_web_shutdown.py`, `test_web_session_catalog.py`: numeric/export/privacy contracts; exact input/cache/revision cases; retained frame/no subprocess; owned-socket cancellation/independent streams; global sorts/fairness/epochs/detail isolation. **None executed.** Other test routes are navigation only.

Only `development/` docs/progress change. Product tests, validator, Diagnostics/live probes, browser/native runs and benchmarks: **not run / not applicable**, not waived or PASS. No assertion/timeout/gate/budget weakened. Development checks cover scope, revisions, diagram bounds, links/paths, progress delta and whitespace; results belong in the PR.

### Retained historical evidence, not current results

Milestone 30 (2026-11-04, source `020e50071671ee863ceffcd37b6871af789bbe0f` plus its diff) removed unreachable comparison-cache/weighted-profile code: two modules / 214 runtime lines; unchanged `MixEvidence` moved to analysis records. Five retired tests covered superseded policy; canonical deduplication/unknown filtering and independent export assertions remained. Caller tracing, not passing tests alone, justified removal.

Historical results: 140 files / 1,659 tests (1,658 passed, one macOS skip), validator 11 passes / 6 warnings, bounded real V2 report/Live probe. A mistaken Quick-bound foundation timeout was rerun under Full; the timeout was not PASS. None validates milestone 60. Older counts/weighted rationale are superseded; Git retains originals. No historical approval/platform proof is promoted.

## Next investigations

- Suspend/reconnect, retained bytes, fanout/backpressure and provider combinations need runtime evidence; static tracing cannot measure them.
- Physical Windows/browser and macOS Finder/Gatekeeper acceptance remains unverified.
- Revisit large routines/seven test-import edges when responsibilities overlap/change; preserve critical evidence, not count-driven splits.
- Existing journal INDEX exceeds eight-route guidance. Only its architecture description changes; no router migration/unrelated revalidation.

## Rejected hypotheses

- **One service/scheduler/cache for every report and Live lane:** similar loops do not imply shared lifetime, consistency, population or privacy. The inspected alternatives increase cancellation/ownership coupling.
- **Growth/zero exact duplicates proves quality:** inventory is triage, not a design score.
- **Map cleanup is runtime simplification:** owners/modules/lines unchanged; no speedup, token saving or executed parity.
- **Tests once passed, therefore keep every internal algorithm:** milestone 30 showed the opposite. Current NO_CHANGE rests on current caller/contract and alternative analysis, not historical PASS.
