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

    def test_material_root_hints_coalesce_and_do_not_capture_unrelated_or_identical_frames(self):
        from src.watch.observers import observe_catalog
        from dataclasses import replace
        now = [0]
        details = SessionDetails(clock=lambda: now[0])
        token = details.open('root-0000', 'live')
        peer = details.open('root-0001', 'live')
        observation = observe_catalog(self.source)
        details.observe_source(observation)
        details.tick(self.service)
        details.tick(self.service)
        loads = self.source.load_count
        initial = details.live_hints()
        for _ in range(100):
            details.observe_source(replace(observation, revisions={**observation.revisions, 'unrelated': 'new'}))
            details.tick(self.service)
        self.assertEqual(loads, self.source.load_count)
        self.assertEqual(initial, details.live_hints())

        changed = replace(observation, revisions={**observation.revisions, 'root-0000': 'changed'})
        details.observe_source(changed)
        key, attempt, history = details.claim()
        self.assertEqual('root-0000', key)
        from src.application.session_detail import acquire_detail
        outcome = acquire_detail(self.service, history, key)
        details.observe_source(replace(changed, revisions={**changed.revisions, 'root-0000': 'later'}))
        details.finish(key, attempt, outcome)
        self.assertEqual('root-0000', details.claim()[0], 'one trailing source revalidation survives inflight work')
        self.assertIsNone(details.claim(), 'no parallel capture for the same selected root')
        self.assertIsNotNone(details.page(token, 0)['result'])
        self.assertIsNotNone(details.page(peer, 0)['result'])

    def test_return_wakes_are_bounded_and_do_not_bypass_retry_or_terminal_state(self):
        now = [0]
        details = SessionDetails(clock=lambda: now[0])
        token = details.open('root-0000', 'live')
        details.tick(self.service)
        for _ in range(100):
            details.wake(token)
        key, attempt, _ = details.claim()
        details.finish(key, attempt, dict(error='connection_reset'))
        now[0] = 1
        details.wake(token)
        self.assertIsNone(details.claim(), 'return cannot bypass retry delay')
        now[0] = 5
        key, attempt, _ = details.claim()
        details.finish(key, attempt, dict(error='http_auth_failure', terminal=True))
        now[0] = 200
        details.wake(token)
        self.assertIsNone(details.claim(), 'hints cannot reset authentication failure')

    def test_only_qualified_selected_activity_acknowledges_held_owner_work(self):
        from dataclasses import replace
        from types import SimpleNamespace
        from src.watch.observers import observe_catalog

        details = self.details
        key = 'root-0000'
        token = details.open(key, 'live')
        frozen = details.open(key, 'snapshot')
        peer = details.open('root-0001', 'live')
        observation = observe_catalog(self.source)
        details.observe_source(observation)
        details.tick(self.service)
        details.tick(self.service)
        details.freeze(frozen)
        first = details.page(token, 0, begin=True)
        entry = details.histories[key]
        snapshot = entry['history'].snapshot
        rows = entry['result'].prompt_blocks[0].rows
        new_row = replace(rows[-1], event_id='new-prompt')
        card = SimpleNamespace(snapshot=replace(snapshot, source_revision='changed'), generation=2,
            verified_generation=2, source_status=SimpleNamespace(failed_at=None))
        card.capture = SimpleNamespace(rows=rows, observed_ids={row.event_id for row in rows},
            authoritative=True, retained=False, observed_at_ms=entry['observed_at_ms'])
        changed = replace(observation, revisions={**observation.revisions, key: 'changed'})
        details.observe_source(changed, {key: card})
        self.assertIsNone(details.page(token, 0, begin=True)['activity_refresh'], 'generic revision is not proof')
        claimed_key, attempt, _ = details.claim()
        self.assertEqual(key, claimed_key)
        card.capture.rows = (*rows, new_row)
        card.capture.observed_at_ms += 1
        card.capture.observed_ids.add(new_row.event_id)
        card.verified_generation = 1
        details.observe_source(changed, {key: card})
        self.assertIsNone(details.page(token, 0, begin=True)['activity_refresh'], 'stale Watch capture')
        card.verified_generation = 2
        details.observe_source(changed, {key: card})
        pending = details.page(token, 0, begin=True)
        self.assertEqual('pending', pending['activity_refresh'])
        self.assertEqual((first['revision'], first['total']), (pending['revision'], pending['total']))
        self.assertIsNone(details.page(frozen, 0, begin=True)['activity_refresh'])
        self.assertIsNone(details.page(peer, 0, begin=True)['activity_refresh'])
        hint, loads = details.live_hints(), self.source.load_count
        for _ in range(100):
            details.observe_source(changed, {key: card})
        self.assertEqual(hint, details.live_hints())
        self.assertEqual(loads, self.source.load_count)
        details.finish(key, attempt, dict(error='connection_reset'))
        self.assertEqual('unavailable', details.page(token, 0, begin=True)['activity_refresh'])
        details.observe_source(replace(changed, source_epoch='replacement'), {key: card})
        self.assertIsNone(details.page(token, 0, begin=True)['activity_refresh'])

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

    def test_revision_churn_rearms_after_cooldown_not_poll_or_open(self):
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
        now[0] = 44
        self.details.tick(self.service)
        self.assertEqual(3, self.details.page(token, 0)['acquisition']['attempts'])
        self.source.load_session_snapshot = SyntheticMonthSource(2, 3, month_start_ms=1000).load_session_snapshot
        now[0] = 45
        self.details.tick(self.service)
        self.assertEqual(3, self.details.page(token, 0, begin=True)['total'])
        self.assertEqual(0, self.details.histories['root-0000']['retry_windows'])

    def test_loaded_unadmitted_detail_heals_on_owned_lane_without_false_recovery(self):
        now = [0]
        details = SessionDetails(clock=lambda: now[0])
        token = details.open('root-0000', 'live')
        details.tick(self.service)
        before = details.page(token, 0, begin=True)
        entry = details.histories['root-0000']
        entry['acquisition'].update(phase='queued', changed_at=0)
        now[0] = 120

        stalled = details.page(token, 0, begin=True)
        self.assertEqual('detail_not_admitted', stalled['acquisition']['reason'])
        self.assertEqual(before['revision'], stalled['revision'])
        self.assertEqual(before['result'], stalled['result'])
        for second in (121, 130, 149):
            now[0] = second
            self.assertIsNone(details.claim())
            self.assertEqual('failed', details.page(token, 0)['acquisition']['phase'])
        now[0] = 150
        self.source.snapshots['root-0000'] = __import__('dataclasses').replace(
            self.source.snapshots['root-0000'], source_revision='healed')
        details.tick(self.service)
        self.assertEqual('ready', entry['acquisition']['phase'])
        self.assertGreater(entry['generation'], 1)
        self.assertEqual(0, entry['retry_windows'])
        self.assertNotIn('acquisition', details.page(token, 0, begin=True))

    def test_repeated_failed_windows_back_off_and_peer_and_inflight_keep_ownership(self):
        now = [0]
        details = SessionDetails(clock=lambda: now[0])
        token = details.open('root-0000', 'live')
        for window in range(7):
            for attempt_index in range(3):
                key, attempt, _ = details.claim()
                details.finish(key, attempt, dict(error='detail_worker_failed'))
                now[0] += 5 * (attempt_index + 1)
            entry = details.histories['root-0000']
            due = entry['retry_at']
            cooldown = min(300, 30 * 2 ** min(window, 4))
            self.assertEqual(cooldown, due - (now[0] - 15))
            now[0] = due - 1
            details.page(token, 0)  # Renew only the existing interested lease.
            self.assertIsNone(details.claim())
            now[0] = due
            self.assertIsNone(details.claim(unavailable=True))
        peer = details.open('root-0001', 'live')
        key, attempt, _ = details.claim()
        self.assertEqual('root-0000', key)
        now[0] += 121
        details.progress(key, attempt, 'reading', 200)
        self.assertNotEqual('detail_not_admitted', details.page(token, 0)['acquisition']['reason'])
        self.assertTrue(details.current(key, attempt))
        self.assertEqual('root-0001', details.claim()[0], 'inflight work cannot be reset or starve the peer')

    def test_hard_failures_and_expired_attempts_never_automatically_reopen(self):
        for reason in ('http_auth_failure', 'source_identity_changed', 'session_missing',
                       'unsupported_schema', 'permission_denied'):
            now = [0]
            details = SessionDetails(clock=lambda: now[0])
            token = details.open('root', 'live')
            key, attempt, _ = details.claim()
            details.finish(key, attempt, dict(error=reason, terminal=True))
            now[0] = 200
            details.page(token, 0)
            self.assertIsNone(details.claim(), reason)
        now = [0]
        details = SessionDetails(clock=lambda: now[0])
        details.open('root', 'live')
        key, old, _ = details.claim()
        now[0] = 301
        replacement = details.open('root', 'live')
        self.assertFalse(details.current(key, old))
        details.finish(key, old, dict(error='old_failure', terminal=True))
        self.assertEqual('queued', details.page(replacement, 0)['acquisition']['phase'])

    def test_only_retryable_http_status_rearms_after_exhausted_window(self):
        for http_status in (403, 404, 503):
            with self.subTest(http_status=http_status):
                now = [0]
                details = SessionDetails(clock=lambda: now[0])
                token = details.open('root-0000', 'live')
                error = SourceUnavailableError('synthetic status',
                    code=FailureCode.AUTH if http_status == 403 else FailureCode.HTTP,
                    http_status=http_status)
                with patch.object(self.service, 'root_for_session', side_effect=error):
                    for second in (0, 5, 15):
                        now[0] = second
                        details.tick(self.service)
                now[0] = 45
                details.tick(self.service)
                page = details.page(token, 0, begin=True)
                if http_status == 503:
                    self.assertEqual(3, page['total'])
                    self.assertEqual('ready', details.histories['root-0000']['acquisition']['phase'])
                else:
                    self.assertIsNone(page['result'])
                    self.assertEqual('failed', page['acquisition']['phase'])

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
