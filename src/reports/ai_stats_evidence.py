"""Compact AI Stats evidence and conservative, pricing-independent exclusion proofs."""
from decimal import InvalidOperation

from src.analysis.ai_stats import StatsRoot
from src.analysis.cache import dependency_signature
from .token_mix_cache import encode, decode
from .matched_runs import project_run, encode_run, decode_run

ALGORITHM = 'ai-stats-evidence-3-matched-first-input-1'
NAMESPACE = 'ai-stats-evidence'
COVERAGE = 'ai-stats-coverage-1'
INVALID = (KeyError, IndexError, TypeError, ValueError, InvalidOperation, OverflowError)


def payload(bundle, reference, snapshot, config):
    intervals = [(p.prompt_time_ms, p.execution_duration_ms, p.in_progress) for p in bundle.prompts]
    intervals.extend((c.created_at_ms, c.duration_ms, c.in_progress) for c in bundle.compactions)
    return dict(usage=encode(bundle, reference), intervals=intervals,
                complete=snapshot.complete,
                matched=encode_run(project_run(snapshot, bundle, reference, config)),
                pending=any(p.in_progress and not p.entries for p in bundle.prompts))


def decoded(value, root):
    facts = decode(value['usage'])
    intervals = value['intervals']
    if (not isinstance(intervals, list) or type(value['pending']) is not bool
            or type(value['complete']) is not bool):
        raise ValueError('invalid_timing')
    for left, duration, running in intervals:
        if (type(left) is not int or duration is not None and (type(duration) is not int or duration < 0)
                or type(running) is not bool):
            raise ValueError('invalid_timing')
    matched = decode_run(value['matched'])
    if matched is not None and matched.session_id != root.session_id:
        raise ValueError('invalid_match_root')
    return StatsRoot(root.session_id, root.title, tuple(e for e, _p, _c in facts),
                     tuple(tuple(pair) for pair in intervals), value['pending'], value['complete']), facts, matched


def coverage_key(root):
    p = root.provenance
    return dependency_signature((COVERAGE, p.source_type, p.source_generation, p.source_instance, root.session_id))


def coverage(value):
    """Only a complete stable root with known ends may be irrelevant to a window."""
    intervals = value['intervals']
    known = value['complete'] and not value['pending'] and all(
        left > 0 and duration is not None and not running for left, duration, running in intervals)
    ends = [left + duration for left, duration, _running in intervals] if known else []
    ends.extend(fact['completed'] for fact in value['usage'])
    run = value['matched']
    if run:
        ends.append(run['started_at_ms'])
    return dict(end=max(ends, default=0) if known else None, matched=run is not None)


def exclusion(item, revision, start):
    if not item or item.source_revision != revision or item.algorithm_version != COVERAGE or start is None:
        return False
    value = item.payload
    return (isinstance(value, dict) and type(value.get('end')) is int and 0 <= value['end'] < start
            and type(value.get('matched')) is bool)
