"""Host-owned demand, freshness/backoff and real cooperative process arbitration."""
import time
import unittest
import tempfile
import subprocess
import sys
import shutil
from pathlib import Path
from threading import Timer
from types import SimpleNamespace
from dataclasses import replace
from unittest.mock import patch

from development.tests.fixtures.dispatch_reports import quantum_report, durable_history_report, HistoryFixture
from development.tests.fixtures.compact_reports import report_service, NOW
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.reports import ReportKind, ReportRequest
from src.web.dispatch import DataDispatcher, cadence, usable
from src.web.jobs import ReportJobs
from src.web.report_control import ManagedReport


def result(observed, *, sample=100):
    return dict(error=None, source=dict(status='acquired', observed_at_ms=observed),
                view=dict(kind='normal', model_comparison_sample_size=sample))


class RecordingJobs:
    def __init__(self):
        self.values = {}
        self.priorities = {}

    def submit(self, request):
        key = str(len(self.values))
        self.values[key] = dict(status='queued', result=None, request=request)
        return key

    def snapshot(self, key):
        return self.values.get(key)

    def prioritize(self, priorities):
        self.priorities = priorities

    def cancel(self, key):
        self.values[key]['status'] = 'cancelled'


class DispatcherTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'node unavailable')
    def test_full_and_mini_lease_document_visibility_and_closed_callbacks(self):
        result = subprocess.run([shutil.which('node'), 'development/tests/integration/history_demand.cjs'],
            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def setUp(self):
        self.now = 1000
        self.jobs = RecordingJobs()
        self.dispatch = DataDispatcher(self.jobs, clock=lambda: self.now, wall_clock=lambda: self.now)
        self.dispatch.tick(identity='source')
        self.models = ReportRequest()

    def test_no_speculative_launch_before_interest_and_foreground_completes_first(self):
        self.dispatch.tick()
        self.assertEqual({}, self.jobs.values)
        self.dispatch.interest('tab', 'models', True, self.models)
        self.dispatch.tick(identity='source')
        self.assertFalse(self.dispatch.warm_allowed)
        self.assertEqual(1, len(self.jobs.values))
        self.assertEqual(ReportKind.NORMAL, self.jobs.values['0']['request'].kind)
        self.assertEqual('source', self.jobs.values['0']['request'].source_identity)
        self.jobs.values['0'].update(status='complete', result=result(1_000_000))
        self.dispatch.tick(identity='source')
        self.assertTrue(self.dispatch.warm_allowed)
        self.assertEqual(2, len(self.jobs.values))
        self.assertEqual(ReportKind.AI_STATS, self.jobs.values['1']['request'].kind)

    def test_hidden_and_expired_tabs_drop_priority_but_host_work_survives(self):
        self.dispatch.interest('one', 'models', True, self.models)
        key = self.dispatch.lookup(self.models)['id']
        self.dispatch.tick()
        self.assertEqual(0, self.jobs.priorities[key])
        self.dispatch.interest('one', 'watch', False)
        self.dispatch.tick()
        self.assertEqual(1, self.jobs.priorities[key])
        self.now += 91
        self.dispatch.tick()
        self.assertEqual({}, self.dispatch.tabs)
        self.assertEqual('queued', self.jobs.values[key]['status'])

    def test_visible_earlier_history_demand_does_not_demote_hidden_requested_reports(self):
        self.dispatch.interest('models', 'models', True, self.models)
        self.dispatch.tick()
        key = self.dispatch.entries[self.models]['job']
        self.dispatch.interest('mini', 'watch', True, history=True)
        self.dispatch.tick()
        self.assertEqual(0, self.jobs.priorities[key])
        self.dispatch.interest('models', 'watch', False)
        self.dispatch.tick()
        self.assertEqual(1, self.jobs.priorities[key], 'visible Mini Earlier leaves the hidden request at 1')
        self.dispatch.interest('full', 'watch', True, history=True)
        self.dispatch.tick()
        self.assertEqual(1, self.jobs.priorities[key])
        self.dispatch.tick(ready=False)
        self.assertEqual(3, self.jobs.priorities[key], 'existing source-outage suspension remains separate')
        self.assertEqual('queued', self.jobs.values[key]['status'])

    def test_interest_history_is_optional_strict_and_watch_only(self):
        from src.web.dispatch_http import handle
        replies = []
        handler = SimpleNamespace(path='/api/interest', server=SimpleNamespace(lifecycle=SimpleNamespace(
            dispatcher=self.dispatch)), reply=lambda status, value: replies.append((status, value)))
        original = dict(tab='a' * 32, section='watch', visible=True, request=None)
        for body in (original, dict(original, history=True), dict(original, history=False)):
            handle(handler, body)
            self.assertEqual(200, replies[-1][0])
        for body in (dict(original, history=1), dict(original, history=None),
                dict(original, history=True, section='models', request={'kind':'normal'}),
                dict(original, history=False, section='settings'), dict(original, history=True, capacity=4)):
            handle(handler, body)
            self.assertEqual(400, replies[-1][0])

    def test_two_tabs_coalesce_and_cached_observation_is_not_renewed_on_failure(self):
        self.dispatch.interest('one', 'models', True, self.models)
        self.dispatch.interest('two', 'models', True, self.models)
        key = self.dispatch.lookup(self.models)['id']
        self.assertEqual(key, self.dispatch.lookup(self.models)['id'])
        self.jobs.values[key].update(status='complete', result=result(1_000_000))
        self.dispatch.tick()
        self.now += 300
        self.assertEqual(1_000_000, self.dispatch.lookup(self.models)['result']['source']['observed_at_ms'])
        self.dispatch.lookup(self.models, retry=True)
        current = self.dispatch.entries[self.models]['job']
        self.jobs.values[current].update(status='failed', result={'error': {'code': 'http_auth_failure', 'retryable': False}})
        self.dispatch.tick()
        lookup = self.dispatch.lookup(self.models)
        self.assertTrue(lookup['terminal'])
        self.assertEqual(1_000_000, lookup['result']['source']['observed_at_ms'])

    def test_source_identity_rotation_cancels_work_and_removes_old_results(self):
        self.dispatch.interest('one', 'models', True, self.models)
        self.dispatch.tick(identity='first')
        self.dispatch.tick(identity='second')
        self.assertEqual('cancelled', self.jobs.values['0']['status'])
        self.assertFalse(any(entry['result'] for entry in self.dispatch.entries.values()))

    def test_repeated_transient_faults_back_off_without_a_three_attempt_terminal_cutoff(self):
        for failure in range(10):
            key = self.dispatch.lookup(self.models)['id']
            self.jobs.values[key].update(status='failed', result=dict(
                error=dict(code='concurrent_source_change', retryable=True)))
            self.dispatch.tick()
            lookup = self.dispatch.lookup(self.models)
            self.assertFalse(lookup['terminal'])
            self.assertIsNone(lookup['id'])
            before = len(self.jobs.values)
            self.dispatch.tick()
            self.assertEqual(before, len(self.jobs.values), 'backoff never creates a tight retry loop')
            self.now = self.dispatch.entries[self.models]['due']

        key = self.dispatch.lookup(self.models)['id']
        self.jobs.values[key].update(status='complete', result=result(int(self.now * 1000)))
        self.dispatch.tick()

        self.assertFalse(self.dispatch.lookup(self.models)['terminal'])
        self.assertIsNotNone(self.dispatch.lookup(self.models)['result'])
        self.assertEqual(0, self.dispatch.entries[self.models]['failures'])

    def test_age_boundary_and_qualified_sample_cadence(self):
        for kind in (ReportKind.NORMAL, ReportKind.TOKEN_MIX, ReportKind.AI_STATS, ReportKind.COMPARISONS):
            value = result(1_000_000)
            value['scope'] = dict(kind=kind.value, timezone_id='UTC', local_day_start_ms=0)
            for minutes, expected in [(0, True), (15, True), (59, True), (60, True), (61, True), (2880, True)]:
                with self.subTest(kind=kind, minutes=minutes):
                    self.assertEqual(expected, usable(value, 1_000_000 + minutes * 60_000))
        self.assertFalse(usable(result(1_000_001), 1_000_000))
        self.assertEqual(900, cadence(self.models, result(0, sample=99), True))
        self.assertEqual(3600, cadence(self.models, result(0, sample=100), True))
        self.assertEqual(3600, cadence(self.models, result(0, sample=100), False))

    def test_worker_interruption_recovers_on_host_backoff_but_typed_blockers_do_not_loop(self):
        for kind in (ReportKind.TOKEN_MIX, ReportKind.AI_STATS):
            request = ReportRequest(kind)
            self.dispatch.interest('one', kind.value, True, request)
            for code in ('report_unavailable', 'worker_unavailable', 'cancelled'):
                key = self.dispatch.lookup(request)['id']
                self.jobs.values[key].update(status='failed', error=code)
                self.dispatch.tick()
                entry = self.dispatch.entries[request]
                self.assertFalse(entry['terminal'])
                self.assertIsNone(self.dispatch.lookup(request)['id'])
                self.assertGreater(entry['due'], self.now)
                before = len(self.jobs.values)
                self.dispatch.lookup(request)
                self.assertEqual(before, len(self.jobs.values))
                self.now = entry['due']
            key = self.dispatch.lookup(request)['id']
            self.jobs.values[key].update(status='failed', result=dict(
                error=dict(code='history_resource_limit', retryable=False)))
            self.dispatch.tick()
            self.now += 86400
            self.assertTrue(self.dispatch.lookup(request)['terminal'])
            self.assertIsNone(self.dispatch.entries[request]['job'])

    def test_incomplete_stats_refresh_preserves_accepted_scope_until_coherent_replacement(self):
        request = ReportRequest(ReportKind.AI_STATS)
        first = self.dispatch.lookup(request)['id']
        accepted = result(1_000_000)
        accepted['view'].update(ai_stats=[dict(period='30-days')],
            ai_stats_work=dict(scopes={'30-days': dict(ready=True)}))
        self.jobs.values[first].update(status='complete', result=accepted)
        self.dispatch.lookup(request)
        self.now = self.dispatch.entries[request]['due']
        self.dispatch.interest('one', 'ai-stats', True, request)
        self.dispatch.tick()
        refresh = self.dispatch.entries[request]['job']
        partial = result(int(self.now * 1000))
        partial['view'].update(ai_stats=[dict(period='30-days')],
            ai_stats_work=dict(scopes={'30-days': dict(ready=False)}))
        self.jobs.values[refresh].update(status='running', result=partial)

        waiting = self.dispatch.lookup(request)

        self.assertIs(accepted, waiting['result'])
        self.assertEqual(first, waiting['result_id'])
        self.assertEqual(refresh, waiting['id'])
        partial['view']['ai_stats_work']['scopes']['30-days']['ready'] = True
        self.jobs.values[refresh]['status'] = 'complete'
        replaced = self.dispatch.lookup(request)
        self.assertIs(partial, replaced['result'])
        self.assertEqual(refresh, replaced['result_id'])

    def test_corrected_source_access_rechecks_report_blocker_without_explicit_retry(self):
        request = ReportRequest(ReportKind.TOKEN_MIX)
        self.dispatch.interest('one', 'token-mix', True, request)
        key = self.dispatch.lookup(request)['id']
        self.jobs.values[key].update(status='failed', result=dict(
            error=dict(code='source_permission_denied', retryable=False)))
        self.dispatch.tick()
        self.assertTrue(self.dispatch.lookup(request)['terminal'])
        self.dispatch.tick(ready=False, error='source_permission_denied', terminal=True)
        self.dispatch.tick(ready=True)
        self.assertFalse(self.dispatch.lookup(request)['terminal'])
        self.assertNotEqual(key, self.dispatch.lookup(request)['id'])

    def test_unready_completed_stats_are_not_cached_for_the_success_cadence(self):
        request = ReportRequest(ReportKind.AI_STATS)
        key = self.dispatch.lookup(request)['id']
        partial = result(1_000_000)
        partial['view'].update(ai_stats=[dict(period='30-days')],
            ai_stats_work=dict(scopes={'30-days': dict(ready=False)}))
        self.jobs.values[key].update(status='complete', result=partial)

        waiting = self.dispatch.lookup(request)

        self.assertIsNone(waiting['result'])
        self.assertEqual('ai_stats_no_progress', waiting['error'])
        self.assertFalse(waiting['terminal'])
        self.assertIsNone(waiting['id'])
        self.now = self.dispatch.entries[request]['due']
        self.assertNotEqual(key, self.dispatch.lookup(request)['id'])

    def test_prior_stats_policy_regenerates_without_accepting_old_podium_or_resetting_other_reports(self):
        request = ReportRequest(ReportKind.AI_STATS)
        key = self.dispatch.lookup(request)['id']
        old = result(1_000_000)
        old['view'].update(kind='ai-stats', ai_stats_policy='fun-2-tokens', ai_stats=[dict(period='30-days')],
            ai_stats_work=dict(scopes={'30-days': dict(ready=True)}))
        self.jobs.values[key].update(status='complete', result=old)
        unrelated = self.dispatch.lookup(self.models)['id']

        waiting = self.dispatch.lookup(request)

        self.assertFalse(usable(old, 1_000_000))
        self.assertIsNone(waiting['result'])
        self.assertFalse(waiting['terminal'])
        self.assertEqual('ai_stats_schema_changed', waiting['error'])
        self.now = self.dispatch.entries[request]['due']
        fresh = self.dispatch.lookup(request)['id']
        self.assertNotEqual(key, fresh)
        current = dict(old, view=dict(old['view'], ai_stats_policy='fun-3-responses'))
        self.jobs.values[fresh].update(status='complete', result=current)
        self.assertIs(current, self.dispatch.lookup(request)['result'])
        self.assertEqual(unrelated, self.dispatch.entries[self.models]['job'])

    def test_cache_connection_fault_is_typed_without_claiming_source_disconnection(self):
        import sqlite3
        from src.application import ReportApplication
        for sqlite_code, expected in ((sqlite3.SQLITE_BUSY, 'report_cache_busy'),
                (sqlite3.SQLITE_READONLY, 'report_cache_unavailable')):
            error = sqlite3.OperationalError('private path must not escape')
            error.cache_phase = 'connect'
            error.sqlite_errorcode = sqlite_code
            application = ReportApplication(lambda *_: (_ for _ in ()).throw(error))
            with patch('src.application.service.recoverable'):
                value = application.execute(ReportRequest(ReportKind.AI_STATS)).to_json()
            self.assertEqual(dict(code=expected, retryable=True), value['error'])
            self.assertEqual('not_acquired', value['source']['status'])
            self.assertIsNone(value['view'])

    def test_rejected_comparison_pin_is_terminal_and_new_first_page_can_run(self):
        pinned = ReportRequest(ReportKind.COMPARISONS, comparison_offset=10, comparison_revision='a' * 64)
        self.dispatch.interest('one', 'comparisons', True, pinned)
        key = self.dispatch.lookup(pinned)['id']
        self.jobs.values[key].update(status='complete', result=dict(
            error=dict(code='session_catalog_changed', retryable=False)))
        self.dispatch.tick()
        self.now += 10000
        self.assertTrue(self.dispatch.lookup(pinned)['terminal'])
        self.dispatch.tick()
        self.assertEqual(1, sum(job['request'].comparison_revision == 'a' * 64 for job in self.jobs.values.values()))
        first = ReportRequest(ReportKind.COMPARISONS)
        self.dispatch.interest('one', 'comparisons', True, first)
        self.assertIsNotNone(self.dispatch.lookup(first)['id'])

    def test_completed_human_work_returns_to_idle_priority_and_sleep_due_work_staggers(self):
        self.dispatch.interest('one', 'models', True, self.models)
        key = self.dispatch.lookup(self.models)['id']
        self.jobs.values[key].update(status='complete', result=result(1_000_000))
        self.dispatch.tick()
        self.assertFalse(self.dispatch.entries[self.models]['requested'])
        self.dispatch.interest('one', 'watch', False)
        self.now += 7200
        before = len(self.jobs.values)
        self.dispatch.tick()
        self.assertLessEqual(len(self.jobs.values) - before, 1)

    def test_sleep_missed_cycles_coalesce_then_each_default_product_staggers(self):
        self.dispatch.interest('one', 'watch', False)
        self.now += 7200
        seen = []
        for number in range(4):
            self.dispatch.tick()
            pending = [(key, value) for key, value in self.jobs.values.items() if value['status'] == 'queued']
            self.assertEqual(1, len(pending))
            key, job = pending[0]
            seen.append(job['request'].kind)
            publication = result(int(self.now * 1000))
            publication['view']['ai_stats'] = [dict(period='30-days')]
            job.update(status='complete', result=publication)
            self.now += 14
            self.dispatch.tick()
            self.assertEqual(number + 1, len(self.jobs.values), 'no simultaneous due-product stampede')
            self.now += 1
        self.assertEqual({ReportKind.NORMAL, ReportKind.AI_STATS, ReportKind.TOKEN_MIX, ReportKind.COMPARISONS}, set(seen))
        self.dispatch.tick()
        self.assertEqual(4, len(self.jobs.values), 'missed periods are not replayed')

    def test_source_terminal_error_preserves_valid_result_but_never_launches_new_work(self):
        self.dispatch.interest('one', 'models', True, self.models)
        key = self.dispatch.lookup(self.models)['id']
        self.jobs.values[key].update(status='complete', result=result(1_000_000))
        self.dispatch.tick()
        self.dispatch.tick(ready=False, error='http_auth_failure', terminal=True)
        before = len(self.jobs.values)
        lookup = self.dispatch.lookup(self.models)
        self.assertTrue(lookup['terminal'])
        self.assertEqual('http_auth_failure', lookup['error'])
        self.assertIsNotNone(lookup['result'])
        self.assertEqual(before, len(self.jobs.values))

    def test_price_refresh_invalidates_every_warm_projection_only_on_success(self):
        self.dispatch.interest('one', 'models', True, self.models)
        key = self.dispatch.lookup(self.models)['id']
        self.jobs.values[key].update(status='complete', result=result(1_000_000))
        self.dispatch.tick()
        failed = self.jobs.submit(self.models)
        self.dispatch.price_refresh(failed)
        self.jobs.values[failed].update(status='failed', error='pricing_unavailable')
        self.dispatch.tick()
        self.assertIsNotNone(self.dispatch.entries[self.models]['result'])
        action = self.jobs.submit(self.models)
        self.dispatch.price_refresh(action)
        self.jobs.values[action].update(status='complete', result=result(1_000_000))
        self.dispatch.tick()
        self.assertIsNone(self.dispatch.entries[self.models]['result'])

    def test_source_identity_must_be_proved_before_any_managed_admission(self):
        dispatch = DataDispatcher(self.jobs)
        dispatch.interest('one', 'models', True, self.models)
        self.assertIsNone(dispatch.lookup(self.models)['id'])
        dispatch.tick()
        self.assertEqual({}, self.jobs.values)
        dispatch.tick(identity='verified')
        self.assertEqual('verified', self.jobs.values['0']['request'].source_identity)

    def test_first_observation_wait_never_expires_or_cancels_feasible_work(self):
        self.dispatch.tick(identity='source', ready=False)
        for tab in ('first', 'second'):
            self.dispatch.interest(tab, 'models', True, self.models)
            lookup = self.dispatch.lookup(self.models)
            self.assertIsNone(lookup['id'])
            self.assertEqual('source_starting', lookup['error'])
            self.assertFalse(lookup['terminal'])
        self.assertEqual({}, self.jobs.values)
        self.now += 2 * 86400
        self.dispatch.tick(ready=False)
        self.assertEqual('source_starting', self.dispatch.lookup(self.models)['error'])
        self.dispatch.interest('first', 'models', True, self.models)

        self.dispatch.tick(ready=True)

        self.assertEqual(1, len(self.jobs.values))
        self.assertEqual(ReportKind.NORMAL, self.jobs.values['0']['request'].kind)
        self.assertIsNone(self.dispatch.lookup(self.models)['error'])
        self.assertFalse(self.dispatch.warm_allowed)
        self.dispatch.tick(ready=False)
        self.now += 2 * 86400
        self.dispatch.tick(ready=False)
        lookup = self.dispatch.lookup(self.models)
        self.assertFalse(lookup['terminal'])
        self.assertEqual('source_starting', lookup['error'])
        self.assertEqual('queued', self.jobs.values['0']['status'])
        self.assertEqual(3, self.jobs.priorities['0'], 'waiting work holds no acquisition capacity')
        self.dispatch.interest('first', 'models', True, self.models)
        self.dispatch.tick(ready=True)
        self.assertEqual('0', self.dispatch.lookup(self.models)['id'])
        self.assertEqual(1, len(self.jobs.values), 'recovery resumes the original work')

    def test_http_handshake_matrix_preserves_temporary_and_terminal_source_evidence(self):
        from src.web.dispatch_http import handle
        for selected, identity, observed in ((False, '', False), (True, '', False),
                (True, 'source', False), (True, 'source', True)):
            with self.subTest(selected=selected, identity=identity, observed=observed):
                jobs = RecordingJobs()
                dispatcher = DataDispatcher(jobs)
                dispatcher.tick(identity=identity, ready=observed)
                replies = []
                startup = SimpleNamespace(report_status=lambda: dict(ready=selected,
                    error=None if selected else 'source_starting', retryable=not selected))
                handler = SimpleNamespace(path='/api/data', server=SimpleNamespace(lifecycle=SimpleNamespace(
                    dispatcher=dispatcher, source_startup=startup)),
                    reply=lambda status, body: replies.append((status, body)))
                handle(handler, {'request': {'kind': 'normal'}, 'retry': False})
                status, body = replies[-1]
                self.assertEqual(200 if observed else 503, status)
                if observed:
                    self.assertIsNotNone(body['id'])
                    self.assertIsNone(body['error'])
                else:
                    self.assertEqual({'error': 'source_starting', 'retryable': True}, body)
                    self.assertEqual({}, jobs.values)
        for error in ('http_auth_failure', 'source_permission_denied', 'unsupported_schema',
                'unsupported_version', 'registration_invalid', 'source_identity_changed'):
            with self.subTest(error=error):
                self.dispatch.tick(ready=False, error=error, terminal=True)
                replies = []
                handler = SimpleNamespace(path='/api/data', server=SimpleNamespace(lifecycle=SimpleNamespace(
                    dispatcher=self.dispatch)), reply=lambda status, body: replies.append((status, body)))
                handle(handler, {'request': {'kind': 'normal'}, 'retry': False})
                self.assertEqual(200, replies[-1][0])
                self.assertEqual(error, replies[-1][1]['error'])
                self.assertTrue(replies[-1][1]['terminal'])

    def test_coalesced_stats_scope_uses_highest_interested_priority(self):
        foreground = ReportRequest(ReportKind.AI_STATS, stats_scope='7-days')
        inactive = ReportRequest(ReportKind.AI_STATS)
        self.dispatch.interest('one', 'ai-stats', True, foreground)
        key = self.jobs.submit(ManagedReport(ReportKind.AI_STATS, source_identity='source'))
        self.dispatch.entries[foreground]['job'] = key
        self.dispatch.entries[inactive]['job'] = key
        self.dispatch.tick()
        self.assertEqual(0, self.jobs.priorities[key])

    def test_managed_terminal_jobs_never_override_dispatcher_invalidation(self):
        jobs = ReportJobs()
        self.addCleanup(jobs.close)
        for kind in (ReportKind.AI_STATS, ReportKind.TOKEN_MIX, ReportKind.COMPARISONS):
            with self.subTest(kind=kind):
                request = ManagedReport(kind, source_identity='source')
                key = jobs.submit(request)
                jobs._jobs[key].update(status='complete', finished_at=time.monotonic(), result={
                    'view': {'ai_stats': [{'period': '30-days'}]}})
                self.assertNotEqual(key, jobs.submit(request))

    def test_stats_scope_promotions_preserve_one_job_and_all_requested_goals(self):
        jobs = ReportJobs()
        self.addCleanup(jobs.close)
        key = jobs.submit(ManagedReport(ReportKind.AI_STATS, source_identity='source'))
        jobs.select_scope(key, '7-days')
        self.assertEqual('7-days', jobs._jobs[key]['request'].stats_scope)
        jobs.select_scope(key, '30-days')
        self.assertEqual('30-days', jobs._jobs[key]['request'].stats_scope)
        self.assertEqual(('30-days', '7-days'), jobs._jobs[key]['goals'])
        self.assertEqual(1, len(jobs._jobs))

    def test_aged_completed_snapshot_survives_refresh_backoff_without_new_observation(self):
        key = self.dispatch.lookup(self.models)['id']
        self.jobs.values[key].update(status='complete', result=result(1_000_000))
        self.dispatch.tick()
        entry = self.dispatch.entries[self.models]
        self.now += 3660
        entry.update(failures=1, due=self.now + 120, error='http_timeout')
        lookup = self.dispatch.lookup(self.models)
        self.assertEqual(key, lookup['result_id'])
        self.assertEqual(1_000_000, lookup['result']['source']['observed_at_ms'])
        self.assertEqual('delayed', lookup['refresh'])
        self.assertFalse(lookup['stale'])
        self.assertEqual(entry['due'], self.now + 120)

    def test_midnight_does_not_discard_qualified_historical_stats(self):
        value = result(86_390_000)
        value['scope'] = dict(kind='ai-stats', timezone_id='UTC', local_day_start_ms=0)
        self.assertTrue(usable(value, 86_399_999))
        self.assertTrue(usable(value, 86_400_000))

    def test_days_old_completion_is_delivered_once_and_refreshes_only_on_cadence(self):
        self.dispatch.interest('one', 'models', True, self.models)
        key = self.dispatch.lookup(self.models)['id']
        self.now += 2 * 86400
        value = result(1_000_000)
        self.jobs.values[key].update(status='complete', result=value)
        self.dispatch.tick()
        entry = self.dispatch.entries[self.models]
        due = entry['due']
        before = len(self.jobs.values)

        for _ in range(10):
            self.dispatch.interest('one', 'models', True, self.models)
            lookup = self.dispatch.lookup(self.models)
            self.dispatch.tick()
            self.assertIs(value, lookup['result'])
            self.assertEqual(key, lookup['result_id'])
            self.assertEqual('scheduled', lookup['refresh'])
            self.assertEqual(1_000_000, value['source']['observed_at_ms'])
        self.assertEqual(before, len(self.jobs.values), 'old as-of never forces an immediate recomputation loop')
        self.assertGreater(due, self.now)

        self.now = entry['due']
        self.dispatch.interest('one', 'models', True, self.models)
        self.dispatch.tick()
        lookup = self.dispatch.lookup(self.models)
        self.assertNotEqual(key, lookup['id'])
        self.assertEqual(key, lookup['result_id'], 'refresh identity is not publication identity')
        self.assertIs(value, lookup['result'])
        self.assertEqual('queued', lookup['refresh'])

    def test_http_lookup_requires_explicit_boolean_and_rejects_nonfinite_scope(self):
        from src.web.dispatch_http import handle
        replies = []
        handler = SimpleNamespace(path='/api/data', server=SimpleNamespace(lifecycle=SimpleNamespace(
            dispatcher=self.dispatch)), reply=lambda status, value: replies.append((status, value)))
        for body in ({'request': {'kind': 'normal'}}, {'request': {'kind': 'normal'}, 'retry': None},
                {'request': {'kind': 'normal'}, 'retry': 0}, {'request': {'kind': 'session', 'session_id': 'root'}, 'retry': False}):
            handle(handler, body)
            self.assertEqual(400, replies[-1][0])
        self.assertEqual({}, self.jobs.values)
        handle(handler, {'request': {'kind': 'normal'}, 'retry': False})
        self.assertEqual(200, replies[-1][0])
        self.assertIsNotNone(replies[-1][1]['id'])

    def test_dependency_observer_invalidates_external_prices_and_requires_restart_for_runtime_config(self):
        from src.web.dispatch_dependencies import DispatchDependencies
        config = dict(timezone='UTC', webSettings={'theme': 'light'})
        prices = SimpleNamespace(analysis_signature='first')
        observer = DispatchDependencies(lambda: config, lambda: prices, clock=lambda: self.now)
        self.assertTrue(observer.check(self.dispatch))
        key = self.dispatch.lookup(self.models)['id']
        config['webSettings']['theme'] = 'dark'
        self.now += 30
        self.assertTrue(observer.check(self.dispatch))
        self.assertEqual('queued', self.jobs.values[key]['status'])
        prices.analysis_signature = 'changed'
        self.now += 30
        self.assertTrue(observer.check(self.dispatch))
        self.assertEqual('cancelled', self.jobs.values[key]['status'])
        self.assertIsNone(self.dispatch.entries[self.models]['job'])
        config['timezone'] = 'Europe/Stockholm'
        self.now += 30
        self.assertFalse(observer.check(self.dispatch))

    def test_temporary_dependency_price_read_failure_is_not_a_proven_invalidation(self):
        from src.web.dispatch_dependencies import DispatchDependencies
        observer = DispatchDependencies(lambda: {'timezone': 'UTC'}, lambda: SimpleNamespace(analysis_signature='first'),
                                        clock=lambda: self.now)
        observer.check(self.dispatch)
        key = self.dispatch.lookup(self.models)['id']
        self.now += 30
        with patch.object(observer, 'prices', side_effect=OSError('disposable cache unavailable')):
            self.assertTrue(observer.check(self.dispatch))
        self.assertEqual(key, self.dispatch.entries[self.models]['job'])

    def test_first_dependency_check_compares_live_pinned_configuration_not_a_new_baseline(self):
        from src.web.dispatch_dependencies import DispatchDependencies
        observer = DispatchDependencies(lambda: {'timezone': 'Europe/Stockholm'}, lambda: None)
        self.assertFalse(observer.check(self.dispatch, baseline={'timezone': 'UTC'}))
        observer = DispatchDependencies(lambda: {'timezone': 'UTC', 'webSettings': {'theme': 'dark'}}, lambda: None)
        self.assertTrue(observer.check(self.dispatch, baseline={'timezone': 'UTC', 'webSettings': {'theme': 'light'}}))


class QuantumProcessTests(unittest.TestCase):
    def test_background_paced_finite_work_really_parks_then_finishes_on_the_same_stack(self):
        jobs = ReportJobs(target=quantum_report)
        self.addCleanup(jobs.close)
        dispatch = DataDispatcher(jobs)
        dispatch.tick(identity='source')
        request = ReportRequest(ReportKind.COMPARISONS)
        dispatch.interest('opener', 'comparisons', True, request)
        dispatch.tick()
        key = dispatch.entries[request]['job']
        jobs.prioritize({key: 2})
        deadline = time.monotonic() + 12
        parked_progress = []
        while time.monotonic() < deadline and jobs.snapshot(key)['status'] != 'complete':
            jobs.tick()
            if key in jobs._parked:
                job = jobs._jobs[key]
                self.assertEqual(2, job['priority'])
                self.assertGreater(job['not_before'], job['served_at'])
                parked_progress.append(jobs.snapshot(key)['progress']['completed'])
            time.sleep(.01)
        self.assertEqual('complete', jobs.snapshot(key)['status'])
        self.assertGreater(len(set(parked_progress)), 1)
        self.assertEqual(1, jobs.snapshot(key)['work']['slices'], 'same private stack, not a restarted scan')

    def test_parked_job_respects_explicit_backoff_even_with_negative_clock_origin(self):
        from unittest.mock import Mock
        jobs = ReportJobs()
        self.addCleanup(jobs.close)
        key = jobs.submit(ManagedReport())
        child, connection = Mock(), Mock()
        child.is_alive.return_value = False
        jobs._parked[key] = child, connection
        jobs._jobs[key]['not_before'] = -120

        with patch('src.web.jobs.time.monotonic', return_value=-121):
            jobs.tick()

        self.assertEqual('queued', jobs.snapshot(key)['status'])
        self.assertIsNone(jobs._active)
        connection.send.assert_not_called()

        with patch('src.web.jobs.time.monotonic', return_value=-120):
            jobs.tick()

        self.assertEqual('running', jobs.snapshot(key)['status'])
        self.assertIs(jobs._active[1], child)
        connection.send.assert_called_once_with('free')  # Requested (priority 1) work resumes unparked.

    def test_parent_loss_terminates_a_parked_private_stack(self):
        from src.web.process_identity import process_identity, terminate_owned
        code = '''
import time
from src.web.jobs import ReportJobs
from src.web.report_control import ManagedReport
from src.reports import ReportKind
from development.tests.fixtures.dispatch_reports import quantum_report
jobs = ReportJobs(target=quantum_report)
key = jobs.submit(ManagedReport(ReportKind.COMPARISONS))
jobs.prioritize({key: 2})
while not jobs._parked:
    jobs.tick()
    time.sleep(.01)
print(jobs._parked[key][0].pid, flush=True)
time.sleep(30)
'''
        parent = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        worker_pid = birth = None
        deadline = Timer(8, parent.kill)
        deadline.start()
        try:
            worker_pid = int(parent.stdout.readline())
            birth = process_identity(worker_pid)
            self.assertIsNotNone(birth)
            parent.kill()
            parent.wait(timeout=5)
            until = time.monotonic() + 5
            while process_identity(worker_pid) == birth and time.monotonic() < until:
                time.sleep(.05)
            self.assertNotEqual(process_identity(worker_pid), birth)
        finally:
            deadline.cancel()
            deadline.join()
            if parent.poll() is None:
                parent.kill()
            parent.wait(timeout=5)
            parent.stdout.close()
            if worker_pid and birth and process_identity(worker_pid) == birth:
                terminate_owned(worker_pid, birth)

    def test_foreground_finishes_before_background_then_original_stack_resumes(self):
        jobs = ReportJobs(target=quantum_report)
        self.addCleanup(jobs.close)
        background = jobs.submit(ManagedReport(ReportKind.COMPARISONS))
        jobs.prioritize({background: 2})
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            jobs.tick()
            before = jobs.snapshot(background)['progress']['completed']
            if before >= 3:
                break
            time.sleep(.01)
        self.assertGreaterEqual(before, 3)
        foreground = jobs.submit(ManagedReport())
        jobs.prioritize({background: 2, foreground: 0})
        started = time.monotonic()
        while time.monotonic() < deadline:
            jobs.tick()
            if jobs.snapshot(foreground)['status'] == 'complete':
                break
            time.sleep(.01)
        self.assertEqual('complete', jobs.snapshot(foreground)['status'])
        self.assertNotEqual('complete', jobs.snapshot(background)['status'])
        self.assertLess(time.monotonic() - started, 3)
        self.assertGreaterEqual(jobs.snapshot(background)['progress']['completed'], before)
        jobs.prioritize({background: 0})
        while time.monotonic() < deadline:
            jobs.tick()
            if jobs.snapshot(background)['status'] == 'complete':
                break
            time.sleep(.01)
        self.assertEqual('complete', jobs.snapshot(background)['status'])
        self.assertEqual(1, jobs.snapshot(background)['work']['slices'])


class SharedEvidenceTests(unittest.TestCase):
    def test_thousands_of_roots_keep_real_counts_and_reuse_then_repair_compact_evidence(self):
        from src.domain import ModelRef
        from src.reports import ReportService
        from src.reports.token_mix_cache import NAMESPACE, cache_key
        source = SyntheticMonthSource(3217, 2, month_start_ms=NOW - 5 * 86400000)
        source.snapshots = {sid: replace(value, complete=True) for sid, value in source.snapshots.items()}
        raw = source.snapshots['root-0000']
        opaque = ModelRef('claude-agent', 'large-agent')
        source.snapshots['root-0000'] = replace(raw,
            invocations=tuple(replace(item, model=opaque) for item in raw.invocations),
            messages=tuple(replace(item, model=opaque) if item.model else item for item in raw.messages))
        original = report_service(self, source)

        def fresh():
            service = ReportService(selection=original.selection, pricing_provider=original.pricing_provider,
                account_provider=None, cache_repository=original.cache_repository, config=original.config,
                now_ms=NOW, cache_token_mix_history=True)
            service.shared_web_evidence = True
            return service

        cold = fresh().build_token_mix_history()
        stats = fresh().build(ReportRequest(ReportKind.AI_STATS, stats_scope='all'))
        warm = fresh().build_token_mix_history()
        self.assertEqual(6434, cold.token_mix.request_count)
        self.assertEqual(839637, cold.token_mix.known_total_tokens)
        self.assertEqual(cold.model_token_mix, warm.model_token_mix)
        self.assertEqual(3217, source.load_count)
        self.assertEqual(3217, stats.ai_stats_work['completed'])
        self.assertGreater(stats.ai_stats[-1].metrics[1].value, 0)
        service = fresh()
        root = source.snapshots['root-0000'].root
        key = cache_key(service, root, service._load_comparison_catalog())
        entry = service.cache_repository.get(NAMESPACE, key)
        service.cache_repository.put(NAMESPACE, key, {'corrupt': True},
            source_revision=entry.source_revision, algorithm_version=entry.algorithm_version)
        repaired = fresh().build_token_mix_history()
        self.assertEqual(cold.model_token_mix, repaired.model_token_mix)
        self.assertEqual(3218, source.load_count, 'one disposable corrupt entry is a miss, not a report failure')

    def test_price_dependency_lookup_is_cache_only_even_with_expired_prices(self):
        from src.pricing.github_copilot import GitHubCopilotPricingProvider, CACHE_NAMESPACE, CACHE_KEY, _catalog_payload
        service = report_service(self)
        expected = service._load_catalog()
        service.cache_repository.put(CACHE_NAMESPACE, CACHE_KEY, _catalog_payload(expected))
        with patch('src.pricing.github_copilot._default_fetch_text', side_effect=AssertionError('network forbidden')):
            provider = GitHubCopilotPricingProvider(cache=service.cache_repository, max_age_hours=0, now_ms=lambda: NOW)
            with patch.object(provider, 'fetch_text', side_effect=AssertionError('network forbidden')) as fetch:
                actual = provider.cached_catalog()
        self.assertEqual(expected.analysis_signature, actual.analysis_signature)
        fetch.assert_not_called()

    def test_unstable_roots_keep_partial_provenance_and_stats_retains_changed_activity(self):
        from src.application import ReportApplication
        for kind, later_changed in ((kind, changed) for kind in
                (ReportKind.TOKEN_MIX, ReportKind.AI_STATS, ReportKind.COMPARISONS) for changed in (False, True)):
            with self.subTest(kind=kind, later_changed=later_changed):
                source = SyntheticMonthSource(3, 3, month_start_ms=NOW - 86400000)
                source.snapshots = {sid: replace(value, complete=True) for sid, value in source.snapshots.items()}
                service = report_service(self, source)
                service.selection = replace(service.selection, warnings=())
                service.shared_web_evidence = service.allow_partial_history = True
                service.cache_token_mix_history = True
                def available(ids, _progress):
                    snapshots = {sid: source.load_session_snapshot(sid) for sid in ids
                                 if later_changed or sid != 'root-0000'}
                    if later_changed:
                        source.snapshots['root-0000'] = replace(source.snapshots['root-0000'], source_revision='changed')
                    return snapshots
                with patch.object(source, 'load_session_snapshots_available', side_effect=available, create=True):
                    value = ReportApplication(lambda *_: service, clock=lambda: NOW).execute(ReportRequest(kind)).to_json()
                self.assertIsNone(value['error'])
                self.assertEqual('partial', value['source']['status'])
                retained_stats = kind is ReportKind.AI_STATS and later_changed
                self.assertEqual(0 if retained_stats else 1, value['source']['omitted_roots'])
                self.assertNotIn('root-0000', [row['session_id'] for row in value['source']['revisions']])
                if kind is ReportKind.TOKEN_MIX:
                    self.assertEqual(6, sum(row['calls'] for row in value['view']['model_token_mix']))
                elif kind is ReportKind.AI_STATS:
                    row = next(row for row in value['view']['ai_stats'] if row['period'] == '30-days')
                    self.assertTrue(any('source-incomplete' in metric['reasons'] for metric in row['metrics']))
                else:
                    self.assertFalse(value['view']['comparisons']['complete'])

    def test_unverifiable_history_rejects_precise_reports_but_stats_has_playful_zeros(self):
        from src.application import ReportApplication
        for kind in (ReportKind.TOKEN_MIX, ReportKind.AI_STATS, ReportKind.COMPARISONS):
            with self.subTest(kind=kind):
                source = SyntheticMonthSource(1, 3, month_start_ms=NOW - 86400000)
                service = report_service(self, source)
                service.shared_web_evidence = service.allow_partial_history = True
                service.cache_token_mix_history = True
                with patch.object(source, 'load_session_snapshots_available', return_value={}, create=True):
                    value = ReportApplication(lambda *_: service, clock=lambda: NOW).execute(ReportRequest(kind)).to_json()
                if kind is ReportKind.AI_STATS:
                    self.assertIsNone(value['error'])
                    self.assertEqual('partial', value['source']['status'])
                    self.assertEqual(1, value['source']['omitted_roots'])
                    self.assertEqual(5, len(value['view']['ai_stats']))
                    for row in value['view']['ai_stats']:
                        self.assertEqual(12, len(row['metrics']))
                        for metric in row['metrics']:
                            self.assertEqual('0', str(metric['value']))
                            self.assertNotRegex(str(metric['display']), r'Unavailable|N/A')
                            self.assertFalse(metric.get('session_id'))
                else:
                    self.assertIsNone(value['view'])
                    self.assertEqual('history_revision_churn', value['error']['code'])

    def test_partial_history_still_rejects_membership_archive_and_source_changes(self):
        from src.reports.history_work import HistoryWork, revisions
        from src.reports.service import SessionCatalogChangedError
        source = SyntheticMonthSource(2, 1, month_start_ms=NOW - 86400000)
        service = report_service(self, source)
        service.shared_web_evidence = service.allow_partial_history = True
        sessions = tuple(source.list_sessions())
        work = HistoryWork(service, sessions, sessions, revisions(service, sessions), service._load_comparison_catalog())
        changed = replace(sessions[0], updated_at_ms=NOW)
        with patch.object(source, 'list_sessions', return_value=(changed, sessions[1])):
            self.assertEqual({'root-0000'}, work.verify())
        archived = replace(sessions[0], archived_at_ms=NOW)
        foreign = replace(sessions[0], provenance=replace(sessions[0].provenance, source_instance='foreign'))
        for membership in ((archived, sessions[1]), (foreign, sessions[1]), sessions[1:]):
            with self.subTest(membership=membership), patch.object(source, 'list_sessions', return_value=membership):
                with self.assertRaises(SessionCatalogChangedError):
                    work.verify()

    def test_history_revision_bracket_rejects_changed_deleted_archived_and_foreign_roots(self):
        from src.reports.history_work import HistoryWork, revisions
        from src.reports.service import SessionCatalogChangedError
        source = SyntheticMonthSource(2, 1, month_start_ms=NOW - 86400000)
        service = report_service(self, source)
        service.shared_web_evidence = True
        sessions = tuple(source.list_sessions())
        work = HistoryWork(service, sessions, list(sessions), revisions(service, sessions), service._load_comparison_catalog())
        changed = replace(sessions[0], updated_at_ms=NOW)
        archived = replace(sessions[0], archived_at_ms=NOW)
        foreign = replace(sessions[0], provenance=replace(sessions[0].provenance, source_instance='another-source'))
        for membership in ((changed, sessions[1]), (archived, sessions[1]), (foreign, sessions[1]), sessions[1:]):
            with self.subTest(membership=membership[0].session_id), patch.object(source, 'list_sessions', return_value=membership):
                with self.assertRaises(SessionCatalogChangedError):
                    work.verify()
        source.snapshots[sessions[0].session_id] = replace(source.snapshots[sessions[0].session_id], source_revision='changed')
        with self.assertRaises(SessionCatalogChangedError):
            work.verify()

    def test_active_descendant_invalidates_stable_root_cache_eligibility(self):
        from src.reports.history_work import active_roots
        source = SyntheticMonthSource(1, 1, month_start_ms=NOW - 86400000)
        root = source.list_sessions()[0]
        child = replace(root, session_id='child', parent_session_id=root.session_id, active=True)
        self.assertEqual({root.session_id}, active_roots((root, child)))

    def test_bounded_history_steps_reuse_saved_roots_and_cannot_continue_without_writes(self):
        from src.reports import ReportService
        from src.reports.history_work import HistoryContinuation, HistoryCheckpointError
        source = SyntheticMonthSource(12, 3, month_start_ms=NOW - 86400000)
        source.snapshots = {key: replace(value, complete=True) for key, value in source.snapshots.items()}
        original = report_service(self, source)
        receipts = []
        for step in range(3):
            service = ReportService(selection=original.selection, pricing_provider=original.pricing_provider,
                cache_repository=original.cache_repository, account_provider=None, config=original.config,
                now_ms=NOW, cache_token_mix_history=True)
            service.shared_web_evidence = True
            service.history_checkpoint = receipts.append
            service.history_slice_roots = 4
            service.history_batch_size = 2
            if step < 2:
                with self.assertRaises(HistoryContinuation):
                    service.build_token_mix_history()
            else:
                report = service.build_token_mix_history()
        self.assertTrue(report.model_token_mix)
        self.assertEqual(12, source.load_count, 'continuation must not restart hydrated roots')
        self.assertEqual([2, 4, 6, 8, 10, 12], [value['completed'] for value in receipts])
        self.assertEqual(1, len({value['signature'] for value in receipts}))
        original.shared_web_evidence = True
        original.cache_token_mix_history = True
        original.history_checkpoint = receipts.append
        original.history_slice_roots = 4
        original.history_batch_size = 2
        with patch.object(original.cache_repository, 'get_many', return_value={}), patch.object(
                original.cache_repository, 'put_many', side_effect=OSError('synthetic disk unavailable')):
            with self.assertRaises(HistoryCheckpointError):
                original.build_token_mix_history()

    def test_distinct_views_reuse_compatible_roots_without_reusing_each_others_totals(self):
        from src.reports import ReportService
        source = SyntheticMonthSource(12, 3, month_start_ms=NOW - 86400000)
        source.snapshots = {key: replace(value, complete=True) for key, value in source.snapshots.items()}
        original = report_service(self, source)
        original.selection = replace(original.selection, warnings=())
        actual = {}
        for kind in (ReportKind.NORMAL, ReportKind.TOKEN_MIX, ReportKind.AI_STATS, ReportKind.COMPARISONS):
            service = ReportService(selection=original.selection, pricing_provider=original.pricing_provider,
                account_provider=None, cache_repository=original.cache_repository,
                config=original.config, now_ms=NOW, cache_token_mix_history=True)
            service.shared_web_evidence = True
            actual[kind] = service.build_token_mix_history() if kind is ReportKind.TOKEN_MIX else service.build(ReportRequest(kind))
        self.assertEqual(12, source.load_count)
        with original.cache_repository.database.connect(operation='read') as connection:
            self.assertEqual(0, connection.execute(
                "SELECT COUNT(*) FROM cache_entries WHERE namespace = 'derived-analysis'").fetchone()[0],
                'managed evidence must not add full raw-bearing analysis payloads')
        expected_source = SyntheticMonthSource(12, 3, month_start_ms=NOW - 86400000)
        expected_source.snapshots = {key: replace(value, complete=True) for key, value in expected_source.snapshots.items()}
        expected_service = report_service(self, expected_source)
        expected_service.selection = replace(expected_service.selection, warnings=())
        self.assertEqual(expected_service.build(ReportRequest(ReportKind.AI_STATS)).ai_stats,
                         actual[ReportKind.AI_STATS].ai_stats)
        self.assertEqual(expected_service.build_token_mix_history().model_token_mix,
                         actual[ReportKind.TOKEN_MIX].model_token_mix)
        self.assertEqual(expected_service.build(ReportRequest(ReportKind.COMPARISONS)).comparisons,
                          actual[ReportKind.COMPARISONS].comparisons)

    def test_incomplete_snapshots_do_not_publish_shared_complete_evidence(self):
        from src.reports.shared_evidence import publish
        from src.reports.ai_stats_evidence import NAMESPACE
        source = SyntheticMonthSource(1, 3, month_start_ms=NOW - 86400000)
        service = report_service(self, source)
        service.shared_web_evidence = True
        snapshot = next(iter(source.snapshots.values()))
        bundle = service._analyze_snapshot(snapshot)
        self.assertFalse(snapshot.complete)
        publish(service, snapshot, bundle)
        with service.cache_repository.database.connect(operation='read') as connection:
            self.assertEqual(0, connection.execute(
                'SELECT COUNT(*) FROM cache_entries WHERE namespace = ?', (NAMESPACE,)).fetchone()[0])


class HistoryJobTests(unittest.TestCase):
    def test_changing_catalog_keeps_durable_coverage_pending_with_backoff_then_recovers(self):
        from src.web.history_jobs import checkpoint, resume
        job = dict(request=ManagedReport(ReportKind.TOKEN_MIX), status='running')
        for count in range(1, 6):
            checkpoint(job, dict(signature=str(count) * 64, completed=count * 64, total=2700))
            resume(job)
            self.assertEqual('queued', job['status'])
        for signature in ('a', 'b', 'c'):
            checkpoint(job, dict(signature=signature * 64, completed=320, total=2700))
            resume(job)
        self.assertEqual('queued', job['status'])
        self.assertGreater(job['not_before'], job['queued_at'])
        self.assertNotIn('error', job)
        checkpoint(job, dict(signature='c' * 64, completed=384, total=2700))
        resume(job)
        self.assertEqual(job['not_before'], job['queued_at'], 'verified progress removes churn backoff')

    def test_real_children_resume_durable_roots_even_after_long_valid_analysis(self):
        for slow in (False, True):
            with self.subTest(slow=slow), tempfile.TemporaryDirectory() as directory:
                jobs = ReportJobs(target=durable_history_report)
                try:
                    key = jobs.submit(HistoryFixture(ReportKind.TOKEN_MIX, source_identity='source',
                        directory=directory, slow_once=slow))
                    end = time.monotonic() + 12
                    advanced = False
                    while time.monotonic() < end:
                        jobs.tick()
                        if slow and not advanced and jobs._active:
                            owner, process, receiver, started = jobs._active
                            jobs._active = owner, process, receiver, started - 2 * 86400
                            advanced = True
                        snapshot = jobs.snapshot(key)
                        if snapshot['status'] in {'complete', 'failed'}:
                            break
                        time.sleep(.01)
                    self.assertEqual('complete', snapshot['status'], snapshot)
                    self.assertGreaterEqual(snapshot['work']['slices'], 3)
                    self.assertLessEqual(snapshot['result']['view']['roots_read'], 4)
                    self.assertEqual(10, jobs._jobs[key]['continued']['completed'] + snapshot['result']['view']['roots_read'],
                        'completed roots must not be hydrated again in the final child')
                    self.assertIsNone(jobs._jobs[key]['error'])
                finally:
                    jobs.close()

    def test_more_than_32_durable_slices_can_finish_without_a_work_count_deadline(self):
        from src.web.history_jobs import checkpoint, resume
        job = dict(request=ManagedReport(ReportKind.TOKEN_MIX), status='running')
        for count in range(1, 65):
            checkpoint(job, dict(signature='a' * 64, completed=count * 64, total=8192))
            resume(job)
            self.assertEqual('queued', job['status'])
        self.assertEqual(4096, job['continued']['completed'])
        self.assertEqual(64, job['history_steps'])
        resume(job)
        self.assertEqual('failed', job['status'], 'missing promised receipt is still a protocol error')
        self.assertEqual('history_no_progress', job['error'])

    def test_broken_resume_pipe_retains_ownership_until_child_stop_is_confirmed(self):
        from unittest.mock import Mock
        jobs = ReportJobs()
        self.addCleanup(jobs.close)
        key = jobs.submit(ManagedReport())
        child, connection = Mock(), Mock()
        child.is_alive.return_value = False
        connection.send.side_effect = BrokenPipeError()
        jobs._parked[key] = child, connection
        jobs.tick()
        self.assertEqual('failed', jobs.snapshot(key)['status'])
        child.close.assert_called_once()
        connection.close.assert_called_once()
        self.assertIsNone(jobs._active)

    def test_failed_resume_stop_retains_exact_owner_for_cleanup_retry(self):
        from unittest.mock import Mock
        from src.web.jobs import ReportWorkerStopError
        jobs = ReportJobs()
        key = jobs.submit(ManagedReport())
        child, connection = Mock(), Mock()
        child.is_alive.return_value = True
        connection.send.side_effect = BrokenPipeError()
        jobs._parked[key] = child, connection
        with self.assertRaises(ReportWorkerStopError):
            jobs.tick()
        self.assertIs(jobs._active[1], child)
        self.assertIs(jobs._active[2], connection)
        child.close.assert_not_called()
        connection.close.assert_not_called()
        child.is_alive.return_value = False
        jobs.close()
        self.assertIsNone(jobs._active)
        child.close.assert_called_once()

    def test_cancel_parked_child_cannot_release_a_different_active_owner(self):
        from unittest.mock import Mock
        jobs = ReportJobs()
        parked = jobs.submit(ManagedReport(ReportKind.COMPARISONS))
        active = jobs.submit(ManagedReport())
        child, connection, other_child, other_connection = Mock(), Mock(), Mock(), Mock()
        child.is_alive.return_value = other_child.is_alive.return_value = False
        jobs._parked[parked] = child, connection
        owner = jobs._active = (active, other_child, other_connection, time.monotonic())
        jobs.cancel(parked)
        self.assertIs(owner, jobs._active)
        self.assertEqual('cancelled', jobs.snapshot(parked)['status'])
        other_child.close.assert_not_called()
        jobs.close()
        other_child.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
