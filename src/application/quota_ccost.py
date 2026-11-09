"""Reference equivalents of verified quota facts, or explicitly estimated period costs."""
from decimal import Decimal

from src.numbers import ccost_amount
from .contracts import record
from .quota_estimates import estimate_amount, estimate_help


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


def monthly_values(values, capacity, cost, coherent, current, now_ms):
    monthly, duration, label = capacity_period(values)
    if monthly:
        return dict(capacity_label=label, monthly_capacity=None, monthly_reason="", monthly_applicable=False)
    deadline = values.get("reset_at_ms")
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
    elif not coherent:
        reason = "Contradictory native quota amounts or fractions."
    elif cost and not cost.get("complete"):
        reason = "Same-window usage has incomplete attribution or pricing."
    elif capacity is None or not capacity.is_finite() or capacity <= 0:
        reason = "No compatible same-window reference CCost Capacity."
    raw = None if reason else capacity * Decimal(30 * 24 * 3600) / Decimal(duration)
    return dict(capacity_label=label, monthly_capacity=raw, monthly_reason=reason, monthly_applicable=True)


def monthly_tokens(reference):
    raw, reason = reference["monthly_capacity"], reference["monthly_reason"]
    explanation = reason or ("Approximate 30-day equivalent of this window’s reference CCost capacity, "
        "not a guaranteed monthly entitlement.")
    return {"capacity_label": reference["capacity_label"],
            "monthly_capacity": ("N/A" if raw is None else "~" + estimate_amount(raw)) if reference["monthly_applicable"] else "",
            "monthly_capacity_help": explanation if reference["monthly_applicable"] else ""}


def coherent_native(limit, used, remaining, fraction):
    """Reject contradictions, not rounded UI percentages or independent local costs."""
    if any(value is not None and (not value.is_finite() or value < 0)
           for value in (limit, used, remaining, fraction)):
        return False
    if fraction is not None and fraction > 1:
        return False
    if limit is None:
        return True
    if (limit <= 0 or used is not None and used > limit or remaining is not None and remaining > limit
            or used is not None and remaining is not None and used + remaining != limit):
        return False
    # Normalized raw fractions must match amounts; either Decimal division order
    # is valid when both complementary amounts exist.
    ratios = ([1 - used / limit] if used is not None else []) + ([remaining / limit] if remaining is not None else [])
    return fraction is None or not ratios or fraction in ratios


def native_reference_amounts(capacity, limit, used, remaining, fraction, *, direct):
    """Convert one coherent native snapshot, with complements only on this basis."""
    if not direct:
        used = capacity * used / limit if limit is not None and used is not None else None
        remaining = capacity * remaining / limit if limit is not None and remaining is not None else None
    if used is None and remaining is not None:
        used = capacity - remaining
    elif remaining is None and used is not None:
        remaining = capacity - used
    elif used is None and fraction is not None:
        remaining = capacity * fraction
        used = capacity - remaining
    return used, remaining


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
               values.get("status") not in {"stale", "unavailable", "error", "paused", "invalid"} and
               (deadline is None or now_ms is None or deadline > now_ms))
    limit = values.get("limit")
    limit = None if limit is None else Decimal(limit)
    native_used, native_remaining, fraction = (None if values.get(key) is None else Decimal(values[key])
        for key in ("used", "remaining", "remaining_fraction"))
    coherent = coherent_native(limit, native_used, native_remaining, fraction)
    # Recognize the conversion separately from freshness/validity. A failed native
    # mapping must not fall through to independently observed OpenCode Used.
    direct = (context["provider_id"] in {"github-copilot", "github-copilot-enterprise"} and
              values.get("scope") == "account" and values.get("model_id") is None and
              values.get("period") == "fixed" and values.get("label", "").casefold() in {"monthly", "month"} and
              (values.get("unit") or "").casefold() == "ai credits")
    verified = values.get("reference_ccost_capacity")
    convertible = direct or verified is not None
    if convertible and not values.get("unlimited"):
        used = None
    if values.get("unlimited"):
        basis = "unlimited"
    elif current and coherent:
        if convertible:
            if values.get("status") != "blocked" and values.get("window_active") is not False:
                capacity = Decimal(verified) if verified is not None else limit
                if capacity is not None and capacity.is_finite() and capacity > 0:
                    basis = "native"
                    used, remaining = native_reference_amounts(capacity, limit, native_used, native_remaining,
                        fraction, direct=direct and verified is None)
                else:
                    capacity = None
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
    return dict(**monthly_values(values, capacity, {} if basis == "native" else cost, coherent, current, now_ms),
                context=context, cost=cost, used=used, capacity=capacity, remaining=remaining,
                basis=basis, coherent=coherent, current=current)


