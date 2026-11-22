"""Observed first-input run records and evidence-qualified, non-benchmark gaps."""
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class MatchedRun:
    fingerprint: str
    session_id: str
    started_at_ms: int
    completed_at_ms: int | None
    status: str
    provider: str
    model: str
    effort: str
    mixed: bool
    ccost: Decimal | None
    cost_complete: bool
    main_ccost: Decimal | None
    subagent_ccost: Decimal | None
    incoming_context_ccost: Decimal | None
    extra_ccost: Decimal | None
    duration_ms: int | None
    next_context_tokens: int | None
    token_mix_percent: tuple | None
    token_totals: tuple
    calls: int
    linked_agents: int
    errors: int
    contributors: tuple  # (provider, model, effort, calls, known CCost, complete)
    title: str = ''  # Current catalog display only; not persisted by the index.
    activity_ms: int = 0
    model_label: str = ''
    model_identities: tuple = ()  # Compact source-qualified mutable dependencies.
    recorded_models: tuple = ()  # (provider, effective model, effort, recorded selectors)
    effort_evidence: tuple = ()  # Tooltip-only facts, separate from grouping/visible effort.


@dataclass(frozen=True, slots=True)
class RunGap:
    kind: str
    low_id: str
    high_id: str
    low_label: str
    high_label: str
    minimum: Decimal | int
    maximum: Decimal | int
    difference: Decimal | int
    ratio: Decimal | None
    samples: int


@dataclass(frozen=True, slots=True)
class MatchGroup:
    runs: tuple[MatchedRun, ...]
    preview: str
    facts: tuple[RunGap, ...]


@dataclass(frozen=True, slots=True)
class MatchesPage:
    groups: tuple[MatchGroup, ...]
    offset: int
    total: int
    revision: str
    complete: bool
    scanned: int
    excluded: int


def grouped(runs):
    index = defaultdict(dict)
    for run in runs:
        index[run.fingerprint][run.session_id] = run
    groups = [tuple(sorted(values.values(), key=lambda run: (-run.activity_ms, run.session_id)))
              for values in index.values() if len(values) >= 2]
    return tuple(sorted(groups, key=lambda group: (-group[0].activity_ms, group[0].session_id)))


def gap(runs, kind):
    values = [(run.duration_ms if kind == 'time' else run.ccost, run) for run in runs
        if run.status == 'complete' and (kind == 'time' and run.duration_ms is not None
            or kind == 'cost' and run.cost_complete and run.ccost is not None)]
    if len(values) < 2:
        return None
    values.sort(key=lambda pair: (pair[0], pair[1].session_id))
    low, first = values[0]
    high, last = values[-1]
    return RunGap(kind, first.session_id, last.session_id, first.title or first.model,
        last.title or last.model, low, high, high - low,
        Decimal(high) / Decimal(low) if low > 0 else None, len(values))


def facts(runs):
    result = [value for kind in ('time', 'cost') if (value := gap(runs, kind)) is not None]
    same = defaultdict(list)
    for run in runs:
        if not run.mixed and run.provider and run.model and run.effort:
            same[run.provider, run.model, run.effort].append(run)
    # One quiet same-model snippet, selected deterministically by repeat count.
    for key, repeats in sorted(same.items(), key=lambda pair: (-len(pair[1]), pair[0])):
        value = gap(repeats, 'time') or gap(repeats, 'cost')
        if value is not None:
            from dataclasses import replace
            result.append(replace(value, kind='same-' + value.kind,
                low_label='/'.join(key), high_label='/'.join(key)))
            break
    return tuple(result)


def period_fact(runs, start, end, *, complete):
    """Optional eleventh fact; no independent source scan, no partial champions."""
    from .ai_stats import Stat
    if not complete:
        return None
    selected = [run for run in runs if run.started_at_ms >= (start or 0)
                and run.completed_at_ms is not None and run.completed_at_ms <= end]
    gaps = [value for group in grouped(selected)
            if (value := gap(group, 'time')) is not None and value.ratio is not None]
    if not gaps:
        # Failed/unfinished repeats are not proof that no matching input exists.
        if grouped([run for run in runs if run.started_at_ms >= (start or 0)]):
            return None
        return Stat('original-thinker', None, detail='No repeat first prompts found in this period.')
    largest = max(gaps, key=lambda value: (value.ratio, value.high_id, value.low_id))
    return Stat('match-speed-gap', largest.ratio, detail=(
        f'{largest.low_label} → {largest.high_label}; {largest.samples} qualifying runs. '
        'Same first input, not controlled context or answer quality.'))
