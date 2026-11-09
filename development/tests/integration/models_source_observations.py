"""Read-only real Models/Harbor HTTP assertions; export only public/count evidence."""
from decimal import Decimal
import re
import time
from uuid import uuid4

from src.analysis.timezones import format_local_timestamp
from src.application.benchmark import reference_key


def observe_benchmark(get, cookie, host):
    get('/api/interest', value=dict(tab=uuid4().hex, section='models', visible=True,
        request=dict(kind='normal')), cookie=cookie)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        value, _ = get('/api/data', value=dict(request=dict(kind='normal'), retry=False), cookie=cookie)
        if value['result']:
            break
        if value['terminal']:
            raise RuntimeError('probe_models_unavailable')
        time.sleep(.2)
    else:
        raise RuntimeError('probe_models_timeout')
    view = value['result']['view']
    references = view['model_catalog']['rows']
    assert references and all(row['price_help'].startswith('GitHub Copilot · USD / 1M tokens') for row in references)
    assert view['model_comparison_sample_size'] <= 100
    mix = view['model_comparison_mix']
    if mix is not None:
        assert abs(sum(map(Decimal, mix)) - 1) < Decimal('1e-25')
        assert view['model_comparison_sample_size'] > 0
        percentages = re.findall(r'([0-9.]+)%', view['display']['model_comparison_mix_help'])
        assert sum(map(Decimal, percentages)) == 100
    else:
        assert 'unavailable' in view['display']['model_comparison_mix_help']
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        benchmark, _ = get('/api/models/benchmark', cookie=cookie)
        if benchmark['fetched_at_ms'] and not benchmark['refreshing']:
            break
        time.sleep(.1)
    else:
        raise RuntimeError('probe_benchmark_unavailable')
    assert benchmark['rows'], 'real source/catalog intersection is empty'
    snapshot = host.benchmark.snapshot
    denominator = min(row.usd_per_task for row in snapshot.rows if row.usd_per_task is not None and row.usd_per_task > 0)
    native = {row.id: row for row in snapshot.rows}
    catalog = {(row['publisher'], row['model']): row for row in references}
    for row in benchmark['rows']:
        source = native[row['id']]
        assert reference_key(row['publisher'], row['model']) == reference_key(source.publisher, source.model)
        assert row['selectable'] == catalog[row['publisher'], row['model']]['selectable']
        expected = source.usd_per_task / denominator if source.usd_per_task is not None and source.usd_per_task > 0 else None
        assert (Decimal(row['relative_cost']) if row['relative_cost'] else None) == expected
    assert benchmark['efforts'] == sorted({row.effort or '' for row in snapshot.rows})
    assert benchmark['fetched_text'] == format_local_timestamp(benchmark['fetched_at_ms'], view['timezone_id'])
    before = benchmark['fetched_at_ms']
    get('/api/models/benchmark/refresh', value={}, cookie=cookie)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        refreshed, _ = get('/api/models/benchmark', cookie=cookie)
        if not refreshed['refreshing'] and refreshed['fetched_at_ms'] > before:
            break
        time.sleep(.1)
    else:
        raise RuntimeError('probe_forced_benchmark_refresh_unavailable')
    # Reading this same retained result must not have repriced GitHub data.
    after, _ = get('/api/data', value=dict(request=dict(kind='normal'), retry=False), cookie=cookie)
    assert after['result']['view'] == view
    return dict(benchmark='complete', source_rows=len(snapshot.rows), matched_rows=len(benchmark['rows']),
        reference_rows=len(references), effort_options=benchmark['efforts'],
        comparison_sample=view['model_comparison_sample_size'], comparison_percentages_verified=mix is not None,
        fetched_at_ms=before, forced_fetched_at_ms=refreshed['fetched_at_ms'],
        full_source_denominator_verified=True, independent_pricing_retained=True, model_calls_started_by_probe=0)
