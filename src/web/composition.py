"""One-shot Web composition, no CLI wake, Watch, browser or model inference."""
from pathlib import Path

from src.application import ReportApplication
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.pricing.github_copilot import GitHubCopilotPricingProvider
from src.reports import ReportKind, ReportService
from src.sources.selection import SourceSelector


def application(request):
    # Reuse existing account/model wiring, not CLI source wake or dispatch.
    from src.bootstrap import _account_providers, _model_availability_source

    root = Path(__file__).resolve().parents[2]
    config = load_configuration(root).values

    def factory(now, progress):
        selection = SourceSelector().select(str(config["openCode"]["source"]))
        database = CacheDatabase(root)
        database.initialize()
        cache = CacheRepository(database)
        accounts = _account_providers(config, selection.selected) if request.kind is ReportKind.NORMAL else ()
        return ReportService(selection=selection,
            pricing_provider=GitHubCopilotPricingProvider(cache=cache,
                max_age_hours=float(config.get("pricingMaxAgeHours", 1))),
            account_provider=accounts[0] if accounts else None, account_providers=accounts,
            model_availability_source=_model_availability_source(selection),
            cache_repository=cache, config=config, now_ms=now, progress=progress)

    return ReportApplication(factory)
