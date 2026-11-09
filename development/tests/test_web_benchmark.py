"""Independent optional Harbor contract, precise display and last-good lifetime."""
from datetime import datetime, timezone
from decimal import Decimal
import http.client
import json
import tempfile
from threading import Event, Thread
from types import SimpleNamespace
import time
import unittest
from unittest.mock import Mock, patch

from development.tests.fixtures.benchmark import finite_benchmark, page, payload, references, row
from src.benchmarks import MAX_BYTES, fetch_snapshot, parse_pages, read_page
from src.application.projection import benchmark_view
from src.cache.benchmark import BenchmarkCache
from src.web.benchmark import BenchmarkLane
from src.web.http import LoopbackServer
from src.web.jobs import ReportJobs

NOW = 1794182400000


class BenchmarkTests(unittest.TestCase):
    def test_complete_pagination_uses_last_page_cheapest_and_preserves_every_effort_client_and_run(self):
        pages = [page([row(1, effort='medium', cost=330), row(2, effort='high', cost=660)], total=3, size=2),
            page([row(3, effort='max', cost=33)], index=2, total=3, size=2)]
        calls = []
        def reader(index, remaining, deadline):
            calls.append((index, remaining))
            return pages[index - 1], 100

        value = fetch_snapshot(reader=reader, clock=lambda: NOW / 1000)
        snapshot = parse_pages(value['pages'], value['fetched_at_ms'])
        result = benchmark_view(snapshot, references(), now_ms=NOW)

        self.assertEqual([(1, MAX_BYTES), (2, MAX_BYTES - 100)], calls)
        self.assertEqual(['medium', 'high', 'max'], [item['effort'] for item in result['rows']])
        self.assertEqual([Decimal(10), Decimal(20), Decimal(1)], [Decimal(item['relative_cost']) for item in result['rows']])
        self.assertEqual(['61.0%'] * 3, [item['solved_text'] for item in result['rows']])

    def test_invalid_contract_or_missing_pages_cannot_be_a_full_snapshot(self):
        changes = [lambda p: p['pagination'].update(total_pages=2),
            lambda p: p['pagination'].update(page=2), lambda p: p['pagination'].update(total=0),
            lambda p: p['leaderboard'].update(name='4-1-0'),
            lambda p: p['leaderboard'].update(dataset_version_ids=['other']),
            lambda p: p['leaderboard']['metrics_schema']['properties']['accuracy'].update(maximum=1),
            lambda p: p['rows'][0]['metrics'].update(n_trials=0),
            lambda p: p['rows'][0]['metrics'].update(n_trials=True),
            lambda p: p['rows'][0]['metrics'].update(n_trials=1.5),
            lambda p: p['rows'][0]['metrics'].update(total_cost_usd=-1),
            lambda p: p['rows'][0]['metrics'].update(total_cost_usd=float('nan')),
            lambda p: p['rows'][0]['metrics'].update(accuracy=101),
            lambda p: p['rows'][0]['metadata']['model_display'].update(label=''),
            lambda p: p['rows'][0]['metadata'].update(date='2026-02-30'),
            lambda p: p['rows'][0]['metadata']['agent_display'].update(url='javascript:alert(1)'),
            lambda p: p['rows'][0]['metrics'].pop('total_cost_usd')]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                value = page()
                change(value)
                with self.assertRaises((ValueError, KeyError)):
                    parse_pages([value], NOW)
        with self.assertRaises(ValueError):
            parse_pages([page([row(), row()])], NOW)
        first, second = page([row()], total=2, size=1), page([row(2)], index=2, total=2, size=1)
        second['leaderboard']['updated_at'] = 'changed'
        with self.assertRaises(ValueError):
            parse_pages([first, second], NOW)

    def test_zero_partial_unknown_effort_and_tiny_positive_costs_are_not_fabricated_ratios(self):
        partial = row(2)
        partial['metrics']['display_cost'] = '$1 (partial: 324/330)'
        missing_effort = row(3, cost=0.000001, score=0.61)
        missing_effort['metadata'].pop('reasoning_effort')
        snapshot = parse_pages([page([row(1, cost=0), partial, missing_effort])], NOW)

        result = benchmark_view(snapshot, references(), now_ms=NOW)['rows']

        self.assertEqual([None, None, '1'], [item['relative_cost'] for item in result])
        self.assertEqual(['$0.00', 'N/A', '<$0.0001'], [item['usd_text'] for item in result])
        self.assertEqual('0.6%', result[2]['solved_text'])
        self.assertIsNone(result[2]['effort'])
        self.assertEqual(Decimal('0.000001') / 330, Decimal(result[2]['usd_per_task']))

    def test_integral_numeric_trials_and_explicit_null_optional_labels_remain_source_facts(self):
        value = row()
        value['metrics']['n_trials'] = 330.0
        value['metadata'].update(reasoning_effort=None, agent_version=None)

        snapshot = parse_pages([page([value])], NOW)

        self.assertEqual(330, snapshot.rows[0].trials)
        self.assertEqual('', snapshot.rows[0].effort)
        self.assertEqual('', snapshot.rows[0].client_version)

    def test_wire_duplicate_fields_and_positive_numeric_underflow_are_rejected(self):
        connection, response = Mock(), Mock()
        connection.getresponse.return_value = response
        response.status = 200
        response.getheader.return_value = 'application/json'
        for body in [b'{"cost":1,"cost":2}', b'{"cost":1e-999}']:
            with self.subTest(body=body):
                response.read1.side_effect = [body, b'']
                with patch('src.benchmarks.http.client.HTTPSConnection', return_value=connection):
                    with self.assertRaises(ValueError):
                        read_page(1, 100, time.monotonic() + 20)

    def test_new_only_from_exact_reference_release_for_all_efforts_clients_not_run_date(self):
        value = payload()
        snapshot = parse_pages(value['pages'], NOW)
        for age, expected in [(0, True), (6, True), (7, False), (8, False)]:
            release = datetime.fromtimestamp((NOW - age * 86400000) / 1000, timezone.utc).date().isoformat()
            references = [dict(publisher='Anthropic', model='Claude Opus 5.5', release_date=release, promotional=True)]

            result = benchmark_view(snapshot, references, now_ms=NOW)['rows']

            self.assertEqual([expected] * 4, [item['recent'] for item in result])
            self.assertTrue(all('promotion' not in item for item in result))
        for references in [[], [dict(publisher='Anthropic', model='Claude Opus 5', release_date='2026-11-09')],
                [dict(publisher='Anthropic', model='Claude Opus 5.5', release_date=None)],
                [dict(publisher='Other', model='Opus 5.5', release_date='2026-11-09')]]:
            self.assertFalse(any(item['recent'] for item in benchmark_view(snapshot, references, now_ms=NOW)['rows']))
        reference = dict(publisher='Anthropic', model='Claude Opus 5.5', release_date='2026-11-03')
        self.assertFalse(any(item['recent'] for item in benchmark_view(snapshot, [reference, reference], now_ms=NOW)['rows']))
        self.assertFalse(any(item['recent'] for item in benchmark_view(snapshot, [reference], now_ms=NOW + 86400000)['rows']))

    def test_transport_is_fixed_https_post_with_bounds_and_no_credentials_or_redirects(self):
        connection, response = Mock(), Mock()
        response.status = 200
        response.getheader.return_value = 'application/json; charset=utf-8'
        response.read1.side_effect = [b'{"ok":true}', b'']
        connection.getresponse.return_value = response
        with patch('src.benchmarks.http.client.HTTPSConnection', return_value=connection) as connect:
            value, size = read_page(1, 100, time.monotonic() + 20)

        self.assertEqual(({'ok': True}, 11), (value, size))
        self.assertEqual('api.harborframework.com', connect.call_args.args[0])
        args, kwargs = connection.request.call_args
        self.assertEqual(('POST', '/functions/v1/leaderboard-read'), args)
        self.assertEqual(dict(package='terminal-bench/terminal-bench', name='4-0-0', page=1, page_size=100), json.loads(kwargs['body']))
        self.assertEqual({'Content-Type', 'Accept', 'User-Agent'}, set(kwargs['headers']))
        self.assertTrue(connection.close.called)
        for status, chunks, remaining in [(302, [], 100), (429, [], 100), (200, [b'x' * 11], 10)]:
            response.status, response.read1.side_effect = status, chunks
            with patch('src.benchmarks.http.client.HTTPSConnection', return_value=connection):
                with self.assertRaises(ValueError):
                    read_page(1, remaining, time.monotonic() + 20)

    def test_last_good_cache_retained_after_failure_and_independent_lane_coalesces_backoff(self):
        with tempfile.TemporaryDirectory() as root:
            cache = BenchmarkCache(root)
            cache.put(payload())
            original = cache.path.read_bytes()
            jobs = Mock()
            jobs.submit.return_value = 'one'
            jobs.snapshot.return_value = dict(status='running')
            clock = [0]
            lane = BenchmarkLane(root, jobs=jobs, clock=lambda: clock[0], wall_clock=lambda: NOW / 1000 + 90000)
            self.assertEqual(NOW, lane.view()['fetched_at_ms'])
            lane.view(); lane.tick(); lane.tick()
            jobs.submit.assert_called_once()
            jobs.snapshot.return_value = dict(status='failed', result=None)

            lane.tick(); lane.view(); lane.tick()

            self.assertEqual(original, cache.path.read_bytes())
            self.assertEqual(NOW, lane.view()['fetched_at_ms'])
            self.assertEqual(1, jobs.submit.call_count)
            self.assertEqual('benchmark_unavailable', lane.error)
            lane.close(); jobs.close.assert_called_once()

    def test_spawned_finite_job_publishes_cache_then_restart_keeps_real_date_without_refetch(self):
        with tempfile.TemporaryDirectory() as root:
            jobs = ReportJobs(target=finite_benchmark)
            lane = BenchmarkLane(root, jobs=jobs, wall_clock=lambda: NOW / 1000)
            try:
                self.assertEqual([], lane.view()['rows'])
                deadline = time.monotonic() + 10
                while lane.snapshot is None and time.monotonic() < deadline:
                    lane.tick()
                    time.sleep(0.01)
                self.assertIsNotNone(lane.snapshot)
                self.assertEqual(4, len(lane.view(references())['rows']))
                deadline = time.monotonic() + 3
                while jobs._retiring and time.monotonic() < deadline:
                    lane.tick()
                    time.sleep(0.01)
                self.assertEqual([], jobs._retiring)
            finally:
                lane.close()
            replacement = Mock()
            restarted = BenchmarkLane(root, jobs=replacement, wall_clock=lambda: NOW / 1000)
            self.assertEqual(NOW, restarted.view()['fetched_at_ms'])
            restarted.tick()
            replacement.submit.assert_not_called()
            restarted.close()

    def test_http_benchmark_is_authenticated_benign_and_never_submits_price_or_report_work(self):
        server = LoopbackServer(Mock())
        stopped = Event()
        thread = Thread(target=lambda: self._serve(server, stopped))
        thread.start()
        try:
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            connection.request('GET', '/api/models/benchmark')
            response = connection.getresponse(); response.read()
            self.assertEqual(401, response.status)
            connection.close()
            credential = server.session.bootstrap()
            cookie, _ = server.session.exchange(credential)
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            connection.request('GET', '/api/models/benchmark', headers={'Cookie': f'{server.session.cookie_name}={cookie}'})
            response = connection.getresponse()
            self.assertEqual(200, response.status)
            self.assertEqual([], json.loads(response.read())['rows'])
            connection.close()
            server.jobs.submit.assert_not_called()
        finally:
            stopped.set(); thread.join(3); server.server_close()

    def test_intersection_is_exact_canonical_unique_and_keeps_full_dataset_efforts_and_denominator(self):
        unmatched = row(9, model='Not in GitHub', effort='unmatched-effort', cost=33)
        missing = row(10, effort=''); missing['metadata'].pop('reasoning_effort')
        hostile = row(11); hostile['metadata']['model_org']['url'] = 'https://example.com'
        snapshot = parse_pages([page([row(), unmatched, missing, hostile])], NOW)
        reference = dict(publisher='Anthropic', model='Claude Opus 5.5', release_date='2026-11-09',
            selectable=False, superseded=True, superseded_selectable=False)

        value = benchmark_view(snapshot, [reference], now_ms=NOW, timezone_id='Europe/Stockholm')

        self.assertEqual(['', 'max', 'unmatched-effort'], value['efforts'])
        self.assertEqual(2, len(value['rows']))
        self.assertEqual(['Claude Opus 5.5'] * 2, [item['model'] for item in value['rows']])
        self.assertTrue(all(item['publisher'] == 'Anthropic' and not item['selectable'] and item['superseded']
            and not item['superseded_selectable'] and Decimal(item['relative_cost']) == 10 for item in value['rows']))
        self.assertEqual('2026-11-09 01:00', value['fetched_text'])
        self.assertIn('Coding Client: Claude Code', value['rows'][0]['configuration_help'])
        self.assertIn('USD/Task: $1 per attempted task (failures included)', value['rows'][0]['task_help'])
        for candidates in ([], [reference, reference], [dict(reference, model='Claude Opus 5')],
                [dict(reference, publisher='Other')]):
            self.assertEqual([], benchmark_view(snapshot, candidates, now_ms=NOW)['rows'])

    def test_manual_refresh_bypasses_freshness_coalesces_and_retains_last_success_after_failure(self):
        with tempfile.TemporaryDirectory() as root:
            BenchmarkCache(root).put(payload())
            jobs = Mock(); jobs.submit.return_value = 'one'
            jobs.snapshot.return_value = dict(status='running')
            lane = BenchmarkLane(root, jobs=jobs, wall_clock=lambda: NOW / 1000 + 60)
            lane.view(); lane.tick(); jobs.submit.assert_not_called()

            lane.refresh(); lane.refresh(); self.assertTrue(lane.view()['refreshing'])
            lane.tick(); lane.refresh(); lane.tick()

            jobs.submit.assert_called_once()
            jobs.snapshot.return_value = dict(status='failed')
            lane.tick()
            self.assertFalse(lane.view()['refreshing'])
            self.assertTrue(lane.view()['unavailable'])
            self.assertEqual(NOW, lane.view()['fetched_at_ms'])
            lane.refresh(); lane.tick()
            self.assertEqual(2, jobs.submit.call_count)
            updated = payload(); updated['fetched_at_ms'] = NOW + 60000
            jobs.snapshot.return_value = dict(status='complete', result=dict(benchmark=updated))
            lane.tick()
            self.assertEqual(NOW + 60000, lane.view()['fetched_at_ms'])
            self.assertFalse(lane.view()['unavailable'])
            lane.close()

    def test_manual_http_refresh_requires_cookie_csrf_origin_and_empty_body(self):
        lane = Mock()
        server = LoopbackServer(Mock())
        server.lifecycle = SimpleNamespace(benchmark=lane, stopping=Event(), dispatcher=None,
            observations=Mock(), nonce='benchmark-test')
        stopped = Event(); thread = Thread(target=lambda: self._serve(server, stopped)); thread.start()
        try:
            cookie, csrf = server.session.exchange(server.session.bootstrap())
            origin = f'http://127.0.0.1:{server.server_port}'
            headers = {'Content-Type': 'application/json', 'Origin': origin,
                'Cookie': f'{server.session.cookie_name}={cookie}', 'X-CG-CSRF': csrf}
            for changes, body, expected in [({'Cookie': ''}, {}, 401), ({'X-CG-CSRF': ''}, {}, 403),
                    ({'Origin': 'http://example.com'}, {}, 403), ({}, {'force': True}, 400), ({}, {}, 202)]:
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                connection.request('POST', '/api/models/benchmark/refresh', json.dumps(body), headers | changes)
                response = connection.getresponse(); response.read(); connection.close()
                self.assertEqual(expected, response.status)
            lane.refresh.assert_called_once_with()
            server.jobs.submit.assert_not_called()
        finally:
            stopped.set(); thread.join(3); server.server_close()

    @staticmethod
    def _serve(server, stopped):
        while not stopped.is_set():
            server.handle_request()
