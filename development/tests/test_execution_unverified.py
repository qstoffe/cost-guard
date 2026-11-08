"""Process-local active status is not proof of a persisted request's execution."""
from dataclasses import replace
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from development.tests.fixtures.opencode_v2_service import source_with_current_service
from development.tests.fixtures.execution_lifecycle import checkpoint_timeline
from development.tests.fixtures.compact_reports import rendered
from development.tests.fixtures.watch_runtime import make_service
from src.analysis.causal import build_prompt_records
from src.analysis.core import analyze_snapshot
from src.domain import BackgroundActivity
from src.application.live_projection import project_live
from src.reports.session_history import SessionHistory
from src.reports import ReportKind, ReportRequest
from src.reports.sampling import AnalyzedRoot, latest_prompts, latest_token_prompts
from src.presentation import WatchRenderer
from src.sources.opencode_v2 import OpenCodeV2Source
from src.sources.opencode_v2_wire import fetch_active_ids
from src.watch.card_workers import CardWorkers
from src.watch.cards import WatchCards
from src.watch.models import WatchProjection
from src.watch.observers import observe_catalog
from src.watch.running import running_prompts
from src.watch import WatchCoordinator
from src.watch.tracker import WatchRowTracker


class ExecutionObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.source, self.native, self.registration = self.enterContext(source_with_current_service())
        self.counter = 0
        self.workers = CardWorkers(self.service, workers=1)
        self.addCleanup(self.workers.close)
        self.cards = WatchCards(self.workers)

    def service(self, now):
        self.counter += 1
        source = OpenCodeV2Source(self.registration, timeout_seconds=2)
        service = make_service(str(Path(self.temp) / str(self.counter)), source, now_ms=now)[2]
        self.addCleanup(source.close_reads)
        return service

    def capture(self, now):
        self.cards.catalog(observe_catalog(self.source))
        entry = self.cards.sessions['ses_current']
        self.workers._capture(entry.root, entry.generation, now, entry.snapshot, ())
        for result in self.workers.drain():
            if result.phase != 'timing':
                self.cards.accept(result, now)
        return self.cards.project(now)

    def test_primary_zero_assistant_shape_characterizes_native_status_not_a_red_regression(self):
        checkpoint_timeline(self.native)
        for active in ({'ses_current': {'type': 'running'}}, {}, None):
            with self.subTest(active=active):
                self.native.active = active
                snapshot = self.source.load_session_snapshot('ses_current')
                rows = build_prompt_records(snapshot, tracked_provider=None, now_ms=4_000_000)
                self.assertEqual(2 if active is None or not active else 3, len(rows))
                self.assertTrue(all(row.completed_successfully and not row.in_progress for row in rows[:2]))
                if active:
                    self.assertTrue(rows[-1].in_progress)
                    self.assertEqual(0, rows[-1].model_calls)
                self.assertIs(snapshot.root.active, None if active is None else bool(active))
        self.native.active = {'ses_current': {'type': 'running'}}
        active, _, _ = self.capture(10_000)
        self.assertTrue(active[0].rows[0].prompt.in_progress)
        self.native.active = {}
        active, _, _ = self.capture(4_000_000)
        retired = active[0].rows[0].prompt
        self.assertFalse(retired.in_progress)
        self.assertFalse(retired.completed_successfully)
        self.assertIsNone(retired.completed_at_ms)
        self.capture(5_000_000)
        self.assertEqual(retired.duration_ms, self.cards.sessions['ses_current'].capture.rows[-1].duration_ms)

    def test_unfinished_cross_process_request_is_unverified_in_canonical_detail_and_watch(self):
        for usage in (False, True):
            with self.subTest(usage=usage):
                checkpoint_timeline(self.native, assistant=True, usage=usage)
                self.cards = WatchCards(self.workers)
                history = SessionHistory()
                self.native.active = {'ses_current': {'type': 'running'}}
                owning = self.source.load_session_snapshot('ses_current')
                running = build_prompt_records(owning, tracked_provider=None, now_ms=10_000)[-1]
                self.assertTrue(running.in_progress)
                self.capture(10_000)
                history.acquire(self.service(10_000), 'ses_current')
                self.native.active = {}  # same persisted timeline, another process's drain map
                for now in (4_000_000, 8_000_000):
                    selected = self.source.load_session_snapshot('ses_current')
                    self.assertEqual(owning.messages, selected.messages)
                    record = build_prompt_records(selected, tracked_provider=None, now_ms=now)[-1]
                    self.assertFalse(record.in_progress)
                    self.assertTrue(record.execution_unverified)
                    self.assertFalse(record.aborted or record.watch_error or record.completed_successfully)
                    self.assertEqual(0, record.terminal_time_ms)
                    self.assertIsNone(record.execution_duration_ms)
                    self.assertEqual(running.entries, record.entries)
                    report, _ = history.acquire(self.service(now), 'ses_current')
                    row = report.prompt_blocks[0].rows[-1]
                    self.assertTrue(row.execution_unverified)
                    self.assertIsNone(row.duration_ms)
                    self.assertIsNone(report.prompt_blocks[0].duration_ms)
                    active, earlier, state = self.capture(now)
                    aggregate = running_prompts(active, state)
                    self.assertIsNone(aggregate.count)
                    self.assertFalse(aggregate.complete)
                    wire = project_live(WatchProjection('Watch', 'fixture', (), now_ms=now,
                        active_cards=active, history_cards=earlier, cards_state=state)).to_json()
                    prompt = wire['active_cards'][0]['rows'][0]['prompt']
                    self.assertTrue(prompt['execution_unverified'])
                    self.assertFalse(prompt['in_progress'])
                    self.assertIsNone(prompt['duration_ms'])
                    self.assertIsNone(prompt['completed_at_ms'])
                    self.assertNotEqual('✓', active[0].rows[0].marker)

    def test_unsupported_active_map_cannot_manufacture_negative_evidence(self):
        client = Mock()
        for data in ({'ses_current': {}}, {'ses_current': {'type': 'future'}},
                     {'ses_current': None}, {'ses_current': {'type': 'idle'}}, []):
            with self.subTest(data=data):
                client.json.return_value = {'data': data}
                self.assertIsNone(fetch_active_ids(client))
        client.json.return_value = {'data': {}}
        self.assertEqual(set(), fetch_active_ids(client))
        for raw in ({'data': {}, 'cursor': {'next': 'partial'}}, {'data': {}, 'partial': True},
                    {'data': {'ses_current': {'type': 'running', 'partial': True}}}):
            with self.subTest(raw=raw):
                client.json.return_value = raw
                self.assertIsNone(fetch_active_ids(client))

    def test_web_detail_and_export_do_not_advance_unverified_execution(self):
        checkpoint_timeline(self.native, assistant=True)
        self.native.active = {}
        report, _ = SessionHistory().acquire(self.service(4_000_000), 'ses_current')
        active, earlier, state = self.capture(4_000_000)
        wire = project_live(WatchProjection('Watch', 'fixture', (), now_ms=4_000_000,
            active_cards=active, history_cards=earlier, cards_state=state)).to_json()
        with self.subTest(surface='session detail'):
            self.assertFalse(report.prompt_blocks[0].rows[-1].in_progress)
            self.assertIsNone(report.prompt_blocks[0].rows[-1].duration_ms)
        with self.subTest(surface='Watch export'):
            prompt = wire['active_cards'][0]['rows'][0]['prompt']
            self.assertFalse(prompt['in_progress'])
            self.assertIsNone(prompt['duration_ms'])

    def test_unavailable_partial_and_positive_tool_evidence_remain_conservative(self):
        checkpoint_timeline(self.native, assistant=True)
        for active in (None, {'ses_current': {'type': 'running'}}, {'ses_current': {}}):
            with self.subTest(active=active):
                self.native.active = active
                snapshot = self.source.load_session_snapshot('ses_current')
                record = build_prompt_records(snapshot, tracked_provider=None, now_ms=8_000_000)[-1]
                self.assertTrue(record.in_progress)
                self.assertFalse(record.execution_unverified)
        self.native.active = {}
        snapshot = self.source.load_session_snapshot('ses_current')
        record = build_prompt_records(replace(snapshot, complete=False), now_ms=8_000_000)[-1]
        self.assertTrue(record.in_progress, 'partial data cannot establish the contradiction')
        self.native.messages['ses_current'][-1]['content'] = [{'type': 'tool', 'name': 'read',
            'time': {'created': 6900, 'ran': 6901}, 'state': {'status': 'running'}}]
        record = build_prompt_records(self.source.load_session_snapshot('ses_current'), now_ms=8_000_000)[-1]
        self.assertTrue(record.in_progress, 'positive tool evidence is not an inactivity timeout')

    def test_terminal_recovery_cold_reconstruction_and_new_attempt(self):
        for outcome in ('succeeded', 'failed', 'interrupted'):
            with self.subTest(outcome=outcome):
                checkpoint_timeline(self.native, assistant=True)
                self.native.active = {}
                self.cards = WatchCards(self.workers)
                self.capture(10_000)
                self.native.messages['ses_current'].extend([
                    {'id': 'resume', 'type': 'synthetic', 'text': 'resume checkpoint',
                     'time': {'created': 11_000}},
                    {'id': 'answer', 'type': 'assistant', 'content': [], 'finish': 'stop',
                     'model': {'providerID': 'openai', 'id': 'gpt-5.6'},
                     'time': {'created': 11_100, 'completed': 12_000}},
                    {'id': 'final_idle', 'type': 'idle', 'outcome': outcome,
                     'time': {'created': 12_010}}])
                for now in (13_000, 8_000_000):
                    snapshot = self.source.load_session_snapshot('ses_current')
                    bundle = analyze_snapshot(snapshot, tracked_provider=None, now_ms=now)
                    record = bundle.prompts[-1]
                    self.assertFalse(record.execution_unverified or record.in_progress)
                    self.assertEqual(outcome == 'succeeded', record.completed_successfully)
                    self.assertEqual(outcome == 'failed', record.watch_error)
                    self.assertEqual(outcome == 'interrupted', record.aborted)
                    active, _, _ = self.capture(now)
                    if active:
                        self.assertFalse(active[0].rows[0].prompt.execution_unverified)
                self.native.messages['ses_current'].append({'id': 'new_attempt', 'type': 'assistant',
                    'content': [], 'time': {'created': 9_000_000}})
                self.native.active = {'ses_current': {'type': 'running'}}
                active, _, _ = self.capture(9_100_000)
                self.assertTrue(active[0].rows[0].prompt.in_progress)
                self.assertFalse(active[0].rows[0].prompt.execution_unverified)

    def test_later_positive_status_resolves_uncertainty_without_usage_changes(self):
        checkpoint_timeline(self.native, assistant=True, usage=True)
        self.native.active = {}
        snapshot = self.source.load_session_snapshot('ses_current')
        self.assertFalse(analyze_snapshot(snapshot).cacheable)
        self.capture(10_000)
        entry = self.cards.sessions['ses_current']
        unverified = entry.capture.rows[-1]
        self.native.active = {'ses_current': {'type': 'running'}}
        active, _, _ = self.capture(20_000)
        resumed = active[0].rows[0].prompt
        self.assertTrue(resumed.in_progress)
        self.assertFalse(resumed.execution_unverified)
        self.assertEqual((unverified.ccost, unverified.calls), (resumed.ccost, resumed.calls))

    def test_cli_watch_and_finite_report_share_uncertainty_not_idle_or_success(self):
        checkpoint_timeline(self.native, assistant=True)
        self.native.active = {}
        config, selection, service, _ = make_service(self.temp, self.source, now_ms=4_000_000)
        report = service.build(ReportRequest(ReportKind.SESSION, 'ses_current'))
        self.assertIn('[UNVERIFIED]', rendered(report))
        self.assertIsNone(report.prompt_blocks[0].duration_ms)
        watch = WatchCoordinator(selection=selection, report_service=service, config=config,
            session_id='ses_current', clock_ms=lambda: 4_000_000)
        projection = watch.initialize().projection
        self.assertEqual(0, projection.active_count, 'not a count of confirmed execution')
        self.assertIn('Execution unverified', projection.status)
        row = next(row for row in projection.rows if row.prompt.event_id == 'checkpoint')
        renderer = WatchRenderer(config, stream=io.StringIO(), interactive=False)
        self.assertIn('[UNVERIFIED]', renderer._row_label(row))
        self.assertEqual('?', row.marker)
        self.assertIsNone(row.prompt.duration_ms)

    def test_unverified_usage_stays_observed_but_is_not_a_completed_comparison_sample(self):
        checkpoint_timeline(self.native, assistant=True, usage=True)
        self.native.active = {}
        snapshot = self.source.load_session_snapshot('ses_current')
        bundle = analyze_snapshot(snapshot, tracked_provider=None, now_ms=10_000)
        roots = (AnalyzedRoot(snapshot.root, bundle, False, snapshot),)
        completed = latest_prompts(roots, lambda entry: True)
        observed = latest_token_prompts(roots, lambda entry: True)
        self.assertEqual({'user_0', 'user_1'}, {record.prompt_id for record in completed})
        self.assertEqual({'user_0', 'user_1', 'checkpoint'}, {record.prompt_id for record in observed})

    def test_partial_refresh_cannot_restore_confirmed_running_after_uncertainty(self):
        checkpoint_timeline(self.native, assistant=True)
        self.native.active = {}
        history = SessionHistory()
        self.capture(10_000)
        history.acquire(self.service(10_000), 'ses_current')
        partial = replace(self.source.load_session_snapshot('ses_current'), complete=False)
        with patch.object(OpenCodeV2Source, 'load_session_snapshot', return_value=partial):
            for now in (20_000, 30_000):
                active, _, _ = self.capture(now)
                row = active[0].rows[0].prompt
                self.assertFalse(row.in_progress)
                self.assertTrue(row.execution_unverified)
                self.assertIsNone(row.duration_ms)
                report, _ = history.acquire(self.service(now), 'ses_current')
                self.assertTrue(report.prompt_blocks[0].rows[-1].execution_unverified)
                self.assertIsNone(report.prompt_blocks[0].rows[-1].duration_ms)
        self.native.active = None  # unavailable status alone is not a positive restart
        active, _, _ = self.capture(35_000)
        self.assertTrue(active[0].rows[0].prompt.execution_unverified)
        report, _ = history.acquire(self.service(35_000), 'ses_current')
        self.assertTrue(report.prompt_blocks[0].rows[-1].execution_unverified)
        self.native.active = {'ses_current': {'type': 'running'}}
        active, _, _ = self.capture(40_000)
        self.assertTrue(active[0].rows[0].prompt.in_progress)

    def test_new_positive_work_in_partial_refresh_resolves_retained_uncertainty(self):
        for kind in ('tool', 'background'):
            with self.subTest(kind=kind):
                checkpoint_timeline(self.native, assistant=True)
                self.native.active = {}
                self.cards = WatchCards(self.workers)
                history = SessionHistory()
                self.capture(10_000)
                history.acquire(self.service(10_000), 'ses_current')
                if kind == 'tool':
                    self.native.messages['ses_current'][-1]['content'] = [{
                        'type': 'tool', 'name': 'read', 'time': {'created': 11_000, 'ran': 11_001},
                        'state': {'status': 'running'}}]
                partial = replace(self.source.load_session_snapshot('ses_current'), complete=False)
                if kind == 'background':
                    partial = replace(partial, background=(BackgroundActivity(
                        'new-work', 'ses_current', 'shell', 11_000, 'pending'),))
                with patch.object(OpenCodeV2Source, 'load_session_snapshot', return_value=partial):
                    active, _, _ = self.capture(20_000)
                    row = active[0].rows[0].prompt
                    self.assertTrue(row.in_progress)
                    self.assertFalse(row.execution_unverified)
                    report, _ = history.acquire(self.service(20_000), 'ses_current')
                    self.assertTrue(report.prompt_blocks[0].rows[-1].in_progress)
                    self.assertFalse(report.prompt_blocks[0].rows[-1].execution_unverified)

    def test_cli_retains_uncertainty_through_partial_and_unavailable_until_new_work(self):
        checkpoint_timeline(self.native, assistant=True)
        self.native.active = {}
        snapshot = self.source.load_session_snapshot('ses_current')
        service = self.service(10_000)
        tracker = WatchRowTracker(started_at_ms=10_000, recent_seconds=30, max_rows=1)
        for now, current in ((10_000, snapshot),
                (20_000, replace(snapshot, complete=False)),
                (30_000, replace(snapshot, root=replace(snapshot.root, active=None)))):
            bundle = service._analyze_snapshot(current)
            block = service._prompt_block(AnalyzedRoot(current.root, bundle, False, current))
            rows = tracker.project({'ses_current': block}, {'ses_current': current}, now_ms=now)
            self.assertEqual(1, len(rows))
            self.assertTrue(rows[0].prompt.execution_unverified)
            self.assertFalse(rows[0].prompt.in_progress)
            self.assertEqual('?', rows[0].marker)
            self.assertIsNone(rows[0].prompt.duration_ms)
        self.native.messages['ses_current'][-1]['content'] = [{
            'type': 'tool', 'name': 'read', 'time': {'created': 31_000, 'ran': 31_001},
            'state': {'status': 'running'}}]
        current = replace(self.source.load_session_snapshot('ses_current'), complete=False)
        bundle = service._analyze_snapshot(current)
        block = service._prompt_block(AnalyzedRoot(current.root, bundle, False, current))
        rows = tracker.project({'ses_current': block}, {'ses_current': current}, now_ms=40_000)
        self.assertTrue(rows[0].prompt.in_progress)
        self.assertFalse(rows[0].prompt.execution_unverified)


if __name__ == '__main__':
    unittest.main()
