"""Deep date reports retain every eligible V2 root and canonical range result."""
from decimal import Decimal
from math import ceil
from pathlib import Path
import shutil
import subprocess
import tempfile
from threading import Event, Lock, Thread
import threading
import time
import unittest
from unittest.mock import patch

from development.tests.fixtures.historical_reports import DAY, HistoricalWire, blocked_date_report
from development.tests.fixtures.opencode_v2_service import source_with_current_service
from development.tests.fixtures.watch_runtime import make_service
from src.reports import ReportKind, ReportRequest
from src.application import ReportApplication
from src.web.jobs import ReportJobs


class HistoricalReportTests(unittest.TestCase):
    def test_deep_report_cancel_keeps_live_http_sse_and_shutdown_bounded(self):
        from development.tests.fixtures.web_lifecycle import run_cycle
        result = run_cycle(competing=True, deep_date=True)
        self.assertEqual(0, result['owned_threads'])
        self.assertEqual(0, result['owned_processes'])
        self.assertEqual(2, result['streams'])

    def test_deadline_retains_actual_pending_read_phase_not_an_empty_result(self):
        jobs = ReportJobs(target=blocked_date_report)
        key = jobs.submit(ReportRequest(ReportKind.DATE, date_text='2026-10-25'))
        try:
            until = time.monotonic() + 5
            while time.monotonic() < until:
                jobs.tick()
                state = jobs.snapshot(key)
                if state['progress'].get('stage') == 'date-messages' and state['progress']['completed'] == 4:
                    break
                time.sleep(.01)
            self.assertEqual('running', state['status'])
            self.assertEqual('date-messages', state['progress'].get('stage'))
            self.assertEqual(4, state['progress']['completed'])
            # Once actual HTTP reads are pending, trigger the existing deadline
            # deterministically instead of adding a 120-second test sleep.
            jobs._deadline = 0
            jobs.tick()
            failed = jobs.snapshot(key)
            self.assertEqual('failed', failed['status'])
            self.assertEqual('report_timeout', failed['error'])
            self.assertIsNone(failed['result'])
            self.assertEqual(state['progress'], failed['progress'])
            self.assertIsNone(jobs._active)
        finally:
            jobs.close()

    def test_application_exports_date_phases_without_private_labels(self):
        wire = HistoricalWire(4)
        progress = []
        with source_with_current_service() as (source, _, _), tempfile.TemporaryDirectory() as directory:
            with patch.object(source, '_client', return_value=wire):
                def factory(now, observe):
                    service = make_service(directory, source, now_ms=now)[2]
                    service.progress = observe
                    return service

                result = ReportApplication(factory, clock=lambda: DAY + 86_400_000).execute(
                    ReportRequest(ReportKind.DATE, date_text='2026-10-25'), progress=progress.append).to_json()

        self.assertIsNone(result['error'])
        stages = [event.to_json().get('stage') for event in progress]
        self.assertIn('date-catalog-before', stages)
        self.assertIn('date-messages', stages)
        self.assertIn('date-catalog-after', stages)
        self.assertIn('date-analysis', stages)
        messages = [event for event in progress if event.stage == 'date-messages']
        self.assertEqual([0, 1, 2, 3, 4], [event.completed for event in messages])
        self.assertTrue(all(event.total == 4 for event in messages))
        self.assertEqual(DAY, result['scope']['start_ms'])
        self.assertEqual(DAY + 86_400_000, result['scope']['end_ms'])

    @unittest.skipUnless(shutil.which('node'), 'optional JS VM unavailable')
    def test_browser_work_text_distinguishes_unverified_reads_from_analysis(self):
        path = Path(__file__).resolve().parents[2] / 'src/web/assets/app.js'
        source = path.read_text(encoding='utf-8')
        function = source[source.index('function reportWork('):source.index('function failure(')]
        checks = """
const assert = require('node:assert/strict');
assert.equal(reportWork({phase:'history', stage:'date-messages', completed:868, total:872}),
  'Reading session trees (not yet revision-verified) · 868/872');
assert.equal(reportWork({phase:'history', stage:'date-analysis', completed:4, total:872}),
  'Analyzing date-history roots · 4/872');
"""
        result = subprocess.run(['node', '-'], input=function + checks, text=True, encoding='utf-8',
                                capture_output=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


class HistoricalReportScaleTests(unittest.TestCase):
    def test_many_root_report_overlaps_only_four_independent_source_reads(self):
        wire = HistoricalWire(872)
        first, entered, release, lock = Event(), Event(), Event(), Lock()
        active = [0]
        maximum = [0]
        results, errors = [], []
        with source_with_current_service() as (source, _, _), tempfile.TemporaryDirectory() as directory:
            original = source._load_messages

            def held_read(native):
                first.set()
                with lock:
                    active[0] += 1
                    maximum[0] = max(maximum[0], active[0])
                    if active[0] == 4:
                        entered.set()
                try:
                    release.wait(15)
                    return original(native)
                finally:
                    with lock:
                        active[0] -= 1

            def build():
                try:
                    results.append(service.build(ReportRequest(ReportKind.DATE, date_text='2026-10-25')))
                except BaseException as error:
                    errors.append(error)

            with patch.object(source, '_client', return_value=wire):
                _, _, service, _ = make_service(directory, source, now_ms=DAY + 86_400_000)
                with patch.object(source, '_load_messages', side_effect=held_read):
                    worker = Thread(target=build)
                    worker.start()
                    try:
                        self.assertTrue(first.wait(10), 'Report never reached source hydration')
                        self.assertTrue(entered.wait(2), 'Independent V2 reads remain serialized')
                    finally:
                        release.set()
                        worker.join(30)
                self.assertFalse(worker.is_alive())
                self.assertEqual([], errors)
        self.assertEqual(4, maximum[0])
        self.assertEqual(0, active[0])
        self.assertEqual(872, results[0].range_comparison.observed_requests)
        # Synthetic latency model, not measured HTTP time: 140ms per root's
        # independent reads plus two seconds per actual full-catalog bracket.
        modeled_seconds = ceil(872 / maximum[0]) * .14 + wire.calls['catalog'] * 2
        self.assertLess(modeled_seconds, 120)
        self.assertGreater(872 * .14, 120, 'Serial source work exceeds the unchanged budget in this model')

    def test_872_root_date_report_keeps_all_prompts_costs_and_revision_proofs(self):
        wire = HistoricalWire(872)
        with source_with_current_service() as (source, _, _), tempfile.TemporaryDirectory() as directory:
            with patch.object(source, '_client', return_value=wire):
                _, _, service, _ = make_service(directory, source, now_ms=DAY + 86_400_000)
                result = service.build(ReportRequest(ReportKind.DATE, date_text='2026-10-25'))

        self.assertEqual(872, len(result.prompt_blocks))
        self.assertEqual(872, sum(len(block.rows) for block in result.prompt_blocks))
        self.assertEqual(872, result.range_comparison.observed_requests)
        self.assertEqual(Decimal('12.20800'), result.range_comparison.known_ccost)
        self.assertTrue(result.range_comparison.complete)
        self.assertEqual(872, len(service.report_source_revisions()))
        self.assertEqual(872, wire.calls['messages'])
        self.assertEqual(872, wire.calls['context'])
        self.assertIn(wire.calls['catalog'], (2, 3), 'Only before/after catalogs, allowing an expired initial hint')


class HistoricalReportSourceTests(unittest.TestCase):
    def test_serial_parallel_range_parity_includes_children_archives_and_partial_prices(self):
        wire = HistoricalWire(4)
        wire.sessions[0]['time']['created'] = DAY - 86_400_000
        wire.sessions[1]['parentID'] = 'root-0000'
        wire.sessions[2]['time']['archived'] = DAY + 10_000
        wire.messages['root-0002'][1]['model']['id'] = 'unpriced-model'
        wire.messages['root-0003'][1]['tokens'].pop('output')
        values, revisions = [], []
        with source_with_current_service() as (source, _, _), tempfile.TemporaryDirectory() as directory:
            with patch.object(source, '_client', return_value=wire):
                for parallel in (False, True):
                    service = make_service(str(Path(directory) / str(parallel)), source,
                                           now_ms=DAY + 3 * 86_400_000)[2]
                    service.config['timezone'] = 'Europe/Stockholm'
                    loader = source.load_session_snapshots_observed if parallel else lambda ids, _progress: source.load_session_snapshots(ids)
                    with patch.object(source, 'load_session_snapshots_observed', side_effect=loader):
                        values.append(service.build(ReportRequest(ReportKind.DATE, date_text='2026-10-25:2026-10-26')))
                    revisions.append(service.report_source_revisions())

        self.assertEqual(values[0], values[1])
        self.assertEqual(revisions[0], revisions[1])
        self.assertEqual(3, len(revisions[1]))
        self.assertEqual(4, values[1].range_comparison.observed_requests)
        self.assertFalse(values[1].range_comparison.complete)

    def test_parallel_real_http_brackets_retry_only_changed_root(self):
        with source_with_current_service() as (source, remote, _):
            remote.sessions[1].pop('parentID')
            source.list_sessions()
            original = source._load_messages
            reads, progress = [], []
            lock = Lock()

            def changing(native):
                result = original(native)
                with lock:
                    reads.append(native.data['id'])
                    if native.data['id'] == 'ses_current' and reads.count('ses_current') == 1:
                        remote.sessions[0]['time']['updated'] += 1
                return result

            with patch.object(source, '_load_messages', side_effect=changing):
                snapshots = source.load_session_snapshots_observed(('ses_current', 'ses_current_child'),
                    lambda stage, done, total: progress.append((stage, done, total)))

            self.assertEqual(2, reads.count('ses_current'))
            self.assertEqual(1, reads.count('ses_current_child'))
            self.assertEqual(4, source.metrics.counts['full_catalog_fetches'])
            self.assertEqual({'ses_current', 'ses_current_child'}, set(snapshots))
            self.assertTrue(all(snapshot.complete and snapshot.source_revision == source.get_session_tree_revision(key)
                                for key, snapshot in snapshots.items()))
            self.assertIn(('messages', 2, 2), progress)
            self.assertIn(('catalog-after', 0, 2), progress)
            self.assertFalse(any(thread.name.startswith('cost-guard-v2-history') for thread in threading.enumerate()))

    def test_parallel_source_failure_preserves_first_error_and_joins_workers(self):
        wire = HistoricalWire(20)
        expected = ValueError('controlled source failure')
        with source_with_current_service() as (source, _, _):
            def failing(native):
                raise expected

            with patch.object(source, '_client', return_value=wire), patch.object(source, '_load_messages', side_effect=failing):
                source.list_sessions()
                with self.assertRaises(ValueError) as caught:
                    source.load_session_snapshots_observed(tuple(item['id'] for item in wire.sessions), lambda *_: None)
            self.assertIs(expected, caught.exception)
            self.assertFalse(any(thread.name.startswith('cost-guard-v2-history') for thread in threading.enumerate()))


if __name__ == '__main__':
    unittest.main()
