"""Allowlisted Comparisons DTOs and unit-aware display, never acquisition/pricing."""
from decimal import Decimal

from src.analysis.timezones import format_local_timestamp
from src.display import duration_text, context_tokens
from src.numbers import ccost_amount
from src.pricing.identities import unverified_alias
from src.domain.model_identity import catalog_display_name
from .contracts import record
from .model_help import request_model_help
from .effort_help import evidence_help


def run(value):
    # Fingerprints never leave the backend; URLs use only canonical session IDs.
    names = '''session_id title started_at_ms completed_at_ms status provider model effort mixed ccost
        cost_complete main_ccost subagent_ccost incoming_context_ccost extra_ccost duration_ms
        next_context_tokens token_mix_percent token_totals calls linked_agents errors'''.split()
    labels = {(item['provider'], item['model']): item.get('display_name') for item in value.model_identities}
    recorded = {(p, m, e): selected for p, m, e, selected in value.recorded_models}
    efforts = {(p, m, e): values for p, m, e, values in value.effort_evidence}
    return record(**{name: getattr(value, name) for name in names}, match_run=True,
        model_label=catalog_display_name(value.provider, value.model_label) or unverified_alias(value.model, value.provider) or value.model,
        contributors=tuple(record(provider=p, model=m, model_label=labels.get((p, m)) or unverified_alias(m, p) or m,
                                  model_help=request_model_help(p, recorded.get((p, m, e), ()),
                                      catalog_model=m if labels.get((p, m)) else None),
                                   effort=e, calls=n, ccost=c, complete=known,
                                   effort_help=evidence_help(efforts.get((p, m, e), ()), explicit=e) or e,
                                   effort_value_help=evidence_help(efforts.get((p, m, e), ()), value_cell=True, explicit=e) or e)
                           for p, m, e, n, c, known in value.contributors))


def fact(value):
    return record(**{name: getattr(value, name) for name in (
        'kind low_id high_id low_label high_label minimum maximum difference ratio samples'.split())}, match_fact=True)


def page(value):
    if value is None:
        return None
    return record(offset=value.offset, total=value.total, revision=value.revision, complete=value.complete,
        scanned=value.scanned, excluded=value.excluded,
        groups=tuple(record(preview=group.preview, runs=tuple(run(item) for item in group.runs),
                            facts=tuple(fact(item) for item in group.facts)) for group in value.groups))


def display_tokens(values, zone):
    if values.get('match_run'):
        start, end = values['started_at_ms'], values['completed_at_ms']
        prefix = '' if values['cost_complete'] else '?'
        return dict(started=format_local_timestamp(start, zone, '%Y-%m-%d %H:%M'),
            precise_start=format_local_timestamp(start, zone, '%Y-%m-%d %H:%M:%S %z'),
            precise_end='Unknown' if end is None else format_local_timestamp(end, zone, '%Y-%m-%d %H:%M:%S %z'),
            ccost='N/A' if values['ccost'] is None else prefix + ccost_amount(Decimal(values['ccost'])),
            context='N/A' if values['next_context_tokens'] is None else '~' + context_tokens(values['next_context_tokens']),
            totals='/'.join(str(item) for item in values['token_totals']))
    if values.get('match_fact'):
        time = values['kind'].endswith('time')
        format_value = duration_text if time else lambda item: ccost_amount(Decimal(item))
        ratio = values['ratio']
        return dict(minimum=format_value(values['minimum']), maximum=format_value(values['maximum']),
            difference=format_value(values['difference']), ratio='N/A (zero baseline)' if ratio is None else f'{Decimal(ratio):.1f}×')
    return {}
