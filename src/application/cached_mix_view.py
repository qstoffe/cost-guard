"""Scope and present one materialized Token Mix total without acquisition."""
from dataclasses import replace

from src.analysis.ai_stats import windows
from src.analysis.token_mix import MIX_FIELDS, summarize_token_mix

from .contracts import record
from .display import with_display
from .projection import token_mix


def _mix(row):
    known = tuple(name for name, volume in zip(MIX_FIELDS, row.totals) if volume is not None)
    mix = summarize_token_mix(tuple(volume if volume is not None else 0 for volume in row.totals),
                              known, row.calls, row.known_volume, sample_size=row.prompts)
    mix = replace(mix, costs=row.costs, priced_requests=row.priced)
    return token_mix(mix) if row.calls else None


def cached_mix_view(history, source, timezone_id, period, now_ms):
    start = dict(windows(timezone_id, now_ms))[period]
    saved = history.mix_total(source, timezone_id, period, start, now_ms, include_groups=True)
    if saved is None:
        return dict(scope=period, start_ms=start, end_ms=None, coverage="unknown", current_archive_revision=False,
                    token_mix=None, observed_category_totals=None, gaps=None, groups=None)
    row, current, run, groups = saved
    result = record(scope=period, start_ms=start, end_ms=row.end_ms, coverage="partial" if row.calls else "unknown",
                     current_archive_revision=current, token_mix=_mix(row),
                     observed_category_totals=tuple(map(str, row.observed)) if row.calls else None,
                     gaps=record(unqualified_forks=row.unqualified_forks, undated_calls=row.undated_calls,
                                 stale_prices=None),
                     groups=record(run=run, **{kind: _page(*page) for kind, page in groups.items()}) if run else None)
    return with_display(result, timezone_id, row.end_ms).to_json()


def cached_mix_groups(history, source, timezone_id, period, now_ms, kind, *, after="", known=None):
    start = dict(windows(timezone_id, now_ms))[period]
    saved = history.mix_group_page(source, timezone_id, period, start, now_ms, kind, after, known=known)
    if saved is None:
        return dict(scope=period, kind=kind, run=None, end_ms=None, next=None, rows=[])
    run, as_of, rows, cursor = saved
    return with_display(record(scope=period, kind=kind, run=run, end_ms=as_of, next=cursor,
                               reset=known is not None and known != run, rows=_group_rows(rows)), timezone_id, as_of).to_json()


def _page(rows, cursor):
    return record(rows=_group_rows(rows), next=cursor)


def _group_rows(rows):
    return tuple(record(identity=row.identity, model=row.label, publisher=row.publisher,
                        prompts=row.prompts, calls=row.calls, mix=_mix(row)) for row in rows)
