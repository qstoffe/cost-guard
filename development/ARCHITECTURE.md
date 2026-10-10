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

`src/sources/opencode_errors.py` is the shared V1/V2 native error boundary. Known cancellation identifiers and bounded message forms in top-level/data error fields normalize to canonical `AbortedError`; arbitrary payload/stack substring matches are not cancellation evidence. Analysis uses the terminal logical attempt, never lets zero usage override an explicit generic error, and retains terminal errors with missing usage. Watch's persistent aborted label and transient emphasis remain separate presentation/lifecycle concerns.

### OpenCode V1 boundary

`src/sources/opencode_v1.py` alone knows the legacy V1 SQLite projection. Process-free discovery honors `OPENCODE_DB`, else the standard XDG data location. It validates the required `session`/`message`/`part` columns, opens SQLite `mode=ro` plus `PRAGMA query_only=ON`, and never starts the OpenCode CLI.

Hydration reads a root and its recursive descendants in one pinned read transaction, normalizing them into canonical sessions, messages, parts, events and invocations. `step-finish` parts, when present, replace cumulative assistant-message tokens/cost. Native message/part structure survives only through canonical types that compaction/tool/context analysis needs.

`get_session_tree_revision()` hashes tree membership plus compact session/message/part counts, timestamps and IDs without parsing JSON. Unchanged `session.time_updated` cannot hide descendant/message changes; this cheap cache/change gate is never business truth.

### OpenCode V2 boundary

`opencode_v2_transport.py` owns stdlib HTTP/SSE (pooled keep-alive JSON GETs, one retry on a service-closed idle socket, privacy-safe counters), `opencode_v2_wire.py` wire compatibility, `opencode_v2_normalization.py` pure message/part/request mapping with injected provenance, and `opencode_v2.py` acquisition/revision/snapshot assembly. Discovery reads standard registration, validates loopback, ignores proxies and probes `/api/info`. No auth logging, V2 SQLite or CLI/subprocess.

Global discovery uses cursor-paginated sessions, falling back to project enumeration/de-duplication. Current and transitional message APIs share canonical V1/V2 session/message/part/event/invocation contracts; synthetic histories verify semantic parity.

The adapter caches the latest complete V2 session catalog in-process, avoiding `N roots × all projects` listing. Discovery/resync replaces it; live events invalidate it. This is change-gating input, never durable truth. A snapshot's tree revision must match before and after its message reads; a complete catalog at most 2s old may be the before bracket (a mismatch then gets two fresh attempts); repeated instability fails rather than persisting mixed generations.

`opencode_v2_wire.py` binds qualified persisted `idle` outcomes to the preceding assistant as neutral `TerminalEvidence`. Intervening boundaries, ambiguous timestamps or later tool work block attribution. Status/inactivity/transport failure alone proves no end. Native completion/usage/billing stays unchanged; Diagnostics counts terminal evidence separately. Path-free `location-switched` items become `SessionSnapshot.context_boundaries`: never usage; they retire a Next-Ictx anchor not yet followed by a request. `opencode_v2_background.py` maps background jobs/completion notices to neutral `BackgroundActivity`/`BACKGROUND_COMPLETION`; a job without notice runs until its location's shell registry drops it.

`/api/event` is a non-replaying live hint; stream end, disconnect or failure requires an authoritative snapshot before live state is trusted again.

### Source selection and migration-gap diagnostics

`src/sources/selection.py` selects process-free `auto|v1|v2`: healthy V2 first, otherwise healthy V1. Forced generations never silently fall back. Unhealthy V2 fallback warns; normal V1-only installations do not. Only `src/bootstrap.py` owns one-time CLI service wake after selection failure.
After failed selection/wake, Watch retries process-free selection every five seconds, constructing reports/coordinator only once healthy. Reports fail promptly: installation wording requires no PATH CLI and no standard filesystem evidence; otherwise retain source errors. Healthy V1 auto-selection never switches later.

