# Architecture assessments

## Current assessment — milestone 150

Source and checked revision: `a874c664cc67d8b08be40debc7821b9317eef5ab`, 2026-11-14.

**Completed two-level static assessment: global runtime NO_CHANGE and independently
justified local runtime NO_CHANGE.** The [report](../architecture/governance/verification/architecture-150-20261114.md)
records all-module metadata coverage, representative source/test reads, normal and
failure/recovery ownership, simpler alternatives and remaining uncertainty.

Keep display retention separate from source validity: a retained Sessions context,
model or effort is not a newly qualified sort key. Period controls share calendar
boundaries, not populations: Sessions uses tree activity; Token Mix uses deduplicated
request time. Session model/effort and Mini cost groupings consume different facts,
so merging them into a universal contributor engine would obscure their contracts.
The finite dispatcher, process cleanup, shared Live and browser attempt lifetimes
remain distinct; no causal evidence justified replacing their coordination.

Updated the overview/module flow and stale Sessions column/test-route summaries;
no product, test, tool, release or version change. The report preserves concrete
navigation risks without treating large routines or two sibling-test imports as
proof of a runtime defect. Static checks are not product/runtime PASS.

Only Architecture **120 → 150** advances on merge. Ordinary count **150**, last
ordinary identity `fr/000705`, Test Health **135**, Performance **120**, Session
Learning **0** and its existing milestone-100 deferral remain unchanged. No new
exception or deferral; no FR move or second selected task.

## Prior assessment — milestone 120 (historical)

Source and checked revision: `3f994921849ae2cf6f87245c6f3a010353fcbd08`, 2026-11-10.

**Completed two-level static assessment: global runtime NO_CHANGE and independently
justified local runtime NO_CHANGE.** The [assessment report](../architecture/governance/verification/architecture-120-20261110.md)
preserves current inventory, source/test samples, normal/failure/recovery traces,
simpler alternatives and limits. It does not convert source reading into runtime PASS.

The new benchmark lane reuses finite-process ownership but has independent aggregate
freshness; Sessions progress/cancellation does not own canonical acquisition; the V1
notice consumes qualified Live proof, not a second selector. Keep these distinct
lifetimes rather than adding a universal scheduler or browser-side accounting.
Large routines and retained feature narratives remain navigation risks, not automatic
proof of a defective state machine. Corrected the stale six-column Sessions summary,
mapped actual module recovery branches, and refreshed the overview without product churn.

Only Architecture **90 → 120** advances on merge. Ordinary count **120**, last ordinary
identity `fr/000670`, other method milestones and the existing Session Learning deferral
remain unchanged. Development-only: no product tests/validator, live/native probes,
version, release or ZIP; no assertion, permission or gate was waived.

## Prior assessment — milestone 90 (historical)

Source revision: 54f613db6777eb4fc7fc3c5c193ad774df6c3ece
Checked revision: 54f613db6777eb4fc7fc3c5c193ad774df6c3ece
Last checked: 2026-11-09
Status: historical; superseded by the milestone-120 assessment above

## Outcome and scope

**Completed two-level static assessment: independently justified global NO_CHANGE and local runtime NO_CHANGE.** Current source did not establish a material orchestration defect or a local refactor with demonstrated net benefit. This is not an exhaustive correctness, security, dead-code or performance audit. Metadata for every Python runtime module was reviewed; substantial areas were source-sampled and representative normal/failure/recovery transitions traced. Not every routine or test was read.

Development-only delivery updates this journal, its route, the two-level overview and the scoped Web demand contract. No runtime/test/tool/config/launcher change, FR move, proposal implementation, dependency, version, release or ZIP. Only Architecture **60 → 90** advances on merge. Ordinary count **90**, last ordinary identity `fr/000640`, other method milestones and the existing Session Learning deferral remain unchanged. That deferral is not completed/PASS.

## Whole-repository inventory and reproducibility

Installed `shared-repo/scripts/maintenance_evidence.py inventory --repo-root .` at the source revision returned **1,125 text/config records**: 356 source-or-config, 439 documentation, 330 test; **301 binary/over-1-MiB exclusions**, **zero exact-byte duplicate groups**. Scope is tracked plus nonignored untracked files, excluding runtime artifacts. Its largest text hotspots are development verification JSON, not evidence that runtime coordination is defective. Excluded assets were not semantically audited.

