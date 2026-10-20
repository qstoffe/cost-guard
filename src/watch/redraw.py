"""Watch redraw decisions: which projection changes need a full dashboard frame.

The coordinator compares a new projection with the frame actually drawn, never
with internal state that a status-only wake may already have advanced.
"""
from __future__ import annotations

from .models import WatchProjection


def visible_signature(projection: WatchProjection) -> tuple[object, ...]:
    """Dashboard content excluding status; expired markers, quotas and model highlights repaint live."""
    warnings = tuple((projection.session_warnings or {}).items())
    return (projection.rows, projection.quota, projection.quota_stale, projection.quota_recovering_accounts,
            projection.source_warnings, warnings, projection.recent_model_notice,
            projection.recent_promotion_notices, projection.token_mix, projection.run_total,
            projection.today_total, projection.today_label, projection.today_pending,
            projection.watch_started_at_ms, projection.title, projection.source_label,
            projection.recent_model_notice_highlight_spans,
            tuple(projection.session_subtotals.items()))


def transient_signature(projection: WatchProjection) -> tuple[object, ...]:
    """Wake-time dashboard changes: marker/retention transitions, notices, accounts and the Today label."""
    return (tuple((row.session_id, row.prompt.event_id, row.marker, row.earlier,
                   row.session_active, row.session_latest_ms) for row in projection.rows),
            projection.recent_model_notice, projection.recent_promotion_notices,
            projection.quota, projection.quota_stale, projection.quota_recovering_accounts,
            projection.today_total, projection.today_label, projection.today_pending)


def needs_full_render(drawn: WatchProjection, current: WatchProjection, *, source_changed: bool) -> bool:
    """Source hints alone are not visible changes; running durations still tick."""
    if current.active_count > 0 and current.now_ms != drawn.now_ms:
        return True
    return visible_signature(drawn) != visible_signature(current)
