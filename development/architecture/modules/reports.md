# Reports source contracts

Source revision: 1b0fd64375bfc10c6653dda86dea41e2d0c1eb88
Checked revision: 1b0fd64375bfc10c6653dda86dea41e2d0c1eb88
Last checked: 2026-10-29
Status: current

[Architecture overview](../OVERVIEW.md) · [Owner/test routes](CODE_MAP.md). Source remains authoritative.

## Responsibility and ownership

`src/reports/` owns use cases/neutral projections over abstract sources/providers, analysis and cache; never concrete integrations, Watch or presentation.

Candidate roots are ordered by whole-tree activity, so newly updated child work is not skipped. Hydrated snapshots/analysis remain the semantic authority; session metadata activity is only a bounded discovery gate. Session dominant model is selected by whole-session attributed CCost; listing order is recent tree activity, never cost.

## Public contract

FR 000534 updates the comparison policy below in the same delivery; module boundaries are unchanged.

Immutable projections cover dashboard/catalog, lists and detail/date. Global latest-100 samples stop below whole-tree activity cutoffs (ties qualify); historical Token Mix has an independent deep scope below. Hydration is authoritative. Quotas remain native observations; normal account CCost independently loads local-day/rolling/month history. Other modes fetch no accounts. Lists hydrate requested roots; detail/date project prompts. Web pages reject catalog membership/order revision drift and report truthful root totals, but row observations are per-page, not cross-page transactions; sorting/filtering stays page-local.

`reports/sampling.py` owns both eligibility/cutoff rules; `history.py` owns explicit root/range/limit scopes and incremental Watch-day/rolling-window acquisition. `acquisition.py` coordinates source batches/exact cache proofs; `ReportService` dispatches modes and account/availability overlap. `prompt_rows.py`/`prompts.py` own shared timeline/epoch projection, range/order and totals. No second analyzer or worker.

Dashboard usage mix stays latest-100, including running/interrupted priceable usage. Relative CCost independently uses the latest up to 100 completed priceable prompts globally through `latest_prompts` and `_relative_usage`. Pooled I/C/W/O shares price every model/tier; warnings reuse that same global mix for the existing 15-minute observation window. Ordinary model lists no longer call `src/reports/comparison_history.py` or acquire deep per-model samples. The retained compact evidence helpers are not the model-list pricing policy. `src/pricing/publishers.py` resolves catalog manufacturers, never request/account routes. `src/reports/token_mix_history.py` separately groups the same availability-filtered historical requests by model and publisher, with pooled shares, distinct per-group prompts, absolute Tokens and original per-request CCost. Prompt counts are not additive. Immutable report/application projections export the actual global comparison sample size and publisher rows; CLI/Web render, never revalue. Web history stays explicit/cancellable; collapsed comparison help and model tooltips describe the shared sample. Exact tiers, promotions, no-history sorting and accounts stay unchanged.

`src/analysis/model_supersession.py` shares table-local classification with CLI/Web. `presentation/model_supersession.py` is a compatibility export. Fading/older-stable text never changes valuation, ordering or notices.

V2 availability uses settled global `/api/model` selectable `id`, not `modelID`; empty/partial location boot is not settled. `sources/model_availability.py` rejects controls/malformed shapes and owns CLI compatibility, independently of quotas. Pricing identities are exact or bounded verified dated/context aliases: explicit variant rates/input tiers win, ambiguity stays unknown; no fuzzy Claude suffixes. Failed lookups visibly fail open to the catalog; settled empty stays empty. Highlights follow selection; `--all-models` bypasses availability.

`reports/accounts.py` separates CCost/billing from native capacity/status/balances; percentages never imply history or money. Adapters own capacity kind. Accounts sort credit before usage-limit, then casefolded provider/plan/account identity, never remaining/timing. `presentation/accounts.py` shares bars, resets and warnings between Watch and reports; Pace replaces resets only on paced compact rows. Watch omits AI-credit conversion; Copilot overage stays distinct. Pricing diagnostics remain sample-scoped. [Account details](../../../docs/account-support.md).


`src/analysis/period_ccost.py` owns canonical provider aliases (never model publishers), validated reset/trailing-window bounds, shared incomplete-telemetry reconciliation and deduplicated valuation prefix indexes. `src/reports/accounts.py` permits unassigned provider estimates only for one compatible detected account; multiple accounts stay unknown, with provider totals retained in projection notes but not printed as account prose. Proven history from another account is never reassigned. Calendar-month scopes are independent of overlapping windows and never appear in Watch. Indexed quota publication performs no source I/O or repeated history valuation. `ReportService` supplies the existing acquired range through `observed_start_ms`; an empty period becomes zero only when that range covers its start, never from account-attribution capability alone. Watch uses only a published current-day history range. Missing history, unknown window bounds and ambiguous requests remain unknown. `presentation/accounts.py` owns account-only zero/unknown notation (`0`, `—`) and the known priced subtotal with ordinary upward rounding and no partial marker (missing prices may understate complete valuation), rolling CCost inline on quota rows, and numeric today/month report rows without provenance prose or a footer. Global partial markers and layer dependencies are unchanged.

Normal Copilot reports reconcile native used credits with indexed CCost over a validated fixed UTC month; normal history extends through that start if earlier than the local month. `AccountProjection.unaccounted_usage` stays unknown without sufficient native usage/bounds/acquisition/pricing/attribution. The signed estimate is not billing or proven external use. Existing partial subtotals and Watch stay independent; presentation adds one report-only Copilot row, including unknowns.

