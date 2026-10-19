# Cost Guard v80 architecture

## Goals

Retain v78 Python/v77 behavior contracts; integrations add, not rewrite.

Core product principles:

- standard supported OpenCode installations should work without Cost Guard configuration;
- OpenCode persistence is authoritative and read-only;
- Cost Guard cache is disposable acceleration state, never durable user history;
- one analysis core serves reports and Watch;
- provider/source-specific formats stop at their adapter boundary;
- concurrent global Watch, session Watch and one-shot reports must be safe;
- recurring external process starts are avoided, especially in Watch.

## Runtime layers

```text
cost-guard.py
    -> src.runtime_errors (minimal process guard, before application import)
       -> src.bootstrap (composition root)
       -> CLI/config/source/provider selection
       -> Session Source(s) -> normalized domain
       -> Account Provider(s) -> normalized quota/account domain
       -> Pricing Provider(s) -> normalized pricing domain
       -> analysis core
       -> cache repositories
       -> report projections / Watch coordinator
       -> presentation
```

## Configuration

`src/config.py` owns JSONC, v77-compatible recursive merging, legacy normalization and startup validation. Omitted properties inherit defaults; explicit null overrides. Optional `config/user-config.jsonc` is never auto-created.

Configuration must be validated before any OpenCode/provider/network/runtime-cache work. Errors use terminal-default presentation and must not echo arbitrary configured paths/secrets. `openCode.source` is normalized to `auto|v1|v2`; concrete source selection remains outside the config layer.

## Session Sources

A Session Source normalizes agent history into provenance-bearing domain records. V1 is read-only SQLite; V2 is registered loopback HTTP with non-durable Watch hints. `openCode.source=auto|v1|v2` selects one healthy generation, preferring V2; histories are never unioned. Only bootstrap may wake the shared service once through the installed CLI's read-only API info command before reselecting; no Desktop/TUI or recurring Watch subprocess.

`sources/opencode_errors.py` maps explicit cancellation/limit IDs and bounded messages/JSON errors to `AbortedError` plus optional cause, never stack guesses. V2 idle errors carry `TerminalEvidence`; later success wins. `opencode_v2_interruptions.py` keeps bounded live user actors, matched to persisted idle session/ID/time only. Its revision signature invalidates pre-event cache; `observed_live` prevents persistence. Events never manufacture ends/usage. Labels outlast emphasis; tool-call success stays neutral.

### OpenCode V1 boundary

`src/sources/opencode_v1.py` alone knows the legacy V1 SQLite projection. Process-free discovery honors `OPENCODE_DB`, else the standard XDG data location. It validates the required `session`/`message`/`part` columns, opens SQLite `mode=ro` plus `PRAGMA query_only=ON`, and never starts the OpenCode CLI.

Hydration reads a root and its recursive descendants in one pinned read transaction, normalizing them into canonical sessions, messages, parts, events and invocations. `step-finish` parts, when present, replace cumulative assistant-message tokens/cost. Native message/part structure survives only through canonical types that compaction/tool/context analysis needs.

`get_session_tree_revision()` hashes membership/counts/timestamps/IDs without JSON. Catalog activity includes message/part row clocks; unchanged session clocks cannot hide descendants. A separate status-only latest-message/live-tool probe conservatively discovers old running candidates without declaring lifecycle truth. Revisions remain payload-free gates.

### OpenCode V2 boundary

`opencode_v2_transport.py` owns stdlib HTTP/SSE (pooled keep-alive JSON GETs, one retry on a service-closed idle socket, privacy-safe counters), `opencode_v2_wire.py` wire compatibility, `opencode_v2_normalization.py` pure message/part/request mapping with injected provenance, and `opencode_v2.py` acquisition/revision/snapshot assembly. Discovery reads standard registration, validates loopback, ignores proxies and probes `/api/info`. No auth logging, V2 SQLite or CLI/subprocess.

