"""Add allowlisted display tokens to immutable DTOs, never replace raw values.

Only already-exported fields are inspected; no source/provider access, valuation,
ranking or arbitrary object introspection. CLI and Web consume shared primitives.
"""
from decimal import Decimal, ROUND_HALF_UP

from src.analysis.timezones import format_local_timestamp
from src.display import (compact_threshold, compact_tokens, context_delta, context_tokens,
                         duration_text, format_reset, money, native_amount, price_summary, relative_cost, unaccounted_usage, quota_usage, token_volume)
from src.numbers import balanced_share_percents, ccost_amount, ccost_display, ccost_range, remaining_capacity

from .contracts import ObjectValue, record


def decimal(value):
    return None if value is None else Decimal(value)


def amount_tokens(values):
    tokens = {}
    for key in ("ccost", "total_ccost", "known_ccost", "run_ccost", "main_ccost", "subagent_ccost",
                "total_main_ccost", "total_subagent_ccost", "incoming_context_ccost", "extra_ccost",
                "next_context_cached_ccost", "next_context_fresh_ccost",
                "watch_next_context_cached_ccost", "watch_next_context_fresh_ccost"):
        if key not in values:
            continue
        unresolved = False
        if key == "ccost":
            unresolved = values.get("unresolved_cost", not values.get("complete", True))
        elif key == "total_ccost":
            unresolved = not values.get("comparison_cost_complete", True)
        elif key == "known_ccost":
            unresolved = not values.get("complete", True)
        elif key in ("main_ccost", "subagent_ccost", "total_main_ccost", "total_subagent_ccost"):
            flag = {"main_ccost": "main_estimated", "subagent_ccost": "subagent_estimated",
                    "total_main_ccost": "total_main_estimated", "total_subagent_ccost": "total_subagent_estimated"}[key]
            unresolved = values.get(flag, False)
        tokens[key] = ccost_amount(decimal(values[key]), unresolved=unresolved)
    for key in ("billed_cost", "billed_today", "billed_month", "remaining_money", "limit_money"):
        if key in values:
            tokens[key] = money(decimal(values[key]))
    for key in ("used", "limit", "remaining", "amount"):
        if key in values:
            kind = "consumed" if key == "used" else "remaining" if key == "remaining" else "exact"
            if key == "amount":
                kind = {"spend": "consumed", "balance": "remaining"}.get(values.get("kind"), "exact")
            tokens[key] = ("N/A" if values[key] is None else
                           native_amount(decimal(values[key]), values.get("unit", values.get("currency")), kind=kind))
    for key in ("per_day", "per_workday"):
        if key in values:
            tokens[key] = "N/A" if values[key] is None else remaining_capacity(decimal(values[key]))
    if "unaccounted_usage" in values:
        tokens["unaccounted_usage"] = unaccounted_usage(decimal(values["unaccounted_usage"]))
    if "remaining_fraction" in values:
        fraction = decimal(values["remaining_fraction"])
        tokens["remaining_fraction"] = "N/A" if fraction is None else f"{fraction * 100:.0f}%"
    if "known_ccost" in values:
        tokens["account_ccost"] = ("—" if values.get("observed_requests") and not values.get("priced_requests")
                                   else ccost_amount(decimal(values["known_ccost"])))
    if "run_ccost" in values:
        mix = dict(values["run_total"].fields)
        tokens["run_ccost"] = ("N/A" if values["run_ccost"] is None or (mix["request_count"] and not mix["priced_requests"])
            else ("" if mix["cost_complete"] else "?") + ccost_amount(decimal(values["run_ccost"])))
    return tokens


def quota_tokens(values):
    """Same Used presentation as CLI; canonical remaining fields stay untouched."""
    if "remaining_fraction" not in values:
        return {}
    fraction, used, used_money = quota_usage(**{key: decimal(values.get(key)) for key in
        ("used", "limit", "remaining", "remaining_fraction", "remaining_money", "limit_money")},
        unlimited=values.get("unlimited", False))
    unit = values.get("unit") or "units"
    native = "N/A" if used is None else native_amount(used, unit, kind="consumed")
    if not values.get("unlimited") and values.get("limit") is not None and decimal(values["limit"]) > 0:
        native += "/" + native_amount(decimal(values["limit"]), unit)
    return {"used_fraction": "N/A" if fraction is None else f"{fraction * 100:.0f}%",
            "quota_used": native + " " + unit, "used_money": money(used_money)}


