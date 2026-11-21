"""Scope and present one materialized Token Mix total without acquisition."""
from dataclasses import replace

from src.analysis.ai_stats import windows
from src.analysis.token_mix import MIX_FIELDS, summarize_token_mix

from .contracts import record
from .display import with_display
from .projection import token_mix


def cached_mix_view(history, source, timezone_id, period, now_ms):
    start = dict(windows(timezone_id, now_ms))[period]
    saved = history.mix_total(source, timezone_id, period, start, now_ms)
    if saved is None:
        return dict(scope=period, start_ms=start, end_ms=None, coverage="unknown", current_archive_revision=False,
                    token_mix=None, observed_category_totals=None, gaps=None)
    row, current = saved
    known = tuple(name for name, volume in zip(MIX_FIELDS, row.totals) if volume is not None)
    mix = summarize_token_mix(tuple(volume if volume is not None else 0 for volume in row.totals),
                              known, row.calls, row.known_volume, sample_size=row.prompts)
    mix = replace(mix, costs=row.costs, priced_requests=row.priced)
    shaped = token_mix(mix) if row.calls else None
    result = record(scope=period, start_ms=start, end_ms=row.end_ms, coverage="partial" if row.calls else "unknown",
                     current_archive_revision=current, token_mix=shaped,
                     observed_category_totals=tuple(map(str, row.observed)) if row.calls else None,
                     gaps=record(unqualified_forks=row.unqualified_forks, undated_calls=row.undated_calls,
                                 stale_prices=None))
    return with_display(result, timezone_id, row.end_ms).to_json()