## Transport-neutral application boundary and parity inventory

`src/application/service.py` owns isolated one-shot jobs: `ReportApplication(factory, clock=...)`, then `execute(ReportRequest, progress=...)`. The composition root must transfer a **fresh** `ReportService` per call using canonical sources, validated config, pricing/cache and account providers. It must not pass the live scheduler or share mutable source/provider context with another owner. No CLI subprocess, web import, alternate analysis or account scheduler is involved. A nonblocking serialized owner rejects concurrent/reentrant requests with `busy`; the host owns admission bounds/retry. The factory owns any extra resources outside ReportService. Every admitted job closes its accounts, including acquisition/projection failures; live/already-owned services are rejected without closing foreign work. Services cannot be reused across jobs. Live retains its own scheduler and exports immutable snapshots.

`src/application/contracts.py` defines frozen result/error/progress DTOs and detached JSON export. `src/application/projection.py` explicitly selects known fields, never introspects/dumps arbitrary dataclasses. Decimal amounts/ratios are exact strings; null, zero, incomplete coverage, provisional status and existing precomputed shares/warnings stay distinct. Consumers sort/display values without revaluing usage. Scope includes configured timezone, local day/month starts, resolved date bounds, history policy and **report execution** duration, not Watch duration.

Schema version and application instance UUID are separate from per-request-view sequence and hashed per-root source revisions. A result is immutable; source acquisition ensures each root snapshot, **not a transaction across roots/accounts/providers**. Account observations retain their own timestamp/status/availability and safe classified error facts. Source errors return a typed code/retryability and no empty-success view. Only safe progress phase/counts cross the boundary, not labels containing identifiers or exception text. Expected pricing unavailability and missing targets are distinct from logged unexpected defects; internal errors discard the whole view as `internal_error`, never raw transport messages. Cleanup faults propagate. Account locators and revisions use opaque hashes; raw provider observations, arbitrary reasons/warnings and pricing diagnostics are not exported. Session titles/previews remain intentional user content, so this is not a public/anonymous data feed. The optional `src/web/` adapter now owns HTTP authorization/security and process-level finite-job admission; see [Web](web.md).

| Existing mode | Application request / published view | Scope and protected parity |
| --- | --- | --- |
| Normal | NORMAL / model comparison, Token Mix, accounts/quotas | One global latest-up-to-100 completed-prompt comparison mix and independent latest-100 usage; account-period acquisition independent; CCost is reference value, not billing. Full root revision evidence remains; unused month-wide request identities are not exported. |
| All models | ALL_MODELS / model comparison, Token Mix | Same comparison eligibility, no selectable filter or accounts |
| Session list | SESSIONS / session_usage | Limit/all or bounded revision-checked page; whole-tree cost, completeness, archived/running flags and report duration |
| Session detail | SESSION / prompt_blocks, request_identities | Complete requested root/child tree, stable event/message/part references and opaque request key; no global Watch cap; inherited FR000200 running metrics |
| Date/range | DATE / prompt_blocks | Configured-local inclusive date target mapped to exclusive end; DST, context and duration remain existing semantics |
| Historical Token Mix | TOKEN_MIX / model_token_mix, publisher_token_mix and total | Separate deep all-available-history method, not build's dashboard fallback; existing availability fail-open behavior; no request rows or promise to recover pruned history |

The [Web route inventory](../../../docs/web-beta.md#navigation-and-static-reports) maps views; visual/native acceptance is separate. Application tests pin canonical V1/V2 lifecycle/child/compaction/partial, timezone/account-error, uncapped detail, deduplication, immutable export and typed-failure parity. Fresh ownership, cleanup and forbidden application/Web imports in CLI/Diagnostics remain covered. Focused workload/history tests cover revision/catalog invalidation, deletion and publisher totals; no new dependency or permanent gate.

Historical model/publisher `Tokens` reuse `TokenMix.total_tokens` and its exact `known_total_tokens` subtotal, accumulated during the existing category pass. Incomplete telemetry keeps shares/complete totals unknown while retaining known-category volume (including reasoning). The application exports the subtotal as an exact decimal string for Web sorting, independent of compact Python display tokens and price completeness. Narrow CLI falls back to labeled metrics; Web retains its keyboard-scrollable tables. No acquisition, publisher, analysis-layer or account boundary changes. [Volume evidence](../governance/verification/historical-token-volumes.md).

## Allowed dependencies

Reports depend on canonical domain, analysis, cache and abstract source/account/pricing contracts, never Watch, presentation or concrete adapters. Period analysis depends on domain and provider-neutral pricing/valuation only.

## Entrypoints

`src/application/service.py`, `src/application/contracts.py`, `src/application/projection.py`; `src/reports/service.py`, `src/reports/accounts.py`, `src/reports/history.py`, `src/analysis/period_ccost.py`; account rendering: `src/presentation/accounts.py`.

## Tests

`development/tests/test_workload_mix.py`, `development/tests/test_application_reports.py`, `development/tests/test_account_period_ccost.py`, `development/tests/test_copilot_unaccounted_usage.py`, `development/tests/test_accounts_ccost.py`, `development/tests/test_report_sampling.py`, `development/tests/test_history_loading.py`, `development/tests/test_step7_reports_cli.py`, `development/tests/test_quota_presentation.py`, `development/tests/test_session_list_pages.py`. Page/browser/native evidence: `development/architecture/governance/verification/sessions-pagination.md`.

[FR 000521 evidence](../governance/verification/model-publisher-mix.md).
