"""One real authenticated forced-pricing action; sanitized evidence, no inference."""
import json
import time


def observe_price_refresh(get, cookie, driver):
    pinned = driver.coordinator.report_service.catalog
    started = time.monotonic()
    requested_at_ms = int(time.time() * 1000)
    key = get('/api/models/refresh', value={}, cookie=cookie)[0]['id']
    deadline = time.monotonic() + 125
    while time.monotonic() < deadline:
        job = get('/api/jobs/' + key, cookie=cookie)[0]
        if job['status'] not in {'queued', 'running'}:
            break
        time.sleep(.25)
    if job['status'] != 'complete' or not job['result'] or job['result']['error']:
        print(json.dumps({'price_refresh': job['status'], 'error': job['error'],
                          'result_error': (job['result'] or {}).get('error')}))
        raise RuntimeError('probe_price_refresh_failed')
    view = job['result']['view']
    assert view['pricing_retrieved_at_ms'] >= requested_at_ms
    assert view['model_catalog']['rows']
    assert driver.coordinator.report_service.catalog is pinned
    print(json.dumps({'price_refresh': 'complete', 'new_upstream_observation': True,
        'catalog_rows': len(view['model_catalog']['rows']), 'watch_catalog_pinned': True,
        'seconds': round(time.monotonic() - started, 3), 'model_calls_started_by_probe': 0}))
