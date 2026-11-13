"""Finite cold-detail outcomes and poison-root isolation through owned processes."""
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.detail_child import run_owned_fixture
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.application.session_detail import SessionDetails
from src.sources.errors import FailureCode, SourceConcurrentChangeError, SourceSchemaError, SourceUnavailableError
from src.watch.detail_capture import DetailCapture, DetailWorkerStopError, WorkMeter


class DetailProgressTests(unittest.TestCase):
    def test_milestones_known_fractions_and_scalar_work_are_distinct(self):
        from multiprocessing import get_context
        shared = get_context('spawn').Array('d', (0, 0, 0, -1, -1))
        meter = WorkMeter(shared)

        meter.observe('selecting')
        self.assertEqual(3, shared[2])
        meter.observe('verifying')
        self.assertEqual(10, shared[2])
        meter.observe('reading')
        self.assertEqual(15, shared[2])
        meter.observe('analyzing', 73000)
        self.assertEqual(15, shared[2], 'nested heterogeneous units cannot change stage/percent')
        meter.observe('reading', 1, completed=1, total=2)
        self.assertEqual([27, 1, 2], list(shared[2:]))
        meter.observe('reading', completed=0, total=2)
        self.assertEqual(27, shared[2], 'repeated/backward work retains the watermark')
        meter.observe('reading', completed=2, total=2)
        self.assertEqual(40, shared[2])
        meter.observe('analyzing')
        self.assertEqual(40, shared[2])
        meter.observe('projecting')
        self.assertEqual(55, shared[2])
        meter.observe('publishing', completed=1, total=2)
        self.assertEqual(67, shared[2])
        meter.observe('publishing', completed=2, total=2)
        self.assertEqual(69, shared[2], 'only accepted parent publication owns source completion')
        for completed, total in ((1, None), (1, 0), (3, 2), (-1, 2)):
            meter.observe('publishing', completed=completed, total=total)
            self.assertEqual([69, -1, -1], list(shared[2:]))

    def test_attempt_scoped_status_rejects_old_work_and_clock_does_not_advance_percent(self):
        now = [1]
        details = SessionDetails(clock=lambda: now[0])
        token = details.open('root', 'live')
        self.assertEqual(0, details.page(token, 0)['acquisition']['percent'])
        key, attempt, _ = details.claim()

        details.progress(key, attempt, 'reading', 73, percent=27, phase_completed=1, phase_total=2)
        first = details.page(token, 0)['acquisition']
        self.assertEqual((attempt, 27, 1, 2), tuple(first[name] for name in
            ('attempt_id', 'percent', 'phase_completed', 'phase_total')))
        now[0] = 30
        details.progress(key, attempt, 'reading', 73, percent=15)
        self.assertEqual(27, details.page(token, 0)['acquisition']['percent'])
        self.assertEqual(29, details.page(token, 0)['acquisition']['progress_age_seconds'])
        details.finish(key, attempt, dict(error='detail_no_progress'))
        self.assertEqual(27, details.page(token, 0)['acquisition']['percent'])
        now[0] = 36
        _, second, _ = details.claim()
        details.progress(key, attempt, 'publishing', 9000, percent=69)
        after = details.page(token, 0)['acquisition']
        self.assertNotEqual(attempt, second)
        self.assertEqual((second, 3, None), (after['attempt_id'], after['percent'], after['phase_total']))
        details.retry(token)
        self.assertEqual(0, details.page(token, 0)['acquisition']['percent'])


