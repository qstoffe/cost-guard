"""Read-only real-source Sessions observations; output contains no titles or IDs."""
import json
import time

from src.domain.reference_cost import REASONS
from src.display import context_tokens


def reference_cost_evidence(values):
    unavailable = 0
    reasons = set()
    for value in values:
        comparison = value.get('comparison_cost') or {}
        issues = value.get('ccost_unavailable', comparison.get('ccost_unavailable', []))
        assert len(issues) <= 6
        assert all(set(issue) == {'reason', 'model', 'detail'} and issue['reason'] in REASONS for issue in issues)
        if value['display'].get('ccost', value['display'].get('total_ccost')) == 'N/A':
            unavailable += 1
            assert not issues or 'N/A does not mean zero' in value['display']['ccost_unavailable_help']
            reasons.update(issue['reason'] for issue in issues)
    return {'values': len(values), 'unavailable': unavailable, 'reasons': sorted(reasons)}


def observe_sessions(get, cookie, host, driver):
    started = time.monotonic()
    timings, coverage, visible_coverage, progress = [], [], [], []

    def request(path, value):
        before = time.monotonic()
        result = get(path, value=value, cookie=cookie)[0]
        timings.append(time.monotonic() - before)
        return result

    page = request('/api/sessions', {})
    token = page['token']
    first_seconds = time.monotonic() - started
    original = {row['session_id'] for row in page['view']['session_usage']}
    arrival = None
    cold_running = 0
    multiple_model_rows = 0
    for _ in range(30):
        current = request('/api/sessions', dict(token=token, sort='ctx'))
        coverage.append(current['indexed'])
        progress.append(current['progress'])
        assert len(current['view']['session_usage']) <= 50
        assert current['pending_sort'] == (current['indexed'] != current['available'])
        if current['pending_sort']:
            assert current['sort'] == 'activity'
        latest = request('/api/sessions', dict(token=token))
        for row in latest['view']['session_usage']:
            tokens = row['context_tokens']
            assert tokens is None or type(tokens) is int and tokens >= 0
            assert row['display']['context_tokens'] == ('0' if tokens == 0 else context_tokens(tokens))
            assert row['metric_states']['ctx'] in ('ready', 'pending', 'retained', 'unavailable')
            models = row['contributor_models']
            assert len(models) <= 64 and all(isinstance(value, str) and 0 < len(value) <= 256 for value in models)
            assert models == sorted(set(models))
            cold_running += bool(row['running'] and not row['has_summary'])
            multiple_model_rows += bool(row['multiple_models'] and len(models) > 1)
        visible_coverage.append(sum(row['indexed'] for row in latest['view']['session_usage']))
        if original and any(row['session_id'] not in original for row in latest['view']['session_usage']):
            arrival = 'changed_first_page_observed; no session created by probe'
        # Keep the intended global sort's interest active during the observation,
        # rather than accidentally restoring Activity demand between every sample.
        request('/api/sessions', dict(token=token, sort='ctx'))
        time.sleep(1)
    candidates = [row for row in latest['view']['session_usage']
                  if row['indexed'] and 0 < (row['prompt_count'] or 0) <= 1000]
    if not candidates:
        raise RuntimeError('probe_no_indexed_detail_candidate')
    opened = request('/api/detail', dict(action='open', session_id=candidates[0]['session_id'], mode='live'))
    detail_started = time.monotonic()
    try:
        deadline = detail_started + 60
        while time.monotonic() < deadline:
            detail = request('/api/detail', dict(action='begin', token=opened['token'], offset=0))
            if detail.get('result'):
                break
            time.sleep(.25)
        else:
            raise RuntimeError('probe_sessions_detail_timeout')
        rows = list(detail['result']['view']['prompt_blocks'][0]['rows'])
        sizes = [len(json.dumps(detail).encode('utf-8'))]
        while len(rows) < detail['total'] and time.monotonic() < deadline:
            chunk = request('/api/detail', dict(action='chunk', token=opened['token'],
                revision=detail['revision'], offset=len(rows)))
            assert chunk['revision'] == detail['revision'] and chunk['total'] == detail['total']
            assert chunk['offset'] == len(rows)
            next_rows = chunk['result']['view']['prompt_blocks'][0]['rows']
            assert 0 < len(next_rows) <= 25
            rows.extend(next_rows)
            sizes.append(len(json.dumps(chunk).encode('utf-8')))
        assert len(rows) == detail['total'] == len({row['id'] for row in rows})
        assert [row['at_ms'] for row in rows] == sorted(row['at_ms'] for row in rows)
        assert max(sizes) <= 200_000
        block = detail['result']['view']['prompt_blocks'][0]
        assert 'session_context' in block and 'watch_model' in rows[0]
        cost_evidence = reference_cost_evidence([*latest['view']['session_usage'], block, *rows])
        print(json.dumps(dict(sessions='ok', available=current['available'],
            indexed_before=coverage[0], indexed_after=coverage[-1],
            visible_indexed_before=visible_coverage[0], visible_indexed_after=visible_coverage[-1],
            visible_metric_states={state: sum(row.get('metric_state') == state for row in latest['view']['session_usage'])
                                   for state in ('ready', 'pending', 'retained', 'unavailable')},
            metric_sort='pending' if current['pending_sort'] else 'global',
            applied_sort=current['sort'], requested_sort=current['requested_sort'],
            progress_status=progress[-1]['status'], progress_reason=progress[-1]['reason'],
            progress_generations=len({item['generation'] for item in progress}),
            index_metrics=progress[-1]['metrics'],
            cold_running_observations=cold_running, multi_model_observations=multiple_model_rows,
            contributor_contract='validated bounded distinct identities; no identities exported by probe',
            context_contract='validated raw tokens, server formatting and qualified states; no context sizes exported',
            exact_owner_incident='not established by this read-only observation',
            first_page_seconds=round(first_seconds, 3), observation_seconds=round(time.monotonic() - started, 3),
            natural_arrival=arrival or 'unobserved; source-to-browser arrival latency not measured',
            detail_rows=len(rows), detail_chunks=len(sizes), detail_max_bytes=max(sizes),
            detail_seconds=round(time.monotonic() - detail_started, 3),
            reference_cost_evidence=cost_evidence,
            http_max_seconds=round(max(timings), 3), live_owner_preserved=host.live.driver is driver,
            model_calls_started_by_probe=0)))
    finally:
        request('/api/detail', dict(action='close', token=opened['token']))