`py -3 development/tools/code_inventory.py --json` parsed without importing product code: **237 runtime Python modules / 36,341 lines**, tools **15 / 2,986**, test tree **298 / 59,580**, nested fixtures **53 / 4,746** (fixtures are not additive). All 237 purpose/local-import records were reviewed. The separate Web asset inventory has eighteen JavaScript, two CSS and one HTML file, plus the icon. Browser/platform source was sampled separately; asset counts are not rendering proof.

Static test reachability leaves only `src/__init__.py` and `src/pricing/__init__.py` without a test-import path. That does **not** prove executed coverage. Three remaining test-to-test edges are `test_model_pricing_presentation.py` → `test_step6_pricing_accounts.py`, `test_v2_synthetic_attribution.py` → `test_effort_presentation.py`, and `test_v784_regressions.py` → `test_v783_regressions.py`. They were inventoried, not repaired or accepted as new growth.

Temporary full metadata: `scratch:/architecture-inventory.json`, `scratch:/code-inventory.json`. The counts, source identity, exact candidate paths and decisions here survive scratch cleanup. No personal history, prompts, account observations, auth, private session storage or other workers' records were acquired. An initial metadata print failed under the Windows output encoding; explicit UTF-8 successfully returned the remaining records. That failed print was not successful evidence.

## Level 1 — the red thread and simpler targets

| Normal and failure/recovery source trace inspected | Authority and alternative decision |
| --- | --- |
| `src/bootstrap.py` → `config.py::load_configuration/validated_values` → `reports/service.py` → terminal; Watch takes its own coordinator path | CLI parse/config validation precedes runtime acquisition/cache. `finally` closes owned account work/progress. Configuration/source errors remain distinct from successful results. Making CLI enter HTTP/Live would add host/browser lifetimes rather than remove a duplicated decision. |
| `src/web/host.py` → `dispatch.py` → `jobs.py` / `report_control.py` → `application/service.py` → existing reports | Dispatcher owns leases, retained result IDs, due/backoff and priority; jobs own executing/parked/retiring processes; application owns detached allowlisted exports. Finite admission waits for source identity and the first healthy Live observation. Four pending jobs, sixteen records and 8 MiB results bound work; there is no elapsed-computation deadline. A single shared mutable Live/report service would couple deep scans and cancellation to publication. |
| Finite yield/result/cancel/parent-loss paths in `jobs.py`, `report_control.py`, plus `reports/shared_evidence.py` | Cooperative checkpoints park an existing private stack; a host grant resumes it. Durable report continuation is a different protocol from stack parking. Accepted result publication need not wait for natural exit; exact child handles remain until confirmed reap. Unconfirmed termination latches host failure, not silent success. Shared compact facts require stable complete snapshots and revision proof; recipient reports keep separate totals/populations. Collapsing these protocols into one generic state machine would hide process ownership versus durable coverage. |
| `application/live.py` → `watch/acquisition.py` → `watch/web_coordinator.py` / `web/composition.py` | One Live owner drives canonical acquisition. Hints/HTTP never prove completion. Outage retains the last frame, retries the selected generation, discards partial startup, and stops on terminal/confirmed persistent unreadability. Cards, daily/account history, detail, scalar Sessions indexing and session-cost reconciliation have distinct resource lifetimes. Combining those lanes would introduce shared cancellation/head-of-line blocking; no duplicated valuation engine was found. |
| `reports/acquisition.py` → `sources/selection.py`, V1 snapshot, V2 snapshot/tree brackets | One selected generation, no merged history. V1 pins metadata/revision/messages/parts in one read transaction. V2 verifies before/after tree revisions with two fresh attempts; scoped card topology cannot become a global catalog. Capability absence differs from auth/malformed/transport failure. A universal raw adapter or cached hint as authority would erase these different consistency proofs. |
| `accounts/acquisition.py` / `refresh_loop.py`, `pricing/github_copilot.py` | Account attempt/credential generation and deadlines reject stale results; an expired call retains its occupied lane. Discovery precedes result publication; a coalesced mailbox decouples quotas from source/renderer cadence. Pricing fallback, explicit strict refresh and metadata-only recovery have different authority/freshness. A universal retry or expiry policy would remove meaningful distinctions, not duplicate work. |
| `web/http.py::route`, `security.py`, `lifecycle.py`; browser `app.js`, `live.js`, `data-demand.js`, `report-loading.js`, `cached-reports.js`, Mini controller | Host/Origin/method/body/cookie/CSRF guards precede protected routes. Native launch control/exact-process restart, host cleanup, browser replay/instance identity, finite attempts and Mini window ownership are separate boundaries. In dispatcher mode the browser's five-second check looks up publications, not a second source refresh schedule. Collapsing browser/native/source recovery would conflate authorization, observation and layout. No native UI was exercised. |

