"""Bounded read-only real-installation probe; no UI, inference or service stop."""
import http.client
import argparse
import json
import re
from pathlib import Path
import sys
from threading import enumerate as threads
import time
import traceback
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.web.composition import live_acquisition
from src.web.host import WebHost
from src.web.jobs import ReportJobs
from src.numbers import ccost_amount
from development.tests.integration.web_live_observations import ProbeObservations, probe_lifecycle


def check_reference_quotas(accounts):
    """Independent native-fact oracle; export only counts, never private balances."""
    counts = dict(native_capacities=0, native_amount_pairs=0, native_pace=0)
    for item in accounts['accounts']:
        for slot in (item['primary'], *item['secondary']):
            quota = slot['quota']
            if quota.get('display', {}).get('capacity_basis') != 'native':
                continue
            tokens = quota['display_units']['credits']
            counts['native_capacities'] += 1
            capacity = Decimal(quota['reference_ccost_capacity'] or quota['limit'])
            limit = None if quota['limit'] is None else Decimal(quota['limit'])
            used = None if quota['used'] is None else Decimal(quota['used'])
            remaining = None if quota['remaining'] is None else Decimal(quota['remaining'])
            if quota['reference_ccost_capacity'] is not None:
                used = None if used is None or limit is None else used * capacity / limit
                remaining = None if remaining is None or limit is None else remaining * capacity / limit
            if used is None and remaining is None and quota['remaining_fraction'] is not None:
                remaining = capacity * Decimal(quota['remaining_fraction'])
            if used is None and remaining is not None:
                used = capacity - remaining
            if remaining is None and used is not None:
                remaining = capacity - used
            expected = tuple('?' if value is None else ccost_amount(value) for value in (used, remaining, capacity))
            assert tuple(tokens['ccost_' + key] for key in ('used', 'remaining', 'capacity')) == expected, 'native reference tokens'
            if used is not None and remaining is not None:
                counts['native_amount_pairs'] += 1
                assert used + remaining == capacity, 'native reference reconciliation'
            pace = quota['ccost_pace']
            if pace:
                counts['native_pace'] += 1
                assert Decimal(pace['ccost_remaining']) == remaining, 'native remaining pace basis'
                assert Decimal(pace['ccost_per_day']) == remaining / pace['days'], 'native daily pace'
    return counts


def check_estimate_quotas(accounts):
    """Count raw/display bound checks without exporting private quantities or identities."""
    count = 0
    for item in accounts['accounts']:
        for slot in (item['primary'], *item['secondary']):
            quota = slot['quota']
            raw = quota.get('ccost_reference', {})
            tokens = {**quota.get('display', {}), **quota.get('display_units', {}).get('credits', {})}
            fields = [('monthly_capacity', raw.get('monthly_capacity'))]
            if raw.get('basis') == 'ratio':
                fields += [('ccost_' + key, raw.get(key)) for key in ('capacity', 'remaining')]
            pace = quota.get('ccost_pace')
            records = [(tokens, fields)]
            if pace and pace.get('capacity_basis') == 'ratio':
                records.append(({**pace.get('display', {}), **pace.get('display_units', {}).get('credits', {})},
                    [(key, pace[key]) for key in ('ccost_per_day', 'ccost_per_workday')]))
            for display, estimates in records:
                for key, value in estimates:
                    if value is None:
                        continue
                    original = Decimal(value)
                    rendered = Decimal(display[key].removeprefix('~'))
                    assert abs(rendered - original) <= original / 20, 'estimate display tolerance'
                    assert original == 0 or rendered > 0, 'positive estimate display'
                    if key == 'monthly_capacity':
                        assert 'not an actual monthly provider entitlement' in display[key + '_help'], 'monthly provenance help'
                    else:
                        assert 'not verified provider usage' in display[key + '_help'], 'estimate provenance help'
                    count += 1
    return dict(checked_amounts=count)