Global discovery uses cursor-paginated sessions, falling back to project enumeration/de-duplication. Current and transitional message APIs share canonical V1/V2 session/message/part/event/invocation contracts; synthetic histories verify semantic parity.

Invocations are model requests, not assistant records. Current V2 can split one response's tool calls into explicit-zero, tool-only records; `normalize_request_invocations` drops only such a record's invocation (the message stays canonical history) when it directly follows a usage-bearing `tool-calls` record of the same session/prompt/model and either shares its provider response id or, without ids on both sides, began streaming within 500 ms of creation. Differing or one-sided ids, latency, own text/reasoning, absent counters, errors, model switches and user/compaction boundaries keep it a request.

The adapter caches a complete catalog and one shared child/tree index with memoized revisions. Discovery/resync replaces it; events invalidate it. Required snapshot batches share before/after catalogs, but every tree must match around its message reads; only unstable trees retry. A complete catalog at most 2s old may be the before bracket, followed by two fresh attempts on mismatch. Repeated instability fails; hints never become durable truth.

`opencode_v2_wire.py` binds qualified persisted `idle` outcomes to the preceding assistant as neutral `TerminalEvidence`. Intervening boundaries, ambiguous timestamps or later tool work block attribution. Status/inactivity/transport failure alone proves no end. Native completion/usage/billing stays unchanged; Diagnostics counts terminal evidence separately. Path-free `location-switched`, `agent-switched`, and `model-switched` items become non-billable context boundaries. When supported, the documented session-context route contributes only path-free active message IDs; unsupported evidence stays absent. `opencode_v2_background.py` maps background jobs/completion notices to neutral `BackgroundActivity`/`BACKGROUND_COMPLETION`; a job without notice runs until its location's shell registry drops it.

`/api/event` decodes current JSON-string and legacy object events. Hints invalidate snapshots; explicit live actors supplement only a matching persisted cancellation. End/disconnect/failure requires authoritative resync; older history and a fresh source never invent actors.

Watch classifies V2 skill-call origin only from the location-scoped `/api/skill` registry: `/builtin` paths are built-in, other absolute source paths are custom, and unsupported/ambiguous paths remain unknown. Registry reads are cached per location and service connection; Cost Guard does not write OpenCode data.

### Source selection and migration-gap diagnostics

`src/sources/selection.py` selects process-free `auto|v1|v2`: healthy V2 first, otherwise healthy V1. Forced generations never silently fall back. Unhealthy V2 fallback warns; normal V1-only installations do not. Only `src/bootstrap.py` owns one-time CLI service wake after selection failure.
Typed source errors/health carry stable registration/transport/HTTP/version/schema/data/concurrency categories. Only readiness failures permit the shared report read budget (`read_recovery.py`: three failed attempts, 0.5s spacing, 4s recovery deadline); one CLI wake stays separate. Watch selection waits every five seconds without runtime/provider reconstruction. Missing-installation wording requires absent CLI and filesystem evidence. Presentation receives scalar failure facts, never concrete adapters or raw errors. Healthy V1 auto-selection never switches later.

With V2 selected and readable V1 metadata, a best-effort metadata-only diagnostic finds V1 sessions missing from V2 or newer than their V2 copy, without merged hydration, source changes or OpenCode writes. It is evidence, not a source warning: each gap carries its V1 root and possibly unrepresented activity window; `reports/migration_notice.py` notes it only when that window meets the report scope (sample cutoff, dates, requested root, all history). Watch never shows it; Diagnostics keeps full counts.

## Account and Pricing Providers

These are intentionally separate roles.

- **Account Provider:** account/subscription quota, usage windows, balances and reset metadata.
- **Pricing Provider:** model price/rate metadata used for repricing/comparison/fallback valuation.

