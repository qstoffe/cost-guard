"""Reference-cost quota displays; never provider allocation or billing arithmetic."""
from decimal import Decimal

from src.numbers import ccost_amount
from .contracts import record


def capacity_period(values):
    """Use normalized native period facts, never a provider's arbitrary plan name."""
    native = values.get("origin") == "provider_native"
    monthly = (native and values.get("period") == "fixed" and values.get("scope") == "account"
        and values.get("model_id") is None and values.get("duration_seconds") is None
        and values.get("label", "").casefold() in {"monthly", "month"})
    duration = values.get("duration_seconds") if native and values.get("period") in {"fixed", "rolling"} else None
    label = "Monthly" if monthly else {604800: "Weekly", 86400: "Daily"}.get(duration)
    if not label and duration and duration > 0:
        if duration % 86400 == 0:
            label = f"{duration // 86400}-day"
        elif duration % 3600 == 0:
            label = f"{duration // 3600}-hour"
        elif duration % 60 == 0:
            label = f"{duration // 60}-minute"
    return monthly, duration, (label + " Capacity" if label else "Capacity")


def monthly_tokens(values, capacity, cost, coherent, current, now_ms):
    monthly, duration, label = capacity_period(values)
    if monthly:
        return {"capacity_label": label, "monthly_capacity": "", "monthly_capacity_help": ""}
    deadline = values.get("reset_at_ms")
    fraction = values.get("remaining_fraction")
    reason = None
    if values.get("unlimited"):
        reason = "No finite quota limit."
    elif not duration or duration <= 0:
        reason = "No verified full recurring window duration; reset time alone is insufficient."
    elif not current:
        reason = "Quota source is stale, unavailable or expired."
    elif (values.get("window_active") is False or deadline is None or now_ms is None
            or not deadline - duration * 1000 <= now_ms < deadline):
        reason = "No verified active recurring quota window."
    elif not coherent or fraction is not None and not 0 <= Decimal(fraction) <= 1:
        reason = "Contradictory native quota amounts or fractions."
    elif (fraction is not None and values.get("limit") is not None and Decimal(values["limit"]) > 0
            and ((values.get("used") is not None and Decimal(fraction) != 1 - Decimal(values["used"]) / Decimal(values["limit"]))
                 or (values.get("remaining") is not None and Decimal(fraction) != Decimal(values["remaining"]) / Decimal(values["limit"])))):
        reason = "Contradictory native quota amounts or fractions."
    elif cost and not cost.get("complete"):
        reason = "Same-window usage has incomplete attribution or pricing."
    elif capacity is None or not capacity.is_finite() or capacity <= 0:
        reason = "No compatible same-window reference CCost Capacity."
    value = "N/A" if reason else ccost_amount(capacity * Decimal(30 * 24 * 3600) / Decimal(duration)) + " (guesstimate)"
    explanation = (reason or "Theoretical 30-day guesstimate: full-period CCost Capacity × 2,592,000 ÷ full-window seconds.\n"
        "Assumes repeated full windows; not a monthly entitlement, bill or spending forecast.\n"
        "Other quotas may constrain usage; compare each separately, never add their monthly equivalents.")
    return {"capacity_label": label, "monthly_capacity": value, "monthly_capacity_help": explanation}


def quota_ccost_values(values, now_ms):
    """Unrounded reference amounts shared by quota tokens and Web remaining pace."""
    context = values.get("period_ccost")
    if context is None:
        return {}
    context = dict(context.fields)
    cost = dict(context["cost"].fields) if context["cost"] is not None else {}
    used = cost.get("known_ccost")
    priced = not cost.get("observed_requests") or bool(cost.get("priced_requests"))
    used = Decimal(used) if used is not None and priced else None
    if used is not None and (not used.is_finite() or used < 0):
        used = None
    capacity = remaining = None
    basis = "unknown"
    deadline = values.get("reset_at_ms")
    current = (values.get("availability") in {"available", "partial"} and values.get("origin") == "provider_native" and
               values.get("status") not in {"stale", "unavailable", "error", "paused"} and
               (deadline is None or now_ms is None or deadline > now_ms))
    limit = values.get("limit")
    limit = None if limit is None else Decimal(limit)
    native_used, native_remaining, fraction = (None if values.get(key) is None else Decimal(values[key])
        for key in ("used", "remaining", "remaining_fraction"))
    coherent = (limit is None or limit > 0) and not (limit is not None and limit > 0 and (
        native_used is not None and native_used > limit or
        native_remaining is not None and native_remaining > limit or
        native_used is not None and native_remaining is not None and native_used + native_remaining != limit))
    if values.get("unlimited"):
        basis = "unlimited"
    elif current and coherent:
        # Only the normalized, account-scoped Copilot included allowance is on
        # the CCost reference scale. A matching unit name alone is not evidence.
        direct = (context["provider_id"] in {"github-copilot", "github-copilot-enterprise"} and
                  values.get("scope") == "account" and values.get("model_id") is None and
                  values.get("period") == "fixed" and values.get("label", "").casefold() in {"monthly", "month"} and
                   (values.get("unit") or "").casefold() == "ai credits" and limit is not None and limit > 0)
        verified = values.get("reference_ccost_capacity")
        if verified is not None and Decimal(verified) > 0:
            basis, capacity = "native", Decimal(verified)
        elif direct:
            basis, capacity = "native", limit
            remaining = native_remaining if native_remaining is not None else (
                limit - native_used if native_used is not None else None)
        else:
            if limit is not None and limit > 0 and native_used is not None:
                fraction = 1 - native_used / limit
            elif limit is not None and limit > 0 and native_remaining is not None:
                fraction = native_remaining / limit
            duration = values.get("duration_seconds")
            active = (values.get("window_active") is not False and deadline is not None and
                      (not duration or now_ms is None or deadline - duration * 1000 <= now_ms))
            if (active and fraction is not None and 0 <= fraction < 1 and used is not None and used > 0
                    and cost.get("complete") and values.get("scope") in {"account", "model"}
                    and (values.get("scope") != "model" or values.get("model_id"))):
                basis, capacity = "ratio", used / (1 - fraction)
                remaining = capacity - used
    return dict(context=context, cost=cost, used=used, capacity=capacity, remaining=remaining,
                basis=basis, coherent=coherent, current=current)