def check_account_today(accounts):
    """Observe daily accounting separately from native quota availability; no private values."""
    from src.analysis.valuation import ComparisonCost
    from src.numbers import ccost_display
    from src.presentation.accounts import account_ccost_text
    results = []
    for item in accounts['accounts']:
        cost = next(scope['cost'] for scope in item['ccost_scopes'] if scope['name'] == 'today')
        state = 'unknown'
        if cost is not None:
            value = ComparisonCost(Decimal(cost['known_ccost']), cost['observed_requests'], cost['priced_requests'])
            for unit in ('credits', 'usd'):
                with ccost_display(unit):
                    assert cost['display_units'][unit]['account_ccost'] == account_ccost_text(value), 'account Today display'
            state = ('unpriced' if value.observed_requests and not value.priced_requests else
                'partial' if not value.complete else 'positive' if value.known_ccost > 0 else 'zero')
        results.append(dict(provider=item['observation']['provider_id'], today=state))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detail", action="store_true", help="Also probe complete session capture/pages/freeze.")
    parser.add_argument("--sessions", action="store_true", help="Measure live Sessions scalar indexing and complete pinned history.")
    parser.add_argument("--reports", action="store_true", help="Also capture finite reports beside Live and cancel deep history.")
    parser.add_argument("--models", action="store_true", help="Capture only task-focused Normal/full Models snapshots beside Live.")
    parser.add_argument("--refresh-prices", action="store_true", help="Force one upstream pricing fetch/rebuild beside pinned Live; no account refresh.")
    parser.add_argument('--benchmark', action='store_true', help='Observe the independent public Harbor lane via authenticated local HTTP.')
    parser.add_argument('--benchmark-cold', action='store_true', help='Ignore this probe host\'s cached benchmark in memory; keep the on-disk last-good file.')
    parser.add_argument("--watch-cards", action="store_true", help="Wait for independently published real one-row Watch cards.")
    parser.add_argument('--context-deltas', action='store_true', help='Check real card context export/formatting; counts only, no prompt text or source mutation.')
    parser.add_argument("--watch-seconds", type=int, default=90,
        help="Watch-card observation cap, 90..300 seconds; no product deadline change.")
    parser.add_argument("--accounts", action="store_true", help="Observe shared account publications without finite reports or new owners.")
    parser.add_argument("--tool-outcomes", action="store_true", help="Check evidenced tool outcome subsets in the published cards.")
    parser.add_argument("--tool-invocations", action="store_true", help="Observe active invocation DTOs without waiting for unrelated Earlier coverage; scalar evidence only.")
    parser.add_argument("--prompt-token-mix", action="store_true", help="Observe card token mix over twelve seconds; no inference or extra capture.")
    parser.add_argument("--prompt-cost", action="store_true", help="Compare an observed completed prompt's raw cost split with a CLI session report.")
    parser.add_argument("--daily", action="store_true", help="Wait for coherent full-day cost, initiating prompts and category prices.")
    parser.add_argument("--session-cost", action="store_true", help="Compare a stable real session total with independent full history and persisted reuse.")
    parser.add_argument("--report-timings", action="store_true", help="Print sanitized child-process acquisition timings.")
    parser.add_argument('--history-oracle', type=Path, help='Owned new output directory for independent large-real-source history proof')
    parser.add_argument('--browser', type=Path, help='Explicit hidden Chromium executable for history-oracle Full/Mini DOM')
    parser.add_argument('--oracle-seconds', type=int, default=1800, help='Operational observation cap, never a product computation timeout')
    parser.add_argument('--oracle-serial-first', action='store_true',
        help='Time the first verified history certificate without competing reference refresh; validate that exact proof afterwards')
    args = parser.parse_args()
    if args.benchmark_cold and not args.benchmark:
        parser.error('--benchmark-cold requires --benchmark')
    if not 90 <= args.watch_seconds <= 300:
        parser.error('--watch-seconds requires 90..300 observation seconds')
    if args.history_oracle is not None:
        if args.browser is None or not args.browser.is_file() or not 120 <= args.oracle_seconds <= 3600:
            parser.error('history-oracle requires an explicit browser and 120..3600 observation seconds')
        from development.tests.integration.real_history_oracle import run
        if not run(ROOT, args.history_oracle, args.browser, seconds=args.oracle_seconds,
                serial_first=args.oracle_serial_first):
            raise SystemExit(1)
        return
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
    host = WebHost(ROOT, jobs=None if args.benchmark else jobs, live_factory=factory)
    if args.benchmark_cold:
        host.benchmark.snapshot = host.benchmark.cached = None
    streams = []
    observations = ProbeObservations(tool_invocations=args.tool_invocations)
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
        selected = owners[0].coordinator.selection.selected
        assert selected in {'v1', 'v2'} and live['source_generation'] == selected
        print(json.dumps(dict(source_generation='verified', selected=selected,
            transport='authenticated_host_live', live_owners=len(owners))))
        if args.benchmark:
            from development.tests.integration.models_source_observations import observe_benchmark
            print(json.dumps(observe_benchmark(get, cookie, host)))
            assert len(owners) == 1 and owners[0].coordinator.report_service is not None
        if args.accounts:
            observations.stage = 'accounts'
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                state, _ = get('/api/live', cookie=cookie)
                account_view = (state['values'].get('live', {}).get('view') or {}).get('accounts')
                if account_view is not None:
                    break
                time.sleep(.25)
            else:
                raise RuntimeError('probe_accounts_timeout')
            owner = owners[0].coordinator
            account_owner = owner.accounts
            first_sequence = state['sequence']
            for _ in range(5):
                time.sleep(1)
                state, _ = get('/api/live', cookie=cookie)
                current = state['values']['live']['view']
                assert len(owners) == 1 and owners[0].coordinator is owner and owner.accounts is account_owner
                assert current['started_at_ms'] == start
                assert current['accounts'] is not None
            assert state['sequence'] > first_sequence
            print(json.dumps(dict(accounts='ok', account_cards=len(current['accounts']['accounts']),
                account_refresh_owners=1, live_owners=len(owners), publication_advanced=True,
                reference_quotas=check_reference_quotas(current['accounts']),
                estimate_quotas=check_estimate_quotas(current['accounts']),
                finite_jobs_started=0, model_calls_started_by_probe=0)))
        if args.sessions:
            from development.tests.integration.session_catalog_observations import observe_sessions
            observations.stage = 'sessions'
            observe_sessions(get, cookie, host, owners[0])
        card_evidence = None
        if args.watch_cards or args.tool_outcomes or args.context_deltas:
            observations.stage = 'watch_cards'
            first_rows = None
            publications = []
            deadline = time.monotonic() + args.watch_seconds
            while time.monotonic() < deadline:
                state, _ = get('/api/live', cookie=cookie)
                live = state['values'].get('live', {})
                view = live.get('view') or {}
                publications.append((time.monotonic(), state['sequence']))
                if view.get('history_state') == 'loading':
                    assert not view.get('history_cards'), 'provisional history escaped the producer'
                cards = [*view.get('active_cards', []), *view.get('history_cards', [])]
                if any(card['rows'] for card in cards) and first_rows is None:
                    first_rows = round(time.monotonic() - started, 3)
                if any('totals' in card or 'provisional' in card for card in cards):
                    raise RuntimeError('probe_watch_card_legacy_totals')
                if args.context_deltas and not args.watch_cards and any(
                        row['live_context']['watch_delta_context_tokens'] is not None
                        for card in cards for row in card['rows']):
                    # Context proof is independent of certifying every Earlier
                    # winner in a large installation. Do not label that history PASS.
                    card_evidence = dict(scope='observed_context_only', active_cards=len(view['active_cards']),
                        history_cards=len(view['history_cards']), history_state=view['history_state'],
                        first_rows_seconds=first_rows)
                    break
                if first_rows is not None and view.get('history_state') == 'observed':
                    assert view['history_checked'] == view['history_total']
                    assert view['history_epoch'] > 0 and view['history_verified_at_ms'] is not None
                    owner = owners[0].coordinator
                    expected = sorted((entry.finished_ms, key) for key, entry in owner.cards.sessions.items()
                        if entry.latest_ms and not owner.cards._focals(entry, owner.clock_ms()))
                    expected = sorted(expected, key=lambda pair: (-pair[0], pair[1]))[:5]
                    assert {card['session_id'] for card in view['history_cards']} == {key for _, key in expected}
                    history_prompts = [row['prompt'] for card in view['history_cards'] for row in card['rows']]
                    known_finishes = [prompt for prompt in history_prompts if prompt['completed_at_ms'] is not None]
                    for prompt in history_prompts:
                        tokens = prompt['display']
                        if prompt['completed_at_ms'] is not None:
                            assert re.fullmatch(r'\d{2}:\d{2}', tokens['finished_clock'])
                            assert re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2} [+-]\d{4}', tokens['finished_date_time'])
                        else:
                            assert (tokens['finished_clock'], tokens['finished_date_time']) == ('—', 'Unknown finish time')
                    card_evidence = dict(active_cards=len(view['active_cards']), history_cards=len(view['history_cards']),
                        known_history_finishes=len(known_finishes), unknown_history_finishes=len(history_prompts)-len(known_finishes),
                        row_cards=sum(bool(card['rows']) for card in cards),
                        first_rows_seconds=first_rows,
                        first_verified_history_seconds=round(time.monotonic() - started, 3),
                        history_checked=view['history_checked'], history_total=view['history_total'],
                        history_state=view['history_state'], proof_epoch=view['history_epoch'],
                        publication_advances=len(set(seq for _, seq in publications)),
                        max_http_sample_gap_seconds=round(max((b[0]-a[0] for a,b in zip(publications, publications[1:])), default=0), 3),
                        max_rows_per_card=max(len(card['rows']) for card in cards),
                        pending_captures=len(owners[0].coordinator.card_workers.jobs))
                    if card_evidence['max_rows_per_card'] != 1 or card_evidence['pending_captures'] > 4:
                        raise RuntimeError('probe_watch_card_bound_failed')
                    break
                if live.get('state') in {'failed', 'internal_error'}:
                    raise RuntimeError('probe_watch_cards_failed')
                time.sleep(.25)
            else:
                print(json.dumps(dict(history_verification='inconclusive', history_state=view.get('history_state'),
                    checked=view.get('history_checked'), total=view.get('history_total'),
                    cause=view.get('history_cause'), deadline_seconds=args.watch_seconds)))
                raise RuntimeError('probe_watch_cards_timeout')
        if args.context_deltas:
            from src.display import context_delta, context_tokens
            counts = dict(known=0, unavailable=0, running_known=0, historical_known=0, handoffs=0)
            for card in cards:
                handoff = card.get('context_handoff')
                if handoff is not None:
                    counts['handoffs'] += 1
                    assert card['state'] == 'observed' and card['focal_id']
                    assert handoff['previous_id'] != card['focal_id']
                    assert type(handoff['previous_tokens']) is int and handoff['previous_tokens'] >= 0
                    current = next(row for row in card['rows'] if row['prompt']['event_id'] == card['focal_id'])
                    assert current['prompt']['in_progress'] and not current['prompt']['execution_unverified']
                    assert current['live_context']['watch_next_context_tokens'] is None
                for row in card['rows']:
                    context = row['live_context']
                    delta = context['watch_delta_context_tokens']
                    assert context['display']['watch_delta_context_tokens'] == context_delta(delta)
                    assert context['display']['watch_next_context_tokens'] == context_tokens(context['watch_next_context_tokens'])
                    counts['unavailable' if delta is None else 'known'] += 1
                    if delta is not None:
                        assert context['watch_next_context_tokens'] is not None
                        counts['running_known' if row['prompt']['in_progress'] else 'historical_known'] += 1
            print(json.dumps(dict(context_deltas='export_checked', **counts)))
        if args.tool_outcomes:
            activities = [row['tool'] for card in cards for row in card['rows'] if row.get('tool')]
            for activity in activities:
                outcomes = activity['outcomes']
                assert all(item['outcome'] in {'failed', 'cancelled'} and item['count'] > 0 for item in outcomes)
                assert len({(item['tool_name'], item['outcome']) for item in outcomes}) == len(outcomes)
                assert sum(item['count'] for item in outcomes if item['outcome'] == 'failed') == activity['failed_count']
                assert sum(item['count'] for item in outcomes if item['outcome'] == 'cancelled') == activity['cancelled_count']
                assert sum(item['count'] for item in outcomes) == activity['failed_or_cancelled_count']
                counts = dict(activity['counts'])
                for name, count in counts.items():
                    assert sum(item['count'] for item in outcomes if item['tool_name'] == name) <= count
                assert all(item['tool_name'] in counts for item in outcomes)
            print(json.dumps(dict(tool_outcomes='ok' if activities else 'unobserved', cards_with_activity=len(activities),
                failed=sum(item['failed_count'] for item in activities),
                cancelled=sum(item['cancelled_count'] for item in activities), model_calls_started_by_probe=0)))
        if args.tool_invocations:
            observations.stage = 'tool_invocations'
            deadline = time.monotonic() + 60
            observed = 0
            while time.monotonic() < deadline:
                state, _ = get('/api/live', cookie=cookie)
                view = (state['values'].get('live') or {}).get('view') or {}
                for card in view.get('active_cards', []):
                    for row in card['rows']:
                        activity = row.get('tool') or {}
                        for key in ('running_invocation', 'background_invocation'):
                            detail = activity.get(key)
                            if detail is None:
                                continue
                            assert card['state'] == 'observed' and row['prompt']['in_progress']
                            assert not row['prompt']['execution_unverified']
                            assert set(detail) == {'identity', 'revision', 'text', 'qualification'}
                            assert len(detail['identity']) == len(detail['revision']) == 64
                            assert len(json.dumps(detail)) < 10_000
                            assert isinstance(detail['qualification'], str)
                            assert detail['text'] or detail['qualification'], 'input or factual absence reason'
                            observed += 1
                if observed:
                    break
                time.sleep(1)
            print(json.dumps(dict(tool_invocations='observed' if observed else 'unobserved',
                observed_details=observed, native_commands_preserved=len(observations.invocation_commands),
                native_timeouts_labeled=len(observations.invocation_timeouts),
                scalar_evidence_only=True, model_calls_started_by_probe=0)))
            if not observed:
                raise RuntimeError('probe_no_live_invocation_observed')
        if args.prompt_cost:
            from development.tests.integration.prompt_cost_observations import observe_prompt_cost
            observations.stage = 'prompt_cost'
            observe_prompt_cost(get, cookie, owners[0])
        if args.session_cost:
            from development.tests.integration.session_cost_observations import observe_session_cost
            observations.stage = 'session_cost'
            observe_session_cost(get, cookie, owners[0])
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
                    from src.numbers import ccost_amount, ccost_display
                    for unit in ('credits', 'usd'):
                        tokens = daily.get('display_units', {}).get(unit, {})
                        shown = tokens.get('daily_ccost', daily['display']['daily_ccost'])
                        with ccost_display(unit):
                            expected = ('N/A' if total['observed_requests'] and not total['priced_requests']
                                else ccost_amount(Decimal(total['known_ccost'])))
                        assert shown == expected
                    print(json.dumps(dict(daily='ok', requests=mix['request_count'], prompts=daily['prompt_count'],
                        prompt_count_complete=daily['prompt_count_complete'], cost_complete=total['complete'],
                        category_costs_reconcile=True, quiet_daily_units=True,
                        account_today=check_account_today(live['view']['accounts']),
                        seconds=round(time.monotonic() - started, 3))))
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
        # A bounded source read can exceed two seconds without a stream fault.
        # Wait for an actual later publication rather than guessing its cadence.
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            latest, _ = get('/api/live', cookie=cookie)
            if latest['sequence'] > state['sequence']:
                break
            time.sleep(.25)
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
        if args.refresh_prices:
            from development.tests.integration.models_price_observations import observe_price_refresh
            observations.stage = 'price_refresh'
            observe_price_refresh(get, cookie, owners[0])
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
    if args.benchmark:
        # A short benchmark probe can finish during unrelated native quota HTTP.
        # Observe those exact in-process workers' natural exit, not change product
        # close latency, kill them, or weaken the final zero-owner assertion.
        retiring = [thread for thread in threads() if thread.name.startswith('cost-guard-')]
        started_retiring = time.monotonic()
        deadline = started_retiring + 45
        for thread in retiring:
            thread.join(timeout=max(0, deadline - time.monotonic()))
        print(json.dumps(dict(retiring_workers_observed=len(retiring),
            retirement_seconds=round(time.monotonic() - started_retiring, 3))))
    final = observations.snapshot(host)
    if final['owned_threads'] or final['owned_processes']:
        raise RuntimeError('probe_owned_workers_remaining')
    print('PASS owned live and HTTP workers closed; shared OpenCode untouched')


if __name__ == '__main__':
    main()
