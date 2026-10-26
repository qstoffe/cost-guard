"""Explicit immutable Watch export. No raw provider/source observations."""
from .contracts import ObjectValue, record
from .projection import account, comparison, fields, prompt, token_mix
from .display import with_display


def watch_accounts(value):
    if value is None:
        return None
    allowed = {"observation", "ccost_scopes", "pace", "ccost_notes", "ccost_account_unknown"}
    return record(now_ms=value.now_ms, accounts=tuple(
        ObjectValue(tuple((name, field) for name, field in account(item).fields if name in allowed))
        for item in value.accounts))


def project_live(value, timezone_id="UTC"):
    rows = []
    for row in value.rows:
        tool = row.tool
        activity = None if tool is None else record(
            counts=tool.tool_counts, failed_count=tool.failed_count, running_tool=tool.running_tool,
            running_ms=tool.running_ms, background_kinds=tool.background_kinds,
            background_ms=tool.background_ms, todo_completed=tool.todo_completed,
            todo_total=tool.todo_total, active_todo=tool.active_todo,
            skills=tuple(fields(skill, "skill_id failed_count") for skill in tool.skills))
        rows.append(record(session_id=row.session_id, session_title=row.session_title,
            prompt=prompt(row.prompt), marker=row.marker, tool=activity, earlier=row.earlier,
            session_active=row.session_active, session_latest_ms=row.session_latest_ms,
            is_latest_session_event=row.is_latest_session_event,
            next_context_warning=row.next_context_warning,
            next_context_warning_severity=row.next_context_warning_severity,
            live_context=fields(row.prompt, """watch_next_context_tokens watch_next_context_warning
                watch_next_context_cached_ccost watch_next_context_fresh_ccost watch_delta_context_tokens""")))
    return with_display(record(source_label=value.source_label, source_warning_count=len(value.source_warnings),
        rows=tuple(rows), active_count=value.active_count, status=value.status,
        now_ms=value.now_ms, started_at_ms=value.watch_started_at_ms,
        run_origin="Web live engine start (not tab open)",
        run_total=token_mix(value.run_total), token_mix=token_mix(value.token_mix),
        run_ccost=None if value.run_total.costs is None else sum(value.run_total.costs),
        today_total=comparison(value.today_total), today_label=value.today_label,
        today_pending=value.today_pending, accounts=watch_accounts(value.quota), quota_stale=value.quota_stale,
        quota_recovering_count=len(value.quota_recovering_accounts),
        recent_model_notice=value.recent_model_notice,
        recent_promotion_notices=value.recent_promotion_notices,
        session_subtotals=tuple(record(session_id=key, ccost=item.ccost,
            unresolved_cost=item.unresolved_cost) for key, item in value.session_subtotals.items())), timezone_id)