def quota_ccost_pace(values, now_ms):
    """Spread only this quota's accepted reference Remaining over its native calendar."""
    pace = values.get("native_pace")
    if (pace is None or values.get("period") != "fixed" or values.get("duration_seconds")
            or values.get("window_active") is False or now_ms is None
            or values.get("reset_at_ms") is None or values["reset_at_ms"] <= now_ms):
        return None
    # Invalid native facts must not become a positive reference budget, even if
    # an independent observed-cost ratio happens to produce one.
    for key in ("used", "remaining", "remaining_fraction"):
        value = values.get(key)
        if value is not None and (not Decimal(value).is_finite() or Decimal(value) < 0):
            return None
    reference = quota_ccost_values(values, now_ms)
    remaining = reference.get("remaining")
    counts = dict(pace.fields)
    days, workdays = counts["days"], counts["workdays"]
    if (remaining is None or not remaining.is_finite() or remaining < 0
            or not reference["current"] or days <= 0 or not 0 <= workdays <= days):
        return None
    return record(ccost_remaining=remaining, ccost_per_day=remaining / days,
                  ccost_per_workday=remaining / workdays if workdays else None,
                  days=days, workdays=workdays)


def quota_ccost_tokens(values, now_ms):
    reference = quota_ccost_values(values, now_ms)
    if not reference:
        return {}
    context, cost = reference["context"], reference["cost"]
    used, capacity, remaining = (reference[key] for key in ("used", "capacity", "remaining"))
    basis = reference["basis"]
    amount = lambda value: "?" if value is None else ccost_amount(value)
    explanation = {
        "native": "Provider-reported included AI-credit limit.\n"
                  "Observed Used CCost is separate; Used + Remaining need not equal Capacity.",
        "ratio": "Guesstimated full-period CCost: observed CCost ÷ native fraction used.\n"
                 "Changes with model usage; not a guaranteed budget.",
        "unlimited": "Capacity: N/A — The provider reports no finite usage limit.\n"
                     "Remaining mode keeps the observed Used CCost; no finite remaining amount applies.",
        "unknown": "No reliable same-window CCost Capacity / Remaining estimate.\n"
                   "A native quota percentage alone is not enough.",
    }[basis]
    if cost and not cost.get("complete"):
        explanation += "\nUsed CCost has partial attribution / pricing."
    if context["estimated"]:
        explanation += "\nUsed CCost has estimated attribution, not verified account attribution."
    if context["note"]:
        explanation += "\n" + context["note"]
    if values.get("reference_ccost_capacity") is not None and basis == "native":
        explanation = "Source-verified full-period reference CCost Capacity.\nObserved Used CCost is independent."
    brief = {
        "native": "Reference Remaining uses native AI credits; Used + Remaining need not equal Capacity.",
        "ratio": "Reference Capacity estimates a full period from observed CCost ÷ native fraction used; not a guaranteed budget.",
        "unlimited": "Unlimited quota; no finite reference Remaining applies.",
        "unknown": "Reference Capacity / Remaining unavailable; a native percentage alone is not enough.",
    }[basis]
    if cost and not cost.get("complete"):
        brief += "\nUsed CCost has partial attribution / pricing."
    if context["estimated"]:
        brief += "\nUsed CCost has estimated attribution."
    if context["note"]:
        brief += "\n" + context["note"]
    if values.get("reference_ccost_capacity") is not None and basis == "native":
        brief = "Source-verified reference Capacity; observed Used CCost is independent."
    return {**monthly_tokens(values, capacity, cost, reference["coherent"], reference["current"], now_ms),
            "ccost_used": amount(used), "ccost_remaining": amount(remaining),
            "ccost_capacity": ("N/A" if basis == "unlimited" else amount(capacity)) +
                (" (guesstimate)" if basis == "ratio" and capacity is not None else ""),
            "capacity_basis": basis,
            "ccost_help": explanation, "ccost_brief": brief}
