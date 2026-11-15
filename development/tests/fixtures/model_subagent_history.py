"""Offline native V2 trees with synthetic Sol/Astra prices, never private history."""
from contextlib import ExitStack
from dataclasses import replace
from types import SimpleNamespace

from .compact_reports import Availability, report_service
from .pricing_catalog import catalog
from .subagent_sessions import assistant, incident_source, user
from .watch_runtime import MutableSource
from src.analysis.ai_stats import DAY_MS
from src.application.projection import project
from src.domain import ModelRef
from src.pricing.catalog import PricingCatalog
from src.reports import ReportKind, ReportRequest

SOL, ASTRA = 'gpt-6.1-sol', 'gpt-astra'
NOW = 3 * DAY_MS + 20_000
# Deliberately synthetic prices, not claims about the production catalog.
PRICES = PricingCatalog(tuple(replace(price, model=ModelRef('github-copilot', identity, label))
    for price, identity, label in zip(catalog().models, (SOL, ASTRA), ('GPT-6.1 Sol', 'GPT Astra'))))


def shift_times(value, offset):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == 'time':
                for name in child:
                    child[name] += offset
            else:
                shift_times(child, offset)
    elif isinstance(value, list):
        for child in value:
            shift_times(child, offset)


def native_tree(child_model=SOL, *, multiple=False, older_astra=False):
    with incident_source() as (source, server):
        root = server.messages['ses_current']
        child = server.messages['ses_current_child']
        for message in (*root, *child):
            if message['type'] == 'assistant':
                message['model'].update(id=SOL if message in root else child_model,
                                        variant='high' if message in root else 'max')
        if multiple:
            child[1]['time']['completed'] = 3500
            child.extend((assistant('ca-repeat', 3510, 3550, model=child_model),
                          user('cu2', 3600), assistant('ca2', 3650, 3700, model=child_model)))
            for message in child:
                if message['type'] == 'assistant':
                    message['model']['variant'] = 'max'
            child[2]['finish'] = 'tool-calls'
        shift_times(server.messages, 3 * DAY_MS)
        if older_astra:
            # Available child history outside the current initiating prompt.
            old = assistant('old-astra', 3400, 3800, model=ASTRA)
            old['model']['variant'] = 'max'
            child[:0] = [user('old-cu', 3300), old]
        return source.load_session_snapshot('ses_current')


def attribution_views():
    """Source-normalized evidence through both real report pipelines and wire DTOs."""
    result = []
    with ExitStack() as cleanup:
        owner = SimpleNamespace(addCleanup=cleanup.callback)
        for name, snapshot, scope in (
            ('same', native_tree(), 'today'), ('different', native_tree(ASTRA), 'today'),
            ('mixed-today', native_tree(older_astra=True), 'today'),
            ('mixed-week', native_tree(older_astra=True), '7-days'),
            ('logical-prompts', native_tree(multiple=True), 'today'),
        ):
            service = report_service(owner, MutableSource(snapshot), now_ms=NOW,
                                     availability=Availability(('github-copilot/' + SOL,)))
            service.pricing_provider.catalog = PRICES
            service.cache_token_mix_history = True
            mix = service.build_token_mix_history(scope=scope)
            stats = service.build(ReportRequest(ReportKind.AI_STATS, stats_scope=scope))
            result.append(dict(name=name, period=scope, mix=project(mix).to_json(), stats=project(stats).to_json()))
    return result
