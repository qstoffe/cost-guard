"""Explicit immutable Watch export. No raw provider/source observations."""
from datetime import datetime

from .contracts import ObjectValue, record
from .projection import account, comparison, fields, prompt, token_mix
from .display import with_display
from .watch_accounts import watch_account
from .prompt_costs import cost_detail
from .reference_cost import issue_records
from src.analysis.timezones import local_date_range, resolve_timezone


def card_row(row, now_ms, invocation_verified=True):
    tool = row.tool
    invocation_verified = invocation_verified and row.prompt.in_progress and not row.prompt.execution_unverified
    projected = fields(row.prompt, """at_ms prompt_number label preview ccost incoming_context_ccost extra_ccost cost_estimated unresolved_cost
        incoming_context_ccost_known extra_ccost_known
        calls token_mix_percent incoming_context_tokens in_progress execution_unverified is_compaction aborted abort_reason completed_successfully event_id duration_ms completed_at_ms has_additional_model""")
    projected = ObjectValue(projected.fields + (("has_error", row.prompt.watch_error),
        ("comparison_cost", comparison(row.prompt.comparison_cost)),
        ("linked_agent_count", row.prompt.linked_agent_count), ("cost_detail", cost_detail(row.prompt))))
    return record(prompt=projected, model=row.prompt.watch_model or "N/A",
        effort=row.prompt.watch_effort or "N/A", marker=row.marker,
        watch_duration_ms=row.prompt.duration_ms,
        live_context=fields(row.prompt, "watch_delta_context_tokens watch_next_context_tokens watch_context_detail"),
        tool=None if tool is None else record(counts=tool.tool_counts, failed_count=tool.failed_count,
            cancelled_count=tool.cancelled_count, failed_or_cancelled_count=tool.failed_or_cancelled_count,
            outcomes=tuple(fields(item, "tool_name outcome count") for item in tool.tool_outcomes),
            running_tool=tool.running_tool, running_ms=tool.running_ms,
            running_invocation=(fields(tool.running_invocation, "identity revision text qualification")
                if invocation_verified and tool.running_invocation and row.prompt.in_progress and not row.prompt.execution_unverified else None),
            background_invocation=(fields(tool.background_invocation, "identity revision text qualification")
                if invocation_verified and tool.background_invocation and row.prompt.in_progress and not row.prompt.execution_unverified else None),
            running_invocations=tuple(fields(item, 'identity revision text qualification kind started_at_ms mode')
                for item in tool.running_invocations) if invocation_verified else (),
            background_invocations=tuple(fields(item, 'identity revision text qualification kind started_at_ms mode')
                for item in tool.background_invocations) if invocation_verified else (),
            running_invocation_count=tool.running_invocation_count,
            background_invocation_count=tool.background_invocation_count,
            background_kinds=tool.background_kinds, background_ms=tool.background_ms,
            skills=tuple(fields(skill, "skill_id failed_count") for skill in tool.skills)))


def card(value, now_ms):
    context = value.session_context
    cost = value.session_cost
    return record(session_id=value.session_id, title=value.title, focal_id=value.focal_id,
        rows=tuple(card_row(row, now_ms, value.state == "observed") for row in value.rows), state=value.state,
        observed_at_ms=value.observed_at_ms,
        context_handoff=None if value.context_handoff is None else record(
            previous_id=value.context_handoff[0], previous_tokens=value.context_handoff[1]),
        session_summary=record(context=None if context is None else record(
            watch_next_context_tokens=context.tokens,
            **{name: getattr(context, name) for name in ('context_state', 'context_scope', 'context_epoch',
                'context_provider', 'context_model', 'context_anchor')},
            warning=fields(context, "owner_id text severity multiplier cached_ccost fresh_ccost guidance_state guidance_sample_at_ms")),
            cost=None if cost is None else record(known_ccost=cost.total.known_ccost,
                observed_requests=cost.total.observed_requests, priced_requests=cost.total.priced_requests,
                ccost_unavailable=issue_records(cost.total.unavailable),
                complete=cost.total.complete and cost.source_complete),
            state=value.session_cost_state, cache_available=None if cost is None else cost.cache_available))


def watch_accounts(value, now_ms):
    if value is None:
        return None
    # Reset display follows the existing Live publication clock, not the last
    # account-history projection. Native observation timestamps remain untouched.
    return record(now_ms=now_ms, accounts=tuple(watch_account(item) for item in value.accounts))


