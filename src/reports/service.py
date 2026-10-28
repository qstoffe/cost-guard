"""One-shot Cost Guard report orchestration over abstract runtime boundaries."""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Callable, Mapping, Sequence

from src.accounts.base import AccountProvider
from src.accounts.acquisition import AccountAcquisition, AccountUpdate
from src.accounts.refresh_loop import AccountRefreshLoop
from src.cache.account_refresh_state import persist_refresh_state
from src.analysis import (
    AnalysisDependencies,
    DerivedAnalysisCache,
    analyze_snapshot,
    cached_analysis,
    dependency_signature,
    local_day_start_ms,
    local_report_range,
    local_month_start_ms,
)
from src.analysis.comparisons import model_comparison_rows, threshold_cost_multiplier
from src.analysis.models import PromptRecord, RootAnalysisBundle, TraceEntry
from src.analysis.duration import accumulated_duration
from src.analysis.token_mix import CategoryValuation, PricedUsage, priceable_request, priced_sample_mix, priced_usage
from src.analysis.valuation import ComparisonCost, comparison_cost, unique_usage
from src.cache import CacheRepository
from src.numbers import ccost_amount
from src.domain import AccountSnapshot, NormalizedSession, SessionSnapshot
from src.domain.acquisition import AcquisitionMetrics
from src.domain.progress import WorkProgress
from src.domain.ccost import ReferenceValuation
from src.domain.session_tree import root_activity, root_for_session
from src.pricing.base import PricingProvider
from src.pricing.catalog import PricingCatalog, normalized_average_token_mix
from src.sources.model_availability import ModelAvailabilitySource
from src.sources.selection import SourceSelection

from .semantics import (
    active_promotion_notes,
    model_is_recent,
    recent_model_notice_details,
)

from .model_comparison import AvailabilityPrefetch, price_summary, selectable_catalog
from .prompts import build_prompt_block
from .accounts import accounts_quota_projection, WatchAccountProjection
from .migration_notice import migration_gap_notes
from .token_mix_history import HistoryProgress, build_token_mix_history
from .sampling import AnalyzedRoot, latest_prompts, latest_token_prompts, recent_sample_roots
from .history import HistoryRequirements, WatchHistoryAcquisition
from .acquisition import RootAcquisition

from .models import (
    AccountsQuotasProjection,
    ModelComparisonProjection,
    SessionUsageRow,
    ReportKind,
    ReportProjection,
    SessionPromptBlock,
)

_TRACKED_PROVIDER: str | None = None


class ReportRequestError(ValueError):
    """Expected invalid/unavailable report target, not an analysis defect."""


class SessionNotFoundError(ReportRequestError):
    """No matching catalog session; distinct from an acquired empty session."""


class SessionCatalogChangedError(ReportRequestError):
    """A page cannot be positioned safely in a changed catalog."""