def metric_tokens(values, timezone_id, now_ms=None):
    tokens = {}
    for key in ("duration_ms", "watch_duration_ms", "running_ms", "background_ms"):
        if key in values:
            tokens[key] = duration_text(values[key])
    for key in ("incoming_context_tokens", "next_context_tokens", "watch_next_context_tokens"):
        if key in values:
            tokens[key] = context_tokens(values[key])
    for key in ("delta_context_tokens", "watch_delta_context_tokens"):
        if key in values:
            tokens[key] = context_delta(values[key])
    for key in ("pricing_retrieved_at_ms", "observed_at_ms", "now_ms", "started_at_ms", "reset_at_ms"):
        if key in values:
            tokens[key] = "unknown" if values[key] is None else format_local_timestamp(values[key], timezone_id)
    if "reset_at_ms" in values and now_ms is not None:
        tokens["reset"] = ("Window not started" if values.get("window_active") is False and values["reset_at_ms"] is None
                           else format_reset(values["reset_at_ms"], timezone_id, now_ms=now_ms))
    if "duration_seconds" in values:
        tokens["window"] = "" if values["duration_seconds"] is None else duration_text(values["duration_seconds"] * 1000)
    if "relative_cost" in values:
        if "evidence" in values:
            evidence = dict(values["evidence"].fields)
            tokens["evidence"] = (f"{evidence['model_prompts']} model prompts + "
                f"{evidence['publisher_prompts']} other same-publisher prompts; "
                f"{evidence['generic_prior_weight']}% generic prior from "
                f"{evidence['global_prompts']} completed prompts. 100 weight slots, not 100 observed prompts.")
        parts = [relative_cost(decimal(values["relative_cost"]))]
        for level in values.get("relative_levels", ())[1:]:
            tier = dict(level.fields)
            text = relative_cost(decimal(tier["relative_cost"]))
            if tier["threshold_tokens"] is not None:
                text += f" ({tier['threshold_operator']}{compact_threshold(tier['threshold_tokens'])})"
            parts.append(text)
        tokens["relative_cost"] = " → ".join(parts)
    if "token_mix_percent" in values:
        tokens["token_mix_percent"] = ("N/A" if values["token_mix_percent"] is None else
                                        "/".join(str(item) for item in values["token_mix_percent"]))
    if "price_summary" in values:
        tokens["price_summary"] = price_summary(values["price_summary"])
    if "incoming_context_tokens" in values and values.get("next_context_tokens") is not None and values.get("delta_context_tokens") is not None:
        tokens["incoming_context_tokens"] = context_delta(values["delta_context_tokens"]) + " → " + context_tokens(values["next_context_tokens"])
    if values.get("in_progress") and values.get("token_mix_percent") is None:
        tokens["token_mix_percent"] = "running - consider ABORT" if values.get("running_cost_warning") else "running"
    if values.get("is_compaction") and values.get("calls") == 0 and decimal(values.get("ccost")) == 0:
        tokens.update({key: "" for key in ("ccost", "calls", "incoming_context_ccost", "extra_ccost", "token_mix_percent")})
    if "totals" in values and "shares" in values:
        tokens["totals"] = "/".join("--" if item is None else compact_tokens(item) for item in values["totals"])
        tokens["percentages"] = ("/".join(balanced_share_percents(values["totals"]))
            if all(item is not None for item in values["shares"]) and sum(values["totals"]) else "--/--/--/--")
        costs = values.get("costs")
        tokens["costs"] = "N/A" if costs is None or (values["request_count"] and not values["priced_requests"]) else "/".join(
            ("" if values["cost_complete"] else "?") + ccost_amount(decimal(item)) for item in costs)
    return tokens


