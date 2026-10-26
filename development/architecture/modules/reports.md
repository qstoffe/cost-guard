# Reports source contracts

Source revision: c982393f29dacdf41560cc3f7c845cab739fdfe6
Checked revision: c982393f29dacdf41560cc3f7c845cab739fdfe6
Last checked: 2026-10-26
Status: current

[Architecture overview](../OVERVIEW.md) · [Owner/test routes](CODE_MAP.md). Source remains authoritative.

## Responsibility and ownership

`src/reports/` owns use cases/neutral projections over abstract sources/providers, analysis and cache; never concrete integrations, Watch or presentation.

Candidate roots are ordered by whole-tree activity, so newly updated child work is not skipped. Hydrated snapshots/analysis remain the semantic authority; session metadata activity is only a bounded discovery gate. Session dominant model is selected by whole-session attributed CCost; listing order is recent tree activity, never cost.

## Public contract

Immutable projections cover dashboard/catalog, lists and detail/date modes. Dashboard/catalog sample 100 eligible prompts by newest tree activity, stopping only below the cutoff (ties qualify); hydration is authoritative. Native quotas use provider observations, never history. Normal account CCost independently acquires relevant local-day/rolling and configured-local calendar-month history; other report modes fetch no accounts. Lists analyze requested roots; detail/date project prompts.

`reports/sampling.py` owns both eligibility/cutoff rules; `history.py` owns explicit root/range/limit scopes and incremental Watch-day/rolling-window acquisition. `acquisition.py` coordinates source batches/exact cache proofs; `ReportService` dispatches modes and account/availability overlap. `prompt_rows.py`/`prompts.py` own shared timeline/epoch projection, range/order and totals. No second analyzer or worker.

Dashboard mix includes running/interrupted usage; Relative CCost keeps completed eligibility/count. Both samples admit only prompts with a priceable request (evaluated live against the current catalog, never cached) and use only those requests, so unpriceable history never fills a sample; scans respect both cutoffs. `reports/token_mix_history.py` scans without a ledger, with fail-open filtering and shown-request totals. `presentation/definitions.py` owns definitions; `presentation/model_comparison.py` aligns fields before color. Normal tables have four columns; full-catalog tables add exact USD tiers/boundaries even under fallback. Presentation never recomputes valuation.

`src/analysis/model_supersession.py` owns shared conservative table-local classification; `presentation/model_supersession.py` retains compatibility exports. CLI hue fading and Web older-stable text/fading consume the same classification, never pricing, sorting, selection or notices.

V2 availability uses settled global `/api/model` selectable `id`, not `modelID`; empty/partial location boot is not settled. `sources/model_availability.py` rejects controls/malformed shapes and owns CLI compatibility, independently of quotas. Pricing identities are exact or bounded verified dated/context aliases: explicit variant rates/input tiers win, ambiguity stays unknown; no fuzzy Claude suffixes. Failed lookups visibly fail open to the catalog; settled empty stays empty. Highlights follow selection; `--all-models` bypasses availability.

`reports/accounts.py` separates attributed CCost/billing from native capacity/status/balances; visibility/inclusion/percentages never imply history/billing/money. Adapters own `AccountSnapshot.capacity_kind`; errors retain metadata. Projection sorts credit before usage-limit accounts, then casefolded provider/plan/account names and stable identity, never remaining values/timing. `presentation/accounts.py` shares bars/values/resets/warnings: Watch compact/split/vertical, reports native units/money/verbose resets. Remaining is Pace; only paced compact rows omit resets. Watch omits AI-credit conversion; Copilot overage stays a separate limit. No gross daily billing; pricing diagnostics are sample-scoped. [Details](../../../docs/account-support.md).


`src/analysis/period_ccost.py` owns canonical provider aliases (never model publishers), validated reset/trailing-window bounds, shared incomplete-telemetry reconciliation and deduplicated valuation prefix indexes. `src/reports/accounts.py` permits unassigned provider estimates only for one compatible detected account; multiple accounts stay unknown, with provider totals retained in projection notes but not printed as account prose. Proven history from another account is never reassigned. Calendar-month scopes are independent of overlapping windows and never appear in Watch. Indexed quota publication performs no source I/O or repeated history valuation. `ReportService` supplies the existing acquired range through `observed_start_ms`; an empty period becomes zero only when that range covers its start, never from account-attribution capability alone. Watch uses only a published current-day history range. Missing history, unknown window bounds and ambiguous requests remain unknown. `presentation/accounts.py` owns account-only zero/unknown notation (`0`, `—`) and the known priced subtotal with ordinary upward rounding and no partial marker (missing prices may understate complete valuation), rolling CCost inline on quota rows, and numeric today/month report rows without provenance prose or a footer. Global partial markers and layer dependencies are unchanged.

Normal Copilot reports additionally reconcile native used AI credits against the same indexed valuation for a supported fixed UTC calendar month, validated from the provider reset. The normal account history scope extends through that native start when earlier than the local month; Watch acquisition is unchanged. `AccountProjection.unaccounted_usage` remains unknown unless native usage, current monthly bounds, full acquisition, pricing and account attribution are sufficient. This signed residual is an estimate, not external-use attribution or billing. Existing partial account subtotals remain independent. Presentation adds exactly one normal-report row per Copilot account, including unknown values.