@dataclass(frozen=True, slots=True)
class ReportRequest:
    kind: ReportKind = ReportKind.NORMAL
    session_id: str | None = None
    date_text: str | None = None
    session_limit: int | None = None
    session_page_size: int | None = None
    session_offset: int = 0
    session_catalog_revision: str | None = None


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
        self.metrics = getattr(self.source, "metrics", AcquisitionMetrics(generation=selection.selected))
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
        self._derived = DerivedAnalysisCache(cache_repository, metrics=self.metrics)
        self._acquisition = RootAcquisition(self.source, self._derived,
            dependencies=lambda: self._dependencies(self._load_catalog()), analyzer=self._analyze_snapshot,
            progress=lambda label: self.progress(label), metrics=self.metrics)
        self._analyzed = self._acquisition.analyzed
        self._analyzed_at_ms = self._acquisition.analyzed_at_ms
        # Current account visibility never proves historical included billing.
        self._subscription_providers = frozenset()
        self._account_work: AccountAcquisition | AccountRefreshLoop | None = None
        self._watch_accounts = False
        self._record_account_evidence = False
        self._watch_quota_entries: tuple[TraceEntry, ...] = ()
        self.account_diagnostics: Mapping[str, object] = {}
        self._comparison_mix: tuple[tuple[Decimal, Decimal, Decimal, Decimal, int], int] | None = None
        self._availability: AvailabilityPrefetch | None = None
        self._watch_history = WatchHistoryAcquisition()
        self._watch_history_active: set[str] = set()
        self._watch_account_projection = WatchAccountProjection(self.metrics)

    @property
    def timezone_id(self) -> str:
        return str(self.config.get("timezone") or "Europe/Stockholm")

    def _load_catalog(self) -> PricingCatalog:
        if self.catalog is None:
            self.progress(WorkProgress("Loading pricing catalog", "pricing"))
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
        return AnalysisDependencies(dependency_signature(config_semantics), catalog.analysis_signature)

    def _analyze(
        self, root: NormalizedSession, *, detail: bool = False, force_fresh: bool = False,
        snapshot: SessionSnapshot | None = None,
    ) -> AnalyzedRoot:
        return self._acquisition.analyze(root, now_ms=self.now_ms, detail=detail, force_fresh=force_fresh, snapshot=snapshot)

    def _analyze_snapshot(self, snapshot: SessionSnapshot) -> RootAnalysisBundle:
        with self.metrics.measure("analysis"):
            bundle = analyze_snapshot(snapshot, tracked_provider=_TRACKED_PROVIDER, estimator=self._load_catalog().estimate,
                                      now_ms=self.now_ms, subscription_providers=self._subscription_providers)
        self.metrics.add("analyzed_prompts", len(bundle.prompts))
        self.metrics.add("analyzed_requests", len(bundle.trace_entries))
        return bundle

    def prepare_roots(self, roots: Sequence[NormalizedSession], *, detail: bool = False,
                      force_fresh_ids: Sequence[str] = ()) -> frozenset[str]:
        return self._acquisition.prepare(roots, now_ms=self.now_ms, detail=detail, force_fresh_ids=force_fresh_ids)

    def _quotas(self) -> tuple[AccountSnapshot, ...]:
        if self._account_work is None:
            self._account_work = AccountAcquisition(self.account_providers, self.source.source_id)
            if self._account_work.start(self.now_ms):
                self.progress("Checking account quotas")
        assert self._account_work is not None
        self.progress(WorkProgress("Waiting for account quotas", "quotas"))
        try:
            return self._account_work.finish(self.now_ms)
        finally:
            self.close_accounts()

    def enable_watch_accounts(self, *, record_evidence: bool = True) -> None:
        self._watch_accounts = True
        self._record_account_evidence = record_evidence
        self._watch_history.reset()

    def _record_account_refresh(self, evidence: dict) -> None:
        if self._record_account_evidence:
            persist_refresh_state(self.cache_repository.database.package_root, evidence)

    def begin_account_refresh(self) -> None:
        """Local shared inventory first; no worker touches progress or analysis."""
        if self._account_work is None:
            self._account_work = (AccountRefreshLoop(
                self.account_providers, self.source.source_id,
                evidence_sink=self._record_account_refresh)
                if self._watch_accounts else AccountAcquisition(self.account_providers, self.source.source_id))
        if self._account_work.start(self.now_ms):
            self.progress("Checking account quotas")

    def poll_account_refresh(self) -> AccountUpdate | None:
        if self._account_work is None:
            return None
        update = self._account_work.poll(self.now_ms)
        self.account_diagnostics = self._account_work.diagnostics()
        return update

    @property
    def accounts_pending(self) -> bool:
        return self._account_work is not None and self._account_work.pending

    def record_account_display(self, evidence: dict[str, object]) -> None:
        self.account_diagnostics = {**self.account_diagnostics, "watch": evidence}
        if isinstance(self._account_work, AccountRefreshLoop):
            self._account_work.set_display(evidence)

    def close_accounts(self) -> None:
        if self._account_work is not None:
            self.account_diagnostics = {**self.account_diagnostics, **self._account_work.diagnostics()}
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
                duration_ms=accumulated_duration(
                    [(record.prompt_time_ms, record.execution_duration_ms) for record in item.bundle.prompts]
                    + [(record.created_at_ms, record.duration_ms) for record in item.bundle.compactions]),
                archived=item.session.archived_at_ms is not None,
                running=any(record.in_progress for record in item.bundle.prompts),
            ))
        return tuple(rows)

    def _prompt_block(
        self,
        item: AnalyzedRoot,
        *,
        start_ms: int | None = None,
        end_ms: int | None = None,
        watch_duration: bool = False,
        snapshot_running_metrics: bool = False,
    ) -> SessionPromptBlock:
        catalog = self._load_comparison_catalog()
        snapshot = item.snapshot or self.source.load_session_snapshot(item.session.session_id)
        with self.metrics.measure("projection"):
            return build_prompt_block(
                session_id=item.session.session_id, title=item.session.title or item.session.session_id,
                bundle=item.bundle, snapshot=snapshot, catalog=catalog, config=self.config,
                start_ms=start_ms, end_ms=end_ms, threshold_multiplier=self._threshold_multiplier,
                watch_duration=watch_duration,
                snapshot_running_metrics=snapshot_running_metrics,
            )

    def _ordered_roots(self, sessions: Sequence[NormalizedSession]) -> tuple[tuple[NormalizedSession, ...], dict[str, int]]:
        activity = root_activity(sessions)
        return tuple(sorted(
            (item for item in sessions if item.parent_session_id is None),
            key=lambda item: (activity.get(item.session_id, item.updated_at_ms), item.session_id), reverse=True,
        )), activity

    def _priceable(self) -> Callable[[TraceEntry], bool]:
        """Shared per-request sample eligibility under the current reference catalog."""
        valuation = self._load_comparison_catalog().reference_category_valuation
        return lambda entry: priceable_request(entry.model, entry.tokens, valuation)

    def _relative_usage(self, sample: Sequence[PromptRecord]) -> tuple[PricedUsage, ...]:
        """Relative CCost usage per sampled prompt from its priceable requests only."""
        valuation = self._load_comparison_catalog().reference_category_valuation
        return tuple(priced_usage(unique_usage(prompt.entries), valuation) for prompt in sample)

    def _threshold_multiplier(self, model_id: str, threshold: int) -> Decimal | None:
        """Warning multiplier from the normal report's Relative CCost sample (refreshed every 15 min)."""
        if self._comparison_mix is None or self.now_ms - self._comparison_mix[1] >= 900_000:
            roots, activity = self._ordered_roots(self.session_catalog())
            priceable = self._priceable()
            sampled = recent_sample_roots(roots, activity, self._analyze, priceable)
            self.metrics.add("context_warning_sample_roots", len(sampled))
            sample = latest_prompts(sampled, priceable)
            self._comparison_mix = (normalized_average_token_mix(self._relative_usage(sample)), self.now_ms)
        catalog = self._load_comparison_catalog()
        return threshold_cost_multiplier(catalog, model_id, threshold, self._comparison_mix[0])

    def _model_comparison(
        self, roots: Sequence[AnalyzedRoot], *, all_models: bool = False,
    ) -> tuple[tuple[ModelComparisonProjection, ...], int, tuple[str, ...], str, tuple[tuple[int, int], ...], tuple[str, ...]]:
        catalog = self._load_catalog()
        if all_models:
            comparison_catalog, warnings = catalog, ()
        else:
            self.progress(WorkProgress("Checking available OpenCode models", "availability"))
            comparison_catalog, warnings = selectable_catalog(
                catalog, availability_source=self._availability or self.model_availability_source,
            )
        promo_markers, promo_notes = active_promotion_notes(comparison_catalog, self.now_ms)
        usage = self._relative_usage(latest_prompts(roots, self._priceable()))
        rows: list[ModelComparisonProjection] = []
        for row in model_comparison_rows(usage, comparison_catalog):
            marker = promo_markers.get(row.model_name)
            price_text = price_summary(comparison_catalog, row.model_name)
            rows.append(ModelComparisonProjection(
                row.publisher, row.model_name, row.relative_to_lowest, price_text, row.release_date,
                marker is not None, model_is_recent(row.release_date, now_ms=self.now_ms), marker,
                row.relative_levels,
                row.evidence,
            ))
        self._comparison_mix = (normalized_average_token_mix(usage), self.now_ms)
        sample_size = self._comparison_mix[0][4]
        notice, highlight_spans = recent_model_notice_details(
            comparison_catalog, now_ms=self.now_ms, cache_repository=self.cache_repository,
        )
        return tuple(rows), sample_size, promo_notes, notice, highlight_spans, warnings

    def _accounts_quotas(
        self,
        quotas: Sequence[AccountSnapshot] | None,
        *,
        roots: Sequence[AnalyzedRoot] = (),
        today_start_ms: int = 0,
        today_prompt_count: int = 0,
        today_session_count: int = 0,
        observed_start_ms: int | None = None,
    ) -> AccountsQuotasProjection:
        entries = tuple(entry for item in roots for entry in item.bundle.trace_entries)
        return accounts_quota_projection(
            quotas or (), entries, self._load_comparison_catalog(), now_ms=self.now_ms,
            today_start_ms=today_start_ms, month_start_ms=local_month_start_ms(self.timezone_id, now_ms=self.now_ms),
            today_prompt_count=today_prompt_count,
            today_session_count=today_session_count,
            observed_start_ms=observed_start_ms,
            timezone_id=self.timezone_id, workday_calendar=str(self.config.get("workdayCalendar") or ""),
        )

    def token_category_valuation(self) -> CategoryValuation:
        """Per-request I/C/W/O CCost using the same reference catalog as CCost."""
        return self._load_comparison_catalog().reference_category_valuation

    def token_reference_valuation(self) -> ReferenceValuation:
        """Per-request scalar CCost valuation for process-local Watch totals."""
        return self._load_comparison_catalog().reference_valuation

    def build_token_mix_history(self, progress: HistoryProgress | None = None) -> ReportProjection:
        """Deep available-history model comparison; never used by normal reports/Watch."""
        self.metrics.mode = "token-mix-history"
        return build_token_mix_history(self, progress or (lambda _label, _percent: None))

    def set_now_ms(self, now_ms: int) -> None:
        """Advance wall-clock-dependent presentation semantics without rebuilding dependencies."""
        self.now_ms = int(now_ms)

    def invalidate_source_observations(self) -> None:
        """Discard unfinished startup's analysis gates, not providers/prices/quotas."""
        self._analyzed.clear()
        self._analyzed_at_ms.clear()
        self._comparison_mix = None
        self._watch_history.reset()
        self._watch_quota_entries = ()

    def invalidate_roots(self, root_ids: Sequence[str]) -> None:
        """Drop in-process analyzed snapshots for source roots known to have changed."""
        for root_id in root_ids:
            self._analyzed.pop(root_id, None)
            self._analyzed_at_ms.pop(root_id, None)

    def session_catalog(self) -> tuple[NormalizedSession, ...]:
        recent = getattr(self.source, "recent_session_catalog", None)
        return tuple(recent() if callable(recent) else self.source.list_sessions())

    def root_for_session(
        self, session_id: str, sessions: Sequence[NormalizedSession] | None = None
    ) -> NormalizedSession | None:
        return root_for_session(tuple(sessions) if sessions is not None else self.session_catalog(), session_id)

    def watch_root_latest_prompt_ms(self, root: NormalizedSession) -> int | None:
        """Latest prompt/compaction start proven by stable cached analysis, else None.

        Analysis is cached only for stable snapshots without running prompts,
        compactions, active sessions or background work, keyed by the exact
        current revision. A value before Watch start means nothing is displayable
        yet (0: no prompt at all); Watch hydrates the root once its revision changes.
        """
        _revision, bundle = cached_analysis(self.source, root, self._derived, self._dependencies(self._load_catalog()))
        if bundle is None:
            return None
        # The same result _analyze would return; later quota/sample reads reuse it.
        self._analyzed[root.session_id] = AnalyzedRoot(root, bundle, True, None)
        return max([prompt.prompt_time_ms for prompt in bundle.prompts]
                   + [item.created_at_ms for item in bundle.compactions], default=0)

    def build_watch_root(
        self, root: NormalizedSession, *, start_ms: int | None = None, force_fresh: bool = False
    ) -> tuple[SessionPromptBlock, SessionSnapshot, RootAnalysisBundle]:
        """Build one Watch root from the same analysis/context truth as one-shot reports."""
        item = self._analyze(root, detail=True, force_fresh=force_fresh)
        snapshot = item.snapshot or self.source.load_session_snapshot(root.session_id)
        return self._prompt_block(item, start_ms=start_ms, watch_duration=True), snapshot, item.bundle

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
        return self.build_watch_quota_with_today_entries(
            sessions, quota_snapshot=quota_snapshot, quota_snapshots=quota_snapshots,
            query_account=query_account,
        )[0]

    def build_watch_quota_with_today_entries(
        self,
        sessions: Sequence[NormalizedSession] | None = None,
        *,
        quota_snapshot: AccountSnapshot | None = None,
        quota_snapshots: Sequence[AccountSnapshot] | None = None,
        query_account: bool = True,
    ) -> tuple[AccountsQuotasProjection, tuple[TraceEntry, ...]]:
        """Build live quota/local-usage status without model-comparison/report rendering work.

        Watch may pass a previously fetched account snapshot so source changes can
        refresh local usage without turning every OpenCode change into a network
        request against the account provider.
        """
        roots = self.watch_history_candidates(tuple(sessions) if sessions is not None else self.session_catalog())
        self.watch_history_batch(roots)
        self.publish_watch_history()
        quotas = self._quotas() if query_account else tuple(
            quota_snapshots if quota_snapshots is not None else ((quota_snapshot,) if quota_snapshot else ())
        )
        return self.project_watch_accounts(quotas)

    def watch_history_candidates(self, sessions: Sequence[NormalizedSession], *,
                                 active_root_ids: Sequence[str] = (), fresh_root_ids: Sequence[str] = (),
                                 live_root_ids: Sequence[str] = ()) -> tuple[NormalizedSession, ...]:
        """Daily accounting, independent of display scope, comparison sampling and quotas."""
        self._watch_history_active = set(live_root_ids) - set(fresh_root_ids)
        roots, revisions = self._watch_history.candidates(self.source, sessions, timezone_id=self.timezone_id,
                                                         now_ms=self.now_ms, active_root_ids=active_root_ids,
                                                         start_ms=getattr(self, "_watch_period_start_ms", None))
        self.metrics.add("history_candidate_roots", len(roots))
        for root in roots:
            item = self._analyzed.get(root.session_id)
            if item is not None and (item.bundle.source_revision != revisions[root.session_id]
                    or (root.session_id not in fresh_root_ids and not item.bundle.cacheable
                        and self._analyzed_at_ms.get(root.session_id) != self.now_ms)):
                self.invalidate_roots((root.session_id,))
        return tuple(root for root in roots if root.session_id in active_root_ids
                     or not self._watch_history.unchanged(root.session_id, revisions[root.session_id]))

    def watch_history_batch(self, roots: Sequence[NormalizedSession]) -> tuple[TraceEntry, ...]:
        with self.metrics.measure("historical_accounting"):
            force = {root.session_id for root in roots if root.session_id in self._watch_history_active}
            prepared = self.prepare_roots(roots, force_fresh_ids=force)
            entries = []
            for root in roots:
                item = self._analyze(root, force_fresh=root.session_id in force and root.session_id not in prepared)
                entries.extend(self._watch_history.record(root.session_id, item.bundle, now_ms=self.now_ms))
        return tuple(entries)

    def publish_watch_history(self) -> None:
        self._watch_quota_entries = self._watch_history.entries()

    def watch_period_history_due(self) -> bool:
        start = self._watch_history.scope_start_ms
        return start is not None and start > getattr(self, "_watch_period_start_ms", start)

    def project_watch_accounts(self, quotas: Sequence[AccountSnapshot]) -> tuple[AccountsQuotasProjection, tuple[TraceEntry, ...]]:
        """Publish new quota evidence over cached local usage, without source I/O."""
        from src.analysis.period_ccost import history_start
        day = local_day_start_ms(self.timezone_id, now_ms=self.now_ms)
        self._watch_period_start_ms = history_start(quotas, day, self.now_ms)
        projection, today = self._watch_account_projection.project(
            quotas, self._watch_quota_entries, self._load_comparison_catalog(), now_ms=self.now_ms,
            day_start_ms=day,
            month_start_ms=local_month_start_ms(self.timezone_id, now_ms=self.now_ms), timezone_id=self.timezone_id,
            workday_calendar=str(self.config.get("workdayCalendar") or ""),
            period_entries=self._watch_history.retained_entries(),
            observed_start_ms=(self._watch_history.published_start_ms
                               if self._watch_history.day_start_ms == day else None))
        if self._watch_history.published_start_ms is None or self._watch_history.published_start_ms > self._watch_period_start_ms:
            projection = replace(projection, accounts=tuple(replace(account, ccost_scopes=tuple(
                (name, None) for name, _cost in account.ccost_scopes)) for account in projection.accounts))
        return projection, today

    def _account_history(self, quotas, roots, root_activity):
        from src.analysis.period_ccost import history_start
        if not quotas:
            return self._accounts_quotas(())
        day = local_day_start_ms(self.timezone_id, now_ms=self.now_ms)
        month = local_month_start_ms(self.timezone_id, now_ms=self.now_ms)
        cutoff = min(month, history_start(quotas, day, self.now_ms, include_copilot_month=True))
        selected = HistoryRequirements("account-periods", start_ms=cutoff).select(roots, root_activity)
        self.prepare_roots(selected)
        return self._accounts_quotas(quotas, roots=tuple(self._analyze(root) for root in selected),
                                     today_start_ms=day, observed_start_ms=cutoff)

    def build(self, request: ReportRequest) -> ReportProjection:
        self.metrics.mode = request.kind.value
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

    def report_source_revisions(self) -> tuple[tuple[str, str], ...]:
        """Per-root evidence, not a claim of one cross-root/provider transaction."""
        return tuple(sorted(self._acquisition.revisions.items()))

    def report_request_identities(self) -> tuple[tuple[str, str | None, str | None, str | None], ...]:
        """Canonical request references for retained report detail, never raw payloads."""
        return tuple((entry.session_id, entry.parent_event_id, entry.message_id, entry.step_part_id)
                     for item in self._analyzed.values() for entry in item.bundle.trace_entries)

    def _build(self, request: ReportRequest) -> ReportProjection:
        catalog = self._load_catalog()
        self.progress(WorkProgress("Listing OpenCode sessions", "catalog"))
        all_sessions = self.session_catalog()
        roots, root_activity = self._ordered_roots(all_sessions)
        self.metrics.counts.update(catalog_sessions=len(all_sessions), catalog_roots=len(roots))
        if request.kind is ReportKind.SESSIONS:
            from .history import session_catalog_revision
            revision = session_catalog_revision(self.selection.selected, all_sessions)
            return self._build_session_list(request, roots, root_activity, revision)
        if request.kind is ReportKind.SESSION:
            return self._build_session_detail(request, all_sessions)
        if request.kind is ReportKind.DATE:
            return self._build_date_detail(request, roots, root_activity)
        return self._build_dashboard(request, catalog, roots, root_activity)

    def _build_session_list(self, request: ReportRequest, roots: Sequence[NormalizedSession],
                            root_activity: Mapping[str, int], revision: str) -> ReportProjection:
        from .models import SessionListPage
        if request.session_catalog_revision is not None and request.session_catalog_revision != revision:
            raise SessionCatalogChangedError("Session catalog changed; restart from the recent page")
        size = request.session_page_size
        if (size is not None and (type(size) is not int or not 1 <= size <= 100)
                or type(request.session_offset) is not int or request.session_offset < 0
                or request.session_offset and (size is None or not request.session_catalog_revision)
                or request.session_offset >= len(roots) and request.session_offset != 0):
            raise ReportRequestError("Invalid session page")
        if request.session_limit is not None and request.session_limit < 1:
            raise ReportRequestError("Session limit must be positive or all")
        available = roots if request.session_limit is None else roots[:request.session_limit]
        if request.session_offset and request.session_offset >= len(available):
            raise ReportRequestError("Session page is outside the requested scope")
        selected = HistoryRequirements("session-list", limit=size, offset=request.session_offset).select(available, root_activity)
        self.prepare_roots(selected)
        analyzed = tuple(self._analyze(root) for root in selected)
        self.progress(WorkProgress("Building session summaries", "projection"))
        # A truncated listing only covers activity since its oldest listed root.
        cutoff = (root_activity.get(selected[-1].session_id, selected[-1].updated_at_ms)
                  if selected and len(selected) < len(roots) else None)
        return ReportProjection(
            ReportKind.SESSIONS, "Available sessions", self.selection.selected.upper(), tuple(self.selection.warnings),
            session_usage=self._session_rows(analyzed),
            notes=migration_gap_notes(self.selection.migration_gap, start_ms=cutoff),
            session_page=SessionListPage(request.session_offset, size, len(available), revision) if size else None,
        )

    def _build_session_detail(self, request: ReportRequest, sessions: Sequence[NormalizedSession]) -> ReportProjection:
        if not request.session_id:
            raise ReportRequestError("Session report requires a session id")
        root = root_for_session(sessions, request.session_id)
        if root is None:
            raise SessionNotFoundError(f"OpenCode session '{request.session_id}' was not found.")
        item = self._analyze(root, detail=True)
        self.progress(WorkProgress("Building prompt analytics", "projection"))
        block = self._prompt_block(item, snapshot_running_metrics=True)
        return self.session_detail_projection(request.session_id, root, block)

    def session_detail_projection(self, session_id, root, block) -> ReportProjection:
        """Shared snapshot/live report semantics, never Watch display metrics."""
        return ReportProjection(
            ReportKind.SESSION, f"Session {session_id}", self.selection.selected.upper(), tuple(self.selection.warnings),
            prompt_blocks=(block,),
            notes=(("WARNING: CCost totals are incomplete because some reference pricing is unavailable.",)
                   if not block.comparison_cost_complete else ())
            + migration_gap_notes(self.selection.migration_gap, root_id=root.session_id),
        )

    def _build_date_detail(self, request: ReportRequest, roots: Sequence[NormalizedSession],
                           root_activity: Mapping[str, int]) -> ReportProjection:
        if not request.date_text:
            raise ReportRequestError("Date report requires a date target")
        date_range = local_report_range(request.date_text, self.timezone_id)
        candidates = HistoryRequirements("date", start_ms=date_range.start_ms).select(roots, root_activity)
        self.prepare_roots(candidates, detail=True)
        analyzed = tuple(self._analyze(root, detail=True) for root in candidates)
        self.progress(WorkProgress("Building prompt analytics", "projection"))
        blocks = _chronological_blocks(tuple(
            block for item in analyzed
            if (block := self._prompt_block(item, start_ms=date_range.start_ms, end_ms=date_range.end_ms)).rows
        ))
        valuation = self._range_comparison(analyzed, date_range.start_ms, date_range.end_ms)
        range_text = ccost_amount(valuation.known_ccost, unresolved=not valuation.complete,
                                  unit=self.config.get("ccostDisplayUnit", "credits"))
        return ReportProjection(
            ReportKind.DATE, f"Date report {date_range.text}", self.selection.selected.upper(), tuple(self.selection.warnings),
            prompt_blocks=blocks,
            notes=(f"CCost for range: {range_text}; reference valuation, not billing.",)
            + migration_gap_notes(self.selection.migration_gap, start_ms=date_range.start_ms, end_ms=date_range.end_ms),
        )

    def _build_dashboard(self, request: ReportRequest, catalog: PricingCatalog, roots: Sequence[NormalizedSession],
                         root_activity: Mapping[str, int]) -> ReportProjection:
        priceable = self._priceable()
        analyzed = recent_sample_roots(roots, root_activity, self._analyze, priceable)
        self.progress(WorkProgress("Comparing model prices", "projection"))
        comparisons, sample, promo_notes, recent, recent_highlight_spans, availability_warnings = self._model_comparison(
            analyzed, all_models=request.kind is ReportKind.ALL_MODELS,
        )
        # Account periods have their own history scope, never the comparison sample.
        quota_projection = self._account_history(self._quotas(), roots, root_activity) if request.kind is ReportKind.NORMAL else None
        sample_prompts = latest_prompts(analyzed, priceable)
        entries = unique_usage(entry for prompt in sample_prompts for entry in prompt.entries)
        reference = self._load_comparison_catalog()
        coverage = comparison_cost(entries, reference.reference_valuation)
        mix_prompts = latest_token_prompts(analyzed, priceable)
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
            recent_model_notice_highlight_spans=recent_highlight_spans,
            token_mix=priced_sample_mix(((entry.model, entry.tokens) for entry in unique_usage(
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
