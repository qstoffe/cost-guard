# Cost Guard architecture

Source revision: 54f613db6777eb4fc7fc3c5c193ad774df6c3ece
Checked revision: 54f613db6777eb4fc7fc3c5c193ad774df6c3ece
Last checked: 2026-11-09
Status: current

## Scope and authority

Milestone-90 two-level static assessment and source map, not an exhaustive correctness audit. `development/journal/architecture.md` records whole-repository inventory, representative normal/failure/recovery traces, local coverage, simpler alternatives and independently justified global/local runtime NO_CHANGE. Module pages retain their own scoped evidence; their earlier runtime/platform results are not rerun here.

Toolkit owns workflow/mirrored `development/README.md`; `development/repository.json` holds release facts; `development/applied-contract.json` records identity (revision 6). History is evidence, not instructions. Development-only work activates no product checks/budgets/version work. Shipped source retains functional release rules. Main is supported; packaged Releases remain paused.

FR000624's scoped delta preserves these layers: bounded Web-card readers and scoped
V2 brackets remain below canonical report capture; reports own compact sampling,
Watch owns its shared guidance lifetime, and Web owns finite scheduling/browser demand.
Healthy pending work has no elapsed-computation failure cutoff. The module pages and
[foreground-recovery ledger](../journal/web/foreground-recovery.md) distinguish actual
oracle/benchmark evidence, scoped exceptions and still-outstanding final gates; this
delta does not claim a fresh audit of every unchanged module.

## System map

```mermaid
flowchart TD
    cli["CLI: validated config / bootstrap"] --> reports["Reports: scope, acquisition, projections"]
    cli --> live["Watch / Live: cadence, observations, recovery"]
    web["Web host: HTTP, lifecycle / security"] --> demand["Dispatcher: demand, due times, retained publications"]
    browser["Browser: routes, tables, one SSE connection / tab"] -->|authenticated route interest / lookup| demand
    demand -->|effective priority / admission| jobs["Jobs: executing, parked and retiring owned children"]
    jobs -->|spawn / resume grant| finite["Finite process: application / private report service"]
    web -->|one publisher, not per tab| live
    finite --> reports
    live --> reports
    reports --> sources["Sources: V1 SQLite / V2 loopback HTTP"]
    reports --> providers["Accounts / pricing: acquisition and normalized facts"]
    reports --> analysis["Analysis: attribution, valuation, context"]
    reports --> cache["Cache: disposable revision-keyed acceleration"]
    sources --> domain["Domain: canonical snapshots / value contracts"]
    providers --> domain
    analysis --> domain
    reports --> terminal["Terminal: report / buffered Watch presentation"]
    live --> terminal
    finite -->|bounded result / progress / continuation IPC| jobs
    jobs -->|accepted publication or typed failure| demand
    demand -->|retained as-of result; retry does not renew observation| browser
    web -->|shared Live export / replay| browser
    live -->|outage: retain frame; same-source retry or terminal stop| sources
    jobs -->|cancel / parent loss / unconfirmed child exit| stopped["Owned cleanup; retained handles / host failure if exit unconfirmed"]
    cli -->|invalid configuration / sanitized fault| terminal
```

Arrows group calls, control and consumption, not literal Python imports or one linear pipeline. Both `cost-guard.py` and `cost-guard-cli.py` install `src/runtime_errors.py` before importing composition. Since v81, `src/product_entry.py` routes no-argument Windows/macOS intent to the existing managed Web launcher, help/version locally, and explicit legacy arguments unchanged to CLI. Unsupported desktop defaults fail with guidance. `src/bootstrap.py` still composes reports or blocking CLI Watch independently of HTTP; `Legacy/` launchers call the explicit CLI entry. CLI parse/config validation precedes source, provider and runtime-cache work. Unexpected faults sanitize evidence and close owned work; Diagnostics observes independently rather than owning product recovery. Parent loss exits that finite child through its exact-parent sentinel; failed host cleanup instead retains ownership and faults the host.

### State, lifetime and recovery owners

