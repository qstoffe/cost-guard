"""Read-only real-source Sessions observations; output contains no titles or IDs."""
import json
import time


def observe_sessions(get, cookie, host, driver):
    started = time.monotonic()
    timings, coverage = [], []

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
    for _ in range(30):
        current = request('/api/sessions', dict(token=token, sort='ccost'))
        coverage.append(current['indexed'])
        assert len(current['view']['session_usage']) <= 50
        assert current['pending_sort'] == (current['indexed'] != current['available'])
        if current['pending_sort']:
            assert current['sort'] == 'activity'
        latest = request('/api/sessions', dict(token=token))
        if original and any(row['session_id'] not in original for row in latest['view']['session_usage']):
            arrival = 'changed_first_page_observed; no session created by probe'
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
        print(json.dumps(dict(sessions='ok', available=current['available'],
            indexed_before=coverage[0], indexed_after=coverage[-1],
            metric_sort='pending' if current['pending_sort'] else 'global',
            first_page_seconds=round(first_seconds, 3), observation_seconds=round(time.monotonic() - started, 3),
            natural_arrival=arrival or 'unobserved; source-to-browser arrival latency not measured',
            detail_rows=len(rows), detail_chunks=len(sizes), detail_max_bytes=max(sizes),
            detail_seconds=round(time.monotonic() - detail_started, 3),
            http_max_seconds=round(max(timings), 3), live_owner_preserved=host.live.driver is driver,
            model_calls_started_by_probe=0)))
    finally:
        request('/api/detail', dict(action='close', token=opened['token']))
