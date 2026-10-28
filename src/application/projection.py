"""Explicit report export allowlists; diagnostic/provider payloads stop here."""
from __future__ import annotations

from hashlib import sha256
from decimal import Decimal
import json

from src.analysis.model_supersession import superseded_rows

from .contracts import ObjectValue, record
from .display import with_display


def identity(parts) -> str:
    """Opaque stable locator; never publish account/source filesystem locators."""
    return sha256(json.dumps(parts, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()


def fields(value, names: str) -> ObjectValue:
    # Each call site names the allowed primitive fields of one known projection.
    return record(**{name: getattr(value, name) for name in names.split()})


def comparison(value):
    if value is None:
        return None
    return record(
        known_ccost=value.known_ccost, ccost=value.ccost, complete=value.complete,
        observed_requests=value.observed_requests, priced_requests=value.priced_requests,
        by_model=record(**dict(value.by_model)), by_day_utc=record(**dict(value.by_day_utc)),
    )


def token_mix(value):
    return record(
        totals=value.totals, percentages=value.percentages, shares=value.shares,
        sample_size=value.sample_size, request_count=value.request_count,
        costs=value.costs, priced_requests=value.priced_requests,
        cost_complete=value.cost_complete, total_tokens=value.total_tokens,
        total_cost=None if value.costs is None else sum(value.costs, Decimal(0)),
    )


def prompt(value):
    base = fields(value, """at_ms prompt_number label preview model_effort ccost cost_estimated
        unresolved_cost calls incoming_context_tokens incoming_context_ccost extra_ccost token_mix_percent
        in_progress aborted is_compaction delta_context_tokens next_context_tokens next_context_cached_ccost
        next_context_fresh_ccost next_context_warning event_id duration_ms main_ccost subagent_ccost
        breakdown_known has_cost_breakdown main_estimated subagent_estimated has_additional_model
        abort_at_ms running_cost_warning ictx_price_threshold billed_cost completed_successfully
        next_context_warning_severity next_context_cost_multiplier background_kinds background_started_ms
        background_only abort_reason ended_after_tool_calls completed_at_ms""")
    return ObjectValue(base.fields + (("comparison_cost", comparison(value.comparison_cost)),
                                      ("has_error", value.watch_error)))


def block(value):
    base = fields(value, """session_id title total_ccost total_calls total_ictx_cost_text total_extra_cost_text
        total_mix_text current_context_tokens next_context_tokens next_context_cached_ccost
        next_context_fresh_ccost next_context_warning event_id duration_ms total_main_ccost total_subagent_ccost
        total_breakdown_known total_has_cost_breakdown total_main_estimated total_subagent_estimated
        comparison_cost_complete billed_cost next_context_warning_severity next_context_cost_multiplier""")
    return ObjectValue(base.fields + (
        ("rows", tuple(prompt(row) for row in value.rows)),
        ("current_context_sources", record(**dict(value.current_context_sources))),
        ("has_error", value.watch_error),
    ))


def account(value):
    native = value.account
    # No AccountRef.source_account/source_instance, observations, raw reason/warnings.
    observation = record(
        id=identity(native.key), provider_id=native.ref.provider_id,
        label=value.label, provider_label=native.provider_label, plan=native.plan,
        observed_at_ms=native.fetched_at_ms, status=native.status, availability=native.availability,
        has_warning=bool(native.warnings), has_error=native.availability in {"error", "unavailable"},
        error_code=account_error(native),
        usage_attribution_complete=native.usage_attribution_complete, capacity_kind=native.capacity_kind,
        quotas=tuple(fields(quota, """label period used limit remaining remaining_fraction unit reset_at_ms
            duration_seconds status unlimited remaining_money limit_money origin model_id scope window_active""")
            for quota in native.quotas),
        billing=tuple(fields(item, "label amount currency period kind status") for item in native.billing),
    )
    return record(
        observation=observation, ccost_scopes=tuple(record(name=name, cost=comparison(cost))
            for name, cost in value.ccost_scopes),
        billed_today=value.billed_today, billed_month=value.billed_month,
        pace=tuple(fields(item, "label unit per_day days workdays per_workday") for item in value.pace),
        ccost_notes=value.ccost_notes, ccost_account_unknown=value.ccost_account_unknown,
        unaccounted_usage=value.unaccounted_usage,
    )


def account_error(native):
    """Only classified facts, never arbitrary exception/reason/observation strings."""
    reason = native.observations.get("parser_reason")
    if isinstance(reason, str) and reason in {"auth_failure", "unsupported_auth_method", "transport_failure", "format_changed",
                  "software_failure", "discovery_failure", "rate_limited"}:
        return reason
    return "account_unavailable" if native.availability in {"error", "unavailable"} else None


def accounts(value):
    if value is None:
        return None
    base = fields(value, """billed_today billed_month today_prompt_count today_session_count today_request_count
        included_subscription_requests now_ms""")
    return ObjectValue(base.fields + (
        ("comparison_today", comparison(value.comparison_today)),
        ("comparison_month", comparison(value.comparison_month)),
        ("accounts", tuple(account(item) for item in value.accounts)),
    ))


def project(report, timezone_id="UTC"):
    models = []
    faded = superseded_rows([(item.publisher, item.model) for item in report.model_comparison])
    for index, item in enumerate(report.model_comparison):
        base = fields(item, "publisher model relative_cost price_summary release_date promotional recent promotion_marker")
        models.append(ObjectValue(base.fields + (("evidence", fields(item.evidence,
            "model_prompts publisher_prompts generic_prior_weight global_prompts history_exhausted observed_prompts")),
            ("superseded", index in faded), ("relative_levels", tuple(
            fields(level, "relative_cost threshold_tokens threshold_operator") for level in item.relative_levels)),)))
    return with_display(record(
        kind=report.kind, title=report.title, source_label=report.source_label,
        # Source messages can contain transport/private details. Preserve status, not raw prose.
        source_warning_count=len(report.source_warnings),
        model_availability_empty="⚠ No available OpenCode models match the pricing catalog." in report.source_warnings,
        model_availability_unverified=any(warning in {
            "⚠ Could not determine available OpenCode models; showing full pricing catalog.",
            "ERROR: Model availability lookup failed internally; showing full pricing catalog.",
            "⚠ Could not verify currently selectable OpenCode models; showing all historically used models.",
            "ERROR: Model availability lookup failed internally; showing all historically used models.",
        } for warning in report.source_warnings),
        model_comparison=tuple(models), model_comparison_sample_size=report.model_comparison_sample_size,
        pricing_retrieved_at_ms=report.pricing_retrieved_at_ms,
        model_comparison_promotion_notes=report.model_comparison_promotion_notes,
        session_usage=tuple(fields(item, "session_id title model multiple_models ccost prompt_count complete duration_ms archived running")
            for item in report.session_usage),
        session_page=fields(report.session_page, "offset size total catalog_revision") if report.session_page else None,
        prompt_blocks=tuple(block(item) for item in report.prompt_blocks),
        accounts_quotas=accounts(report.accounts_quotas), notes=report.notes,
        recent_model_notice=report.recent_model_notice,
        recent_model_notice_highlight_spans=report.recent_model_notice_highlight_spans,
        token_mix=token_mix(report.token_mix),
        model_token_mix=tuple(record(model=item.model, prompts=item.prompts, calls=item.calls, mix=token_mix(item.mix))
            for item in report.model_token_mix),
        publisher_token_mix=tuple(record(publisher=item.publisher, prompts=item.prompts, calls=item.calls, mix=token_mix(item.mix))
            for item in report.publisher_token_mix),
    ), timezone_id)
