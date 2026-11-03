"""Bounded read-only real-installation probe; no UI, inference or service stop."""
import http.client
import argparse
import json
from pathlib import Path
import sys
import time
import traceback
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.web.composition import live_acquisition
from src.web.host import WebHost
from src.web.jobs import ReportJobs
from development.tests.integration.web_live_observations import ProbeObservations, probe_lifecycle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detail", action="store_true", help="Also probe complete session capture/pages/freeze.")
    parser.add_argument("--reports", action="store_true", help="Also capture finite reports beside Live and cancel deep history.")
    parser.add_argument("--models", action="store_true", help="Capture only task-focused Normal/full Models snapshots beside Live.")
    parser.add_argument("--watch-cards", action="store_true", help="Wait for independently published real one-row Watch cards.")
    parser.add_argument("--prompt-token-mix", action="store_true", help="Observe card token mix over twelve seconds; no inference or extra capture.")
    parser.add_argument("--daily", action="store_true", help="Wait for coherent full-day cost, initiating prompts and category prices.")
    parser.add_argument("--report-timings", action="store_true", help="Print sanitized child-process acquisition timings.")
    args = parser.parse_args()
    owners = []
    csrf = None

    def factory():
        driver = live_acquisition()
        owners.append(driver)
        return driver

    started = time.monotonic()
    jobs = ReportJobs()
    if args.report_timings:
        from development.tests.integration.historical_report_observations import measured_report
        jobs = ReportJobs(target=measured_report)
    host = WebHost(ROOT, jobs=jobs, live_factory=factory)
    streams = []
    observations = ProbeObservations()
    with observations.installed(), probe_lifecycle(host, streams, observations):
        host.start()
        shell_seconds = time.monotonic() - started
        server = host.server

        def get(path, *, value=None, cookie=None):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            headers = {'Host': server.host}
            if cookie:
                headers['Cookie'] = cookie
            if value is not None:
                headers.update(Origin=server.origin, **{'Content-Type': 'application/json'})
                if csrf:
                    headers['X-CG-CSRF'] = csrf
            route = path.split('/')[2] if path.startswith('/api/') else 'other'
            try:
                with observations.phase('http.' + route):
                    connection.request('POST' if value is not None else 'GET', path,
                                       json.dumps(value) if value is not None else None, headers)
                    response = connection.getresponse()
                    data = json.loads(response.read())
            finally:
                connection.close()
            if response.status not in {200, 202}:
                raise RuntimeError('probe_http_failed')
            return data, response

        auth, response = get('/api/bootstrap', value={'credential': server.session.bootstrap()})
        csrf = auth['csrf']
        cookie = response.getheader('Set-Cookie').split(';')[0]
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            state, _ = get('/api/live', cookie=cookie)
            live = state['values'].get('live', {})
            if live.get('view'):
                break
            if live.get('state') in {'failed', 'internal_error'}:
                raise RuntimeError('probe_source_unavailable')
            time.sleep(0.25)
        else:
            raise RuntimeError('probe_live_timeout')
        start = live['view']['started_at_ms']
        source_seconds = time.monotonic() - started
        card_evidence = None
        if args.watch_cards:
            observations.stage = 'watch_cards'
            first_rows = None
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                state, _ = get('/api/live', cookie=cookie)
                live = state['values'].get('live', {})
                view = live.get('view') or {}
                cards = [*view.get('active_cards', []), *view.get('history_cards', [])]
                if any(card['rows'] for card in cards) and first_rows is None:
                    first_rows = round(time.monotonic() - started, 3)
                if any('totals' in card or 'provisional' in card for card in cards):
                    raise RuntimeError('probe_watch_card_legacy_totals')
                if first_rows is not None and view.get('history_cards'):
                    card_evidence = dict(active_cards=len(view['active_cards']), history_cards=len(view['history_cards']),
                        row_cards=sum(bool(card['rows']) for card in cards),
                        first_rows_seconds=first_rows,
                        max_rows_per_card=max(len(card['rows']) for card in cards),
                        pending_captures=len(owners[0].coordinator.card_workers.jobs))
                    if card_evidence['max_rows_per_card'] != 1 or card_evidence['pending_captures'] > 4:
                        raise RuntimeError('probe_watch_card_bound_failed')
                    break
                if live.get('state') in {'failed', 'internal_error'}:
                    raise RuntimeError('probe_watch_cards_failed')
                time.sleep(.25)
            else:
                raise RuntimeError('probe_watch_cards_timeout')
        if args.daily:
            observations.stage = 'daily'
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                state, _ = get('/api/live', cookie=cookie)
                live = state['values'].get('live', {})
                daily = (live.get('view') or {}).get('daily_usage')
                if daily is not None:
                    mix, total = daily['mix'], daily['total']
                    assert mix['request_count'] == total['observed_requests']
                    assert mix['priced_requests'] == total['priced_requests']
                    assert sum(Decimal(cost) for cost in mix['costs']) == Decimal(total['known_ccost'])
                    assert isinstance(daily['prompt_count'], int) and daily['prompt_count'] >= 0
                    print(json.dumps(dict(daily='ok', requests=mix['request_count'], prompts=daily['prompt_count'],
                        prompt_count_complete=daily['prompt_count_complete'], cost_complete=total['complete'],
                        category_costs_reconcile=True, seconds=round(time.monotonic() - started, 3))))
                    break
                if live.get('state') in {'failed', 'internal_error'}:
                    raise RuntimeError('probe_daily_failed')
                time.sleep(.25)
            else:
                raise RuntimeError('probe_daily_timeout')
        if args.prompt_token_mix:
            observations.stage = 'prompt_token_mix'
            previous, known, changes, usage_changes = {}, set(), 0, 0
            for _ in range(12):
                state, _ = get('/api/live', cookie=cookie)
                current = (state['values'].get('live') or {}).get('view') or {}
                for card in [*current.get('active_cards', []), *current.get('history_cards', [])]:
                    for item in card['rows']:
                        row = item['prompt']
                        key = (card['session_id'], row['event_id'])
                        mix = row['token_mix_percent']
                        if mix is not None:
                            assert len(mix) == 4 and sum(mix) == 100
                            assert row['display']['token_mix_percent'] == '/'.join(map(str, mix))
                            known.add(key)
                        else:
                            assert row['display']['token_mix_percent'] in {'N/A', 'running'}
                        value = (row['calls'], mix)
                        if key in previous:
                            usage_changes += value[0] != previous[key][0]
                            changes += value[1] != previous[key][1]
                        previous[key] = value
                time.sleep(1)
            print(json.dumps(dict(prompt_token_mix='ok', observed_rows=len(previous), known_rows=len(known),
                call_count_changes=usage_changes, mix_changes=changes, observation_seconds=12,
                model_calls_started_by_probe=0)))
        observations.stage = 'streams'
        for _ in range(2):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            connection.request('GET', '/api/events', headers={'Cookie': cookie,
                'Last-Event-ID': f"{state['instance_id']}:{state['sequence']}"})
            response = connection.getresponse()
            if response.status != 200 or b'retry:' not in response.readline():
                raise RuntimeError('probe_stream_failed')
            streams.append((connection, response))
        time.sleep(2)
        latest, _ = get('/api/live', cookie=cookie)
        view = latest['values']['live']['view']
        if latest['instance_id'] != state['instance_id'] or latest['sequence'] <= state['sequence']:
            raise RuntimeError('probe_stream_continuity_failed')
        for _, response in streams:
            for _ in range(128):
                line = response.readline()
                if not line:
                    raise RuntimeError('probe_stream_ended')
                if line.startswith(b'id: '):
                    instance, sequence = line.decode().strip()[4:].rsplit(':', 1)
                    if instance != state['instance_id'] or int(sequence) <= state['sequence']:
                        raise RuntimeError('probe_stream_continuity_failed')
                    break
            else:
                raise RuntimeError('probe_stream_continuity_failed')
        if len(owners) != 1 or view['started_at_ms'] != start:
            raise RuntimeError('probe_duplicate_owner')
        print(json.dumps({'status': 'ok', 'source': view['source_label'], 'owners': len(owners),
            'streams': len(streams), 'rows': len(view['rows']),
            'accounts': len((view['accounts'] or {}).get('accounts', [])),
            'run_origin_preserved': True, 'sequence_advanced': latest['sequence'] > state['sequence'],
            'stream_ids_verified': True,
            'shell_seconds': round(shell_seconds, 3), 'source_view_seconds': round(source_seconds, 3),
            'watch_cards': card_evidence}))
        if args.detail:
            observations.stage = 'detail'
            sessions = [row['session_id'] for row in view['rows']] + [card['session_id'] for card in
                [*view.get('active_cards', []), *view.get('history_cards', [])]]
            if not sessions:
                raise RuntimeError('probe_no_session_evidence')
            session_id = sessions[0]

            def detail(value):
                return get('/api/detail', value=value, cookie=cookie)[0]

            token = detail(dict(action='open', session_id=session_id, mode='live'))['token']
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                page = detail(dict(action='page', token=token, offset=0))
                if page.get('result'):
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError('probe_detail_timeout')
            last = detail(dict(action='page', token=token, offset=2**52))
            if last['total'] != page['total'] or len(last['result']['view']['prompt_blocks'][0]['rows']) > 50:
                raise RuntimeError('probe_detail_page_contract')
            detail(dict(action='freeze', token=token))
            frozen = detail(dict(action='page', token=token, offset=0))
            time.sleep(1)
            if detail(dict(action='page', token=token, offset=0)) != frozen:
                raise RuntimeError('probe_detail_freeze_changed')
            detail(dict(action='close', token=token))
            print(json.dumps(dict(detail='ok', available_rows=page['total'],
                page_rows=len(page['result']['view']['prompt_blocks'][0]['rows']),
                first_latest_access=True, frozen_consistent=True, account_owners=len(owners))))
        if args.reports or args.models:
            observations.stage = 'reports'
            # Do not emit session IDs, account details, report content or bootstrap values.
            def submit(value):
                return get('/api/reports', value=value, cookie=cookie)[0]['id']

            def job(key):
                return get('/api/jobs/' + key, cookie=cookie)[0]

            requests = ({'kind': 'normal'}, {'kind': 'all-models'}) if args.models else (
                            {'kind': 'normal'}, {'kind': 'all-models'},
                            {'kind': 'sessions', 'session_limit': 1},
                            {'kind': 'date', 'date_text': '2026-10-25'})
            for request in requests:
                report_started = time.monotonic()
                key = submit(request)
                deadline = time.monotonic() + 125
                while time.monotonic() < deadline:
                    value = job(key)
                    if value['status'] not in {'queued', 'running'}:
                        break
                    time.sleep(.25)
                if value['status'] != 'complete' or value['result']['error']:
                    print(json.dumps(dict(report=request['kind'], status=value['status'],
                                          error=value.get('error'), result_error=(value.get('result') or {}).get('error'),
                                          progress=value.get('progress'))))
                    code = value.get('error') or ((value.get('result') or {}).get('error') or {}).get('code') or value['status']
                    raise RuntimeError('probe_finite_report_failed_' + str(code))
                current, _ = get('/api/live', cookie=cookie)
                if len(owners) != 1 or current['values']['live']['view']['started_at_ms'] != start:
                    raise RuntimeError('probe_report_changed_live_owner')
                print(json.dumps(dict(report=request['kind'], status='complete', live_owner_preserved=True,
                                       seconds=round(time.monotonic() - report_started, 3))))
                if args.models:
                    report_view = value['result']['view']
                    rows = report_view['model_catalog']['rows']
                    assert all('selectable' in row and 'superseded_selectable' in row for row in rows)
                    assert report_view['model_comparison_sample_size'] <= 100
                    print(json.dumps(dict(catalog_rows=len(rows), selectable_rows=sum(row['selectable'] for row in rows),
                        selectable_latest_rows=sum(row['selectable'] and not row['superseded_selectable'] for row in rows),
                        availability_unverified=report_view['model_availability_unverified'],
                        accounts_present=report_view['accounts_quotas'] is not None)))
            if not args.models:
                key = submit({'kind': 'token-mix'})
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    value = job(key)
                    if value['status'] not in {'queued', 'running'} or value['progress']['phase'] == 'history':
                        break
                    time.sleep(.05)
                get('/api/jobs/' + key + '/cancel', value={}, cookie=cookie)
                value = job(key)
                if value['status'] not in {'cancelled', 'complete'}:
                    raise RuntimeError('probe_history_cancellation_failed')
                latest, _ = get('/api/live', cookie=cookie)
                if len(owners) != 1 or latest['values']['live']['view']['started_at_ms'] != start:
                    raise RuntimeError('probe_cancel_changed_live_owner')
                print(json.dumps(dict(history=value['status'], live_owner_preserved=True)))
    if host.failure:
        print(json.dumps({'runtime_error_type': type(host.failure).__name__, 'frames': [
            {'file': Path(frame.filename).name, 'function': frame.name, 'line': frame.lineno}
            for frame in traceback.extract_tb(host.failure.__traceback__)]}))
    if host.live.thread.is_alive() or host.thread.is_alive() or host.failure:
        raise RuntimeError('probe_shutdown_failed')
    final = observations.snapshot(host)
    if final['owned_threads'] or final['owned_processes']:
        raise RuntimeError('probe_owned_workers_remaining')
    print('PASS owned live and HTTP workers closed; shared OpenCode untouched')


if __name__ == '__main__':
    main()