## Transport-neutral application boundary and parity inventory

`src/application/service.py` owns isolated one-shot jobs: `ReportApplication(factory, clock=...)`, then `execute(ReportRequest, progress=...)`. The composition root must transfer a **fresh** `ReportService` per call using canonical sources, validated config, pricing/cache and account providers. It must not pass the live scheduler or share mutable source/provider context with another owner. No CLI subprocess, web import, alternate analysis or account scheduler is involved. A nonblocking serialized owner rejects concurrent/reentrant requests with `busy`; the host owns admission bounds/retry. The factory owns any extra resources outside ReportService. Every admitted job closes its accounts, including acquisition/projection failures; live/already-owned services are rejected without closing foreign work. Services cannot be reused across jobs. A future live host must retain its own scheduler and publish immutable snapshots rather than passing it here.

`src/application/contracts.py` defines frozen result/error/progress DTOs and detached JSON export. `src/application/projection.py` explicitly selects known fields, never introspects/dumps arbitrary dataclasses. Decimal amounts/ratios are exact strings; null, zero, incomplete coverage, provisional status and existing precomputed shares/warnings stay distinct. Consumers sort/display values without revaluing usage. Scope includes configured timezone, local day/month starts, resolved date bounds, history policy and **report execution** duration, not Watch duration.

Schema version and application instance UUID are separate from per-request-view sequence and hashed per-root source revisions. A result is immutable; source acquisition ensures each root snapshot, **not a transaction across roots/accounts/providers**. Account observations retain their own timestamp/status/availability and safe classified error facts. Source errors return a typed code/retryability and no empty-success view. Only safe progress phase/counts cross the boundary, not labels containing identifiers or exception text. Expected pricing unavailability and missing targets are distinct from logged unexpected defects; internal errors discard the whole view as `internal_error`, never raw transport messages. Cleanup faults propagate. Account locators and revisions use opaque hashes; raw provider observations, arbitrary reasons/warnings and pricing diagnostics are not exported. Session titles/previews remain intentional user content, so this is not a public/anonymous data feed. The optional `src/web/` adapter now owns HTTP authorization/security and process-level finite-job admission; see [Web](web.md).

| Existing mode | Application request / published view | Scope and protected parity |
| --- | --- | --- |
| Normal | NORMAL / model comparison, Token Mix, accounts/quotas | Existing two 100-priceable-prompt samples; account-period acquisition independent; CCost is reference value, not billing |
| All models | ALL_MODELS / model comparison, Token Mix | Same comparison eligibility, no selectable filter or accounts |
| Session list | SESSIONS / session_usage | Requested root limit or all; whole-tree cost, completeness and report duration; archived history retained |
| Session detail | SESSION / prompt_blocks, request_identities | Complete requested root/child tree, stable event/message/part references and opaque request key; no global Watch cap; inherited FR000200 running metrics |
| Date/range | DATE / prompt_blocks | Configured-local inclusive date target mapped to exclusive end; DST, context and duration remain existing semantics |
| Historical Token Mix | TOKEN_MIX / model_token_mix and total | Separate deep all-available-history method, not build's dashboard fallback; existing availability fail-open behavior; no request rows or promise to recover pruned history |

The [Web route inventory](../../../docs/web-beta.md#navigation-and-static-reports) maps every mode to a delivered view; native/visual acceptance remains separate. Deep-history cache regression proves source/config/pricing invalidation and immutable reuse. `development/tests/test_application_reports.py` compares numerical/status/identity fields to the existing service using shared canonical fixtures (running/completed/aborted, child work, compaction, missing telemetry/prices, subscription evidence), native V1/current V2, DST and independent account errors/freshness. It covers 151-prompt uncapped detail and cloned-request deduplication, immutable exact export, typed source failures, fresh-job/reentrancy ownership, repeated cleanup, and CLI help/version plus Diagnostics import with application/web dependencies blocked. Existing report/Watch tests remain the semantic owners. No new permanent release gate, server, browser, launcher or dependency is added.

## Allowed dependencies

Reports depend on canonical domain, analysis, cache and abstract source/account/pricing contracts, never Watch, presentation or concrete adapters. Period analysis depends on domain and provider-neutral pricing/valuation only.

## Entrypoints

`src/application/service.py`, `src/application/contracts.py`, `src/application/projection.py`; `src/reports/service.py`, `src/reports/accounts.py`, `src/reports/history.py`, `src/analysis/period_ccost.py`; account rendering: `src/presentation/accounts.py`.

## Tests

`development/tests/test_application_reports.py`, `development/tests/test_account_period_ccost.py`, `development/tests/test_copilot_unaccounted_usage.py`, `development/tests/test_accounts_ccost.py`, `development/tests/test_report_sampling.py`, `development/tests/test_history_loading.py`, `development/tests/test_step7_reports_cli.py`, `development/tests/test_quota_presentation.py`.
