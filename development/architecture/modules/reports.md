# Reports source contracts

[Architecture overview](../OVERVIEW.md) · [Owner/test routes](CODE_MAP.md). Source remains authoritative.

## Reports

`src/reports/` owns use cases/neutral projections over abstract sources/providers, analysis and cache; never concrete integrations, Watch or presentation.

Candidate roots are ordered by whole-tree activity, so newly updated child work is not skipped. Hydrated snapshots/analysis remain the semantic authority; session metadata activity is only a bounded discovery gate. Session dominant model is selected by whole-session attributed CCost; listing order is recent tree activity, never cost.

Immutable projections cover dashboard/catalog, lists and detail/date modes. Dashboard/catalog sample 100 eligible prompts by newest tree activity, stopping only below the cutoff (ties qualify); hydration is authoritative. Quotas use provider observations, not history; other modes fetch none. Lists analyze requested roots; detail/date project prompts.

`reports/sampling.py` owns both eligibility/cutoff rules; `history.py` owns explicit root/range/limit scopes and incremental Watch-day acquisition. `acquisition.py` coordinates source batches/exact cache proofs; `ReportService` dispatches modes and account/availability overlap. `prompt_rows.py`/`prompts.py` own shared timeline/epoch projection, range/order and totals. No second analyzer or worker.

Dashboard mix includes running/interrupted usage; Relative CCost keeps completed eligibility/count. Both samples admit only prompts with a priceable request (evaluated live against the current catalog, never cached) and use only those requests, so unpriceable history never fills a sample; scans respect both cutoffs. `reports/token_mix_history.py` scans without a ledger, with fail-open filtering and shown-request totals. `presentation/definitions.py` owns definitions; `presentation/model_comparison.py` aligns fields before color. Normal tables have four columns; full-catalog tables add exact USD tiers/boundaries even under fallback. Presentation never recomputes valuation.

`presentation/model_supersession.py`/`AnsiStyler` own conservative displayed-row classification/hue fading, never pricing, sorting, selection, notices or geometry.

V2 availability uses settled global `/api/model` selectable `id`, not `modelID`; empty/partial location boot is not settled. `sources/model_availability.py` rejects controls/malformed shapes and owns CLI compatibility, independently of quotas. Pricing identities are exact or bounded verified dated/context aliases: explicit variant rates/input tiers win, ambiguity stays unknown; no fuzzy Claude suffixes. Failed lookups visibly fail open to the catalog; settled empty stays empty. Highlights follow selection; `--all-models` bypasses availability.

`reports/accounts.py` separates attributed CCost/billing from native capacity/status/balances; visibility/inclusion/percentages never imply history/billing/money. Adapters own `AccountSnapshot.capacity_kind`; errors retain metadata. Projection sorts credit before usage-limit accounts, then casefolded provider/plan/account names and stable identity, never remaining values/timing. `presentation/accounts.py` shares bars/values/resets/warnings: Watch compact/split/vertical, reports native units/money/verbose resets. Remaining is Pace; only paced compact rows omit resets. Watch omits AI-credit conversion; Copilot overage stays a separate limit. No provider rendering branches/gross daily billing; pricing diagnostics are sample-scoped. [Details](../../../docs/account-support.md).