def project_live(value, timezone_id="UTC", ccost_display_unit="credits"):
    rows = []
    for row in value.rows:
        tool = row.tool
        activity = None if tool is None else record(
            counts=tool.tool_counts, failed_count=tool.failed_count, running_tool=tool.running_tool,
            cancelled_count=tool.cancelled_count, failed_or_cancelled_count=tool.failed_or_cancelled_count,
            outcomes=tuple(fields(item, "tool_name outcome count") for item in tool.tool_outcomes),
            running_ms=tool.running_ms, background_kinds=tool.background_kinds,
            background_ms=tool.background_ms, todo_completed=tool.todo_completed,
            todo_total=tool.todo_total, active_todo=tool.active_todo,
            skills=tuple(fields(skill, "skill_id failed_count") for skill in tool.skills))
        duration = (max(row.prompt.duration_ms or 0, value.now_ms - row.prompt.at_ms)
                    if row.prompt.in_progress else row.prompt.duration_ms)
        sparse = row.prompt.is_compaction and row.prompt.calls == 0 and row.prompt.ccost == 0
        rows.append(record(session_id=row.session_id, session_title=row.session_title,
            watch_model_effort=row.prompt.watch_model_effort or row.prompt.model_effort or "N/A",
            watch_duration_ms=duration, watch_sparse_compaction=sparse,
            prompt=prompt(row.prompt), marker=row.marker, tool=activity, earlier=row.earlier,
            session_active=row.session_active, session_latest_ms=row.session_latest_ms,
            is_latest_session_event=row.is_latest_session_event,
            next_context_warning=row.next_context_warning,
            next_context_warning_severity=row.next_context_warning_severity,
            live_context=fields(row.prompt, """watch_next_context_tokens watch_next_context_warning
                watch_next_context_cached_ccost watch_next_context_fresh_ccost watch_delta_context_tokens watch_context_detail""")))
    return with_display(record(source_label=value.source_label, source_warning_count=len(value.source_warnings),
        ccost_display_unit=ccost_display_unit,
        active_cards=tuple(card(item, value.now_ms) for item in value.active_cards),
        history_cards=tuple(card(item, value.now_ms) for item in value.history_cards),
        cards_state=value.cards_state, history_state=value.history_state,
        history_scope=value.history_scope, history_epoch=value.history_epoch,
        history_catalog_revision=value.history_catalog_revision,
        history_verified_at_ms=value.history_verified_at_ms,
        history_checked=value.history_checked, history_total=value.history_total,
        history_cause=value.history_cause,
        running=fields(value.running, "count ccost duration_ms complete unresolved_cost cost_estimated state"),
        rows=tuple(rows), active_count=value.active_count, status=value.status,
        now_ms=value.now_ms, started_at_ms=value.watch_started_at_ms,
        run_origin="Web live engine start (not tab open)",
        run_total=token_mix(value.run_total), token_mix=token_mix(value.token_mix),
        run_ccost=None if value.run_total.costs is None else sum(value.run_total.costs),
        today_total=comparison(value.today_total), today_label=value.today_label,
        daily_usage=None if value.daily_usage is None else record(
            day_start_ms=value.daily_usage.day_start_ms, observed_at_ms=value.daily_usage.observed_at_ms,
            day_end_ms=local_date_range(datetime.fromtimestamp(value.daily_usage.day_start_ms / 1000,
                tz=resolve_timezone(timezone_id)).date().isoformat(), timezone_id).end_ms,
            total=comparison(value.daily_usage.total), mix=token_mix(value.daily_usage.mix),
            prompt_count=value.daily_usage.prompt_count, prompt_count_complete=value.daily_usage.prompt_count_complete),
        daily_state=value.daily_state,
        today_pending=value.today_pending, accounts=watch_accounts(value.quota, value.now_ms), quota_stale=value.quota_stale,
        quota_recovering_count=len(value.quota_recovering_accounts),
        recent_model_notice=value.recent_model_notice,
        recent_promotion_notices=value.recent_promotion_notices,
        session_subtotals=tuple(record(session_id=key, ccost=item.ccost,
            unresolved_cost=item.unresolved_cost) for key, item in value.session_subtotals.items())), timezone_id,
        ccost_display_unit=ccost_display_unit)
