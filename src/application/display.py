"""Add allowlisted display tokens to immutable DTOs, never replace raw values.

Only already-exported fields are inspected; no source/provider access, valuation,
ranking or arbitrary object introspection. CLI and Web consume shared primitives.
"""
from decimal import Decimal, ROUND_HALF_UP

from src.analysis.timezones import format_local_timestamp
from src.display import (TOKEN_CATEGORIES, TOKEN_CATEGORY_LEGEND, compact_threshold, compact_tokens, context_delta, context_tokens,
                         duration_text, format_reset, money, native_amount, price_summary, relative_cost, unaccounted_usage, quota_usage, token_volume)
from src.numbers import balanced_share_percents, ccost_amount, ccost_display, ccost_range, ccost_unit, remaining_capacity

from .contracts import ObjectValue, record
from .quota_display import quota_displays
from .quota_ccost import quota_ccost_pace, quota_ccost_tokens, quota_ccost_values
from .quota_estimates import estimate_amount, estimate_help
from .prompt_costs import detail_tokens
from .ai_stats import stat_tokens
from .comparisons import display_tokens as comparison_tokens
from .reference_cost import cost_help_tokens


def decimal(value):
    return None if value is None else Decimal(value)


def amount_tokens(values):
    tokens = {}
    if "day_start_ms" in values and "prompt_count_complete" in values:
        # Web Today alone shows the known priced subtotal quietly. Keep the
        # comparison's canonical facts and other scopes' partial tokens intact.
        total = dict(values["total"].fields)
        tokens["daily_ccost"] = ("N/A" if total["observed_requests"] and not total["priced_requests"]
                                 else ccost_amount(decimal(total["known_ccost"])))
    for key in ("ccost", "total_ccost", "known_ccost", "run_ccost", "main_ccost", "subagent_ccost",
                "total_main_ccost", "total_subagent_ccost", "incoming_context_ccost", "extra_ccost",
                "next_context_cached_ccost", "next_context_fresh_ccost",
                "watch_next_context_cached_ccost", "watch_next_context_fresh_ccost"):
        if key not in values:
            continue
        # Only full-Watch cards export these report-owned availability flags.
        # Preserve canonical values and legacy CLI/other-report presentation.
        if key in ("incoming_context_ccost", "extra_ccost") and values.get(key + "_known") is False:
            tokens[key] = "N/A"
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
    for key in ("ccost_per_day", "ccost_per_workday"):
        if key in values:
            amount = decimal(values[key])
            estimated = values.get("capacity_basis") == "ratio"
            tokens[key] = ("N/A" if amount is None else estimate_amount(amount) if estimated else
                           ccost_amount(amount) if ccost_unit() == "usd" else remaining_capacity(amount))
            tokens[key + "_help"] = ("Remaining/" + ("workday" if key.endswith("workday") else "day") + " — " +
                                    estimate_help(amount)) if estimated and amount is not None else ""
    if "unaccounted_usage" in values:
        tokens["unaccounted_usage"] = unaccounted_usage(decimal(values["unaccounted_usage"]))
    if "remaining_fraction" in values:
        fraction = decimal(values["remaining_fraction"])
        tokens["remaining_fraction"] = "N/A" if fraction is None else f"{fraction * 100:.0f}%"
    if "known_ccost" in values:
        tokens["account_ccost"] = ("—" if values.get("observed_requests") and not values.get("priced_requests")
                                   else ccost_amount(decimal(values["known_ccost"])))
    if "rate" in values and "cost_complete" in values:
        tokens["known_ccost"] = ccost_amount(decimal(values["known_ccost"]), unresolved=not values["cost_complete"])
        rate = decimal(values["rate"])
        tokens["rate"] = "N/A" if rate is None else ccost_amount(rate) + ("/h" if ccost_unit() == "usd" else " CCost/h")
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


def watch_reset(quota, timezone_id, now_ms):
    """Full Web Watch alone uses Duration notation; all other reset tokens stay CLI-owned."""
    values = dict(quota.fields)
    deadline = values["reset_at_ms"]
    if values.get("window_active") is False and deadline is None:
        return "Window not started"
    if (isinstance(deadline, bool) or not isinstance(deadline, (int, float)) or deadline <= 0
            or not 0 < deadline - now_ms < 604_800_000):
        return format_reset(deadline, timezone_id, now_ms=now_ms)
    return f"Reset in {duration_text(deadline - now_ms)}, {format_local_timestamp(deadline, timezone_id, '%H:%M')}"


