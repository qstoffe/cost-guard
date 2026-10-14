"""Watch redraw decisions: which projection changes need a full dashboard frame.

The coordinator compares a new projection with the frame actually drawn, never
with internal state that a status-only wake may already have advanced.
"""
from __future__ import annotations

from .models import WatchProjection


def visible_signature(projection: WatchProjection) -> tuple[object, ...]:
    """Dashboard content excluding status; expired markers, quotas and model highlights repaint live."""
    rows = tuple(
        (
            row.session_id, row.prompt.event_id, row.marker, row.prompt.in_progress,
            row.prompt.aborted, row.prompt.duration_ms,
            row.prompt.abort_reason, row.prompt.ended_after_tool_calls, row.prompt.watch_error,
            row.prompt.watch_delta_context_tokens, row.prompt.watch_next_context_tokens,
            row.is_latest_session_event, row.next_context_warning, row.next_context_warning_severity,
            row.prompt.watch_next_context_cached_ccost, row.prompt.watch_next_context_fresh_ccost,
            row.tool, row.session_latest_ms, row.earlier,
        )
        for row in projection.rows
    )
    warnings = tuple((projection.session_warnings or {}).items())
    return (rows, projection.quota, projection.quota_stale, projection.quota_recovering_accounts,
            projection.source_warnings, warnings, projection.recent_model_notice,
            projection.recent_promotion_notices, projection.token_mix, projection.run_total,
            projection.today_total, projection.today_label,
            projection.watch_started_at_ms,
            tuple(projection.session_subtotals.items()))


def transient_signature(projection: WatchProjection) -> tuple[object, ...]:
    """Wake-time dashboard changes: marker/retention transitions, notices, accounts and the Today label."""
    return (tuple((row.session_id, row.prompt.event_id, row.marker, row.earlier) for row in projection.rows),
            projection.recent_model_notice, projection.recent_promotion_notices,
            projection.quota, projection.quota_stale, projection.quota_recovering_accounts,
            projection.today_total, projection.today_label)


def needs_full_render(drawn: WatchProjection, current: WatchProjection, *, source_changed: bool) -> bool:
    """Source changes and running prompts always redraw; otherwise only visible differences do."""
    if source_changed or current.active_count > 0:
        return True
    return visible_signature(drawn) != visible_signature(current)