With V2 selected and readable V1 metadata, a best-effort metadata-only diagnostic finds V1 sessions missing from V2 or newer than their V2 copy, without merged hydration, source changes or OpenCode writes. It is evidence, not a source warning: each gap carries its V1 root and possibly unrepresented activity window; `reports/migration_notice.py` notes it only when that window meets the report scope (sample cutoff, dates, requested root, all history). Watch never shows it; Diagnostics keeps full counts.

## Account and Pricing Providers

These are intentionally separate roles.

- **Account Provider:** account/subscription quota, usage windows, balances and reset metadata.
- **Pricing Provider:** model price/rate metadata used for repricing/comparison/fallback valuation.

`accounts/credentials.py` reads only the selected installation: V2 wins per integration, legacy applies without V2 rows, explicit overrides are file-only, read errors fail closed and secrets stay memory-only. Proven account IDs/source locators distinguish accounts, never provider alone; inactive quota visibility changes neither inference nor history.

`accounts/discovery.py` shares source/WAL views; other identities retain probes. `accounts/acquisition.py` owns four daemon workers, sequences/45s deadlines and nonblocking close. Callers alone apply results; expired generations are discarded, stuck slots never multiply. Workers cannot render or mutate analysis/persistence. Reports overlap analysis (15s final wait); Watch publishes individually without startup HTTPS. Only observations advance timestamps; all exits close workers. [Account contracts](simple-http-accounts.md) own details.

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

`TokenUsage.known_fields` preserves telemetry availability through normalization/cache; absent/null/malformed fields stay unknown. `analysis/token_mix.py` sums volume, folds reasoning into O, apportions 100% and hides shares for unknown denominators. Category CCost reconciles with `comparison_cost`; model rows use reference identity, unique prompts/all calls. `analysis/quota_pace.py` uses fixed-period remaining/reset and workdays, never session state.

`src/domain/accounts.py` owns source-aware `AccountRef`, flexible `QuotaComponent`, `BillingComponent` and `AccountSnapshot`. A request may carry an optional proven account reference. Current-login identity never fills historical request gaps. `src/domain/` must not import concrete source/account/pricing/cache/watch/presentation implementations.

`domain/session_tree.py` shares catalog ancestry/tree activity, never acquisition/attribution. Missing ancestors/cycles terminate without invented records; missing ancestry cannot resolve detail targets. Reports retain archived history; Watch excludes archived roots.

`domain/ccost.py` owns reference conversion (100 CCost/USD), `CCostPricing` and valuation contracts. Catalog `models` remain native monetary metadata; immutable `ccost_models` are converted once before reference usage/category/context/comparison analysis, never billing fallback. Unknown currencies are unpriceable, not guessed FX. CCost is Copilot AI-credit-equivalent reference value, not deduction/billing; projections use explicit CCost fields.

`numbers.py` owns display rounding: upward CCost/consumption, downward Remaining, exact rates/limits, no grouping; analysis never calls it. `version.mode_heading` owns startup grammar, CLI modes, progress transient rows. Reports align all quota labels; Watch only primary labels.

## Analysis

`src/analysis/` owns attribution, prompt/child/synthetic/compaction semantics, clone billing de-duplication, context and comparisons over canonical domain/provider-neutral abstractions only.

Usage/billing consumes all canonical providers: V2 `openai` requests must not disappear because pricing/quota integrations are Copilot-backed. Positive provider-reported cost stays authoritative; fallback and quota are separate capabilities. Provider filters are explicit lower-level/testing scopes only, never default report truth.

The causal core uses `TraceEntry`, `PromptRecord`, `CompactionRecord` and `RootAnalysisBundle`. Billing retains reported/included/fallback provenance. `analysis/valuation.py` independently derives `ComparisonCost` via reference estimation and actual `billed_spend`, never substituting fallback prices. Subscription CCost exposes priced/observed coverage, never billed dollars for unsupported models. `ReportService` may take a separate comparison catalog provider. Exact catalog identities prevent fuzzy CCost matches; clone de-duplication retains source-instance provenance. Root-first provenance reconciles main/subagent CCost before rounding.