`accounts/credentials.py` reads only the selected installation: V2 wins per integration, legacy applies without V2 rows, explicit overrides are file-only, read errors fail closed and secrets stay memory-only. Proven account IDs/source locators distinguish accounts, never provider alone; inactive quota visibility changes neither inference nor history.

`accounts/discovery.py` shares source/WAL views; other identities retain probes. `accounts/acquisition.py` owns generation-checked work: reports use four workers/45s deadlines and 15s final wait; Watch reserves one bounded lane per configured adapter/20s deadlines. `refresh_policy.py` owns start-anchored 30s healthy cadence and bounded recovery; pinned retries observe failed credentials while periodic full inventories preserve healthy neighbors. `refresh_loop.py` owns one account-only scheduler, five-second local discovery and a coalesced mailbox independent of source hydration. Stuck lanes never multiply; workers cannot render or mutate analysis/credentials. Main-thread publication uses cached local usage and completion timestamps, not mailbox drain time. [Account contracts](../docs/account-support.md#watch-freshness-budget) define budgets and limitations.

Providers return independent native account/quota/billing components. Copilot preserves degraded evidence; unlimited/blocked requires explicit native state. OpenAI owns rolling/model windows/credits. Anthropic API and Claude Code logins stay separate; [Claude contracts](claude-code.md) own SDK, identity and privacy boundaries.

First-class adapters (including MiniMax) own complex auth; Simple HTTP handles DeepSeek/OpenRouter. `http_account.py` owns per-record acquisition, `http_transport.py` network/JSON safety, `simple_http_mapping.py`/`simple_http.py` mapping/definitions. [HTTP contracts](simple-http-accounts.md) prohibit custom HTTP/scripts, inferred capacity/CCost, attribution, renderer branches and duplicate polling/cache; local estimates must be visibly distinct.

`pricing/github_copilot.py` normalizes GitHub Docs tiered I/C/W/O rates, release dates and explicit promotion dates into reconstructible metadata. Refresh uses age, UTC month and expiry; expired rates revert to verified standard rates or are withheld. `pricing/promotions.py` owns structured validity/recency; unknown starts never imply recent offers. Reports retain active promotions for their full lifetime; Watch notices require a start within seven days. Presentation owns markers/alignment and label-only notice color, not validity.

`pricing/release_metadata.py` owns date sources/merging; `pricing/metadata_health.py` owns health/backoff/events. `cache/metadata_state.py` persists cache/state/, copying legacy logs/recovery/model-metadata.json without deletion/overwrite; Diagnostics never migrates. Failures log to logs/errors/, recoveries to logs/recovery/. Dates keep prices. `PricingCatalog` memoizes identity resolution per immutable instance. Watch discovery runs metadata and network checks (price/V2 model list) on one bounded worker each; the main thread applies results.

## Canonical domain

The domain separates:

1. Usage — normalized sessions/messages/parts/events/model invocations and I/C/W/O/reasoning token observations.
2. CCost/Billed — independent reference token valuation and actual provider-reported/included billing evidence. Legacy estimated billing fallback is never surfaced as actual spend.
3. Quota/limits — native account units, used/limit/remaining, percentages/windows, reset time and availability state. Provider-native budgets remain supported; the deprecated local monthly CCost budget has no runtime semantics.

Equal numbers are not interchangeable. Analysis consumes capabilities/domain semantics, not version names.

`TokenUsage.known_fields` preserves telemetry availability through normalization/cache; absent/null/malformed fields stay unknown. `analysis/token_mix.py` sums volume, folds reasoning into O, apportions 100% and hides shares for unknown denominators. Category CCost reconciles with `comparison_cost`; `priceable_request` is the one per-request sample rule (real usage, complete telemetry, resolvable reference tier rates) behind priced-only mixes and Relative CCost usage; model rows use reference identity, unique prompts/all calls. `analysis/quota_pace.py` uses fixed-period remaining/reset and workdays, never session state.

`src/domain/accounts.py` owns source-aware `AccountRef`, flexible `QuotaComponent`, `BillingComponent` and `AccountSnapshot`. A request may carry an optional proven account reference. Current-login identity never fills historical request gaps. `src/domain/` must not import concrete source/account/pricing/cache/watch/presentation implementations.

`domain/session_tree.py` shares catalog ancestry/tree activity, never acquisition/attribution. Missing ancestors/cycles terminate without invented records; missing ancestry cannot resolve detail targets. Reports retain archived history; Watch excludes archived roots.

`domain/ccost.py` owns reference conversion (100 CCost/USD), `CCostPricing` and valuation contracts. Catalog `models` remain native monetary metadata; immutable `ccost_models` are converted once before reference usage/category/context/comparison analysis, never billing fallback. Unknown currencies are unpriceable, not guessed FX. CCost is Copilot AI-credit-equivalent reference value, not deduction/billing; projections use explicit CCost fields.

`numbers.py` owns display rounding: upward CCost/consumption, downward Remaining, exact rates/limits, no grouping; analysis never calls it. `version.mode_heading` owns startup grammar, CLI modes, progress transient rows. Reports align all quota labels; Watch only primary labels.

## Analysis

`src/analysis/` owns attribution, prompt/child/synthetic/compaction semantics, clone billing de-duplication, context and comparisons over canonical domain/provider-neutral abstractions only.

Usage/billing consumes all canonical providers: V2 `openai` requests must not disappear because pricing/quota integrations are Copilot-backed. Positive provider-reported cost stays authoritative; fallback and quota are separate capabilities. Provider filters are explicit lower-level/testing scopes only, never default report truth.

The causal core uses `TraceEntry`, `PromptRecord`, `CompactionRecord` and `RootAnalysisBundle`. Billing retains reported/included/fallback provenance. `analysis/valuation.py` independently derives `ComparisonCost` via reference estimation and actual `billed_spend`, never substituting fallback prices. Subscription CCost exposes priced/observed coverage, never billed dollars for unsupported models. `ReportService` may take a separate comparison catalog provider. Exact catalog identities prevent fuzzy CCost matches; clone de-duplication retains source-instance provenance. Root-first provenance reconciles main/subagent CCost before rounding.

Context/comparison consumes canonical messages/parts/invocations. `analysis/context_history.py` uses V2 active-message IDs to separate request-local input from continuing persisted history; unsupported decreases remain unknown. Request accounting stays independent. Compaction summary/tail is resulting context; completed compaction owns its negative delta. Prompt/compaction shares one chronological baseline. Next-Ictx never predicts cache hits; structured severity reaches both projections with live expiry. Comparison prices each published tier under the same 100-completed-prompt mix and cheapest base reference. One full-Decimal sorter orders base/next-tier prices descending, earlier increase boundaries, then name, recursively for later tiers. Without samples, hidden 2/96/1/1 sorts while Relative CCost stays blank. Diagnostics never feed billing.

Stable complete analysis requires exact source revision, algorithm/config compatibility and a semantic pricing signature (identities/aliases, currency, rates/tiers), not retrieval timestamps/document labels. Malformed/incompatible, running or incomplete results never persist. Revisions remain conservative gates, not semantic truth.

Dates use `zoneinfo`; clean Windows Python may lack IANA data, so dependency-free current rules cover shipped `Europe/Stockholm` and UTC. Other IANA zones fail actionably without host data; never substitute local time.

`analysis/effort.py` distinguishes explicit, request-proven/unresolved Default and unattributable effort. Only matching root requests resolve Default, never model/pricing maps or mutable session selection; V2 never stamps session effort onto history. Renderers share one label (no `Default -> X`); compaction uses its own explicit variant.

The latest assistant's `termination` ends running/duration and distinguishes success/failure/cancellation, even without usage. Actual root/child or newer tool activity stays live; stale tool flags do not. Reports/Watch/resync share this truth. Running background work keeps the newest prompt active without usage; resumes stay on it. Incomplete inference stays uncached; older algorithm keys are invalidated.

`analysis/duration.py` qualifies retrospective execution boundaries from normalized assistant/tool/background evidence, never session metadata or report time for terminated work. `PromptRecord.execution_duration_ms` and compaction timing survive derived caching; the legacy prompt `duration_ms` remains unchanged for Watch. Reports project qualified timing into `PromptProjection.duration_ms`; listings union the cached bundle directly, without detail hydration. A sorted interval union excludes idle gaps/overlap and propagates unknown timing to `N/A`; date totals union only selected events. Presentation shares Watch's compact formatter, not timing calculations.

## Reports

`src/reports/` owns use cases/neutral projections over abstract sources/providers, analysis and cache; never concrete integrations, Watch or presentation.

Candidate roots are ordered by whole-tree activity, so newly updated child work is not skipped. Hydrated snapshots/analysis remain the semantic authority; session metadata activity is only a bounded discovery gate. Session dominant model is selected by whole-session attributed CCost; listing order is recent tree activity, never cost.

Immutable projections cover dashboard/catalog, lists and detail/date modes. Dashboard/catalog sample 100 eligible prompts by newest tree activity, stopping only below the cutoff (ties qualify); hydration is authoritative. Quotas use provider observations, not history; other modes fetch none. Lists analyze requested roots; detail/date project prompts.

`reports/sampling.py` owns both eligibility/cutoff rules; `history.py` owns explicit root/range/limit scopes and incremental Watch-day acquisition. `acquisition.py` coordinates source batches/exact cache proofs; `ReportService` dispatches modes and account/availability overlap. `prompt_rows.py`/`prompts.py` own shared timeline/epoch projection, range/order and totals. No second analyzer or worker.

Dashboard mix includes running/interrupted usage; Relative CCost keeps completed eligibility/count. Both samples admit only prompts with a priceable request (evaluated live against the current catalog, never cached) and use only those requests, so unpriceable history never fills a sample; scans respect both cutoffs. `reports/token_mix_history.py` scans without a ledger, with fail-open filtering and shown-request totals. `presentation/definitions.py` owns definitions; `presentation/model_comparison.py` aligns fields before color. Normal tables have four columns; full-catalog tables add exact USD tiers/boundaries even under fallback. Presentation never recomputes valuation.

`presentation/model_supersession.py`/`AnsiStyler` own conservative displayed-row classification/hue fading, never pricing, sorting, selection, notices or geometry.

V2 availability uses settled global `/api/model` selectable `id`, not `modelID`; empty/partial location boot is not settled. `sources/model_availability.py` rejects controls/malformed shapes and owns CLI compatibility, independently of quotas. Pricing identities are exact or bounded verified dated/context aliases: explicit variant rates/input tiers win, ambiguity stays unknown; no fuzzy Claude suffixes. Failed lookups visibly fail open to the catalog; settled empty stays empty. Highlights follow selection; `--all-models` bypasses availability.

`reports/accounts.py` separates attributed CCost/billing from native capacity/status/balances; visibility/inclusion/percentages never imply history/billing/money. Adapters own `AccountSnapshot.capacity_kind`; errors retain metadata. Projection sorts credit before usage-limit accounts, then casefolded provider/plan/account names and stable identity, never remaining values/timing. `presentation/accounts.py` shares bars/values/resets/warnings: Watch compact/split/vertical, reports native units/money/verbose resets. Remaining is Pace; only paced compact rows omit resets. Watch omits AI-credit conversion; Copilot overage stays a separate limit. No provider rendering branches/gross daily billing; pricing diagnostics are sample-scoped. [Details](../docs/account-support.md).

## Cache

Disposable `cache/` uses generation-named SQLite, WAL, short transactions, 5s busy timeout and explicit close after commit/rollback. Schema changes never migrate/delete in-use generations. JSON carries source/algorithm revisions and bounded coordination, never sole history/credential ownership. Delete only while Cost Guard is stopped. Atomic `model_first_sightings` rows keep shared provider-qualified UTC Report/Watch presentation timestamps.

## Watch

The coordinator owns lifecycle, cadence/rendering and provider refreshes over abstract source/report contracts; lower layers never import Watch. Watch shares `ReportService` analysis/cache/context, never a second billing implementation or recurring subprocess. New Models shares the 12-hour first-sighting accent; existing seven-day eligibility is unchanged.

`watch/token_mix.py` owns run CCost and priced-only Token Mix keyed by source/session/message/step; completed pre-Watch requests stay excluded. `today_ccost.py` reconciles exact local-day requests with shared clone de-duplication, retaining deleted observations without a ledger. Interactive startup renders `Today: Pending` before daily revision/history work. Main-thread slices acquire at most four necessary roots, reuse unchanged stable analysis and publish only after reconciliation. Midnight/DST resets the plan/day; native account publication reuses unchanged local totals. The local date replaces `Today` from 00:00–03:00, with idle redraws. [History acquisition](history-loading.md) owns scopes/evidence.

`WatchSessionSubtotal` sums selected rows' `PromptProjection.ccost` as Decimals, propagating unresolved provenance. Presentation formats `Σ`; native non-billable compactions contribute known zero. Amount/completeness enter change detection. Row subtotals need not partition run totals; no per-session run aggregate exists.

Global Watch selects rows before ordering whole session blocks: history first by latest supported end, active/recent last by latest event start, with ID ties. Tracker reuses its finite recent lifecycle, not marker text, and uses all available block events rather than capped rows. `PromptRowProjector` carries existing analysis terminal/compaction times; unavailable ends fall back to event starts, never observation time/duration. Scoped Watch is unchanged. Group/time changes enter both redraw signatures, including idle expiry. Presentation inserts one conditional table rule and adjusts activity placeholder offsets; [Watch lifecycle](../docs/watch-activity.md) owns the visible contract.

`watch/accounts.py` reconciles full keys and ages observations on every wake (stale after 60s, hard expiry after five minutes, including resume). `watch/account_refresh.py` owns main-thread publication and bounded reconnecting presentation over `AccountRefreshWork`; start signals are idempotent for autonomous acquisition, never a second polling clock. Auth/unavailability bypass retention. `ReportService.project_watch_accounts` projects cached local usage without source I/O. `accounts/quota_observations.py` records bounded run-local percentage/reset observations, success/change/publication times independently of scheduling. `cache/account_refresh_state.py` allowlists latest-writer evidence; Diagnostics separates it from independent report acquisition without identity/credential/response data. [Freshness semantics](../docs/account-support.md#watch-freshness-budget) keep upstream freshness unknown. Prompt success cannot regress to aborted; labels persist while red emphasis decays.

V1 batches payload-free revisions with bounded SQL parameters, never a root cap. V2 hints use a five-second cooldown; disconnect resyncs observed roots plus relevant changes. Startup covers 20 baseline roots plus all active/uncertain candidates regardless of age/row cap, skipping proven stable quiet roots; scoped Watch hydrates its tree and independently accounts for global Today. Changed unrelated old roots do not hydrate the dashboard. Quotas retain independent 30s healthy acquisition/60s freshness semantics. Shared local start epochs, lifecycle and cached source-free quota publication remain intact.

Source recovery retains the last projection and retries only the selected source every 5s (no reselection, subprocess or account refresh). The same coordinator owns unfinished initialization: staged hydration/local-usage acquisition precedes account work; partial state is discarded before fresh retry. V2 refreshes discovery/pools and resumes with authoritative snapshots/new events. Retired SSE readers are cancellable; no OpenCode process is stopped. Schema/auth errors are terminal; unreadable/concurrent data is bounded. Only `WatchedSessionEnded` intentionally ends scoped Watch; Ctrl+C includes initialization.

`sources/connectivity.py` observes complete operations, not harmless compatibility probes; `connectivity_events.py` owns the existing bounded source transition file (24 events/30 days, whitelist/no raw endpoints/auth/payloads). Watch and selection share it; Diagnostics archives without deleting live history. Metadata TLS certificate failures are distinct from other TLS; its existing cache/backoff owner is unchanged.

Watch tool observations use canonical prompt/task scope and one physical-call identity. `watch/tool_contracts.py` owns conservative persisted skill-input/metadata and bounded, known-script result evidence; no source reads, commands, secret discovery or accounting changes. `ToolObservation.skills` projects exact confirmed IDs and direct failure counts. Tracker attaches activity only to each session's latest prompt while it runs or retains its existing terminal marker, then removes rows on marker expiry or same-session supersession. Terminal snapshots retain final counts without live status; the final observation is reused for an unchanged source revision and may update on new authoritative evidence. Presentation adapts tool/skill rows to terminal width independently of fixed metric geometry; [activity contracts](../docs/watch-activity.md) define uncertainty and omissions.

## Presentation and CLI

Presentation renders projections/progress, never integration queries or analysis. One-shot tables shrink flexible text, not identifiers/numbers/costs. Watch retains fixed geometry and one overwriteable status row, including empty-dashboard startup progress. `cost-guard.py` stays thin; `src/bootstrap.py` wires concrete layers.

CLI retains v77 report/Watch argument shapes. Public `windows/|macos/` hold everyday launchers; Diagnostics lives under `development/windows|macos/`. Windows `.cmd` files hand off with `start /b` then exit; `src/windows_launcher.ps1` restores inherited Ctrl+C handling, detects Python 3.11+ and runs the relative entry point. `-NoExit` leaves one usable shell after completion/failure/Ctrl+C, never an Enter-to-close or batch confirmation.

## Dependency direction

```text
bootstrap
  -> config / sources / accounts / pricing / analysis / reports / cache / watch / presentation
sources/accounts/pricing/cache
  -> domain (and narrowly defined lower-level shared contracts), never reports/presentation
analysis
  -> domain + provider-neutral pricing contracts, never reports/presentation
reports
  -> domain + abstract source/account/pricing + analysis/cache, never concrete integrations/presentation/watch
presentation
  -> report projection/domain display types, never concrete integrations
domain
  -> Python standard library only
```

The validator resolves absolute/relative/nested layer imports, rejects runtime→development/fixture→tests edges and V2 process/SQLite use. `code_inventory.py` owns AST resolution/metrics; `structure_guard.py` gates `structure-policy.json`: bounded routines, explained legacy debt, no new test coupling/stale exemptions, explicit module responsibilities. Never auto-rebaseline/grow limits for a feature. [CODE_MAP.md](CODE_MAP.md) owns navigation, not runtime logic; new directions/limits require architectural decisions and matching tests.

## Software-failure boundaries

`cost-guard.py` and Diagnostics guard imports with stdlib-only `src/runtime_errors.py` (only version metadata may cross in). It owns logs/crashes, deduplication/30-day retention, hooks, emergency stderr and the Diagnostics hint. Faults default fatal; isolated owners may expose ERROR and continue. [Failure policy/root audit](runtime-failures.md) owns details; new roots need explicit ownership/tests.

## Diagnostics boundary

`collect_diagnostics.py` composes metadata/statistics-only troubleshooting; local Full/validation failures never suppress its bundle. IDs are hashed; prompts/titles/payloads/auth stay excluded. `diagnostic_watch.py` records fixed mode/generation labels, catalog/revision/cache/hydration/analysis counts, staged startup/refresh/render timings and geometry; `domain/acquisition.py` shares numeric instrumentation. Diagnostics remains runtime output, not a release.