**Global decision:** preserve the modular monolith and these lifetime/proof boundaries. The newer finite dispatcher is not a competing accounting authority. The overview now makes its demand/process/report handoffs and material failure branches explicit. Documentation improvement is not a runtime redesign or measured performance gain.

## Level 2 — independent local coverage

Every substantial module group has metadata coverage and representative source inspection below. Python counts/lines are the baseline, not targets. Tests in CODE_MAP not explicitly read below remain navigation only.

| Area (modules / lines) | Representative implementation and local decision |
| --- | --- |
| Root (10 / 1,564) | Full bootstrap and configuration load/normalization seam; CLI/config/fault/display purpose/import routes and Windows shell boundary. Validation, composition and presentation units remain distinct; no generic wrapper would reduce decisions. |
| Domain (10 / 756) | `models.py` canonical/termination/token contracts and full `accounts.py`. Quota, billing, reference valuation, unknown fields and account identity are separate values. The models→accounts import is type-checking-only, not evidence of a runtime import cycle. No concrete integration dependencies appeared in the inventory. |
| Sources (26 / 4,958) | Full selection, V2 snapshot/tree modules, V1 snapshot routine. Native wire adaptation, global membership, scoped consistency and read lifetimes stay below canonical snapshots. A separate scoped bracket is justified by its restricted proof, not a second ordinary semantic core. |
| Accounts (20 / 3,290) | Acquisition scheduling/result/deadline paths and full refresh loop; provider/transport/mapping purpose and dependency records. Late output cannot renew replaced credential capacity. No new provider abstraction or consolidation of native quota semantics is justified. |
| Pricing (11 / 1,734) | Copilot catalog/fallback/strict-refresh/metadata owner and all catalog/alias/tier purpose routes. Optional release metadata does not change prices/retrieval time. Concrete acquisition and pure reference identity/valuation contracts remain distinguishable. |
| Analysis (26 / 4,830) | Full core/valuation and `causal.py::build_prompt_record/build_prompt_records`. Shared billing/child/timing helpers supply both reports and Watch. Unverified unfinished execution is neither success nor a live clock. The 186-line prompt constructor is a local navigation hotspot, but splitting its coherent attempt/child/terminal decision into generic helpers would not yet demonstrate simplification. |
| Cache (8 / 702) | Full database/lifecycle plus repository and scope import routes. Short connections commit/rollback/close; lifecycle writes only disposable Cost Guard state, protects missing/changed/active proof and rolls back cancellation. A new ledger or lifecycle framework would add authority, not remove it. |
| Reports (28 / 4,302) | Full root acquisition/shared evidence; service sampling, account projection, Watch history/invalidation and report dispatch seams. The 856-line service is a composition/navigation hotspot; existing acquisition/history/sample/projection owners retain real responsibilities. No second canonical valuation or evidence-backed dead branch was established. |
| Watch (28 / 4,779) | Full Live acquisition and Web coordinator; all card/read/guidance/history/tracker/tool/totals purpose/import routes. Projection, certified Earlier membership, retained observations, Today/run cost and session baselines have different scopes. Combining their dictionaries would obscure state ownership. |
| Application (16 / 2,178) | Full finite service/Live runtime/quota-reference owner; scalar catalog acquisition/page/epoch paths. Export allowlists, typed failures, exact global metric-sort coverage and pure Web quota conversion remain cohesive. Conversion does not replace observed CCost or native billing. |
| Presentation (19 / 2,725) | Full buffered Watch screen; report/Watch/account render consumers and small duration/model-supersession routes. Caller search found live source/test consumers of both tiny compatibility routes, so size alone is not dead-code evidence. Renderers consume projections rather than acquire source history. |
| Web (35 / 4,523, plus assets) | Full host/dispatcher/jobs/quantum/security/lifecycle/composition, HTTP route, browser acquisition/replay/demand/loading and Mini/account-card samples. Large HTTP and Mini routines coordinate their actual protocol/window, not arbitrary unrelated helpers. No new client framework, microservice or cosmetic split is justified. CSS/physical layout is not exhaustively audited. |
| Development / platform | Runner registration and subprocess/timeout routes; Diagnostics section isolation/sanitized metadata; complete CI workflow, Windows PS and macOS report shell. Focused tests, hosted-only native CI, private diagnostics and authorized real desktop probes have different triggers; no new gate, inference, install/reload or launcher side effect is introduced. |