Context/comparison consumes canonical messages/parts/invocations. Compaction summary/tail is resulting context; exact V2 usage wins. Prompt/compaction shares one chronological Delta baseline. Next-Ictx never predicts cache hits; structured severity reaches both projections with live expiry. Comparison prices each published tier under the same 100-completed-prompt mix and cheapest base reference. One full-Decimal sorter orders base/next-tier prices descending, earlier increase boundaries, then name, recursively for later tiers. Without samples, hidden 2/96/1/1 sorts while Relative CCost stays blank. Diagnostics never feed billing.

Derived analysis is cacheable only for stable complete snapshots. Cache reuse requires exact source revision, analysis algorithm version, config signature and pricing signature. Malformed/incompatible cache state is a miss; running or incomplete roots are never persisted. Source revisions remain conservative gates, not semantic truth.

Dates use `zoneinfo`; clean Windows Python may lack IANA data, so dependency-free current rules cover shipped `Europe/Stockholm` and UTC. Other IANA zones fail actionably without host data; never substitute local time.

`analysis/effort.py` distinguishes explicit, request-proven/unresolved Default and unattributable effort. Only matching root requests resolve Default, never model/pricing maps or mutable session selection; V2 never stamps session effort onto history. Renderers share one label (no `Default -> X`); compaction uses its own explicit variant.

The latest assistant's `termination` ends running/duration and distinguishes success/failure/cancellation, even without usage. Actual root/child or newer tool activity stays live; stale tool flags do not. Reports/Watch/resync share this truth. Running background work keeps the newest prompt active without usage; resumes stay on it. Incomplete inference stays uncached; older algorithm keys are invalidated.

## Reports

`src/reports/` owns use cases/neutral projections over abstract sources/providers, analysis and cache; never concrete integrations, Watch or presentation.

Candidate roots are ordered by whole-tree activity, so newly updated child work is not skipped. Hydrated snapshots/analysis remain the semantic authority; session metadata activity is only a bounded discovery gate. Session dominant model is selected by whole-session attributed CCost; listing order is recent tree activity, never cost.

Immutable projections cover dashboard/catalog, lists and detail/date modes. Dashboard/catalog sample 100 eligible prompts by newest tree activity, stopping only below the cutoff (ties qualify); hydration is authoritative. Quotas use provider observations, not history; other modes fetch none. Lists analyze requested roots; detail/date project prompts.

`reports/sampling.py` owns comparison/token eligibility and cutoffs. `ReportService` keeps acquisition/cache/account work with focused `_build_*` mode methods; dashboards overlap account and availability I/O with analysis. `prompt_rows.py` projects prompt/compaction rows using one shared timeline/epoch scope; `prompts.py` owns range/order, coherent Watch deltas and block totals. No second analysis or worker implementation.

Dashboard mix includes running/interrupted usage; Relative CCost keeps completed eligibility/count. Scans respect both cutoffs. `reports/token_mix_history.py` scans without a ledger, with fail-open filtering and shown-request totals. `presentation/definitions.py` owns definitions; `presentation/model_comparison.py` aligns fields before color. Normal tables have four columns; full-catalog tables add exact USD tiers/boundaries even under fallback. Presentation never recomputes valuation.

`presentation/model_supersession.py`/`AnsiStyler` own conservative displayed-row classification/hue fading, never pricing, sorting, selection, notices or geometry.

V2 availability uses settled global `/api/model` selectable `id`, not `modelID`; empty/partial location boot is not settled. `sources/model_availability.py` rejects controls/malformed shapes and owns CLI compatibility, independently of quotas. Pricing identities are exact or bounded verified dated/context aliases: explicit variant rates/input tiers win, ambiguity stays unknown; no fuzzy Claude suffixes. Failed lookups visibly fail open to the catalog; settled empty stays empty. Highlights follow selection; `--all-models` bypasses availability.

