# Reports source contracts

Source revision: e4d715e170917f5ef2d69d31a68dbc3eb297ff8a
Checked revision: e4d715e170917f5ef2d69d31a68dbc3eb297ff8a
Last checked: 2026-11-06
Status: current

[Architecture overview](../OVERVIEW.md) · [Owner/test routes](CODE_MAP.md). Source remains authoritative.

FR000614 renews only the AI Stats delta below against `d381d399f401c24302fa559eb62ec68e33aba4e7`;
other sections retain their prior scoped checks, not a whole-module audit.

## Responsibility and ownership

`src/reports/` owns use cases/neutral projections over abstract sources/providers, analysis and cache; never concrete integrations, Watch or presentation.

Candidate roots are ordered by whole-tree activity. Hydrated snapshots/analysis remain the semantic authority; metadata is not temporal exclusion proof for AI Stats, whose unknown roots remain candidates in every period. Other reports retain their scoped discovery rules. Session dominant model is selected by whole-session attributed CCost; listing order is recent tree activity, never cost.

## Public contract

FR000658: `matched_inputs.py` emits actual comparison verification/groups/previews
stages while preserving all-history revision/index checks and ephemeral page-only
preview hydration. No offset-only or unqualified pinned-index cache is added.
`application/service.py` exports rejected pinned Comparisons catalog revisions as
terminal for that immutable request; the browser owns its deliberate unpinned rebase.
Other reports and healthy managed continuations keep their existing recovery policy.
[Evidence and source-churn limits](../../journal/web/paging-navigation.md).