def metric_time_tokens(values, timezone_id, now_ms):
    """Unit-independent clocks for one frozen record in this projection only."""
    tokens = {}
    for key in ("pricing_retrieved_at_ms", "observed_at_ms", "now_ms", "started_at_ms", "reset_at_ms", "start_ms", "end_ms"):
        if key in values:
            tokens[key] = "unknown" if values[key] is None else format_local_timestamp(values[key], timezone_id)
    if "reset_at_ms" in values and now_ms is not None:
        tokens["reset"] = ("Window not started" if values.get("window_active") is False and values["reset_at_ms"] is None
                           else format_reset(values["reset_at_ms"], timezone_id, now_ms=now_ms))
        tokens["web_reset"] = tokens["reset"]
        deadline = values["reset_at_ms"]
        if isinstance(deadline, (int, float)) and 86_400_000 <= deadline - now_ms < 604_800_000:
            tokens["web_reset"] = f"Reset in {int((deadline - now_ms) // 3_600_000)}h, {format_local_timestamp(deadline, timezone_id)}"
    if "used_percent" in values and "quota" in values and now_ms is not None:
        tokens["watch_reset"] = watch_reset(values["quota"], timezone_id, now_ms)
    if "duration_seconds" in values:
        tokens["window"] = "" if values["duration_seconds"] is None else duration_text(values["duration_seconds"] * 1000)
    return tokens


def metric_tokens(values, timezone_id, now_ms=None, *, times=None):
    tokens = {}
    if 'model_comparison_mix' in values:
        mix, count = values['model_comparison_mix'], values['model_comparison_sample_size']
        if not count:
            tokens['model_comparison_mix_help'] = 'Token Mix unavailable · no completed priceable sample'
        elif mix is None or not sum(map(decimal, mix)):
            tokens['model_comparison_mix_help'] = 'Token Mix unavailable · comparison percentages not established'
        else:
            # Shares come directly from the comparison sample, not the broader report.
            # Convert finite Decimals to common-denominator integers for exact balancing.
            shares = tuple(map(decimal, mix))
            scale = 10 ** max(0, -min(value.as_tuple().exponent for value in shares))
            percentages = balanced_share_percents(tuple(int(value * scale) for value in shares))
            tokens['model_comparison_mix_help'] = (f'Token Mix · {count} completed priced prompts\n'
                f'Input {percentages[0]} · Cached input {percentages[1]}\n'
                f'Cache write {percentages[2]} · Output {percentages[3]}')
    if "source_label" in values or "token_mix_percent" in values or ("totals" in values and "shares" in values):
        tokens["token_categories"] = record(**dict(TOKEN_CATEGORIES))
        tokens["token_category_legend"] = TOKEN_CATEGORY_LEGEND
    for key in ("duration_ms", "watch_duration_ms", "running_ms", "background_ms"):
        if key in values:
            tokens[key] = duration_text(values[key])
    for key in ("incoming_context_tokens", "next_context_tokens", "watch_next_context_tokens", "context_tokens"):
        if key in values:
            tokens[key] = "0" if key == "context_tokens" and values[key] == 0 else context_tokens(values[key])
    for key in ("delta_context_tokens", "watch_delta_context_tokens"):
        if key in values:
            tokens[key] = context_delta(values[key])
    tokens.update(metric_time_tokens(values, timezone_id, now_ms) if times is None else times)
    if "relative_cost" in values:
        if "evidence" in values:
            evidence = dict(values["evidence"].fields)
            tokens["evidence"] = (f"One shared I/C/W/O mix from the latest {evidence['global_prompts']} "
                "completed priceable prompts globally (up to 100), for every model and tier.")
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
        tokens["first_incoming_context_tokens"] = context_tokens(values["incoming_context_tokens"])
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


def history_time_tokens(values, timezone_id):
    """Canonical start/finish/abort labels are identical in both CCost units."""
    tokens = {}
    if "at_ms" in values:
        tokens["clock"] = format_local_timestamp(values["at_ms"], timezone_id, "%H:%M")
        tokens["date_time"] = format_local_timestamp(values["at_ms"], timezone_id, "%Y-%m-%d %H:%M")
        tokens["start_date_time"] = format_local_timestamp(values["at_ms"], timezone_id, "%Y-%m-%d %H:%M %z")
    if "completed_at_ms" in values:
        finished = values["completed_at_ms"]
        tokens["finished_clock"] = "—" if finished is None else format_local_timestamp(finished, timezone_id, "%H:%M")
        tokens["finished_date_time"] = "Unknown finish time" if finished is None else format_local_timestamp(finished, timezone_id, "%Y-%m-%d %H:%M %z")
    if values.get("aborted") and values.get("abort_at_ms"):
        tokens["abort_clock"] = format_local_timestamp(values["abort_at_ms"], timezone_id, "%H:%M")
    return tokens