`reports/accounts.py` separates attributed CCost/billing from native dashboard capacity/status/balances: visibility never attributes history, inclusion never proves billing, percentages never imply money. `presentation/accounts.py` shares bars/alignment, native values, resets and warnings; Watch uses compact/split/vertical fallback, reports retain units/money/verbose resets. Remaining is unchanged Pace; only paced compact rows omit duplicate resets. Watch omits AI-credit conversion; Copilot overage is a separate limit, not balance/Remaining. No provider renderer branches or gross daily billing. [Account presentation](../docs/account-support.md) owns details; pricing diagnostics stay sample-scoped.

## Cache

Disposable `cache/` uses generation-named SQLite, WAL, short transactions, 5s busy timeout and explicit close after commit/rollback. Schema changes never migrate/delete in-use generations. JSON carries source/algorithm revisions and bounded coordination, never sole history/credential ownership. Delete only while Cost Guard is stopped.

## Watch

The coordinator owns lifecycle, cadence/rendering and provider refreshes over abstract source/report contracts; lower layers never import Watch. Watch shares `ReportService` analysis/cache/context, never a second billing implementation or recurring subprocess.

`watch/token_mix.py` owns run-scoped `Watch total CCost`/`Token Mix %`, keyed by source/session/message/step. Completed pre-Watch requests are excluded. Updates replace usage; steps replace message fallback. Eviction/completion/removal/countdown/resync retain observations until exit; new coordinators start empty. No account queries or persisted ledger.

`WatchSessionSubtotal` sums selected rows' `PromptProjection.ccost` as Decimals, propagating unresolved provenance. Presentation formats `Σ`; native non-billable compactions contribute known zero. Amount/completeness enter change detection. Row subtotals need not partition run totals; no per-session run aggregate exists.

`watch/accounts.py` reconciles full account keys; `watch/account_refresh.py` owns publication/cadence/retry state over `AccountRefreshWork`, not hydration/rendering. Stale TTL is five minutes. Unobserved waits (>90s plus cadence) or first errors allow 60s grace and 5/10/20s retries; processing is excluded. Monotonic deadlines bound recovery; retention/expiry never advance successful-seen timestamps, and auth/unavailability bypasses it. Success/expiry clears recovery. Prompt success cannot regress to aborted; labels persist while red emphasis decays.

V1 batches root revisions in one recursive SQLite query without payload parsing. V2 hints use a five-second cooldown; disconnect forces resync, which re-reads every hydrated root plus changed revisions. Native active-session/tool state proves liveness. Startup discovery covers 20 roots independent of the row cap (default 14), skipping roots whose stable cached analysis (never running work) has nothing since Watch start; a session Watch always hydrates its root. Quota refresh is independent of source activity: normally once per minute, with bounded resume retries. Local quota projection may refresh without another provider request.

Source recovery retains the last projection and retries only the selected source every 5s (no reselection, subprocess or account refresh); V2 resumes with a fresh snapshot/event pump and rereads rewritten registration. Schema errors are terminal; unreadable data is bounded. Only `WatchedSessionEnded` intentionally ends an existing scoped Watch; unexpected errors reach bootstrap non-zero. Ctrl+C is intentional, including initialization.

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

`development/tools/collect_diagnostics.py` composes public runtime boundaries for metadata/statistics-only troubleshooting. Locally it runs Full + package validation with progress; failures never suppress the ZIP. IDs are hashed; prompts/titles/raw payloads/auth are excluded. Siblings own logs/ZIP, metadata, the result screen and `diagnostic_watch.py` (numbers-only headless Watch timings/hydration/render geometry, terminal facts); `diagnostics/` is runtime output.