FR000629 scoped delta (2026-11-09): Sessions, prompt/effort/compaction projections
and Token Mix share `PricingCatalog.display_name` with the actual request provider.
Unresolved alias groups retain provider-qualified keys and unknown publisher evidence.
Comparisons exports `model_label` from the same identity rule alongside unchanged
raw provider/model/contributor IDs; the browser never resolves aliases. Full/Mini
Watch and CLI consume canonical projections. Persisted repair follows the
[analysis contract](analysis.md#session-cache-lifecycle-fr-000626), not UI-only substitution.

FR 000534 updates the comparison policy below in the same delivery; module boundaries are unchanged.

Immutable projections cover dashboard/catalog, lists and detail/date. Global latest-100 samples stop below whole-tree activity cutoffs (ties qualify); historical Token Mix has an independent deep scope below. Hydration is authoritative. Quotas remain native observations; normal account CCost independently loads local-day/rolling/month history. Other modes fetch no accounts. Lists hydrate requested roots; detail/date project prompts. Web pages reject catalog membership/order revision drift and report truthful root totals, but row observations are per-page, not cross-page transactions; sorting/filtering stays page-local.

`reports/sampling.py` owns both eligibility/cutoff rules; `history.py` owns explicit root/range/limit scopes and incremental Watch-day/rolling-window acquisition. `acquisition.py` coordinates source batches/exact cache proofs; `ReportService` dispatches modes and account/availability overlap. `prompt_rows.py`/`prompts.py` own shared timeline/epoch projection, range/order and totals. No second analyzer or worker.

The foreground-recovery candidate prepares one bounded NORMAL/ALL_MODELS
snapshot/cache-observation window of two roots on capable sources. The initial
two-root trial was rejected; canonical bulk cache observations subsequently improved
controlled cold and retained-cache/fresh-host latency, including sparse stale roots,
and the scoped default decision was reconsidered. See the in-progress journal;
candidate selection is not universal performance or whole-FR acceptance.
Sampling still consumes roots one at a time
with both strict cutoffs and ties. Staged hits are not report-owned analysis/provenance;
consumption rechecks provenance, analysis dependencies and available source revision
before reusing a decoded hit. Unused snapshots/hits are released.
The follow-up experiment uses canonical `analysis/cache.py::CacheObservation` and
one bounded bulk lookup on capable caches. An observed miss skips another lookup
only with a matching authoritative staged snapshot; otherwise ordinary lookup can
use a concurrently populated cache. Scalar/bulk decoded identity validation is shared.
With a two-root window, at most one tail root may prove unnecessary; actual speculative source reads are
counted separately. Strict member-local tail failure falls back once to ordinary
required-root reads, never partial publication or suppressed source-wide failure.
Account periods and Watch guidance keep their own scopes/readers. Size-one is the
experiment control; larger comparators are not production-default approval.

The in-progress foreground-recovery candidate adds `context_sample.py` for bounded
canonical comparison/token sample reduction, and `context_guidance.py` for detached
dependency identity and pure numeric-guidance enrichment. Compact context price
bases retain canonical model/token-volume inputs, not analyses, for coherent repricing.
Only the injected Web Watch owner defers/coalesces sampling; CLI/finite report paths
stay synchronous. Guidance is never global Earlier coverage. See
`test_context_sample.py`, `test_watch_guidance.py` and the
[active, incomplete experiment ledger](../../journal/web/foreground-recovery.md).

`prompt_rows.py` owns per-row Token Mix coverage for completed/running prompts and compactions: every attributed entry must know all I/C/W/O fields and pooled volume must be positive. Reasoning remains folded into Output; established integer half-up/Output-residual rounding is unchanged. Missing counters are normalization placeholders, never a complete denominator or an implicitly partial-known share. `watch_capture.py` consumes this projection without a Watch-only override. CLI/Web presentation retains `N/A` for unsupported completed shares and `running` for active ones. `test_watch_token_mix.py` covers same-source coverage/rounding, child calls, correction/retention and display/SSE parity; `test_prompt_projection.py` pins compaction coverage. Accounting, aggregate mix and acquisition are unchanged.

`prompts.py` marks session-table Total mix unknown for incomplete contributing prompt/compaction coverage, rather than silently dropping the now-unknown completed rows. Completed incoming/extra CCost diagnostics remain independent of mix coverage. Dashboard/historical aggregate Token Mix scopes are unaffected.

`prompt_costs.py` projects immutable per-session/model/effort category costs from
canonically owned requests, using each request's unrounded reference price tier.
Own-session logical prompt identities come from the shared canonical prompt-window
index, not physical request counts or agent count. Private group membership deduplicates
those identities across requests and sessions, retaining unknown boundary completeness.
Unknown telemetry remains unknown, independently of a known subtotal. Prompt rows
retain positive causal linked-agent counts even without request usage. The bounded
application adapter exports at most 24 groups plus honest omitted cost/calls and
unit-aware help; no aggregate allocation, new source scans or CLI math changes.

Date detail opts into the optional observed source batch seam. V2 overlaps at most four tree reads, serializes shared normalization/diagnostics and joins the batch before returning. Catalog brackets and changed-tree-only retries stay authoritative; ordinary Watch/Daily batches remain unchanged. Safe date stages distinguish cache, unverified message-tree completion, before/after catalog waits and analysis. A stage count never means the report is complete or revision-verified; explicit timeout/source failures retain no successful view. [Investigation and limits](../../journal/web/historical-reports.md).

Dashboard usage mix stays latest-100, including running/interrupted priceable usage. Relative CCost independently uses the latest up to 100 completed priceable prompts globally through `latest_prompts` and `_relative_usage`. Pooled I/C/W/O shares price every model/tier; warnings reuse that same global mix for the existing 15-minute observation window. Ordinary model lists do not acquire deep per-model samples. Architecture maintenance 30 removes the unreachable comparison-history/cache helper and model/publisher profile engine; `analysis/models.py` retains the evidence value and exported legacy fields, without changing the global policy. `src/pricing/publishers.py` resolves catalog manufacturers, never request/account routes. `src/reports/token_mix_history.py` separately groups the same availability-filtered historical requests by model and publisher, with pooled shares, distinct per-group prompts, absolute Tokens and original per-request CCost. Prompt counts are not additive. Immutable report/application projections export the actual global comparison sample size and publisher rows; CLI/Web render, never revalue. Web history stays explicit/cancellable; collapsed comparison help and model tooltips describe the shared sample. Exact tiers, promotions, no-history sorting and accounts stay unchanged.

`src/analysis/model_supersession.py` shares table-local classification with CLI/Web. `presentation/model_supersession.py` is a compatibility export. Fading/older-stable text never changes valuation, ordering or notices.

V2 availability uses settled global `/api/model` selectable `id`, not `modelID`; empty/partial location boot is not settled. `sources/model_availability.py` rejects controls/malformed shapes and owns CLI compatibility, independently of quotas. Pricing identities are exact or bounded verified dated/context aliases: explicit variant rates/input tiers win, ambiguity stays unknown; no fuzzy Claude suffixes. Failed lookups visibly fail open to the catalog; settled empty stays empty. Highlights follow selection; `--all-models` bypasses availability.

`reports/accounts.py` separates CCost/billing from native capacity/status/balances; percentages never imply history or money. Adapters own capacity kind. Accounts sort credit before usage-limit, then casefolded provider/plan/account identity, never remaining/timing. `presentation/accounts.py` shares bars, resets and warnings between Watch and reports; Pace replaces resets only on paced compact rows. Watch omits AI-credit conversion; Copilot overage stays distinct. Pricing diagnostics remain sample-scoped. [Account details](../../../docs/account-support.md).


`src/analysis/period_ccost.py` owns canonical provider aliases (never model publishers), validated reset/trailing-window bounds, shared incomplete-telemetry reconciliation and deduplicated valuation prefix indexes. `src/reports/accounts.py` permits unassigned provider estimates only for one compatible detected account; multiple accounts stay unknown, with provider totals retained in projection notes but not printed as account prose. Proven history from another account is never reassigned. Calendar-month scopes are independent of overlapping windows and never appear in Watch. Indexed quota publication performs no source I/O or repeated history valuation. `ReportService` supplies the existing acquired range through `observed_start_ms`; an empty period becomes zero only when that range covers its start, never from account-attribution capability alone. Watch uses only a published current-day history range. Missing history, unknown window bounds and ambiguous requests remain unknown. `presentation/accounts.py` owns account-only zero/unknown notation (`0`, `—`) and the known priced subtotal with ordinary upward rounding and no partial marker (missing prices may understate complete valuation), rolling CCost inline on quota rows, and numeric today/month report rows without provenance prose or a footer. Global partial markers and layer dependencies are unchanged.

Normal Copilot reports reconcile native used credits with indexed CCost over a validated fixed UTC month; normal history extends through that start if earlier than the local month. `AccountProjection.unaccounted_usage` stays unknown without sufficient native usage/bounds/acquisition/pricing/attribution. The signed estimate is not billing or proven external use. Existing partial subtotals and Watch stay independent; presentation adds one report-only Copilot row, including unknowns.

## Transport-neutral application boundary and parity inventory

FR000638 adds Web-only `quota.ccost_pace`: `quota_record` binds native calendar counts
by quota identity, and `quota_ccost.py` shares its unrounded accepted reference Remaining
with the existing quota tokens. `with_display` exports distinct raw `ccost_per_day` /
`ccost_per_workday` and both display units; native `QuotaPace` remains unchanged.
Both shared live cards and the legacy/compact Accounts renderer consume this field,
never native pace or browser price arithmetic. Missing/stale/expired budgets omit pace
without clearing other quietly retained figures. Tests: `test_web_quota_pace.py`,
`test_quota_period_lifecycle.py`, existing account/quota VM checks and
`integration/probe_quota_pace.cjs` through the shared Accounts browser driver.

Normal progress additionally distinguishes early-stopping sample roots, availability,
model rows/catalog, account cache/batch/analysis and account projection. Application
packaging owns finalizing observations. `WorkProgress.stage` is optional and separately
allowlisted alongside the established phase/count metadata; labels/identifiers remain
private and CLI consumes the original phase/string contract. Each count follows its
completed unit. Source batch I/O remains opaque until return and prefetch stays parallel.

`src/application/service.py` owns isolated one-shot jobs: `ReportApplication(factory, clock=...)`, then `execute(ReportRequest, progress=...)`. The composition root must transfer a **fresh** `ReportService` per call using canonical sources, validated config, pricing/cache and account providers. It must not pass the live scheduler or share mutable source/provider context with another owner. No CLI subprocess, web import, alternate analysis or account scheduler is involved. A nonblocking serialized owner rejects concurrent/reentrant requests with `busy`; the host owns admission bounds/retry. The factory owns any extra resources outside ReportService. Every admitted job closes its accounts, including acquisition/projection failures; live/already-owned services are rejected without closing foreign work. Services cannot be reused across jobs. Live retains its own scheduler and exports immutable snapshots.

`src/application/contracts.py` defines frozen result/error/progress DTOs and detached JSON export. `src/application/projection.py` explicitly selects known fields, never introspects/dumps arbitrary dataclasses. Decimal amounts/ratios are exact strings; null, zero, incomplete coverage, provisional status and existing precomputed shares/warnings stay distinct. Consumers sort/display values without revaluing usage. Scope includes configured timezone, local day/month starts, resolved date bounds, history policy and **report execution** duration, not Watch duration.

The application opts into `ReportService.build(..., include_model_catalog=True)` for Models: `reports/model_comparison.py` freezes one supplemental full-catalog projection from the already acquired global sample, retaining uncomparable priced rows and existing recent/promotion semantics. Selectable publisher/name pairs and full/selected supersession are exported independently. No repeated history/accounts/availability acquisition is introduced; filters/sorting never reprice. Web uses a fixed full-catalog denominator, explicitly distinct from the unchanged CLI selected-catalog comparison. Normal accounts, verified-empty and fail-open warnings retain their existing owners.

Schema version and application instance UUID are separate from per-request-view sequence and hashed per-root source revisions. A result is immutable; source acquisition ensures each root snapshot, **not a transaction across roots/accounts/providers**. Account observations retain their own timestamp/status/availability and safe classified error facts. Source errors return a typed code/retryability and no empty-success view. Only safe progress phase/counts cross the boundary, not labels containing identifiers or exception text. Expected pricing unavailability and missing targets are distinct from logged unexpected defects; internal errors discard the whole view as `internal_error`, never raw transport messages. Cleanup faults propagate. Account locators and revisions use opaque hashes; raw provider observations, arbitrary reasons/warnings and pricing diagnostics are not exported. Session titles/previews remain intentional user content, so this is not a public/anonymous data feed. The optional `src/web/` adapter now owns HTTP authorization/security and process-level finite-job admission; see [Web](web.md).

| Existing mode | Application request / published view | Scope and protected parity |
| --- | --- | --- |
| Normal | NORMAL / model comparison, Token Mix, accounts/quotas | One global latest-up-to-100 completed-prompt comparison mix and independent latest-100 usage; account-period acquisition independent; CCost is reference value, not billing. Full root revision evidence remains; unused month-wide request identities are not exported. |
| All models | ALL_MODELS / model comparison, Token Mix | Same comparison eligibility, no selectable filter or accounts |
| Session list | SESSIONS / session_usage | Limit/all or bounded revision-checked page; whole-tree cost, completeness, archived/running flags and report duration |
| Session detail | SESSION / prompt_blocks, request_identities | Complete requested root/child tree, stable event/message/part references and opaque request key; no global Watch cap; inherited FR000200 running metrics |
| Date/range | DATE / prompt_blocks | Configured-local inclusive date target mapped to exclusive end; DST, context and duration remain existing semantics |
| Historical Token Mix | TOKEN_MIX / model_token_mix, publisher_token_mix and total | Separate deep all-available-history method, not build's dashboard fallback; existing availability fail-open behavior; no request rows or promise to recover pruned history |
| Web AI Stats | AI_STATS / ai_stats periods plus ai_stats_work | Shared resumable acquisition; scope-ready twelve-card presentation, observed token traffic/rates alongside Stats-only fun cost/time heuristics; configured-local calendar/DST and overlap-safe execution; no accounts/request rows or CLI change |

The [Web route inventory](../../../docs/web-beta.md#navigation-and-static-reports) maps views; visual/native acceptance is separate. Application tests pin canonical V1/V2 lifecycle/child/compaction/partial, timezone/account-error, uncapped detail, deduplication, immutable export and typed-failure parity. Fresh ownership, cleanup and forbidden application/Web imports in CLI/Diagnostics remain covered. Focused workload/history tests cover revision/catalog invalidation, deletion and publisher totals; no new dependency or permanent gate.

Historical model/publisher `Tokens` reuse `TokenMix.total_tokens` and its exact `known_total_tokens` subtotal, accumulated during the existing category pass. Incomplete telemetry keeps shares/complete totals unknown while retaining known-category volume (including reasoning). The application exports the subtotal as an exact decimal string for Web sorting, independent of compact Python display tokens and price completeness. Narrow CLI falls back to labeled metrics; Web retains its keyboard-scrollable tables. No acquisition, publisher, analysis-layer or account boundary changes. [Volume evidence](../governance/verification/historical-token-volumes.md).

## Web historical Token Mix acceleration

`token_mix_history.history_projection` is the shared grouping/availability/deduplication
owner. CLI retains its original acquisition path. Only finite Web composition opts
into `token_mix_cache`: compact normalized request identity, prompt association,
token coverage and canonical per-request category valuations are keyed by source,
tree revision, analysis dependencies and reference catalog. No prompt text or raw
provider payload is cached. Unstable/active evidence is not persisted. Current root
membership removes deleted usage; availability changes regroup without repricing.
Changed roots use bounded 64-root observed batches; SQLite bulk get/put avoids one
connection per root. Managed partial-history chunks likewise observe the derived
analysis cache in existing ≤8-root `observe_many` windows; per-root analysis rechecks
revision/provenance/dependencies and falls back to its scalar read on any mismatch.
The optional cache is disposable, not a second history source.
Exact integer strings accompany existing numeric DTO fields; Web display tokens
split shares/costs and replace only Web partial prefixes, preserving CLI semantics.

`test_web_token_mix.py` covers parity, incremental invalidation, active/empty scope,
cache corruption and a >500-key no-hydration/no-repricing refresh. Performance and
browser proof retain their actual limits in the Token Mix journal.

## Web AI Stats acquisition and accounting

FR000682 current delta (2026-11-12): `fun-2-tokens` preserves the ten historical
fun figures below and appends exact observed `total-tokens`/`token-rate` metrics.
They use the same canonical deduplication/event membership and rate denominators,
but never guessed usage or timing. Missing counters/source/pending evidence qualify
the total and withhold precise rates; unknown/guessed/running active time withholds
the active rate. Application owns compact/exact-help text, independent of CCost units.
A typed pricing outage uses empty catalogs in that finite Stats service only, not
provider/shared-cache writes, so actual traffic remains available. Compact usage
algorithm 5 stays reusable; coverage v3 alone rejects undated-request exclusions.
The browser stores only authoritative ready period snapshots, rejects older/foreign
publications, and atomically reveals twelve stable Loading-only card shells. A cold
terminal failure is Unavailable, not fabricated zero or indefinite Loading. Existing
last-good same-period refresh, host scheduling and the optional matched-run fact keep
their owners. No qualified per-invocation generation interval exists in captured
facts, so no TPS ranking/scan is added. [Evidence](../../journal/web/ai-stats.md#observed-token-traffic-and-ready-card-shells--fr000682).

Historical cost/time policy and acquisition baseline:

FR000633 scoped delta against `9b9fdf389d93d90a09bfa13e9b075b564d026961`,
checked 2026-11-08; unrelated module provenance above remains unchanged.
`src/reports/ai_stats.py::StatsAcquisition` owns bounded slices, root membership,
revision checks and all-five-period snapshots from the usable evidence already
collected. `ai_stats_work` tracks actual readiness separately: numbers no longer
certify full coverage. A changed root's usable observation may remain in Stats but
loses its revision proof; deleted roots are removed. Financial/history reports stay strict.

`ai_stats_evidence.py` retains compact canonical request/category facts and real
interval/matched-run scalars, never prompts. Stats evidence algorithm
`ai-stats-evidence-5-fun-1` invalidates old semantics without replacing shared base
evidence; coverage proof format remains 2. Each slice keeps the 256-root/64-batch/
maximum-four-read bounds, fixed transient namespace and source/revision/pricing
keys. Checkpoint errors retain acquired figures; six nonadvancing slices or a
nonbusy checkpoint failure settle a fun snapshot without falsifying coverage.
BUSY/LOCKED retries use bounded backoff. Root/fact/memory and process ownership
limits remain. Restart reuses valid disposable evidence, never a second source.

`src/analysis/ai_stats.py` policy `fun-1` alone supplements missing time/cost with
bounded deterministic heuristics; healthy formulas retain event-time deduplication,
clipped unions, root concurrency, local-date/night/DST splitting and stable ties.
All ten results are finite, including empty histories. Observation-local
`StatsObservation` preparation sharing does not change each
period's clipping, fallback-rate pooling or completeness calculation. Shared
deduplication requires identical ordered root populations; no cross-slice cache.
Private `Stat` reason codes
and source completeness remain diagnostic facts, not display/admission gates.
`src/application/ai_stats.py` emits unit-aware fun value/trait tokens; projection
marks `ai_stats_policy=fun-1`. `assets/ai-stats.js` validates that policy and retains
usable period figures, renders playful loading/zero outcomes and removes state,
explanation and technical-summary DOM. Shared historical summaries skip Stats only.
JS never revalues. Canonical valuation/duration, Watch, Sessions, CLI, Token Mix,
Comparisons and independent `active_hour.py` contracts remain unchanged.

FR000644/FR000655 delta (2026-11-09): `analysis/ai_stats_rates.py` owns nominal
configured-local calendar/workday rates and raw active-hour intensity over each
already-calculated period's same cost/unioned duration. Raw hypothetical shift fields
remain for compatibility, not card presentation. It reuses `quota_pace.is_workday`, never source/account data or
JavaScript holiday logic. `StatsAcquisition` threads `workdayCalendar`; observation
retains the original active-hour `value` and adds typed `rates`. Projection explicitly
allowlists those scalars; application prepares Calendar/Workday/Active AI average
per-hour values plus three short playful paragraphs with trailing plain-text formulas.
No-workday is a distinct neutral label; zero active duration never erases the other
rows. Rolling membership, source/cache lifetimes and the other nine metrics stay
unchanged. Only the first retained Web card gains three accessible label/value rows.

Focused tests are `development/tests/test_ai_stats.py`, `test_ai_stats_recovery.py`,
`test_ai_stats_rates.py`, `test_ai_stats_resume.py` and Stats-only branches in `test_web_dispatch.py`.
Browser, fixed-history parity and read-only real-source evidence, heuristic constants
and the scoped documentation-method exception are in [AI Stats findings](../../journal/web/ai-stats.md).

## Allowed dependencies

Reports depend on canonical domain, analysis, cache and abstract source/account/pricing contracts, never Watch, presentation or concrete adapters. Period analysis depends on domain and provider-neutral pricing/valuation only.

## Entrypoints

`src/application/service.py`, `src/application/contracts.py`, `src/application/projection.py`; `src/reports/service.py`, `src/reports/accounts.py`, `src/reports/history.py`, `src/analysis/period_ccost.py`; account rendering: `src/presentation/accounts.py`.

## Tests

`development/tests/test_workload_mix.py`, `development/tests/test_application_reports.py`, `development/tests/test_account_period_ccost.py`, `development/tests/test_copilot_unaccounted_usage.py`, `development/tests/test_accounts_ccost.py`, `development/tests/test_report_sampling.py`, `development/tests/test_history_loading.py`, `development/tests/test_step7_reports_cli.py`, `development/tests/test_quota_presentation.py`, `development/tests/test_session_list_pages.py`. Page/browser/native evidence: `development/architecture/governance/verification/sessions-pagination.md`.

[FR 000521 evidence](../governance/verification/model-publisher-mix.md).
