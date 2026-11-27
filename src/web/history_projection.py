"""Render current reports from the display archive, without selecting OpenCode."""
from bisect import bisect_right
from dataclasses import dataclass, replace
from decimal import Decimal
from functools import cache
from types import MappingProxyType, SimpleNamespace
from uuid import uuid4

from src.analysis.active_hour import deduplicated_requests
from src.analysis.ai_stats import StatsObservation, outside_period
from src.analysis.ai_stats_buckets import friendly_model
from src.analysis.matched_runs import period_fact
from src.analysis.timezones import calendar_periods
from src.application.projection import project
from src.reports import ReportKind
from src.reports.migration_notice import migration_gap_notes
from src.reports.models import ReportProjection
from src.reports.token_mix_history import prepare_history_usage, prepared_history_projection


@dataclass(frozen=True, slots=True)
class PreparedHistory:
    roots: tuple
    stats_requests: tuple
    mix_usage: object
    matches: MappingProxyType
    costs: MappingProxyType
    clock_points: tuple
    report_gap: bool

    @classmethod
    def from_facts(cls, facts):
        roots, requests, prompt_of, matches, costs = [], [], {}, {}, {}
        report_gap = False
        for key, fact in sorted(facts.items(), key=lambda pair: pair[1].report_rank):
            report_gap |= fact.report_rank < fact.latest_rank
            if fact.report is None:
                continue
            stats, usage, match = fact.report
            roots.append(stats)
            if match:
                matches[key] = replace(match, title=stats.title)
            for entry, prompt, parts in usage:
                requests.append(entry)
                if prompt is not None:
                    prompt_of[entry] = prompt
                if parts is not None:
                    costs[entry.model, entry.tokens] = parts
        points = {entry.completed_at_ms for entry in requests}
        for root in roots:
            points.update(entry.completed_at_ms for entry in root.entries)
            for left, duration, _ in root.intervals:
                points.add(left + 1)
                if type(duration) is int and duration > 0:
                    points.add(left + duration)
        for match in matches.values():
            points.add(match.started_at_ms)
        return cls(tuple(roots), deduplicated_requests(
            (entry for root in roots for entry in root.entries), shared_history=True),
            prepare_history_usage(requests, prompt_of, archived=True),
             MappingProxyType(matches), MappingProxyType(costs), tuple(sorted(points)), report_gap)


def observed_in_period(root, start, now):
    lower = start or 0
    return (any(entry.completed_at_ms > 0 and lower <= entry.completed_at_ms <= now for entry in root.entries)
            or any(0 < left <= now and duration is not None and duration >= 0
                   and not running and left + duration >= lower
                   for left, duration, running in root.intervals))


