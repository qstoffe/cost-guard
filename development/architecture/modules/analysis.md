# Analysis source contracts

[Architecture overview](../OVERVIEW.md) · [Owner/test routes](CODE_MAP.md). Source remains authoritative.

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

Context/comparison consumes canonical messages/parts/invocations. `analysis/context_history.py` separates request-local input from persisted history; unsupported decreases stay unknown. `estimate_event_context` preserves historical completion estimates independently of current anchor retirement. Model-selection boundaries allow historical comparison only with compatible telemetry and complete retained same-model history; resets remain separate epochs. Accounting stays independent. Completed compaction owns its summary/tail and negative delta. Next-Ictx never predicts cache hits; current warnings require eligible anchors. Comparison prices each tier under one 100-completed-prompt mix and cheapest base reference. Full-Decimal sorting orders base/next-tier prices descending, earlier boundaries, then name, recursively. Without samples, hidden 2/96/1/1 sorts while Relative CCost stays blank. Diagnostics never feed billing.

Stable complete analysis requires exact source revision, algorithm/config compatibility and a semantic pricing signature (identities/aliases, currency, rates/tiers), not retrieval timestamps/document labels. Malformed/incompatible, running or incomplete results never persist. Revisions remain conservative gates, not semantic truth.

Dates use `zoneinfo`; clean Windows Python may lack IANA data, so dependency-free current rules cover shipped `Europe/Stockholm` and UTC. Other IANA zones fail actionably without host data; never substitute local time.

`analysis/effort.py` distinguishes explicit, request-proven/unresolved Default and unattributable effort. Only matching root requests resolve Default, never model/pricing maps or mutable session selection; V2 never stamps session effort onto history. Renderers share one label (no `Default -> X`); compaction uses its own explicit variant.

The latest assistant's `termination` ends running/duration and distinguishes success/failure/cancellation, even without usage. Actual root/child or newer tool activity stays live; stale tool flags do not. Reports/Watch/resync share this truth. Running background work keeps the newest prompt active without usage; resumes stay on it. Incomplete inference stays uncached; older algorithm keys are invalidated.

`analysis/duration.py` qualifies retrospective execution boundaries from normalized assistant/tool/background evidence, never session metadata or report time for terminated work. `PromptRecord.execution_duration_ms` and compaction timing survive derived caching; the legacy prompt `duration_ms` remains unchanged for Watch. Reports project qualified timing into `PromptProjection.duration_ms`; listings union the cached bundle directly, without detail hydration. A sorted interval union excludes idle gaps/overlap and propagates unknown timing to `N/A`; date totals union only selected events. Presentation shares Watch's compact formatter, not timing calculations.

## Cache

Disposable `cache/` uses generation-named SQLite, WAL, short transactions, 5s busy timeout and explicit close after commit/rollback. Schema changes never migrate/delete in-use generations. JSON carries source/algorithm revisions and bounded coordination, never sole history/credential ownership. Delete only while Cost Guard is stopped. Atomic `model_first_sightings` rows keep shared provider-qualified UTC Report/Watch presentation timestamps.

