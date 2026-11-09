"""Synthetic official-shaped public aggregate records, never downloaded trials."""
from src.benchmarks import BOARD_ID, DATASET_ID


def row(index=1, *, model='Opus 5.5', client='Claude Code', effort='max', cost=330, score=61, trials=330):
    return dict(id=f'00000000-0000-0000-0000-{index:012d}', leaderboard_id=BOARD_ID, status='display',
        metadata=dict(model_display=dict(label=model, url='https://www.anthropic.com/claude-opus-5-5'),
            model_org=dict(label='Anthropic', url='https://www.anthropic.com'),
            agent_display=dict(label=client, url='https://claude.com/product/claude-code'),
            reasoning_effort=effort, date='2026-11-09'),
        metrics=dict(total_cost_usd=cost, n_trials=trials, accuracy=score))


def page(rows=None, *, index=1, total=None, size=100):
    rows = [row()] if rows is None else rows
    total = len(rows) if total is None else total
    return dict(leaderboard=dict(id=BOARD_ID, package='terminal-bench/terminal-bench', name='4-0-0',
        visibility='public', dataset_version_ids=[DATASET_ID], updated_at='2026-11-09T00:00:00Z',
        metrics_schema=dict(properties=dict(accuracy=dict(type='number', minimum=0, maximum=100)))),
        rows=rows, pagination=dict(total=total, page=index, page_size=size, total_pages=(total + size - 1) // size))


def payload():
    rows = [row(1, effort='medium', cost=330), row(2, effort='high', cost=660),
        row(3, effort='max', cost=990), row(4, client='Other client', cost=1320),
        row(5, model='Unpriced benchmark model', cost=0)]
    return dict(schema=1, fetched_at_ms=1794182400000, pages=[page(rows)])


def references(**changes):
    return [dict(publisher='Anthropic', model='Claude Opus 5.5', release_date='2026-11-09',
        selectable=True, superseded=False, superseded_selectable=False) | changes]


def finite_benchmark(sender, request):
    import json
    sender.send(('result', json.dumps(dict(error=None, source=dict(status='acquired'), benchmark=payload())).encode()))
    sender.close()
