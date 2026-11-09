"""Prepared benchmark display, independent of canonical reference valuation."""
from decimal import Decimal

from src.reports.semantics import model_is_recent


def reference_key(publisher, model):
    # Harbor's Anthropic model labels omit the Claude brand (official model URLs
    # retain it). Only this exact brand-prefix equivalence is admitted; punctuation,
    # version/variant suffixes and all other labels must match, without fuzzy joins.
    if publisher == 'Anthropic' and model.startswith('Claude '):
        model = model[len('Claude '):]
    return publisher, model


def benchmark_view(snapshot, reference_rows=(), *, now_ms):
    if snapshot is None:
        return dict(fetched_at_ms=None, rows=[])
    references = {}
    for row in reference_rows:
        key = reference_key(row['publisher'], row['model'])
        references.setdefault(key, []).append(row.get('release_date'))
    positive = [row.usd_per_task for row in snapshot.rows if row.usd_per_task is not None and row.usd_per_task > 0]
    cheapest = min(positive) if positive else None
    result = []
    publishers = {'Anthropic': 'https://www.anthropic.com', 'OpenAI': 'https://openai.com', 'Google': 'https://google.com'}
    for row in snapshot.rows:
        cost = row.usd_per_task
        relative = cost / cheapest if cost is not None and cost > 0 and cheapest else None
        key = reference_key(row.publisher, row.model)
        dates = references.get(key, []) if publishers.get(row.publisher) == row.publisher_url.rstrip('/') else []
        recent = len(dates) == 1 and bool(dates[0]) and model_is_recent(dates[0], now_ms=now_ms)
        usd = 'N/A' if cost is None else '$0.00' if cost == 0 else '<$0.0001' if cost < Decimal('0.0001') else f'${cost:.4f}'.rstrip('0').rstrip('.')
        result.append(dict(id=row.id, model=row.model, client=row.client, effort=row.effort or None,
            relative_cost=str(relative) if relative is not None else None,
            usd_per_task=str(cost) if cost is not None else None, solved=str(row.solved), recent=bool(recent),
            relative_text=f'{relative:.1f}x' if relative is not None else 'N/A', usd_text=usd,
            solved_text=f'{row.solved:.1f}%',
            configuration_help=f'Client version: {row.client_version or "not published"}.\n\nSource date: {row.date}.\n\nOfficial row: {row.id}.'))
    return dict(fetched_at_ms=snapshot.fetched_at_ms, rows=result)