**Local decision:** independently justified runtime NO_CHANGE, not an exemption for functioning internals. Largest routines (`causal.py::build_prompt_record`, `web/http.py::route`, `config.py::validate_configuration`, `analysis/context.py::watch_context_state`) and remaining test coupling are navigation risks, not demonstrated defects or automatic split mandates. No unsupported deletion, wrapper layer, fixture migration or baseline increase.

## Characterization and verification actually performed

Representative test source read (not executed):

- `test_web_dispatch.py`: coalescing/retained timestamps, source rotation, transient versus terminal errors, strict price invalidation, actual child parking/parent loss/foreground resume, durable coverage rejection and independent cross-view projections (selected sections, not every test).
- `test_v2_tree_brackets.py`: global/scoped parity, capability/auth separation, insert/remove/reparent retry, active/location parity and epoch replacement (selected sections).
- `test_watch_source_recovery.py`: retained rows, no subprocess/reselection, independent account cadence, terminal schema and bounded unreadability (selected sections).
- Full `test_cache_lifecycle.py`: real SQLite retention/rehydration, unknown clocks, revision isolation, contention and cancellation rollback.
- `test_web_quota_ccost.py`: native/observed independence, exact verified conversion, invalid/stale allowance rejection and unknowns (selected sections).

These characterize intended normal/negative/recovery contracts; reading assertions is **not a passing test**. No mechanism was replaced, so no before/after runtime parity or new negative fixture is claimed. Runtime modules/lines, dependencies, state owners and source behavior are unchanged by this delivery; measured CPU/elapsed/fanout/retained bytes remain unknown.

Actually run: read-only maintenance inventory and Python AST inventory. Development checks cover the changed-path scope, source identities, local Markdown routes, diagram structure, exact progress delta and whitespace; final results belong in the PR. Product suites, package validator, Diagnostics/live probes, browser/native runs and benchmarks: **not run / not applicable to development-only edits**, not waived and not PASS. No assertion, deadline, gate or budget was weakened.

## Limits and retained historical learning

- Current static NO_CHANGE closes this assessment, not outstanding feature acceptance. The [foreground-recovery ledger](web/foreground-recovery.md), Web module pages and feature journals retain their separate oracle/performance/native limitations. This run does not close or reapprove them.
- Suspend/reconnect behavior, actual retained memory/backpressure/fanout and provider combinations require runtime evidence. Windows physical interaction and macOS Finder/Gatekeeper acceptance remain outside this run. No blanket security/correctness/performance conclusion follows from inventory or diagrams.
- Milestone 60 (2026-11-06, source `302784d150a8bd7b7ac203dfc6cfba88a6ea54cd`, checked `20ab74d5927e6d5dbe1f81701cd8448cbb79f1aa`) was also static global/local NO_CHANGE: 953 text records, 212 runtime modules / 32,002 lines, seven sibling-test edges. Its old finite 120-second deadline description is historical and superseded, not current policy.
- Milestone 30 (2026-11-04, source `020e50071671ee863ceffcd37b6871af789bbe0f` plus its diff) removed unreachable weighted comparison-cache/profile code: two modules / 214 lines. Unchanged `MixEvidence` moved to analysis records; canonical deduplication/unknown/export evidence remained. Caller tracing, not passing tests alone, justified removal. Historical 140-file / 1,659-test results (one macOS skip), validator 11 passes / 6 warnings and real V2 probe validate that delivery only. Its initial Quick timeout was not PASS; the affected run used Full.
- The journal INDEX still exceeds the compact routing guidance; only its relevant architecture description changes. No unrelated router migration, whole-history audit or automatic proposal was performed.

Do not mistake growth or zero exact duplicates for quality, map repair for runtime simplification, or historical passing tests for a reason to preserve a flawed internal algorithm. Revisit the exact hotspots when overlapping responsibility or a causal runtime defect supplies evidence; do not split merely to lower a count.
