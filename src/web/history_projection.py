"""Render current reports from the display archive, without selecting OpenCode."""
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from src.analysis.ai_stats import StatsObservation, outside_period, windows
from src.analysis.ai_stats_buckets import friendly_model
from src.analysis.matched_runs import period_fact
from src.analysis.timezones import calendar_periods
from src.application.projection import project
from src.reports import ReportKind
from src.reports.migration_notice import migration_gap_notes
from src.reports.models import ReportProjection
from src.reports.token_mix_history import history_projection


class HistoryProjection:
    def __init__(self, usage):
        self.usage = usage
        self.instance = uuid4().hex
        self.sequence = 0

    def render(self, *, identity, selection, config, reference, now, revisions, activity, available,
               only=None, defer_while_loading=False, unavailable=frozenset(),
               live_roots=frozenset(), snapshot=None):
        _, facts, more = snapshot if snapshot is not None else self.usage.snapshot()
        if more and defer_while_loading:
            return {}, True
        zone = str(config.get('timezone') or 'Europe/Stockholm')
        periods = windows(zone, now)
        mix_starts = dict(calendar_periods(zone, now))
        roots, requests, prompt_of, matches, costs = [], [], {}, {}, {}
        for key, fact in sorted(facts.items(), key=lambda pair: pair[1].report_rank):
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
        pending = {key: activity.get(key) for key, revision in revisions.items()
                   if key not in facts or facts[key].report is None or facts[key].revision != revision}
        historical_cutoff = now - 600_000
        service = SimpleNamespace(timezone_id=zone, now_ms=now, selection=selection)
        def valuation(model, tokens):
            return costs.get((model, tokens)) or reference.reference_category_valuation(model, tokens)
        def total_cost(model, tokens):
            parts = valuation(model, tokens)
            return sum(parts, Decimal(0)) if parts is not None else None
        stats = StatsObservation(roots, total_cost,
            now=now, zone=zone, workday_calendar=config.get('workdayCalendar', 'SE'),
            model_bucket=lambda model: friendly_model(model, reference), shared_history=True)
        self.sequence += 1
        reports, stats_rows, progress = {}, [], {}

        def coverage(start, cached):
            lower = start or 0
            waiting = any(key not in live_roots and key not in unavailable and
                          (at is None or lower <= at < historical_cutoff) for key, at in pending.items())
            unqualified = sum(key not in live_roots and key in unavailable and (at is None or lower <= at)
                              for key, at in pending.items())
            complete = (available and not more and not any(at is None or lower <= at for at in pending.values())
                        and not migration_gap_notes(selection.migration_gap, start_ms=start) and not selection.warnings)
            return complete, dict(cached=cached, complete=not more and not waiting,
                                  remaining=None, unavailable=unqualified)

        for name, start in periods:
            if only is not None and name != only:
                continue
            period_roots = [root for root in roots if not outside_period(root, start)]
            complete, progress[name] = coverage(start, len(period_roots))
            stats_rows.append(replace(stats.period(period=name, start=start, source_complete=complete),
                matched=period_fact([matches[root.session_id] for root in period_roots if root.session_id in matches],
                                    start, now, complete=complete and
                                    all(root.source_complete and root.session_id in matches for root in period_roots))))
            mix = history_projection(service, reference, requests, prompt_of, lambda *_: None, scope=name,
                                      valuation=valuation, archived=True)
            mix_start = mix_starts[name]
            mix_complete, mix_progress = coverage(mix_start, sum(not outside_period(root, mix_start) for root in roots))
            mix = replace(mix, token_mix_period={**mix.token_mix_period,
                            **({'coverage': 'partial'} if not mix_complete else {})})
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
