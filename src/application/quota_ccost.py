"""Reference-cost quota displays; never provider allocation or billing arithmetic."""
from decimal import Decimal

from src.numbers import ccost_amount


def quota_ccost_tokens(values, now_ms):
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
        if direct:
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
    amount = lambda value: "?" if value is None else ccost_amount(value)
    explanation = {
        "native": "Capacity comes from the provider’s reported included AI-credit limit.\n"
                  "Remaining uses native available AI credits on the same reference scale.\n"
                  "Used CCost is a separate observed reference estimate; Used + Remaining need not equal Capacity.",
        "ratio": "Capacity — Estimated CCost equivalent of 100% of this quota period.\n"
                 "Based on: CCost used ÷ provider-reported fraction used.\n"
                 "The amount can change with your models, external activity and the provider’s limits.\n"
                 "It is not a guaranteed budget or billed balance.",
        "unlimited": "Capacity: N/A — The provider reports no finite usage limit.\n"
                     "Remaining mode keeps the observed Used CCost; no finite remaining amount applies.",
        "unknown": "Capacity / Remaining: ? — No reliable same-window estimate is available.\n"
                   "A valid native remaining percentage does not establish remaining CCost.\n"
                   "Zero usage, missing history, partial pricing, uncertain attribution or stale data can prevent an estimate.",
    }[basis]
    explanation += "\nAmounts use the selected CCost Credits / reference USD unit (100 CCost = $1.00), not your bill."
    if cost and not cost.get("complete"):
        explanation += "\nUsed CCost has partial attribution / pricing."
    if context["estimated"]:
        explanation += "\nUsed CCost has estimated attribution, not verified account attribution."
    if context["note"]:
        explanation += "\n" + context["note"]
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
    return {"ccost_used": amount(used), "ccost_remaining": amount(remaining),
            "ccost_capacity": "N/A" if basis == "unlimited" else amount(capacity),
            "ccost_help": explanation, "ccost_brief": brief}
