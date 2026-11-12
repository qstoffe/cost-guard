"""Resumable coverage, real work priority and virtual long-running job boundaries."""
from dataclasses import replace
from decimal import Decimal
import json
import os
from pathlib import Path
import sqlite3
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

    def test_cold_narrow_publishes_numbers_then_resumes_without_rehydration(self):
        first = self.build(2, 'today')
        second = self.build(2, '7-days')
        final = self.build(2)
        loads = self.source.load_count
        canonical = self.build()

        for report in (first, second):
            self.assertEqual(5, len(report.ai_stats))
            self.assertTrue(all(len(row.metrics) == 12 and all(m.value is not None for m in row.metrics if m.metric != 'token-rate')
                                for row in report.ai_stats))
        self.assertFalse(first.ai_stats_work['scopes']['7-days']['ready'])
        self.assertGreater(first.ai_stats[1].metrics[1].value, 0)
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

        for change in (dict(intervals=[(1, None, False)]), dict(intervals=[(1, -1, False)]), dict(intervals=[(1, 10, True)]),
                       dict(pending=True), dict(complete=False)):
            self.assertIsNone(coverage({**base, **change})['end'])
        self.assertEqual(11, coverage(base)['end'])
        self.assertIsNone(coverage({**base, 'usage': [dict(completed=0)]})['end'])

    def test_old_timing_algorithm_and_coverage_proofs_cannot_be_promoted(self):
        from src.cache.repository import CacheEntry
        from src.reports.ai_stats import StatsAcquisition
        from src.reports.ai_stats_evidence import ALGORITHM, exclusion
        self.build(scope='all')
        root = self.source.list_sessions()[0]
        revision = self.source.get_session_tree_revision(root.session_id)
        with self.original.cache_repository.database.connect(operation='read') as connection:
            key = connection.execute('SELECT cache_key FROM cache_entries WHERE namespace=?', (NAMESPACE,)).fetchone()[0]
        saved = self.original.cache_repository.get_many(NAMESPACE, [key])[key]

        self.assertEqual(ALGORITHM, saved.algorithm_version)
        self.assertIsNone(StatsAcquisition._decode(replace(saved,
            algorithm_version='ai-stats-evidence-3-matched-first-input-1'), root, saved.source_revision))
        old = CacheEntry(COVERAGE, 'synthetic', dict(end=1, matched=True), revision, 'ai-stats-coverage-2')
        self.assertFalse(exclusion(old, revision, NOW))
        self.assertTrue(exclusion(replace(old, algorithm_version=COVERAGE), revision, NOW))

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

    def test_membership_change_retains_usable_observation_without_certifying_new_revision(self):
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

        self.assertEqual(5, len(result.ai_stats))
        self.assertEqual(0, result.ai_stats_work['remaining'])
        self.assertEqual(1, len(result.source_warnings))
        self.assertGreater(result.ai_stats[-1].metrics[1].value, 0)
        self.assertTrue(self.build(5).ai_stats_work['scopes']['all']['ready'])

    def test_cache_write_failure_can_finish_small_work_but_not_loop_large_scan(self):
        readonly = sqlite3.OperationalError('read only')
        readonly.sqlite_errorcode = sqlite3.SQLITE_READONLY
        for error in (OSError('unavailable'), readonly, sqlite3.OperationalError('unknown')):
            with self.subTest(error=type(error).__name__), patch.object(self.original.cache_repository, 'put_many', side_effect=error):
                partial = self.build(1)
                result = self.build()

            self.assertEqual('ai_stats_checkpoint_unavailable', partial.ai_stats_work['checkpoint_error'])
            self.assertGreater(partial.ai_stats[-1].metrics[1].value, 0)
            self.assertFalse(partial.ai_stats_work['scopes']['all']['ready'])
            self.assertTrue(result.ai_stats_work['scopes']['all']['ready'])

    def test_real_transient_cache_writer_backs_off_then_dispatcher_automatically_finishes(self):
        from src.application import ReportApplication
        from src.web.dispatch import DataDispatcher, source_identity
        from development.tests.fixtures.historical_web_inputs import observe_cache_writes
        clock, messages, failures, applications = [0.0], [], [], []
        receiver, sender, process, context = Mock(), Mock(), Mock(), Mock()
        context.Pipe.return_value = receiver, sender
        process.is_alive.return_value = False
        receiver.poll.side_effect = lambda: bool(messages)
        receiver.recv.side_effect = lambda: messages.pop(0)

        def create(*, target, args, **_kwargs):
            request = args[2]
            application = ReportApplication(lambda _now, _progress:self.service(1), clock=lambda:NOW)
            result = application.execute(request).to_json()
            applications.append(result)
            messages.append(('result', json.dumps(result).encode()))
            return process

        context.Process.side_effect = create
        jobs = ReportJobs(context=context)
        self.addCleanup(jobs.close)
        dispatch = DataDispatcher(jobs, clock=lambda:clock[0], wall_clock=lambda:NOW / 1000)
        # This single-pipe process double models the requested scan, not parallel
        # speculative report children (covered by dispatcher/process probes).
        dispatch.next_background = float('inf')
        request = ReportRequest(ReportKind.AI_STATS)
        cache = self.original.cache_repository
        with tempfile.TemporaryDirectory() as directory:
            observed = observe_cache_writes(type(cache).put_many, failures, root=Path(__file__).resolve().parents[2],
                lock_once=Path(directory) / 'one-write-lock')
            with patch.object(type(cache), 'put_many', observed), patch('src.web.jobs.time.monotonic', side_effect=lambda:clock[0]):
                dispatch.tick(identity=source_identity(self.original.selection))
                dispatch.interest('visible', 'ai-stats', True, request)
                dispatch.tick()
                jobs.tick()
                jobs.tick()
                dispatch.tick()
                partial = applications[0]
                entry = dispatch.entries[request]

                self.assertEqual(sqlite3.SQLITE_BUSY, failures[0]['sqlite_code'])
                self.assertEqual(50, failures[0]['busy_timeout_ms'])
                self.assertTrue(failures[0]['controlled_write_lock'])
                self.assertIsNone(partial['error'])
                self.assertEqual('ai_stats_checkpoint_busy', partial['view']['ai_stats_work']['checkpoint_error'])
                self.assertIsNotNone(entry['result'])
                self.assertFalse(entry['terminal'])
                for _ in range(12):
                    clock[0] = max(clock[0] + .1, entry['due'],
                                   jobs._jobs[entry['job']].get('not_before', 0) if entry['job'] else 0)
                    dispatch.tick()
                    jobs.tick()
                    jobs.tick()
                    dispatch.tick()
                    if entry['job'] is None:
                        break

        self.assertIsNotNone(entry['result'], dict(entry=entry, applications=[value.get('error') for value in applications],
            jobs=[(job['status'],job.get('error')) for job in jobs._jobs.values()]))
        self.assertEqual(0, entry['failures'], dict(entry=entry,
            errors=[value.get('error') for value in applications],
            jobs=[(j['status'], j.get('error')) for j in jobs._jobs.values()]))
        self.assertFalse(entry['terminal'])
        self.assertIsNone(entry['result']['error'])
        self.assertTrue(any(row['period']=='30-days' for row in entry['result']['view']['ai_stats']))
        self.assertTrue(entry['result']['view']['ai_stats_work']['scopes']['30-days']['ready'])

    def test_token_mix_real_busy_checkpoint_is_retryable_and_recovers_after_lock_release(self):
        from src.application import ReportApplication
        from src.reports.token_mix_cache import NAMESPACE as MIX_NAMESPACE
        failures = []
        cache = self.original.cache_repository
        put_many = cache.put_many

        def locked(entries, **kwargs):
            if not failures and any(entry.namespace == MIX_NAMESPACE for entry in entries):
                with cache.database.connect(operation='write') as connection:
                    connection.execute('BEGIN IMMEDIATE')
                    try:
                        return put_many(entries, **kwargs)
                    except sqlite3.Error as error:
                        failures.append(error.sqlite_errorcode)
                        raise
            return put_many(entries, **kwargs)

        def factory(_now, _progress):
            service = self.service()
            service.cache_token_mix_history = service.shared_web_evidence = True
            service.history_checkpoint = lambda _proof: None
            service.history_slice_roots = service.history_batch_size = 1
            return service

        request = ReportRequest(ReportKind.TOKEN_MIX)
        with patch.object(cache, 'put_many', side_effect=locked):
            failed = ReportApplication(factory, clock=lambda: NOW).execute(request).to_json()
        self.assertEqual([sqlite3.SQLITE_BUSY], failures)
        self.assertEqual(dict(code='history_checkpoint_busy', retryable=True), failed['error'])
        self.assertIsNone(failed['view'])
        recovered = self.service()
        recovered.cache_token_mix_history = recovered.shared_web_evidence = True
        result = ReportApplication(lambda *_: recovered, clock=lambda: NOW).execute(request).to_json()
        self.assertIsNone(result['error'])
        self.assertGreater(int(result['view']['token_mix']['known_total_tokens']), 0)

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
        jobs = ReportJobs(target=slice_report)
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

    def test_stalled_work_settles_boundedly_without_claiming_complete_coverage(self):
        from src.web.stats_jobs import accept
        job = dict(request=ReportRequest(ReportKind.AI_STATS), result=None)
        result = dict(error=None, view=dict(ai_stats=[], ai_stats_work=dict(completed=0)))

        for _ in range(7):
            accept(job, result)

        self.assertEqual('complete', job['status'])
        self.assertNotIn('error', job)
        self.assertEqual([], job['result']['view']['ai_stats'])
        accept(job, dict(error=None, view=dict(ai_stats=[dict(period='30-days')],
            ai_stats_work=dict(completed=1))))
        self.assertEqual('complete', job['status'])


if __name__ == '__main__':
    unittest.main()