def roles(values):
    result = []
    for key, role in (("in_progress", "running"), ("cost_estimated", "estimated"),
                      ("unresolved_cost", "partial"), ("has_error", "error"), ("has_warning", "warning"), ("aborted", "warning"),
                      ("recent", "new"), ("promotional", "promotion"), ("superseded", "superseded")):
        if values.get(key):
            result.append(role)
    if values.get("ictx_price_threshold") or values.get("next_context_warning_severity") not in (None, "none"):
        result.append("threshold")
    if values.get("complete") is False and "partial" not in result:
        result.append("partial")
    if values.get("status") in ("blocked", "paused", "stale", "unavailable", "error") and "warning" not in result:
        result.append("warning")
    return tuple(result)


def history_tokens(values, timezone_id):
    """CLI prompt clocks/context guidance and historical mix cells from frozen facts."""
    tokens = {}
    if "at_ms" in values:
        tokens["clock"] = format_local_timestamp(values["at_ms"], timezone_id, "%H:%M")
    if values.get("aborted") and values.get("abort_at_ms"):
        tokens["abort_clock"] = format_local_timestamp(values["abort_at_ms"], timezone_id, "%H:%M")
    if "next_context_tokens" in values:
        context = values["next_context_tokens"]
        tokens["next_context"] = "Next Ictx: N/A" if context is None else "Next Ictx: ~" + context_tokens(context)
        if context is not None:
            multiplier = decimal(values.get("next_context_cost_multiplier"))
            if multiplier is not None and values.get("next_context_warning_severity") not in (None, "none"):
                ratio = f"{multiplier.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP):f}".removesuffix(".0")
                tokens["next_context"] += f" ({ratio}x more expensive)"
            else:
                tokens["next_context"] += " (Next Ictx CCost " + ccost_range(
                    decimal(values.get("next_context_cached_ccost")), decimal(values.get("next_context_fresh_ccost"))) + ")"
    if "totals" in values and "shares" in values:
        shares = balanced_share_percents(values["totals"]) if all(item is not None for item in values["shares"]) else ("--",) * 4
        costs = values.get("costs")
        priced = costs is not None and not (values["request_count"] and not values["priced_requests"])
        prefix = "" if values["cost_complete"] else "?"
        for index, name in enumerate(("input", "cache", "write", "output")):
            cost = "N/A" if not priced else prefix + ccost_amount(decimal(costs[index]))
            tokens[name] = shares[index] + ("" if costs is None else f" ({cost})")
        tokens["total_cost"] = prefix + ccost_amount(sum((decimal(item) for item in costs), Decimal(0))) if priced else "N/A"
        known_volume = values.get("known_total_tokens")
        tokens["total_tokens"] = token_volume(values.get("total_tokens"),
                                             None if known_volume is None else int(known_volume))
    return tokens


def with_display(value, timezone_id="UTC", now_ms=None, *, ccost_display_unit="credits"):
    """Apply a job-local display policy without changing any canonical fields."""
    with ccost_display(ccost_display_unit):
        return _with_display(value, timezone_id, now_ms)


def _with_display(value, timezone_id, now_ms):
    """Traverse only frozen allowlisted records; preserve field and row ordering."""
    if isinstance(value, tuple):
        return tuple(_with_display(item, timezone_id, now_ms) for item in value)
    if not isinstance(value, ObjectValue):
        return value
    values = dict(value.fields)
    now_ms = values.get("now_ms", now_ms)
    tokens = amount_tokens(values)
    tokens.update(quota_tokens(values))
    tokens.update(metric_tokens(values, timezone_id, now_ms))
    tokens.update(history_tokens(values, timezone_id))
    # These are opaque maps keyed by external model/source labels, not DTO schemas.
    opaque = {"by_model", "by_day_utc", "current_context_sources"}
    fields = tuple((key, item if key in opaque else _with_display(item, timezone_id, now_ms)) for key, item in value.fields)
    role_tokens = roles(values)
    return ObjectValue(fields + ((("display", record(**tokens)),) if tokens else ()) +
                       ((("display_roles", role_tokens),) if role_tokens else ()))