class DetailLivenessTests(unittest.TestCase):
    def setUp(self):
        self.details = SessionDetails()
        self.source = SyntheticMonthSource(2, 3, month_start_ms=1000)
        self.source.source_instance = 'synthetic-detail'
        self.service = report_service(self, self.source, now_ms=100_000_000)

    def test_unavailable_factory_and_unexpected_analysis_have_typed_finite_outcomes(self):
        token = self.details.open('root-0000', 'live')
        self.details.tick(None, unavailable=True)
        page = self.details.page(token, 0, begin=True)
        self.assertEqual('retrying', page['acquisition']['phase'])
        self.assertEqual('source_unavailable', page['acquisition']['reason'])
        self.assertIsNone(page['result'])
        self.details.retry(token)
        self.service.root_for_session = lambda _: (_ for _ in ()).throw(RuntimeError('private content'))
        self.details.tick(self.service)
        page = self.details.page(token, 0, begin=True)
        self.assertEqual('failed', page['acquisition']['phase'])
        self.assertEqual('detail_internal_error', page['acquisition']['reason'])
        self.assertNotIn('private content', str(page))

    def test_real_v1_sqlite_and_v2_http_adapters_recover_and_keep_archived_child_totals(self):
        from development.tests.fixtures.opencode_v1_database import create_v1_database
        from development.tests.fixtures.opencode_v2_service import source_with_service
        from src.domain.progress import observing_work
        from src.sources.opencode_v1 import OpenCodeV1Source
        with tempfile.TemporaryDirectory() as directory, source_with_service() as (v2, _, _):
            path = Path(directory) / 'source.db'
            create_v1_database(path)
            totals = []
            for source in (OpenCodeV1Source(path), v2):
                with self.subTest(source=source.source_id):
                    service = report_service(self, source, now_ms=10000)
                    details = SessionDetails()
                    token = details.open('ses_root', 'live')
                    with patch.object(source, 'load_session_snapshot', side_effect=SourceUnavailableError(
                            'synthetic transport', code=FailureCode.RESET)):
                        details.tick(service)
                    self.assertEqual('connection_reset', details.page(token, 0)['acquisition']['reason'])
                    details.retry(token)
                    work = []
                    with observing_work(lambda phase, units=0, **_: work.append((phase, units))):
                        details.tick(service)
                    page = details.page(token, 0, begin=True)
                    self.assertIsNotNone(page['result'])
                    totals.append(page['result']['view']['prompt_blocks'][0]['total_ccost'])
                    self.assertTrue(any(phase == 'reading' and units > 0 for phase, units in work))
                    archived = details.open('ses_other', 'live')
                    details.tick(service)
                    self.assertEqual('archived', details.page(archived, 0, begin=True)['state'])
            self.assertEqual(totals[0], totals[1], 'linked child/compaction accounting stays canonical')

    def test_repeated_revision_churn_exhausts_budget_poll_and_open_cannot_reset_it(self):
        now = [0]
        self.details = SessionDetails(clock=lambda: now[0])
        token = self.details.open('root-0000', 'snapshot')
        self.source.load_session_snapshot = lambda _: (_ for _ in ()).throw(SourceConcurrentChangeError('changing'))
        for second in (0, 5, 15):
            now[0] = second
            self.details.tick(self.service)
        for _ in range(50):
            page = self.details.page(token, 0, begin=True)
            self.assertEqual('failed', page['acquisition']['phase'])
            self.assertEqual(3, page['acquisition']['attempts'])
        self.details.open('root-0000', 'live')
        now[0] = 100
        self.details.tick(self.service)
        self.assertEqual(3, self.details.page(token, 0)['acquisition']['attempts'])
        self.details.retry(token)
        self.source.load_session_snapshot = SyntheticMonthSource(2, 3, month_start_ms=1000).load_session_snapshot
        self.details.tick(self.service)
        self.assertEqual(3, self.details.page(token, 0, begin=True)['total'])

    def test_missing_and_terminal_source_errors_are_actionable_not_empty_success(self):
        token = self.details.open('absent', 'live')
        self.details.tick(self.service)
        self.assertEqual('session_missing', self.details.page(token, 0)['acquisition']['reason'])
        for error in (SourceSchemaError('unsupported'),
                      SourceUnavailableError('auth', code=FailureCode.AUTH)):
            with self.subTest(code=error.code):
                self.details.retry(token)
                self.service.root_for_session = lambda _, error=error: (_ for _ in ()).throw(error)
                self.details.tick(self.service)
                page = self.details.page(token, 0)
                self.assertTrue(page['acquisition']['retry_available'])
                self.assertIsNone(page['result'])
                self.assertEqual(error.code.value, page['acquisition']['reason'])

    def test_unadmitted_or_stopped_owner_has_finite_status_without_source_io(self):
        now = [0]
        details = SessionDetails(clock=lambda: now[0])
        token = details.open('root', 'live')
        now[0] = 121
        for _ in range(100):
            page = details.page(token, 0)
            self.assertEqual('detail_not_admitted', page['acquisition']['reason'])
            self.assertTrue(page['acquisition']['retry_available'])

    def capture(self, mode, *, rows=3, timeout=2):
        lane = DetailCapture(run_owned_fixture, no_progress_seconds=timeout)
        self.addCleanup(lane.cancel)
        config = dict(detail_test=mode, detail_rows=rows)
        lane.capture(self.details, self.source, config, self.service.now_ms)
        self.assertIsNone(lane.process, 'owned child exit must be confirmed')
        return lane

    def test_permanently_blocked_child_retires_and_healthy_peer_is_not_starved(self):
        poison = self.details.open('root-0000', 'live')
        healthy = self.details.open('root-0001', 'live')
        before = time.monotonic()
        self.capture('blocked')
        self.assertLess(time.monotonic() - before, 5)
        self.assertEqual('detail_no_progress', self.details.page(poison, 0)['acquisition']['reason'])
        self.capture('blocked')
        page = self.details.page(healthy, 0)
        self.assertIn('total', page, page.get('acquisition'))
        self.assertEqual(3, page['total'])

    def test_slow_measured_work_outlives_silence_interval_and_roundtrip_reuses_revision(self):
        token = self.details.open('root-0001', 'live')
        lane = self.capture('progress', rows=1000)
        page = self.details.page(token, 0, begin=True)
        self.assertIn('total', page, page.get('acquisition'))
        self.assertEqual(1000, page['total'])
        self.assertGreater(lane.last_metrics['seconds'], 2)
        self.assertGreater(lane.last_metrics['output_bytes'], 1000)
        self.details.histories['root-0001']['due'] = 0
        self.capture('fast', rows=1000)
        after = self.details.page(token, 0, begin=True)
        self.assertEqual(page['revision'], after['revision'], 'IPC identity must not trigger retransfer')
        self.assertEqual(page['result']['view'], after['result']['view'])

    def test_child_holding_progress_lock_cannot_disable_watchdog(self):
        token = self.details.open('root-0000', 'live')
        before = time.monotonic()
        lane = self.capture('locked')
        self.assertLess(time.monotonic() - before, 5)
        self.assertEqual(1, lane.retired_count)
        self.assertEqual('detail_no_progress', self.details.page(token, 0)['acquisition']['reason'])

    def test_reused_supervisor_thread_can_start_a_healthy_child_after_retirement(self):
        self.details.open('root-0000', 'live')
        peer = self.details.open('root-0001', 'snapshot')
        lane = DetailCapture(run_owned_fixture, no_progress_seconds=2)
        config = dict(detail_test='blocked', detail_snapshots=self.source.snapshots)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(lane.capture, self.details, self.source, config, self.service.now_ms).result(5)
            pool.submit(lane.capture, self.details, self.source, config, self.service.now_ms).result(5)
        page = self.details.page(peer, 0, begin=True)
        self.assertIn('total', page, page.get('acquisition'))
        self.assertEqual(3, page['total'])
        self.assertEqual(2, lane.started_count)
        self.assertEqual(1, lane.retired_count)

    def test_large_child_capture_preserves_complete_rows_and_accounting_without_ipc_truncation(self):
        token = self.details.open('root-0000', 'live')
        lane = self.capture('fast', rows=10000, timeout=3)
        page = self.details.page(token, 0, begin=True)
        block = page['result']['view']['prompt_blocks'][0]
        self.assertEqual(10000, page['total'])
        self.assertEqual(10000, block['total_calls'])
        self.assertEqual(25, len(block['rows']))
        self.assertEqual(1, lane.last_metrics['work']['snapshot_reads'])
        self.assertGreater(lane.last_metrics['output_bytes'], 8 * 1024 * 1024)

    def test_route_retirement_and_late_completion_cannot_publish_or_orphan(self):
        token = self.details.open('root-0000', 'live')
        lane = DetailCapture(run_owned_fixture, no_progress_seconds=2)
        worker = Thread(target=lane.capture, args=(self.details, self.source,
            dict(detail_test='progress'), self.service.now_ms))
        worker.start()
        deadline = time.monotonic() + 3
        while lane.process is None and time.monotonic() < deadline:
            time.sleep(.01)
        self.details.close(token)
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertIsNone(lane.process)
        self.assertIsNone(self.details.histories['root-0000']['result'])
        old = self.details.open('root-0000', 'live')
        key, attempt, _ = self.details.claim()
        self.details.retry(old)
        self.details.finish(key, attempt, dict(error='old_failure', terminal=True))
        self.assertEqual('queued', self.details.page(old, 0)['acquisition']['phase'])

    def test_child_crash_and_failed_start_are_finite_and_release_owned_resources(self):
        token = self.details.open('root-0000', 'live')
        lane = self.capture('crash', timeout=3)
        self.assertEqual('detail_worker_failed', self.details.page(token, 0)['acquisition']['reason'])
        self.assertIsNone(lane.directory)
        self.details.retry(token)
        context = Mock()
        process = context.Process.return_value
        process.start.side_effect = OSError('synthetic failed start')
        process.pid = None
        lane = DetailCapture(run_owned_fixture, context=context)
        lane.capture(self.details, self.source, {}, self.service.now_ms)
        self.assertIsNone(lane.process)
        self.assertIsNone(lane.directory)
        process.close.assert_called_once()
        self.assertEqual('failed', self.details.page(token, 0)['acquisition']['phase'])

    def test_unconfirmed_exit_retains_exact_child_and_ipc_without_new_admission(self):
        token = self.details.open('root-0000', 'live')
        context = Mock()
        context.Array.side_effect = __import__('multiprocessing').get_context('spawn').Array
        process = context.Process.return_value
        process.is_alive.return_value = True
        process.pid = 1  # Simulated handle only; no OS process is addressed.
        lane = DetailCapture(run_owned_fixture, context=context, no_progress_seconds=0)
        with self.assertRaises(DetailWorkerStopError):
            lane.capture(self.details, self.source, {}, self.service.now_ms)
        self.addCleanup(lane.directory.cleanup)
        self.assertIs(lane.process, process)
        self.assertTrue(Path(lane.directory.name, 'input').is_file())
        process.close.assert_not_called()
        self.details.retry(token)
        with self.assertRaises(DetailWorkerStopError):
            lane.capture(self.details, self.source, {}, self.service.now_ms)
        self.assertEqual(1, context.Process.call_count)

    def test_epoch_turnover_rejects_a_late_capture_and_drops_retained_history(self):
        token = self.details.open('root-0001', 'live')
        self.source.observation_epoch = 'old'
        lane = DetailCapture(run_owned_fixture, no_progress_seconds=2)
        worker = Thread(target=lane.capture, args=(self.details, self.source,
            dict(detail_test='progress'), self.service.now_ms))
        worker.start()
        deadline = time.monotonic() + 3
        while lane.process is None and time.monotonic() < deadline:
            time.sleep(.01)
        self.source.observation_epoch = 'new'
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertIsNone(lane.process)
        self.assertEqual('source_identity_changed', self.details.page(token, 0)['acquisition']['reason'])
        self.details.retry(token)
        self.details.tick(self.service)
        self.assertEqual(3, self.details.page(token, 0, begin=True)['total'])
        self.source.observation_epoch = 'next'
        self.source.snapshots = SyntheticMonthSource(2, 1, month_start_ms=1000).snapshots
        self.details.retry(token)
        self.details.tick(self.service)
        self.assertEqual(1, self.details.page(token, 0, begin=True)['total'])


if __name__ == '__main__':
    unittest.main()
