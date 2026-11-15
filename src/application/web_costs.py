"""Web-only unavailable tokens; raw accounting and shared CLI formatting stay intact."""
from decimal import Decimal


COST_KEYS = (
    "ccost", "total_ccost", "known_ccost", "run_ccost", "main_ccost", "subagent_ccost",
    "total_main_ccost", "total_subagent_ccost", "incoming_context_ccost", "extra_ccost",
    "next_context_cached_ccost", "next_context_fresh_ccost",
    "watch_next_context_cached_ccost", "watch_next_context_fresh_ccost",
)


def unavailable_tokens(values):
    comparison = values.get("comparison_cost")
    evidence = dict(comparison.fields) if comparison is not None else values
    groups = [dict(group.fields) for group in values.get("mini_cost_groups", ())]
    priced = (any(group["complete"] for group in groups) if groups else
        evidence.get("priced_requests", 0) > 0)
    result = {}
    for key in COST_KEYS:
        if key not in values:
            continue
        raw = values[key]
        incomplete = (values.get("unresolved_cost", not values.get("complete", True)) if key == "ccost" else
            not values.get("comparison_cost_complete", True) if key == "total_ccost" else
            not values.get("complete", True) if key == "known_ccost" else
            values.get(key.replace("_ccost", "_estimated"), False))
        supported = priced and not (key == "ccost" and comparison is not None and evidence.get("ccost") is None)
        unknown = (raw is None or values.get(key + "_known") is False or
            values.get(key + "_usage_missing") is True or
            Decimal(raw) == 0 and incomplete and not supported)
        if unknown:
            result[key] = "N/A"
    if result.get("known_ccost"):
        result["account_ccost"] = "N/A"
    if "rate" in values and values["rate"] is None:
        result["rate"] = "N/A"
    if values.get("metric") in {"hourly-rate", "total-cost", "average-cost", "expensive-session"}:
        if values["value"] is None or Decimal(values["value"]) == 0 and values.get("status") == "partial":
            result.update({key: "N/A" for key in ("value", "calendar_rate", "workday_rate", "active_rate")})
    if "day_start_ms" in values and "prompt_count_complete" in values:
        total = dict(values["total"].fields)
        if total["known_ccost"] is None or (Decimal(total["known_ccost"]) == 0 and
                not total["complete"] and not total["priced_requests"]):
            result["daily_ccost"] = "N/A"
    if "costs" in values and "shares" in values:
        costs = values["costs"]
        unpriced = not values.get("cost_complete", True) and not values.get("priced_requests", 0)
        for index, name in enumerate(("input", "cache", "write", "output")):
            if costs is None or costs[index] is None or (Decimal(costs[index]) == 0 and unpriced):
                result["mix_" + name + "_cost"] = "N/A"
                result["mix_" + name + "_cost_value"] = "N/A"
                result["mix_" + name + "_cost_help"] = ""
        if costs is None or all(result.get("mix_" + name + "_cost") for name in ("input", "cache", "write", "output")):
            result["total_cost"] = result["mix_total_cost"] = "N/A"
    return result
