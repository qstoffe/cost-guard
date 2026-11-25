"""Restore a complete AI Stats projection while its time-dependent evidence is stable."""
from dataclasses import asdict, replace
from decimal import Decimal, InvalidOperation

from src.analysis.ai_stats import POLICY, Stat, StatsPeriod
from src.analysis.ai_stats_models import ModelStanding
from src.analysis.ai_stats_rates import HourlyRates
from src.analysis.ai_stats_responses import ModelResponse
from src.analysis.cache import dependency_signature
from src.analysis.effort_defaults import REVISION as EFFORT_REVISION
from src.analysis.model_identity import current, decode_model, encode_model
from src.analysis.timezones import calendar_periods
from src.cache import warm_history
from src.domain.effort import EffortEvidence
from src.pricing.identities import MODEL_IDENTITY_SEMANTICS
from .ai_stats_evidence import ALGORITHM as EVIDENCE_ALGORITHM
from .history_cohort import identity, structure

NAMESPACE = 'ai-stats-warm-projection'
ALGORITHM = 'ai-stats-projection-3'
KEY = 'last-complete'
MAX_BYTES = 512 * 1024


def binding(service, sessions, revisions, reference):
    members = structure(sessions)
    if members.keys() != revisions.keys() or any(not revision for revision in revisions.values()):
        return None
    periods = calendar_periods(service.timezone_id, service.now_ms)
    signature = dependency_signature((ALGORITHM, EVIDENCE_ALGORITHM, POLICY, MODEL_IDENTITY_SEMANTICS, EFFORT_REVISION,
        identity(service), service.timezone_id, periods,
        service._dependencies(service._load_catalog()),
        reference.diagnostic_signature, service.config.get('workdayCalendar', 'SE'),
        sorted((sid, members[sid], revision) for sid, revision in revisions.items())))
    return signature, periods


def _metric(stat):
    return {name: value for name, value in asdict(stat, dict_factory=_fields).items() if name != 'session_title'}


def _fields(items):
    def encode(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (tuple, list)):
            return [encode(item) for item in value]
        return value

    return {name: encode(value) for name, value in items}


def _number(value):
    if value is None or type(value) is int:
        return value
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError('invalid cached Stats number')
    return result


def _decode_metric(item, titles):
    fields = dict(item)
    fields['value'] = _number(fields['value'])
    fields['session_title'] = titles[fields['session_id']] if fields['session_id'] is not None else ''
    fields['reasons'] = tuple(fields['reasons'])
    rates = fields['rates']
    if rates is not None:
        fields['rates'] = HourlyRates(**{key: _number(value) for key, value in rates.items()})
    rows = []
    for saved in fields['podium']:
        row = dict(saved)
        row['recorded_models'] = tuple(row['recorded_models'])
        row['effort_evidence'] = tuple(EffortEvidence(**value) for value in row['effort_evidence'])
        row['by_effort'] = tuple((effort, _number(value)) for effort, value in row['by_effort'])
        if fields['metric'] == 'token-rate':
            rows.append(ModelResponse(**row))
        else:
            row['value'] = _number(row['value'])
            rows.append(ModelStanding(**row))
    fields['podium'] = tuple(rows)
    return Stat(**fields)


def restore(service, qualification, roots):
    signature, periods = qualification
    value = warm_history.restore(service.cache_repository, NAMESPACE, KEY, ALGORITHM, signature, limit=MAX_BYTES)
    if value is None:
        return None
    try:
        if not 0 <= service.now_ms - value['observed'] <= warm_history.MAX_AGE_MS:
            return None
        if not current(service.source, (decode_model(model) for model in value['models'])):
            return None
        titles = {root.session_id: root.title for root in roots}
        rows = value['rows']
        if [row['period'] for row in rows] != [period for period, _ in periods]:
            return None
        return tuple(StatsPeriod(period, start, service.now_ms,
            tuple(_decode_metric(metric, titles) for metric in row['metrics']),
            _decode_metric(row['matched'], titles) if row['matched'] else None)
            for row, (period, start) in zip(rows, periods))
    except (KeyError, TypeError, ValueError, InvalidOperation, OverflowError):
        return None


def publish(service, qualification, evidence, matches, rows):
    now = service.now_ms
    models = {}
    for root in evidence:
        # Time fillers for broken intervals can still advance between launches.
        # Only save observations whose event/timing frontier is fully behind Now.
        if (not root.source_complete or root.cost_pending
                or any(entry.completed_at_ms > now for entry in root.entries)
                or any(running or left <= 0 or duration is None or duration < 0 or left + duration > now
                        for left, duration, running in root.intervals)):
            return
        # Request-only roots use a synthetic minute for the Working Time card.
        # Avoid reusing observations that depend on a synthetic interval.
        if (root.entries and not root.intervals
                 or any(type(fact.start_ms) is not int or type(fact.duration_ms) is not int
                        or fact.start_ms + fact.duration_ms > now
                        for fact in root.activity)):
            return
        for entry in root.entries:
            model = entry.model
            models[dependency_signature(encode_model(model))] = model
    if any(run and (run.started_at_ms > now or run.completed_at_ms and run.completed_at_ms > now
                    or run.status == 'running') for run in matches):
        return
    signature, _ = qualification
    value = dict(observed=now,
         models=[encode_model(model) for model in models.values()],
         rows=[dict(period=row.period, metrics=[_metric(metric) for metric in row.metrics],
                   matched=_metric(row.matched) if row.matched else None) for row in rows])
    warm_history.publish(service.cache_repository, NAMESPACE, KEY, ALGORITHM, signature, value, limit=MAX_BYTES)