| Boundary | Authority and transitions |
| --- | --- |
| Web host / finite demand | `src/web/host.py` composes HTTP, dispatcher/jobs and one `src/application/live.py` publisher. `dispatch.py` owns source-qualified retained results, leases, due/backoff and effective priority; `jobs.py` owns executing/parked/retiring child handles, bounded IPC and cancellation. Neither owns report mathematics. See [data-dispatch.md](modules/data-dispatch.md). |
| Finite execution / recovery | `report_control.py` checkpoints park a private stack until a host grant; source workers wait on its read permit. `history_jobs.py` / `stats_jobs.py` own distinct continuation protocols, not a universal elapsed-work deadline. Reports validate durable compact coverage and dependencies. `src/application/service.py` validates and exports immutable values; rejected foreign/Live services must not be closed. Exit uncertainty retains exact handles and fails the host. |
| Shared Live / Watch | `src/watch/acquisition.py` drives the coordinator's initialize/poll/enrich seam; CLI retains its blocking wait adapter. Hints trigger authoritative reads, never usage or completion. Source outage retains the last frame; retry stays in the selected generation, discards partial initialization and ends on terminal/unsupported evidence. Source-change stops rather than reloads. |
| Independent background lanes | `src/watch/web_coordinator.py` owns four card workers, separate single-worker account-history, detail and scalar Sessions-index lanes, plus session-cost reconciliation. Fresh resources isolate blocking work and cancellation; late daily results are checked against the current day. HTTP/pages never tick acquisition. |
| Source consistency | `src/sources/selection.py` chooses one healthy generation; histories never merge. V1 pins a read-only transaction; V2 brackets complete tree hydration with catalog revisions and bounded fresh attempts. Wire/schema adaptation stays below canonical snapshots. Loopback GET, SSE and cancellation have distinct resource lifetimes. |
| Accounts / prices | Attempt/account identity and deadlines reject late quota observations while retaining occupied lanes. Account refresh is independent of source cadence. Normal price-cache fallback differs from explicit strict upstream refresh; optional release metadata has separate freshness. Quotas/capacity, reference CCost and billed cost are not interchangeable. |
| Derived history / cache | Reports own acquisition populations and canonical projections. Cache is reconstructible acceleration, never OpenCode authority or observed history. `src/reports/session_history.py` retains observations; `src/application/session_detail.py` owns revision-pinned rich chunks. `session_catalog.py` owns complete membership, scalar-key coverage and exact global sorts, not page-only guesses. |
| Browser / native launchers | `src/web/security.py` / `http.py` enforce loopback/Host/Origin/method/body/session/CSRF. `lifecycle.py` owns instance arbitration/exact-process restart proof. Browser sequence/gap recovery consumes immutable publications. Native pumps, one-use handoff and host close have separate owners. Windows inspection is not macOS/Finder/Gatekeeper proof. |

## Semantic and dependency contracts

- OpenCode persistence is authoritative and read-only; one analysis core serves finite reports and Watch. Provider/source formats stop at their adapters. Analysis owns causal child/termination attribution, pricing/CCost and historical versus current context; renderers do not revalue or acquire.
- Global comparison samples, Token Mix, period AI Stats, first-input matches and Sessions keys differ in population/validity. AI Stats reuses compact facts/matched-run projection, not a second valuation engine. Match persistence contains digests/scalars; ephemeral previews are never identity.
- `src/reports/shared_evidence.py` publishes compatible compact root facts under existing source/revision/algorithm/config/price keys, not a second history authority. Complete stable snapshots qualify publication; each recipient still owns its population, completeness and totals. A finite retained publication, a refresh job and the authoritative source observation have different identities/lifetimes.
- Sources/accounts/pricing/cache depend on domain and narrow lower contracts, not reports/presentation. Analysis never imports reports/presentation. Reports depend on source/account/pricing contracts plus analysis/cache, not concrete integrations, Watch or renderers. Application owns detached exports and injected drivers, not bootstrap/Web/Watch imports. Web composition alone wires concrete services/Watch. Domain uses the standard library only. The product validator checks actual layer imports; diagrams are not that proof.
- `src/config.py` owns JSONC merge/normalization/validation: omission inherits; null overrides; reads never create user config. `src/web/settings.py` atomically edits only theme, CCost unit, Mini placement/size and quota orientation. Browser owns native geometry. `src/numbers.py` resets display-unit scope safely; canonical values/quotas are unchanged.

## Module and test navigation

Start with [CODE_MAP.md](modules/CODE_MAP.md) for exact entrypoints, platform wrappers, focused tests and bounded legacy debt. Static test-import paths are navigation, not executed coverage.

