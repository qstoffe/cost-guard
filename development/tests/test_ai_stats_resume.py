"""Resumable coverage, real work priority and virtual long-running job boundaries."""
from dataclasses import replace
from decimal import Decimal
import json
import os
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from development.tests.fixtures.compact_reports import report_service, NOW
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.stats_slices import slice_report
from src.application.projection import project
from src.pricing.catalog import PricingCatalog
from src.reports import ReportKind, ReportRequest, ReportService
from src.reports.ai_stats import StatsCheckpointError
from src.reports.ai_stats_evidence import COVERAGE, NAMESPACE, coverage, coverage_key
from src.web.jobs import ReportJobs

DAY = 86400000


class StatsResumeTests(unittest.TestCase):
    def setUp(self):
        self.source = SyntheticMonthSource(5, 3, month_start_ms=NOW - DAY)
        self.source.snapshots = {sid: replace(s, complete=True) for sid, s in self.source.snapshots.items()}
        self.original = report_service(self, self.source)
        self.original.selection = replace(self.original.selection, warnings=())

    def service(self, limit=None, scope='30-days'):
        original = self.original
        service = ReportService(selection=original.selection, pricing_provider=original.pricing_provider,
            account_provider=None, cache_repository=original.cache_repository, config=original.config, now_ms=NOW)
        service.stats_slice_roots = limit
        service.stats_scan = 'synthetic-scan' if limit else None
        return service

    def build(self, limit=None, scope='30-days'):
        return self.service(limit).build(ReportRequest(ReportKind.AI_STATS, stats_scope=scope))

    def test_cold_narrow_waits_for_unknown_roots_then_resumes_without_rehydration(self):
        first = self.build(2, 'today')
        second = self.build(2, '7-days')
        final = self.build(2)
        loads = self.source.load_count
        canonical = self.build()

        self.assertEqual((), first.ai_stats)
        self.assertEqual((), second.ai_stats)
        self.assertEqual((2, 4, 5), tuple(r.ai_stats_work['completed'] for r in (first, second, final)))
        self.assertEqual(5, loads)
        self.assertEqual(loads, self.source.load_count)
        self.assertEqual(canonical.ai_stats, final.ai_stats)

    def test_stale_inactive_metadata_never_excludes_recent_requests_or_overlap(self):
        for sid, snapshot in tuple(self.source.snapshots.items()):
            root = replace(snapshot.root, updated_at_ms=NOW - 60 * DAY, active=False)
            self.source.snapshots[sid] = replace(snapshot, root=root, sessions=(root,))

        narrow = self.build(scope='7-days')
        all_time = self.build(scope='all')
        seven = next(row for row in narrow.ai_stats if row.period == '7-days')

        self.assertEqual(next(row for row in all_time.ai_stats if row.period == '7-days'), seven)
        self.assertGreater(next(m.value for m in seven.metrics if m.metric == 'total-cost'), 0)
        self.assertGreater(next(m.value for m in seven.metrics if m.metric == 'working-time'), 0)

    def test_revision_valid_exclusions_finish_short_scope_before_broader_repricing(self):
        for index, (sid, snapshot) in enumerate(tuple(self.source.snapshots.items())):
            if index < 4:
                # Shift the entire old fixture, not merely its catalog timestamps.
                from development.tests.fixtures.synthetic_month import make_root_snapshot
                self.source.snapshots[sid] = replace(make_root_snapshot(index, 3, month_start_ms=NOW - 60 * DAY), complete=True)
        self.build(scope='all')
        catalog = self.original.pricing_provider.catalog
        self.original.pricing_provider.catalog = PricingCatalog(tuple(replace(model,
            tiers=tuple(replace(tier, per_million_output=Decimal(999)) for tier in model.tiers)) for model in catalog.models))
        before = self.source.load_count

        partial = self.build(1, '7-days')
        final = self.build(scope='all')

        self.assertEqual(before + 5, self.source.load_count)
        self.assertEqual(4, partial.ai_stats_work['remaining'])
        self.assertTrue(partial.ai_stats_work['scopes']['7-days']['ready'])
        self.assertFalse(partial.ai_stats_work['scopes']['all']['ready'])
        self.assertEqual(next(r for r in final.ai_stats if r.period == '7-days'),
                         next(r for r in partial.ai_stats if r.period == '7-days'))

    def test_unknown_ends_running_pending_or_incomplete_never_make_exclusion_proofs(self):
        base = dict(usage=[], intervals=[(1, 10, False)], complete=True, pending=False, matched=None)

        for change in (dict(intervals=[(1, None, False)]), dict(intervals=[(1, 10, True)]),
                       dict(pending=True), dict(complete=False)):
            self.assertIsNone(coverage({**base, **change})['end'])
        self.assertEqual(11, coverage(base)['end'])

    def test_active_root_cannot_be_skipped_using_its_previous_stable_exclusion(self):
        from development.tests.fixtures.synthetic_month import make_root_snapshot
        self.source.snapshots = {sid: replace(make_root_snapshot(index, 3,
            month_start_ms=NOW - 60 * DAY), complete=True)
            for index, sid in enumerate(self.source.snapshots)}
        self.build(scope='all')
        snapshot = self.source.snapshots['root-0000']
        root = replace(snapshot.root, active=True)
        self.source.snapshots[root.session_id] = replace(snapshot, root=root, sessions=(root,))
        catalog = self.original.pricing_provider.catalog
        self.original.pricing_provider.catalog = PricingCatalog(tuple(replace(model,
            tiers=tuple(replace(tier, per_million_output=Decimal(999)) for tier in model.tiers)) for model in catalog.models))

        with patch.object(self.source, 'load_session_snapshot', wraps=self.source.load_session_snapshot) as load:
            result = self.build(1, '7-days')

        self.assertEqual([((root.session_id,), {})], load.call_args_list)
        self.assertTrue(result.ai_stats_work['scopes']['7-days']['ready'])
        self.assertEqual(4, result.ai_stats_work['remaining'])

    def test_history_resource_limits_fail_specifically_without_truncated_totals(self):
        for limit in ('MAX_ROOTS', 'MAX_FACTS'):
            with self.subTest(limit=limit), patch('src.reports.ai_stats.' + limit, 1):
                with self.assertRaisesRegex(StatsCheckpointError, 'ai_stats_resource_limit'):
                    self.build()

    def test_stable_warm_slice_reads_neither_transient_checkpoints_nor_exclusion_proofs(self):
        self.build()
        cache = self.original.cache_repository

        with patch.object(cache, 'get_many', wraps=cache.get_many) as read:
            report = self.build(2)

        self.assertEqual([NAMESPACE], [call.args[0] for call in read.call_args_list])
        self.assertTrue(report.ai_stats_work['scopes']['30-days']['ready'])
        self.assertEqual(5, self.source.load_count)

    def test_changed_root_is_reacquired_and_corrupt_evidence_fails_soft(self):
        self.build(2)
        sid = 'root-0004'
        self.source.snapshots[sid] = replace(self.source.snapshots[sid], source_revision='changed')
        before = self.source.load_count

        result = self.build()

        self.assertEqual(before + 4, self.source.load_count)
        self.assertTrue(result.ai_stats_work['scopes']['all']['ready'])
        with self.original.cache_repository.database.connect(operation='write') as connection:
            connection.execute('UPDATE cache_entries SET payload_json=? WHERE namespace=?', ('{"bad":true}', NAMESPACE))
        self.build()
        self.assertEqual(before + 9, self.source.load_count)

    def test_membership_change_during_final_verification_withholds_all_periods(self):
        original = self.source.list_sessions
        calls = []

        def mutate(since_ms=None):
            calls.append(1)
            if len(calls) == 2:
                sid = 'root-0004'
                self.source.snapshots[sid] = replace(self.source.snapshots[sid], source_revision='late-change')
            return original(since_ms)

        with patch.object(self.source, 'list_sessions', side_effect=mutate):
            result = self.build(5)

        self.assertEqual((), result.ai_stats)
        self.assertEqual(1, result.ai_stats_work['remaining'])
        self.assertTrue(self.build(5).ai_stats_work['scopes']['all']['ready'])

    def test_cache_write_failure_can_finish_small_work_but_not_loop_large_scan(self):
        with patch.object(self.original.cache_repository, 'put_many', side_effect=OSError('unavailable')):
            with self.assertRaisesRegex(StatsCheckpointError, 'ai_stats_checkpoint_unavailable'):
                self.build(1)
            result = self.build()

        self.assertTrue(result.ai_stats_work['scopes']['all']['ready'])

    def test_active_evidence_is_fresh_at_publication_and_not_shared_across_observations(self):
        source = SyntheticMonthSource(5, 3, month_start_ms=NOW - DAY, running_roots=1)
        source.snapshots = {sid: replace(s, complete=True) for sid, s in source.snapshots.items()}
        self.source = source
        self.original.selection = replace(self.original.selection, source=source)
        self.build(2)
        self.build(2)
        result = self.build(2)
        before = source.load_count
        warm = self.build()

        self.assertEqual(before + 1, source.load_count)
        self.assertEqual(warm.ai_stats, result.ai_stats)
        self.assertEqual(1, len(self.original.cache_repository.get_many('ai-stats-transient',
            self._transient_keys())))

    def _transient_keys(self):
        with self.original.cache_repository.database.connect(operation='read') as connection:
            return [r[0] for r in connection.execute('SELECT cache_key FROM cache_entries WHERE namespace=?',
                                                   ('ai-stats-transient',))]

    def test_virtual_long_job_crosses_120_seconds_with_finite_children_and_one_shared_slot(self):
        clock, messages, requests = [0.0], [], []
        receiver, sender, process, context = Mock(), Mock(), Mock(), Mock()
        context.Pipe.return_value = receiver, sender
        context.Process.return_value = process
        process.is_alive.return_value = False
        receiver.poll.side_effect = lambda: bool(messages)
        receiver.recv.side_effect = lambda: messages.pop(0)

        def create(*, target, args, **_kwargs):
            request = args[2]
            requests.append(request)
            service = self.service(1)
            report = service.build(request)
            messages.append(('result', json.dumps(dict(error=None, source=dict(status='acquired'),
                                                       view=project(report).to_json())).encode()))
            return process

        context.Process.side_effect = create
        jobs = ReportJobs(context=context)
        self.addCleanup(jobs.close)
        with patch('src.web.jobs.time.monotonic', side_effect=lambda: clock[0]):
            key = jobs.submit(ReportRequest(ReportKind.AI_STATS, stats_scope='all'))
            jobs.tick()
            for scope in ('7-days', 'today', '30-days', 'all', 'all'):
                clock[0] += 40
                self.assertEqual(key, jobs.submit(ReportRequest(ReportKind.AI_STATS, stats_scope=scope)))
                jobs.snapshot(key)
                jobs.tick()
            result = jobs.snapshot(key)

        self.assertEqual('complete', result['status'])
        self.assertEqual(5, len(requests))
        self.assertEqual(5, self.source.load_count)
        self.assertGreater(clock[0], 120)
        self.assertEqual(1, len(jobs._jobs))
        self.assertEqual(1, len({r.observation_ms for r in requests}))
        self.assertIn('today', {r.stats_scope for r in requests})

    def test_watchdog_retries_shrink_then_fail_without_extending_other_deadlines(self):
        from src.web.stats_jobs import timed_out
        job = dict(request=ReportRequest(ReportKind.AI_STATS), status='running')

        timed_out(job)
        self.assertEqual(('queued', 16), (job['status'], job['batch_size']))
        timed_out(job)
        self.assertEqual(('queued', 1), (job['status'], job['batch_size']))
        timed_out(job)
        self.assertEqual(('failed', 'ai_stats_slice_timeout'), (job['status'], job['error']))
        normal = dict(request=ReportRequest(), status='running')
        timed_out(normal)
        self.assertEqual(('failed', 'report_timeout'), (normal['status'], normal['error']))

    def test_requested_scopes_resume_without_polling_or_losing_earlier_goals(self):
        from src.web.stats_jobs import accept, request
        jobs = ReportJobs()
        self.addCleanup(jobs.close)
        broad = ReportRequest(ReportKind.AI_STATS, stats_scope='30-days')
        with patch('src.web.jobs.time.monotonic', return_value=0):
            key = jobs.submit(broad)
        with patch('src.web.jobs.time.monotonic', return_value=600):
            self.assertEqual(key, jobs.submit(replace(broad, stats_scope='7-days')))
            job = jobs._jobs[key]
            narrow = request(job, key)
            accept(job, dict(error=None, view=dict(ai_stats=[dict(period='7-days')],
                ai_stats_work=dict(completed=1))))
            resumed = request(job, key)
            pending = job['status']
            accept(job, dict(error=None, view=dict(ai_stats=[dict(period='7-days'), dict(period='30-days')],
                ai_stats_work=dict(completed=2))))

        self.assertEqual('7-days', narrow.stats_scope)
        self.assertEqual('30-days', resumed.stats_scope)
        self.assertEqual(narrow.observation_ms, resumed.observation_ms)
        self.assertEqual(narrow.scan, resumed.scan)
        self.assertEqual('queued', pending)
        self.assertEqual('complete', job['status'])
        self.assertEqual(('30-days', '7-days'), job['goals'])

    def test_unobserved_host_owned_stats_starts_finishes_and_still_allows_internal_cancel(self):
        clock = [0.0]
        context, receiver, sender, process = Mock(), Mock(), Mock(), Mock()
        context.Pipe.return_value = receiver, sender
        context.Process.return_value = process
        receiver.poll.return_value = True
        receiver.recv.return_value = ('result', json.dumps(dict(error=None, source=dict(status='acquired'),
            view=dict(ai_stats=[dict(period='30-days')], ai_stats_work=dict(completed=1)))).encode())
        process.is_alive.return_value = False
        jobs = ReportJobs(context=context)
        self.addCleanup(jobs.close)
        with patch('src.web.jobs.time.monotonic', side_effect=lambda: clock[0]):
            key = jobs.submit(ReportRequest(ReportKind.AI_STATS))
            clock[0] = 600
            jobs.tick()  # No tab snapshot/heartbeat since admission.
            self.assertEqual('running', jobs._jobs[key]['status'])
            clock[0] += 20
            jobs.tick()
            self.assertEqual('complete', jobs._jobs[key]['status'])
            queued = jobs.submit(ReportRequest(ReportKind.AI_STATS, stats_scope='all'))
            jobs.cancel(queued)

        self.assertEqual('cancelled', jobs.snapshot(queued)['status'])
        self.assertIsNone(jobs._active)

    def test_actual_spawned_slices_checkpoint_and_complete_one_logical_job(self):
        jobs = ReportJobs(target=slice_report, deadline=5)
        self.addCleanup(jobs.close)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, COST_GUARD_STATS_FIXTURE=directory):
            key = jobs.submit(ReportRequest(ReportKind.AI_STATS))
            seen, end = set(), time.monotonic() + 12
            while time.monotonic() < end:
                jobs.tick()
                result = jobs.snapshot(key)
                work = (result.get('result') or {}).get('view', {}).get('ai_stats_work')
                if work:
                    seen.add(work['completed'])
                if result['status'] not in ('queued', 'running'):
                    break
                time.sleep(.01)

        self.assertEqual('complete', result['status'], result['error'])
        self.assertTrue({2, 4, 6, 8, 9} <= seen)
        self.assertIsNone(jobs._active)

    def test_repeated_no_progress_has_a_terminal_churn_reason(self):
        from src.web.stats_jobs import accept
        job = dict(request=ReportRequest(ReportKind.AI_STATS), result=None)
        result = dict(error=None, view=dict(ai_stats=[], ai_stats_work=dict(completed=0)))

        for _ in range(9):
            accept(job, result)

        self.assertEqual(('failed', 'ai_stats_revision_churn'), (job['status'], job['error']))


if __name__ == '__main__':
    unittest.main()
