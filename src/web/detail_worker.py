"""Spawn-safe detail composition; no endpoint, credential or service crosses IPC."""
from src.application.session_detail import acquire_detail
from src.domain.progress import observing_work
from src.sources.errors import SourceError
from src.watch.detail_capture import WorkMeter, read_payload, write_payload

from .jobs import run_owned_report


def run_owned_detail(shared, paths):
    run_owned_report(run_detail, shared, paths)


def run_detail(shared, paths):
    from pathlib import Path
    from src.cache import CacheDatabase, CacheRepository
    from src.pricing.github_copilot import GitHubCopilotPricingProvider
    from src.reports import ReportService
    from src.sources.selection import SourceSelector
    meter = WorkMeter(shared)
    service = None
    outcome = dict(error='detail_internal_error', terminal=True)
    try:
        with observing_work(meter.observe):
            payload = read_payload(paths[0])
            source_id, instance, epoch = payload['identity']
            selection = SourceSelector(inspect_migration_gap=False).select('v2' if source_id == 'opencode-v2' else 'v1')
            source = selection.source
            if (source.source_id, source.source_instance, getattr(source, 'observation_epoch', None)) != (source_id, instance, epoch):
                outcome = dict(error='source_identity_changed', terminal=True)
            else:
                inherit = getattr(source, 'restore_detail_evidence', None)
                if callable(inherit):
                    inherit(payload['evidence'])
                root = Path(__file__).resolve().parents[2]
                database = CacheDatabase(root)
                database.initialize()
                cache = CacheRepository(database)
                service = ReportService(selection=selection, config=payload['config'], now_ms=payload['now_ms'],
                    pricing_provider=GitHubCopilotPricingProvider(cache=cache,
                        max_age_hours=float(payload['config'].get('pricingMaxAgeHours', 1))),
                    account_provider=None, cache_repository=cache)
                outcome = acquire_detail(service, payload['history'], payload['key'])
            write_payload(paths[1], outcome, meter.observe)
    except SourceError as error:
        write_payload(paths[1], dict(error=error.code.value, terminal=error.terminal))
    except Exception:
        write_payload(paths[1], dict(error='detail_worker_failed', terminal=True))
    finally:
        if service is not None:
            service.close_accounts()