def quota_ccost_pace(values, now_ms, reference=None):
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
    reference = quota_ccost_values(values, now_ms) if reference is None else reference
    remaining = reference.get("remaining")
    counts = dict(pace.fields)
    days, workdays = counts["days"], counts["workdays"]
    if (remaining is None or not remaining.is_finite() or remaining < 0
            or not reference["current"] or days <= 0 or not 0 <= workdays <= days):
        return None
    return record(ccost_remaining=remaining, ccost_per_day=remaining / days,
                  ccost_per_workday=remaining / workdays if workdays else None,
                  capacity_basis=reference["basis"],
                  days=days, workdays=workdays)


def quota_ccost_tokens(values, now_ms, reference=None):
    reference = quota_ccost_values(values, now_ms) if reference is None else reference
    if not reference:
        return {}
    context, cost = reference["context"], reference["cost"]
    used, capacity, remaining = (reference[key] for key in ("used", "capacity", "remaining"))
    basis = reference["basis"]
    amount = lambda value: "?" if value is None else ccost_amount(value)
    explanation = {
        "native": "Provider-reported quota Used/Remaining, converted to reference CCost units.\n"
                  "Used + Remaining = Capacity for coherent finite allowances; not provider cash or billing.\n"
                  "OpenCode-observed period CCost is separate and may differ (including usage in other clients).",
        "ratio": "OpenCode-observed period CCost estimate.\n"
                 "Guesstimated full-period CCost: observed CCost ÷ native fraction used.\n"
                 "Changes with model usage; not a guaranteed budget.",
        "unlimited": "Capacity: N/A — The provider reports no finite usage limit.\n"
                     "Remaining mode keeps the observed Used CCost; no finite remaining amount applies.",
        "unknown": "No reliable same-window CCost Capacity / Remaining estimate.\n"
                   "A native quota percentage alone is not enough.",
    }[basis]
    if basis != "native" and cost and not cost.get("complete"):
        explanation += "\nUsed CCost has partial attribution / pricing."
    if basis != "native" and context["estimated"]:
        explanation += "\nUsed CCost has estimated attribution, not verified account attribution."
    if basis != "native" and context["note"]:
        explanation += "\n" + context["note"]
    if values.get("reference_ccost_capacity") is not None and basis == "native":
        explanation = "Source-verified full-period reference CCost Capacity.\n" + explanation
    brief = {
        "native": "Provider-reported quota Used/Remaining in reference CCost units; OpenCode-observed CCost is separate.",
        "ratio": "Reference Capacity estimates a full period from observed CCost ÷ native fraction used; not a guaranteed budget.",
        "unlimited": "Unlimited quota; no finite reference Remaining applies.",
        "unknown": "Reference Capacity / Remaining unavailable; a native percentage alone is not enough.",
    }[basis]
    if basis != "native" and cost and not cost.get("complete"):
        brief += "\nUsed CCost has partial attribution / pricing."
    if basis != "native" and context["estimated"]:
        brief += "\nUsed CCost has estimated attribution."
    if basis != "native" and context["note"]:
        brief += "\n" + context["note"]
    if values.get("reference_ccost_capacity") is not None and basis == "native":
        brief = "Source-verified reference Capacity. " + brief
    estimated = basis == "ratio"
    capacity_help = {
        "ratio": "Estimated full-window reference CCost from observed same-window CCost and the provider’s reported usage fraction.",
        "native": "Provider-reported full-window allowance in reference CCost units, separate from OpenCode-observed usage.",
        "unlimited": "The provider reports an unlimited quota.",
        "unknown": "Reference CCost capacity is unknown.",
    }[basis]
    if estimated and context["estimated"]:
        capacity_help += "\n\nUses estimated account attribution."
    return {**monthly_tokens(reference),
            "capacity_help": capacity_help,
            "ccost_used": amount(used), "ccost_remaining": estimate_amount(remaining) if estimated else amount(remaining),
            "ccost_remaining_help": "Remaining — " + estimate_help(remaining) if estimated and remaining is not None else "",
            "ccost_capacity_help": "Capacity — " + estimate_help(capacity) if estimated and capacity is not None else "",
            "ccost_capacity": ("N/A" if basis == "unlimited" else "~" + estimate_amount(capacity) if estimated else amount(capacity)),
            "capacity_basis": basis,
            "ccost_help": explanation, "ccost_brief": brief}
