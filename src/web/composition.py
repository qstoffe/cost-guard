"""Fresh report/Live integrations; only host startup owns a service wake."""
from pathlib import Path
import time

from src.application import ReportApplication
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.pricing.github_copilot import GitHubCopilotPricingProvider
from src.reports import ReportKind, ReportService
from src.sources.selection import SourceSelector

from .jobs import ModelsPriceRefresh
from .report_control import ManagedReport


def application(request, *, read_admission=None, history_checkpoint=None):
    # Reuse existing account/model wiring, not CLI source wake or dispatch.
    from src.bootstrap import _account_providers, _model_availability_source

    root = Path(__file__).resolve().parents[2]
    config = load_configuration(root).values

    def factory(now, progress):
        selection = SourceSelector().select(str(config["openCode"]["source"]))
        if read_admission is not None:
            selection.source.read_admission = read_admission
        if isinstance(request, ManagedReport) and request.source_identity:
            from .dispatch import source_identity
            from src.reports.ai_stats import StatsCheckpointError
            if source_identity(selection) != request.source_identity:
                raise StatsCheckpointError('source_identity_changed')
        database = CacheDatabase(root)
        database.initialize()
        cache = CacheRepository(database)
        refresh_prices = isinstance(request, ModelsPriceRefresh)
        price_options = dict(defer_metadata_refresh=True) if isinstance(request, ManagedReport) else {}
        provider = GitHubCopilotPricingProvider(cache=cache,
            max_age_hours=876000 if isinstance(request, ManagedReport) else float(config.get("pricingMaxAgeHours", 1)),
            **price_options)
        # Strict fetch precedes acquisition. A failed request cannot publish a new
        # report/date, and this isolated job never refreshes Live's subscriptions.
        catalog = provider.refresh_catalog() if refresh_prices else None
        accounts = (_account_providers(config, selection.selected) if request.kind is ReportKind.NORMAL
                    and not refresh_prices and not isinstance(request, ManagedReport) else ())
        service = ReportService(selection=selection,
            pricing_provider=provider,
            account_provider=accounts[0] if accounts else None, account_providers=accounts,
            model_availability_source=_model_availability_source(selection),
            cache_repository=cache, config=config, now_ms=now, progress=progress,
            cache_token_mix_history=True)
        service.catalog = catalog  # Pin one coherent valuation/catalog for this job.
        if isinstance(request, ManagedReport):
            service.shared_web_evidence = True
            service.allow_partial_history = True
            service.history_batch_size = request.history_batch_size
            service.history_slice_roots = 256
            service.history_checkpoint = history_checkpoint
        if request.kind is ReportKind.AI_STATS:
            service.stats_slice_roots = getattr(request, 'slice_roots', None)
            service.stats_batch_size = getattr(request, 'batch_size', 64)
            service.stats_scan = getattr(request, 'scan', None)
        return service

    observation = getattr(request, 'observation_ms', 0)
    return ReportApplication(factory, clock=(lambda: observation) if observation else None)


def dispatch_dependencies(root):
    from .dispatch_dependencies import DispatchDependencies
    provider = GitHubCopilotPricingProvider(cache=CacheRepository(CacheDatabase(root)))
    return DispatchDependencies(lambda: load_configuration(root).values, provider.cached_catalog)


def live_acquisition(*, selection=None):
    """Transfer one fresh service to the process-lifetime live owner."""
    from src.bootstrap import _account_providers, _model_availability_source
    from src.watch.web_coordinator import WebWatchCoordinator
    from src.watch.acquisition import LiveAcquisition

    root = Path(__file__).resolve().parents[2]
    config = load_configuration(root).values
    if selection is None:
        selection = SourceSelector().select(str(config["openCode"]["source"]))
    database = CacheDatabase(root)
    database.initialize()
    cache = CacheRepository(database)
    accounts = _account_providers(config, selection.selected)
    service = ReportService(selection=selection,
        pricing_provider=GitHubCopilotPricingProvider(cache=cache,
            max_age_hours=float(config.get("pricingMaxAgeHours", 1))),
        account_provider=accounts[0] if accounts else None, account_providers=accounts,
        model_availability_source=_model_availability_source(selection),
        cache_repository=cache, config=config, now_ms=int(time.time() * 1000))
    def card_service(now_ms):
        # Construct on the worker: no mutable integration/SQLite connection is
        # shared with Live, detail transport, or another card's acquisition.
        card_selection = SourceSelector().select(selection.selected)
        card_database = CacheDatabase(root)
        card_database.initialize()
        card_cache = CacheRepository(card_database)
        return ReportService(selection=card_selection,
            pricing_provider=GitHubCopilotPricingProvider(cache=card_cache,
                max_age_hours=float(config.get("pricingMaxAgeHours", 1))),
            account_provider=None, cache_repository=card_cache, config=config, now_ms=now_ms)

    def session_cost_resources():
        # The host already initialized this disposable schema. Aggregate-only
        # work needs neither another source selection nor schema/metadata writes.
        repository = CacheRepository(CacheDatabase(root))
        provider = GitHubCopilotPricingProvider(cache=repository,
            max_age_hours=float(config.get("pricingMaxAgeHours", 1)))
        return repository, provider.get_catalog()

    return LiveAcquisition(WebWatchCoordinator(selection=selection, report_service=service,
        config=config, service_factory=card_service, session_cost_factory=session_cost_resources))
