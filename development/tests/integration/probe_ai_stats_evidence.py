"""Opt-in count-only Stats diagnosis; never export source identities or payloads."""
import argparse
from collections import Counter
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import time
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.integration.historical_report_observations import peak_memory
from src.analysis.active_hour import USAGE_FIELDS, deduplicated_requests
from src.analysis.ai_stats import outside_period
from src.cache import CacheDatabase, CacheRepository
from src.reports import ReportKind, ReportRequest, ReportService
from src.reports.ai_stats import StatsAcquisition
from src.reports.ai_stats_evidence import payload
from src.sources.opencode_v2_wire import current_union_message_to_legacy_bundle


def matrix(acquisition, report):
    all_roots = [item[0][0] for item in acquisition.evidence.values()]
    costs = {(e.model, e.tokens): parts for item in acquisition.evidence.values() for e, _p, parts in item[0][1]}
    result = []
    for row in report.ai_stats:
        roots = [r for r in all_roots if not outside_period(r, row.start_ms)]
        entries = [e for e in deduplicated_requests(e for r in roots for e in r.entries)
                   if (row.start_ms is None or e.completed_at_ms >= row.start_ms)
                   and e.completed_at_ms <= row.end_ms]
        intervals = [i for r in roots for i in r.intervals]
        result.append(dict(period=row.period, ready=report.ai_stats_work['scopes'][row.period]['ready'],
            proven_outside_roots=len(all_roots) - len(roots),
            incomplete_roots=sum(not r.source_complete for r in roots),
            unknown_start=sum(left <= 0 for left, _duration, _running in intervals),
            missing_duration=sum(duration is None for _left, duration, _running in intervals),
            negative_duration=sum(duration is not None and duration < 0 for _left, duration, _running in intervals),
            running_intervals=sum(running for _left, _duration, running in intervals),
            pending_roots=sum(r.cost_pending for r in roots),
            unpriced_requests=sum(costs[e.model, e.tokens] is None for e in entries),
            unpriced_roots=sum(any((row.start_ms is None or e.completed_at_ms >= row.start_ms)
                                  and e.completed_at_ms <= row.end_ms and costs[e.model, e.tokens] is None
                                  for e in r.entries) for r in roots),
            missing_token_requests=sum(not USAGE_FIELDS <= set(e.tokens.known_fields) for e in entries),
            missing_token_roots=sum(any((row.start_ms is None or e.completed_at_ms >= row.start_ms)
                                       and e.completed_at_ms <= row.end_ms
                                       and not USAGE_FIELDS <= set(e.tokens.known_fields)
                                       for e in r.entries) for r in roots),
            metrics=[dict(metric=s.metric, status=s.status, reasons=s.reasons,
                          value_present=s.value is not None) for s in row.metrics]))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic', action='store_true')
    parser.add_argument('--baseline', help='Exact Git revision for same-observation formula comparison')
    args = parser.parse_args()
    counts = Counter()

    def observed(bundle, reference, snapshot, config):
        counts['incomplete_snapshots'] += not snapshot.complete
        counts['compactions'] += len(bundle.compactions)
        counts['child_sessions'] += max(0, len(snapshot.sessions) - 1)
        for prompt in bundle.prompts:
            if prompt.execution_duration_ms is None:
                counts['unknown_prompts'] += 1
                assistants = [m for m in snapshot.messages if m.parent_message_id == prompt.prompt_id]
                counts['unknown_with_completed_assistant'] += any(m.completed_at_ms for m in assistants)
                counts['unknown_with_termination'] += any(m.termination for m in assistants)
                counts['unknown_with_error'] += any(m.error_name for m in assistants)
        return payload(bundle, reference, snapshot, config)

    def wire(value, **kwargs):
        if value.get('type') == 'compaction':
            times = value.get('time') or {}
            counts['native_compactions'] += 1
            for field in ('created', 'completed', 'start', 'end', 'started', 'finished', 'duration', 'ran'):
                counts['compaction_time_' + field] += type(times.get(field)) is int and times[field] > 0
        return current_union_message_to_legacy_bundle(value, **kwargs)

    with tempfile.TemporaryDirectory(dir=os.environ['OPENCODE_TOOLKIT_SESSION_SCRATCH']) as directory:
        database = CacheDatabase(Path(directory))
        database.initialize()
        if args.synthetic:
            from development.tests.fixtures.compact_reports import NOW
            from development.tests.fixtures.report_runtime import FakePricingProvider
            from development.tests.fixtures.synthetic_month import SyntheticMonthSource
            from src.sources.selection import SourceSelection
            source = SyntheticMonthSource(2700, 20, month_start_ms=NOW - 3 * 86400000)
            source.snapshots = {sid: replace(s, complete=True) for sid, s in source.snapshots.items()}
            service = ReportService(selection=SourceSelection(source, 'v2', (), source.probe()),
                pricing_provider=FakePricingProvider(), account_provider=None,
                cache_repository=CacheRepository(database), config={'timezone': 'UTC'}, now_ms=NOW)
        else:
            from src.web.composition import application
            request = ReportRequest(ReportKind.AI_STATS, stats_scope='all')
            with patch('src.web.composition.CacheDatabase', lambda _root: database):
                service = application(request)._factory(int(time.time() * 1000), lambda _event: None)
        started, cpu = time.monotonic(), time.process_time()
        try:
            with patch('src.reports.ai_stats.payload', observed), patch(
                    'src.sources.opencode_v2_wire.current_union_message_to_legacy_bundle', wire):
                acquisition = StatsAcquisition(service, 'all')
                acquisition.acquire()
                report = acquisition.project()
            baseline_matrix = None
            if args.baseline:
                module = types.ModuleType('src.analysis.probe_baseline')
                module.__package__ = 'src.analysis'
                sys.modules[module.__name__] = module
                original = subprocess.check_output(['git', 'show', args.baseline + ':src/analysis/ai_stats.py'], cwd=ROOT)
                exec(compile(original, '<baseline-formulas>', 'exec'), module.__dict__)
                class HistoricalObservation:
                    def __init__(self, roots, valuation, *, now, zone):
                        self.roots, self.valuation = roots, valuation
                        self.now, self.zone = now, zone

                    def period(self, **scope):
                        return module.period_stats(self.roots, self.valuation,
                            now=self.now, zone=self.zone, **scope)

                with patch('src.reports.ai_stats.StatsObservation', HistoricalObservation):
                    baseline_matrix = matrix(acquisition, acquisition.project())
            gap_matrix = None
            if args.synthetic:
                sid = acquisition.roots[0].session_id
                (stat, facts, run), volatile = acquisition.evidence[sid]
                damaged = replace(stat, intervals=(*stat.intervals, (service.now_ms - 1000, None, False)))
                acquisition.evidence[sid] = ((damaged, facts, run), volatile)
                gap_matrix = matrix(acquisition, acquisition.project())
                acquisition.evidence[sid] = ((stat, facts, run), volatile)
            print(json.dumps(dict(source='synthetic' if args.synthetic else service.selection.selected,
                roots=len(acquisition.roots), pending=len(acquisition.pending),
                source_warnings=len(service.selection.warnings),
                migration_inspected=bool(service.selection.migration_gap and service.selection.migration_gap.inspected),
                migration_gap=bool(service.selection.migration_gap and service.selection.migration_gap.has_gap),
                seconds=round(time.monotonic() - started, 3), cpu_seconds=round(time.process_time() - cpu, 3),
                peak_memory=peak_memory(), source_counts=counts, matrix=matrix(acquisition, report),
                baseline_matrix=baseline_matrix, synthetic_gap_matrix=gap_matrix,
                operations=service.metrics.snapshot())), flush=True)
        finally:
            service.close_accounts()


if __name__ == '__main__':
    main()