def history_tokens(values, timezone_id, *, times=None):
    """CLI prompt clocks/context guidance and historical mix cells from frozen facts."""
    tokens = {}
    if "severity" in values and "multiplier" in values:
        multiplier = decimal(values["multiplier"])
        if values.get('guidance_state') == 'pending':
            tokens['warning_cost'] = '(Price comparison pending)'
        elif values.get('guidance_state') == 'unavailable':
            tokens['warning_cost'] = '(Price comparison unavailable; retrying)'
        elif multiplier is not None:
            ratio = f"{multiplier.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP):f}".removesuffix(".0")
            tokens["warning_cost"] = f"({ratio}x more expensive)"
        elif values.get("cached_ccost") is not None and values.get("fresh_ccost") is not None:
            tokens["warning_cost"] = "(Next Ictx CCost " + ccost_range(
                decimal(values["cached_ccost"]), decimal(values["fresh_ccost"])) + ")"
        else:
            tokens["warning_cost"] = ""
        if values.get('guidance_state') == 'refreshing':
            at = values.get('guidance_sample_at_ms')
            sample = format_local_timestamp(at, timezone_id, '%Y-%m-%d %H:%M') if at is not None else 'earlier'
            tokens['warning_cost'] += f' (Price sample {sample}; updating)'
    tokens.update(history_time_tokens(values, timezone_id) if times is None else times)
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
        for index, (name, _label) in enumerate(TOKEN_CATEGORIES):
            cost = "N/A" if not priced else prefix + ccost_amount(decimal(costs[index]))
            tokens[name] = shares[index] + ("" if costs is None else f" ({cost})")
            tokens["mix_" + name + "_share"] = "N/A" if shares[index] == "--" else shares[index]
            tokens["mix_" + name + "_cost"] = ("N/A" if not priced else
                ("" if values["cost_complete"] else "Partial ") + ccost_amount(decimal(costs[index])))
        tokens["total_cost"] = prefix + ccost_amount(sum((decimal(item) for item in costs), Decimal(0))) if priced else "N/A"
        tokens["mix_total_cost"] = tokens["total_cost"].replace("?", "Partial ", 1)
        known_volume = values.get("known_total_tokens")
        tokens["total_tokens"] = token_volume(values.get("total_tokens"),
                                             None if known_volume is None else int(known_volume))
        tokens["mix_total_tokens"] = tokens["total_tokens"].replace("?", "Partial ", 1)
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
    reference = quota_ccost_values(values, now_ms) if "period_ccost" in values else {}
    if reference:
        value = ObjectValue(value.fields + (("ccost_reference", record(**{key: reference[key] for key in
            ("used", "capacity", "remaining", "basis", "monthly_capacity", "monthly_applicable")})),))
    if "native_pace" in values:
        value = ObjectValue(value.fields + (("ccost_pace", quota_ccost_pace(values, now_ms, reference)),))
    # Only differing CCost tokens need a second wire representation. Native
    # amounts and canonical sort/analysis values never participate in switching.
    variants = {}
    metric_times = metric_time_tokens(values, timezone_id, now_ms)
    history_times = history_time_tokens(values, timezone_id)
    for unit in ("credits", "usd"):
        with ccost_display(unit):
            alternate = amount_tokens(values)
            alternate.update(metric_tokens(values, timezone_id, now_ms, times=metric_times))
            alternate.update(history_tokens(values, timezone_id, times=history_times))
            alternate.update(quota_ccost_tokens(values, now_ms, reference))
            alternate.update(detail_tokens(values))
            alternate.update(stat_tokens(values))
            alternate.update(comparison_tokens(values, timezone_id))
        variants[unit] = alternate
    tokens = dict(variants[ccost_unit()])
    tokens.update(cost_help_tokens(values))
    tokens.update(quota_tokens(values))
    differing = {key for key in variants["credits"] if variants["credits"][key] != variants["usd"][key]}
    unit_tokens = record(**{unit: record(**{key: items[key] for key in tokens if key in differing})
                            for unit, items in variants.items()}) if differing else None
    # Opaque keyed maps and canonical quota reference values need no display recursion.
    opaque = {"by_model", "by_day_utc", "current_context_sources", "ccost_reference"}
    fields = tuple((key, item if key in opaque else _with_display(item, timezone_id, now_ms)) for key, item in value.fields)
    role_tokens = roles(values)
    quota_variants = (("quota_display", quota_displays(values)),) if "remaining_fraction" in values else ()
    return ObjectValue(fields + quota_variants + ((("display", record(**tokens)),) if tokens else ()) +
                       ((("display_units", unit_tokens),) if unit_tokens is not None else ()) +
                       ((("display_roles", role_tokens),) if role_tokens else ()))