| Group | Ownership / public contracts |
| --- | --- |
| Sources | [sources.md](modules/sources.md) |
| Accounts / pricing | [providers.md](modules/providers.md) |
| Domain / analysis / cache | [analysis.md](modules/analysis.md) |
| Reports / application | [reports.md](modules/reports.md) |
| Web demand / finite scheduling | [data-dispatch.md](modules/data-dispatch.md) |
| Watch | [watch.md](modules/watch.md) |
| Web / native lifecycle | [web.md](modules/web.md) |
| CLI / presentation / faults / Diagnostics | [presentation-diagnostics.md](modules/presentation-diagnostics.md) |

## Validation, review and delivery flow

Test Health 105 scoped verification update on `70462006910b0507c7f21412ef87330c3f675e2f` (2026-11-09); unchanged runtime claims keep their metadata above. Contract revision 6 and `development/repository.json` retain authority. No new gate, scheduler, paid inference or self-review. Failed required checks remain unfinished; uncertain merge needs reconciliation, not replay.

```mermaid
flowchart TD
    request["Authorized request"] --> safety["Scoped authority, native permissions, privacy / Git safety"]
    safety --> author{"FR-only authoring?"}
    author -->|yes| publish["Guarded FR-only publication; no product checks"]
    author -->|no| select["Backlog: identity / sync when needed; one fixed task"]
    select --> scope{"Only development changes?"}
    scope -->|yes| skip["Skip product checks and version / release work"]
    scope -->|no| product["Repository tests, validation, relevant read-only installation proof / release facts"]
    product --> live{"Model inference explicitly authorized?"}
    live -->|no| denied["No model calls; default-denied"]
    live -->|yes| bounded["Only established bounded authorized test"]
    denied --> outcome{"Applicable checks successful?"}
    bounded --> outcome
    outcome -->|no| repair["Repair cause; preserve selected work"]
    repair --> scope
    outcome -->|yes| pr["PR to actual default; inspect blockers"]
    skip --> pr
    pr --> ci{"Risk-triggered CI?"}
    ci -->|yes| checks["Quick / validator / browser; native on platform paths; manual Full"]
    ci -->|no| merge["Normal protected merge"]
    checks --> permitted{"Checks / protections permit merge?"}
    permitted -->|no| repair
    permitted -->|yes| merge
    merge --> truth{"Merge and default read-back confirmed?"}
    truth -->|no or uncertain| preserve["Preserve pending work; reconcile actual Git truth"]
    preserve --> merge
    truth -->|yes| finish["Report delivery; native finish / bounded cleanup; fresh worker after response"]
```

### What runs and why

| Stage | Scope / activation | Disposition | Exact source owner | Failure handling |
| --- | --- | --- | --- | --- |
| FR publication / selection | Authoring or fresh Backlog | Scoped authority; fixed task; sync if outdated | Installed `shared-repo` authoring/worker/sync references; `development/applied-contract.json` | Preserve unrelated work; no reselect |
| Development-only | Development/docs changes | No product gates/version work | `development/README.md`; installed maintenance method | Verify changed tooling/facts; no invented product PASS |
| Product verification | Shipped-source changes | Applicable tests/security/release facts | `development/tools/run_tests.py`, `development/tools/validate_package.py`; `development/repository.json` | Repair required failures; focused development checks remain available |
| Installation / inference | Relevant local evidence | Conditional read-only probes; inference default-denied | CODE_MAP probes; `development/tools/collect_diagnostics.py`; `development/tests/integration/live/` reserved | Never stop shared OpenCode; disclose gaps |
| Common CI | Cumulative product/test/tool/workflow PR/push paths; public only | Quick units + validator + Chromium; explicit manual dispatch selects Full | `.github/workflows/web-beta.yml`; `development/tools/ci_web_beta.py`; `development/tests/integration/ci_browser_web.py` | Exact selected report required; missing/failed/cancelled is not PASS; no workstation spoofing |
| Native CI | Platform-sensitive entry/config/host/security/jobs/Live/launcher and native test/tool paths; manual dispatch | Conditional Windows/macOS ARM/Intel profile + native smoke, unchanged mechanisms | `.github/workflows/native-web.yml`; `development/tools/ci_web_beta.py`; `development/tests/integration/ci_native_web.py` | No private paid fallback; retain deadlines, phases and missing/failed truth; isolated assets/calculations do not trigger |
| PR / merge / handoff | Authorized delivery, then confirmed default read-back | Normal checks/protections; native finish/cleanup attempt | Installed `/repo-backlog`; actual GitHub state | No force, replay, cleanup success gate or second task |
