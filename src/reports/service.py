"""One-shot Cost Guard report orchestration over abstract runtime boundaries."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Mapping, Sequence

from src.accounts.base import AccountProvider
from src.accounts.acquisition import AccountAcquisition, AccountUpdate
from src.analysis import (
    AnalysisDependencies,
    DerivedAnalysisCache,
    analyze_snapshot,
    analyze_with_cache,
    cached_analysis,
    dependency_signature,
    local_day_start_ms,
    local_report_range,
    utc_month_start_ms,
)
from src.analysis.comparisons import model_comparison_rows, threshold_cost_multiplier
from src.analysis.models import RootAnalysisBundle
from src.analysis.token_mix import CategoryValuation, priced_token_mix
from src.analysis.valuation import ComparisonCost, comparison_cost, unique_usage
from src.cache import CacheRepository
from src.numbers import ccost_amount
from src.domain import AccountSnapshot, NormalizedSession, SessionSnapshot
from src.domain.session_tree import root_activity, root_for_session
from src.pricing.base import PricingProvider
from src.pricing.catalog import PricingCatalog, normalized_average_token_mix
from src.sources.model_availability import ModelAvailabilitySource
from src.sources.selection import SourceSelection

from .semantics import (
    active_promotion_notes,
    model_is_recent,
    recent_model_notice,
)

from .model_comparison import AvailabilityPrefetch, price_summary, selectable_catalog
from .prompts import build_prompt_block
from .accounts import accounts_quota_projection
from .migration_notice import migration_gap_notes
from .token_mix_history import HistoryProgress, build_token_mix_history
from .sampling import AnalyzedRoot, latest_prompts, latest_token_prompts, recent_sample_roots

from .models import (
    AccountsQuotasProjection,
    ModelComparisonProjection,
    SessionUsageRow,
    ReportKind,
    ReportProjection,
    SessionPromptBlock,
)

_TRACKED_PROVIDER: str | None = None


@dataclass(frozen=True, slots=True)
class ReportRequest:
    kind: ReportKind = ReportKind.NORMAL
    session_id: str | None = None
    date_text: str | None = None
    session_limit: int | None = None


ProgressCallback = Callable[[str], None]


def _noop_progress(_: str) -> None:
    return


def _chronological_blocks(blocks: Sequence[SessionPromptBlock]) -> tuple[SessionPromptBlock, ...]:
    return tuple(sorted(
        blocks,
        key=lambda block: (
            max((row.at_ms for row in block.rows), default=0),
            block.session_id,
        ),
    ))




class ReportService:
    """Build user-facing report projections without knowing concrete integrations."""

    def __init__(
        self,
        *,
        selection: SourceSelection,
        pricing_provider: PricingProvider,
        account_provider: AccountProvider | None,
        cache_repository: CacheRepository,
        config: Mapping[str, object],
        now_ms: int,
        progress: ProgressCallback | None = None,
        account_providers: Sequence[AccountProvider] | None = None,
        model_availability_source: ModelAvailabilitySource | None = None,
        comparison_pricing_provider: PricingProvider | None = None,
    ) -> None:
        self.selection = selection
        self.source = selection.source
        self.pricing_provider = pricing_provider
        self.comparison_pricing_provider = comparison_pricing_provider or pricing_provider
        values = tuple(account_providers) if account_providers is not None else ((account_provider,) if account_provider else ())
        self.account_providers = values
        self.account_provider = account_provider
        self.model_availability_source = model_availability_source
        self.cache_repository = cache_repository
        self.config = config
        self.now_ms = int(now_ms)
        self.progress = progress or _noop_progress
        self.catalog: PricingCatalog | None = None
        self.comparison_pricing_catalog: PricingCatalog | None = None
        self._derived = DerivedAnalysisCache(cache_repository)
        self._analyzed: dict[str, AnalyzedRoot] = {}
        # Current account visibility never proves historical included billing.
        self._subscription_providers = frozenset()
        self._account_work: AccountAcquisition | None = None
        self.account_diagnostics: Mapping[str, int | float] = {}
        self._comparison_mix: tuple[tuple[Decimal, Decimal, Decimal, Decimal, int], int] | None = None
        self._availability: AvailabilityPrefetch | None = None

    @property
    def timezone_id(self) -> str:
        return str(self.config.get("timezone") or "Europe/Stockholm")

    def _load_catalog(self) -> PricingCatalog:
        if self.catalog is None:
            self.progress("Loading pricing catalog")
            self.catalog = self.pricing_provider.get_catalog()
        return self.catalog

    def _load_comparison_catalog(self) -> PricingCatalog:
        if self.comparison_pricing_catalog is None:
            self.comparison_pricing_catalog = (
                self._load_catalog() if self.comparison_pricing_provider is self.pricing_provider
                else self.comparison_pricing_provider.get_catalog()
            )
        return self.comparison_pricing_catalog


    def _dependencies(self, catalog: PricingCatalog) -> AnalysisDependencies:
        config_semantics = {
            "tracked_provider": "all-canonical-providers",
            "timezone": self.timezone_id,
            "subscription_providers": sorted(self._subscription_providers),
        }
        return AnalysisDependencies(
            config_signature=dependency_signature(config_semantics),
            pricing_signature=dependency_signature({
                "provider": self.pricing_provider.provider_id,
                "source_revision": catalog.source_revision,
                "retrieved_at_ms": catalog.retrieved_at_ms,
            }),
        )

    def _analyze(
        self, root: NormalizedSession, *, detail: bool = False, force_fresh: bool = False
    ) -> AnalyzedRoot:
        existing = self._analyzed.get(root.session_id)
        if not force_fresh and existing is not None and (not detail or existing.snapshot is not None):
            return existing
        catalog = self._load_catalog()
        dependencies = self._dependencies(catalog)
        self.progress(f"Analyzing {root.session_id}")

        def analyze(snapshot: SessionSnapshot) -> RootAnalysisBundle:
            return analyze_snapshot(
                snapshot,
                tracked_provider=_TRACKED_PROVIDER,
                estimator=catalog.estimate,
                now_ms=self.now_ms,
                subscription_providers=self._subscription_providers,
            )

        if force_fresh:
            # Active Watch roots are intentionally hydrated authoritatively on
            # every scheduled refresh. OpenCode V1 may update live token/cost JSON
            # in place without changing the cheap payload-free tree revision.
            snapshot = self.source.load_session_snapshot(root.session_id)
            bundle = analyze(snapshot)
            analyzed = AnalyzedRoot(root, bundle, False, snapshot)
        else:
            result = analyze_with_cache(self.source, root, self._derived, dependencies, analyze)
            snapshot = existing.snapshot if existing else result.snapshot
            if detail and snapshot is None:
                snapshot = self.source.load_session_snapshot(root.session_id)
            analyzed = AnalyzedRoot(root, result.bundle, result.cache_hit, snapshot)
        self._analyzed[root.session_id] = analyzed
        return analyzed

    def _analysis_roots_for_watch(
        self,
        roots: Sequence[NormalizedSession],
        month_start: int,
        root_activity: Mapping[str, int],
    ) -> tuple[AnalyzedRoot, ...]:
        result: list[AnalyzedRoot] = []
        sample_prompts = 0
        for root in roots:
            if root_activity.get(root.session_id, root.updated_at_ms) < month_start and sample_prompts >= 100:
                break
            item = self._analyze(root)
            result.append(item)
            sample_prompts += len([p for p in item.bundle.prompts if not p.in_progress and not p.aborted])
        return tuple(result)

    def _quotas(self) -> tuple[AccountSnapshot, ...]:
        if self._account_work is None:
            self._account_work = AccountAcquisition(self.account_providers, self.source.source_id)
            if self._account_work.start(self.now_ms):
                self.progress("Checking account quotas")
        assert self._account_work is not None
        try:
            return self._account_work.finish(self.now_ms)
        finally:
            self.close_accounts()

    def begin_account_refresh(self) -> None:
        """Local shared inventory first; no worker touches progress or analysis."""
        if self._account_work is None:
            self._account_work = AccountAcquisition(self.account_providers, self.source.source_id)
        if self._account_work.start(self.now_ms):
            self.progress("Checking account quotas")

    def poll_account_refresh(self) -> AccountUpdate | None:
        return self._account_work.poll(self.now_ms) if self._account_work is not None else None

    @property
    def accounts_pending(self) -> bool:
        return self._account_work is not None and self._account_work.pending

    def close_accounts(self) -> None:
        if self._account_work is not None:
            self.account_diagnostics = self._account_work.diagnostics()
            self._account_work.close()
            self._account_work = None

    def _range_comparison(self, roots: Sequence[AnalyzedRoot], start_ms: int, end_ms: int | None = None) -> ComparisonCost:
        entries = unique_usage(entry for item in roots for entry in item.bundle.trace_entries)
        return comparison_cost(
            (entry for entry in entries if start_ms <= entry.completed_at_ms < (end_ms or self.now_ms + 1)),
            self._load_comparison_catalog().reference_valuation,
        )

    def _session_rows(self, roots: Sequence[AnalyzedRoot]) -> tuple[SessionUsageRow, ...]:
        catalog = self._load_catalog()
        rows: list[SessionUsageRow] = []
        for item in roots:
            valuation = self._range_comparison((item,), 0)
            model_spend = dict(valuation.by_model)
            primary = max(model_spend, key=lambda model_id: (model_spend[model_id], model_id)) if model_spend else "N/A"
            resolved = catalog.resolve(primary)
            name = resolved.model.display_name if resolved and resolved.model.display_name else primary
            prompt_count = len(item.bundle.prompts)
            rows.append(SessionUsageRow(
                session_id=item.session.session_id,
                title=item.session.title or item.session.session_id,
                model=name,
                multiple_models=len(model_spend) > 1,
                ccost=valuation.known_ccost,
                prompt_count=prompt_count,
                complete=valuation.complete,
            ))
        return tuple(rows)

    def _prompt_block(
        self,
        item: AnalyzedRoot,
        *,
        start_ms: int | None = None,
        end_ms: int | None = None,
    ) -> SessionPromptBlock:
        catalog = self._load_comparison_catalog()
        snapshot = item.snapshot or self.source.load_session_snapshot(item.session.session_id)
        return build_prompt_block(
            session_id=item.session.session_id,
            title=item.session.title or item.session.session_id,
            bundle=item.bundle,
            snapshot=snapshot,
            catalog=catalog,
            config=self.config,
            start_ms=start_ms,
            end_ms=end_ms,
            threshold_multiplier=self._threshold_multiplier,
        )

    def _ordered_roots(self, sessions: Sequence[NormalizedSession]) -> tuple[tuple[NormalizedSession, ...], dict[str, int]]:
        activity = root_activity(sessions)
        return tuple(sorted(
            (item for item in sessions if item.parent_session_id is None),
            key=lambda item: (activity.get(item.session_id, item.updated_at_ms), item.session_id), reverse=True,
        )), activity

    def _threshold_multiplier(self, model_id: str, threshold: int) -> Decimal | None:
        """Warning multiplier from the normal report's Relative CCost sample (refreshed every 15 min)."""
        if self._comparison_mix is None or self.now_ms - self._comparison_mix[1] >= 900_000:
            roots, activity = self._ordered_roots(tuple(self.source.list_sessions()))
            sample = latest_prompts(recent_sample_roots(roots, activity, self._analyze))
            self._comparison_mix = (normalized_average_token_mix(sample), self.now_ms)
        return threshold_cost_multiplier(self._load_comparison_catalog(), model_id, threshold, self._comparison_mix[0])

    def _model_comparison(
        self, roots: Sequence[AnalyzedRoot], *, all_models: bool = False,
    ) -> tuple[tuple[ModelComparisonProjection, ...], int, tuple[str, ...], str, tuple[str, ...]]:
        catalog = self._load_catalog()
        if all_models:
            comparison_catalog, warnings = catalog, ()
        else:
            self.progress("Checking available OpenCode models")
            comparison_catalog, warnings = selectable_catalog(
                catalog, availability_source=self._availability or self.model_availability_source,
            )
        promo_markers, promo_notes = active_promotion_notes(comparison_catalog, self.now_ms)
        candidates = latest_prompts(roots)
        rows: list[ModelComparisonProjection] = []
        for row in model_comparison_rows(candidates, comparison_catalog):
            marker = promo_markers.get(row.model_name)
            price_text = price_summary(comparison_catalog, row.model_name)
            rows.append(ModelComparisonProjection(
                row.publisher, row.model_name, row.relative_to_lowest, price_text, row.release_date,
                marker is not None, model_is_recent(row.release_date, now_ms=self.now_ms), marker,
                row.relative_levels,
            ))
        self._comparison_mix = (normalized_average_token_mix(candidates), self.now_ms)
        sample_size = self._comparison_mix[0][4]
        return tuple(rows), sample_size, promo_notes, recent_model_notice(comparison_catalog, now_ms=self.now_ms), warnings

    def _accounts_quotas(
        self,
        quotas: Sequence[AccountSnapshot] | None,
        *,
        roots: Sequence[AnalyzedRoot] = (),
        today_start_ms: int = 0,
        today_prompt_count: int = 0,
        today_session_count: int = 0,
    ) -> AccountsQuotasProjection:
        entries = tuple(entry for item in roots for entry in item.bundle.trace_entries)
        return accounts_quota_projection(
            quotas or (), entries, self._load_comparison_catalog(), now_ms=self.now_ms,
            today_start_ms=today_start_ms, month_start_ms=utc_month_start_ms(now_ms=self.now_ms),
            today_prompt_count=today_prompt_count,
            today_session_count=today_session_count,
            timezone_id=self.timezone_id, workday_calendar=str(self.config.get("workdayCalendar") or ""),
        )

    def token_category_valuation(self) -> CategoryValuation:
        """Per-request I/C/W/O CCost using the same reference catalog as CCost."""
        return self._load_comparison_catalog().reference_category_valuation

    def build_token_mix_history(self, progress: HistoryProgress | None = None) -> ReportProjection:
        """Deep available-history model comparison; never used by normal reports/Watch."""
        return build_token_mix_history(self, progress or (lambda _label, _percent: None))

    def set_now_ms(self, now_ms: int) -> None:
        """Advance wall-clock-dependent presentation semantics without rebuilding dependencies."""
        self.now_ms = int(now_ms)

    def invalidate_roots(self, root_ids: Sequence[str]) -> None:
        """Drop in-process analyzed snapshots for source roots known to have changed."""
        for root_id in root_ids:
            self._analyzed.pop(root_id, None)

    def session_catalog(self) -> tuple[NormalizedSession, ...]:
        return tuple(self.source.list_sessions())

    def root_for_session(
        self, session_id: str, sessions: Sequence[NormalizedSession] | None = None
    ) -> NormalizedSession | None:
        return root_for_session(tuple(sessions) if sessions is not None else self.session_catalog(), session_id)

    def watch_root_is_quiet(self, root: NormalizedSession, since_ms: int) -> bool:
        """Stable cached analysis proves a root has no Watch row yet.

        Analysis is cached only for stable snapshots without running prompts,
        compactions, active sessions or background work, keyed by the exact
        current revision. With no prompt/compaction at or after ``since_ms``
        nothing is displayable; Watch hydrates the root once its revision changes.
        """
        _revision, bundle = cached_analysis(self.source, root, self._derived, self._dependencies(self._load_catalog()))
        if bundle is None:
            return False
        # The same result _analyze would return; later quota/sample reads reuse it.
        self._analyzed[root.session_id] = AnalyzedRoot(root, bundle, True, None)
        return (all(prompt.prompt_time_ms < since_ms for prompt in bundle.prompts)
                and all(item.created_at_ms < since_ms for item in bundle.compactions))

    def build_watch_root(
        self, root: NormalizedSession, *, start_ms: int | None = None, force_fresh: bool = False
    ) -> tuple[SessionPromptBlock, SessionSnapshot, RootAnalysisBundle]:
        """Build one Watch root from the same analysis/context truth as one-shot reports."""
        item = self._analyze(root, detail=True, force_fresh=force_fresh)
        snapshot = item.snapshot or self.source.load_session_snapshot(root.session_id)
        return self._prompt_block(item, start_ms=start_ms), snapshot, item.bundle

    def recent_promotion_notice_texts(self) -> tuple[str, ...]:
        """Watch's seven-day change notices, independent of full report promotion lifetime."""
        return active_promotion_notes(self._load_catalog(), self.now_ms, recent_only=True)[1]

    def account_quota_snapshots(self) -> tuple[AccountSnapshot, ...]:
        """Read all configured account providers independently."""
        return self._quotas()

    def build_watch_quota(
        self,
        sessions: Sequence[NormalizedSession] | None = None,
        *,
        quota_snapshot: AccountSnapshot | None = None,
        quota_snapshots: Sequence[AccountSnapshot] | None = None,
        query_account: bool = True,
    ) -> AccountsQuotasProjection:
        """Build live quota/local-usage status without model-comparison/report rendering work.

        Watch may pass a previously fetched account snapshot so source changes can
        refresh local usage without turning every OpenCode change into a network
        request against the account provider.
        """
        roots, root_activity = self._ordered_roots(tuple(sessions) if sessions is not None else self.session_catalog())
        month_start = utc_month_start_ms(now_ms=self.now_ms)
        today_start = local_day_start_ms(self.timezone_id, now_ms=self.now_ms)
        analyzed = self._analysis_roots_for_watch(roots, month_start, root_activity)
        self.progress("Calculating month/today CCost")
        quotas = self._quotas() if query_account else tuple(
            quota_snapshots if quota_snapshots is not None else ((quota_snapshot,) if quota_snapshot else ())
        )
        return self._accounts_quotas(
            quotas, roots=analyzed, today_start_ms=today_start
        )

    def build(self, request: ReportRequest) -> ReportProjection:
        try:
            if request.kind is ReportKind.NORMAL:
                # Both are I/O-bound and independent of local analysis: overlap them.
                self.begin_account_refresh()
                if self.model_availability_source is not None:
                    self._availability = AvailabilityPrefetch(self.model_availability_source)
            return self._build(request)
        finally:
            self._availability = None
            self.close_accounts()

    def _build(self, request: ReportRequest) -> ReportProjection:
        catalog = self._load_catalog()
        all_sessions = tuple(self.source.list_sessions())
        roots, root_activity = self._ordered_roots(all_sessions)
        if request.kind is ReportKind.SESSIONS:
            return self._build_session_list(request, roots, root_activity)
        if request.kind is ReportKind.SESSION:
            return self._build_session_detail(request, all_sessions)
        if request.kind is ReportKind.DATE:
            return self._build_date_detail(request, roots, root_activity)
        return self._build_dashboard(request, catalog, roots, root_activity)

    def _build_session_list(self, request: ReportRequest, roots: Sequence[NormalizedSession],
                            root_activity: Mapping[str, int]) -> ReportProjection:
        if request.session_limit is not None and request.session_limit < 1:
            raise ValueError("Session limit must be positive or all")
        selected = roots if request.session_limit is None else roots[:request.session_limit]
        analyzed = tuple(self._analyze(root) for root in selected)
        # A truncated listing only covers activity since its oldest listed root.
        cutoff = (root_activity.get(selected[-1].session_id, selected[-1].updated_at_ms)
                  if selected and len(selected) < len(roots) else None)
        return ReportProjection(
            ReportKind.SESSIONS, "Available sessions", self.selection.selected.upper(), tuple(self.selection.warnings),
            session_usage=self._session_rows(analyzed),
            notes=migration_gap_notes(self.selection.migration_gap, start_ms=cutoff),
        )

    def _build_session_detail(self, request: ReportRequest, sessions: Sequence[NormalizedSession]) -> ReportProjection:
        if not request.session_id:
            raise ValueError("Session report requires a session id")
        root = root_for_session(sessions, request.session_id)
        if root is None:
            raise ValueError(f"OpenCode session '{request.session_id}' was not found.")
        item = self._analyze(root, detail=True)
        block = self._prompt_block(item)
        return ReportProjection(
            ReportKind.SESSION, f"Session {request.session_id}", self.selection.selected.upper(), tuple(self.selection.warnings),
            prompt_blocks=(block,),
            notes=(("WARNING: CCost totals are incomplete because some reference pricing is unavailable.",)
                   if not block.comparison_cost_complete else ())
            + migration_gap_notes(self.selection.migration_gap, root_id=root.session_id),
        )

    def _build_date_detail(self, request: ReportRequest, roots: Sequence[NormalizedSession],
                           root_activity: Mapping[str, int]) -> ReportProjection:
        if not request.date_text:
            raise ValueError("Date report requires a date target")
        date_range = local_report_range(request.date_text, self.timezone_id)
        candidates = [root for root in roots if root_activity.get(root.session_id, root.updated_at_ms) >= date_range.start_ms]
        analyzed = tuple(self._analyze(root, detail=True) for root in candidates)
        blocks = _chronological_blocks(tuple(
            block for item in analyzed
            if (block := self._prompt_block(item, start_ms=date_range.start_ms, end_ms=date_range.end_ms)).rows
        ))
        valuation = self._range_comparison(analyzed, date_range.start_ms, date_range.end_ms)
        range_text = ccost_amount(valuation.known_ccost, unresolved=not valuation.complete)
        return ReportProjection(
            ReportKind.DATE, f"Date report {date_range.text}", self.selection.selected.upper(), tuple(self.selection.warnings),
            prompt_blocks=blocks,
            notes=(f"CCost for range: {range_text}; reference valuation, not billing.",)
            + migration_gap_notes(self.selection.migration_gap, start_ms=date_range.start_ms, end_ms=date_range.end_ms),
        )

    def _build_dashboard(self, request: ReportRequest, catalog: PricingCatalog, roots: Sequence[NormalizedSession],
                         root_activity: Mapping[str, int]) -> ReportProjection:
        analyzed = recent_sample_roots(roots, root_activity, self._analyze)
        self.progress("Comparing model prices")
        comparisons, sample, promo_notes, recent, availability_warnings = self._model_comparison(
            analyzed, all_models=request.kind is ReportKind.ALL_MODELS,
        )
        # Dashboard quotas use provider observations only. A bounded Relative CCost
        # sample cannot establish complete day/month spend or account attribution.
        quota_projection = self._accounts_quotas(self._quotas()) if request.kind is ReportKind.NORMAL else None
        sample_prompts = latest_prompts(analyzed)
        entries = unique_usage(entry for prompt in sample_prompts for entry in prompt.entries)
        reference = self._load_comparison_catalog()
        coverage = comparison_cost(entries, reference.reference_valuation)
        mix_prompts = latest_token_prompts(analyzed)
        # Full bounded samples cover activity since their oldest prompt; a short
        # sample already spans all available history.
        sample_cutoff = (min(sample_prompts[-1].prompt_time_ms, mix_prompts[-1].prompt_time_ms)
                         if len(sample_prompts) == len(mix_prompts) == 100 else None)
        return ReportProjection(
            request.kind,
            "Cost Guard",
            self.selection.selected.upper(),
            tuple(self.selection.warnings) + availability_warnings,
            model_comparison=comparisons,
            model_comparison_sample_size=sample,
            pricing_retrieved_at_ms=catalog.retrieved_at_ms,
            model_comparison_promotion_notes=promo_notes,
            accounts_quotas=quota_projection,
            notes=migration_gap_notes(self.selection.migration_gap, start_ms=sample_cutoff),
            recent_model_notice=recent,
            token_mix=priced_token_mix(((entry.model, entry.tokens) for entry in unique_usage(
                entry for prompt in mix_prompts for entry in prompt.entries)),
                reference.reference_category_valuation, sample_size=len(mix_prompts)),
            pricing_diagnostics={
                "scope": "relcost_sample", "relcost_sample_prompts": len(sample_prompts), "analyzed_roots": len(analyzed),
                "current_price_fallback_requests": sum(p.estimated_fallback_requests for p in sample_prompts),
                "unresolved_billing_fallback_requests": sum(p.unresolved_fallback_requests for p in sample_prompts),
                "reference_price_requests": sum(entry.reported_cost <= 0 and entry.tokens.total > 0
                    and reference.reference_valuation(entry.model, entry.tokens) is not None for entry in entries),
                "reference_price_reason": "missing_or_zero_stored_cost",
                "reference_catalog_revision": reference.source_revision,
                "reference_catalog_retrieved_at_ms": reference.retrieved_at_ms,
                "observed_requests": coverage.observed_requests, "priced_requests": coverage.priced_requests,
            },
        )