class HistoryProjection:
    def __init__(self, usage):
        self.usage = usage
        self.instance = uuid4().hex
        self.sequence = 0
        self._prepared_facts = None
        self._prepared = None
        self._mix_by_period = {}

    def _prepare(self, facts):
        # ArchivedUsage replaces, never mutates, this snapshot. The single
        # projection worker owns the memo; the HTTP reader never uses it.
        if facts is not self._prepared_facts:
            self._prepared = PreparedHistory.from_facts(facts)
            self._prepared_facts = facts
            self._mix_by_period.clear()
        return self._prepared

    def next_clock_change(self, now):
        if self._prepared is None:
            return None
        points = self._prepared.clock_points
        index = bisect_right(points, now)
        return points[index] if index < len(points) else None

    def _token_mix(self, prepared, service, reference, name, start, valuation):
        # Progress-only publications don't need to regroup unchanged requests.
        # A future-dated recorded request enters the range only at its own clock.
        key = (service.timezone_id, start, bisect_right(prepared.clock_points, service.now_ms),
               reference.models, reference.diagnostic_signature, service.selection)
        previous = self._mix_by_period.get(name)
        if previous is not None and previous[0] == key:
            return previous[1]
        report = prepared_history_projection(service, reference, prepared.mix_usage, scope=name, valuation=valuation)
        self._mix_by_period[name] = key, report
        return report

    def render(self, *, identity, selection, config, reference, now, revisions, activity, available,
               only=None, defer_while_loading=False, unavailable=frozenset(),
               live_roots=frozenset(), refresh_roots=frozenset(), snapshot=None):
        _, facts, more = snapshot if snapshot is not None else self.usage.snapshot()
        if more and defer_while_loading:
            return {}, True
        zone = str(config.get('timezone') or 'Europe/Stockholm')
        periods = calendar_periods(zone, now)
        prepared = self._prepare(facts)
        roots, matches = prepared.roots, prepared.matches
        pending = {key: activity.get(key) for key, revision in revisions.items()
                   if key not in facts or facts[key].report is None or facts[key].revision != revision}
        refreshes = {key for key in refresh_roots if key in facts and facts[key].report is not None}
        service = SimpleNamespace(timezone_id=zone, now_ms=now, selection=selection)
        @cache
        def valuation(model, tokens):
            return prepared.costs.get((model, tokens)) or reference.reference_category_valuation(model, tokens)

        @cache
        def total_cost(model, tokens):
            parts = valuation(model, tokens)
            return sum(parts, Decimal(0)) if parts is not None else None

        stats = StatsObservation(roots, total_cost,
            now=now, zone=zone, workday_calendar=config.get('workdayCalendar', 'SE'),
            model_bucket=lambda model: friendly_model(model, reference), shared_history=True,
            prepared_requests=prepared.stats_requests)
        self.sequence += 1
        reports, stats_rows, progress = {}, [], {}

        def coverage(start, cached, mix_quality):
            lower = start or 0
            waiting = reconciling = False
            unavailable_count = stats_unavailable = 0
            for key, at in pending.items():
                if at is not None and at < lower:
                    continue
                if key in unavailable:
                    unavailable_count += 1
                    stats_unavailable += key not in live_roots
                elif (key in live_roots or at is not None and at > now or
                      key in refreshes and observed_in_period(facts[key].report[0], start, now)):
                    # These revisions can still change the total. They don't
                    # make a usable period wait on the Live/refresh owner.
                    reconciling = True
                else:
                    waiting = True
            gap = bool(selection.warnings or migration_gap_notes(selection.migration_gap, start_ms=start))
            ready = available and not more and not waiting
            verified = ready and not reconciling and not unavailable_count and not gap
            stats_progress = dict(cached=cached, complete=ready, remaining=None,
                                  unavailable=stats_unavailable, recovering=not available)
            mix_progress = dict(stats_progress, unavailable=unavailable_count, reconciling=reconciling,
                                 unverifiable=bool(unavailable_count or gap or mix_quality or prepared.report_gap))
            return verified, stats_progress, mix_progress

        for name, start in periods:
            if only is not None and name != only:
                continue
            period_roots = [root for root in roots if not outside_period(root, start)]
            mix = self._token_mix(prepared, service, reference, name, start, valuation)
            period = dict(mix.token_mix_period, end_ms=now)
            complete, progress[name], mix_progress = coverage(start, len(period_roots), period.get('coverage'))
            stats_rows.append(replace(stats.period(period=name, start=start, source_complete=complete),
                matched=period_fact([matches[root.session_id] for root in period_roots if root.session_id in matches],
                                    start, now, complete=complete and
                                    all(root.source_complete and root.session_id in matches for root in period_roots))))
            mix_complete = complete and not mix_progress['unverifiable']
            if not mix_complete:
                # An unreadable fact's recorded usage time is unknown, so it
                # cannot be excluded from any period using its ingestion clock.
                period.setdefault('coverage', 'unknown' if prepared.report_gap and not mix.model_token_mix
                                  else 'partial')
            mix = replace(mix, token_mix_period=period)
            reports['token-mix', name] = self._result(mix, service, config, identity, mix_complete, mix_progress)
        report = ReportProjection(ReportKind.AI_STATS, 'AI Stats', selection.selected.upper(),
            selection.warnings, notes=migration_gap_notes(selection.migration_gap), ai_stats=tuple(stats_rows),
            ai_stats_work=dict(scopes={name: dict(completed=value['cached'], ready=True)
                                       for name, value in progress.items()}))
        result = self._result(report, service, config, identity, available and not more and not pending, progress)
        for name in progress:
            reports['ai-stats', name] = result
        return reports, more

    def _result(self, report, service, config, identity, complete, progress):
        view = project(report, service.timezone_id, config.get('ccostDisplayUnit', 'credits')).to_json()
        view['history_progress'] = progress
        return dict(schema_version=1, instance_id=self.instance, sequence=self.sequence,
                    observed_at_ms=service.now_ms, scope=dict(timezone_id=service.timezone_id),
                    source=dict(status='acquired' if complete else 'partial', identity=identity,
                                generation=service.selection.selected, observed_at_ms=service.now_ms),
                    view=view, error=None, cache_first=True)
