"""Shared CCost help from canonical unrounded costs; no valuation or acquisition."""
from decimal import Decimal

from src.numbers import ccost_amount, ccost_unit
from .contracts import record
from .effort_help import effort_help


def mini_groups(parts, *, complete=True):
    groups = {}
    for part in parts:
        models = part.selected_models or (part.model_id,)
        # A combined selector cannot be allocated after the fact. Report the
        # supported joint identity rather than inventing per-model amounts.
        model = ", ".join(f"{part.provider_id}/{model}" for model in models
                          if part.provider_id and model) or "N/A"
        effort = " / ".join(dict.fromkeys(effort_help(value, explicit=part.effort)
            for value in part.effort_evidence)) if part.effort_evidence else part.effort or "N/A"
        key = (bool(part.agent), model, effort)
        value = groups.setdefault(key, [Decimal(0), 0, complete])
        value[0] += part.known_ccost
        value[1] += part.priced_requests
        value[2] = value[2] and part.complete
    return tuple(record(subagent=child, model=model, effort=effort,
        known_ccost=amount, priced_requests=priced, complete=covered)
        for (child, model, effort), (amount, priced, covered) in sorted(groups.items()))


def mini_cost_tokens(values):
    if "mini_cost_groups" not in values:
        return {}
    groups = [dict(part.fields) for part in values["mini_cost_groups"]]
    models, amounts, evidence = [], [], []
    for part in groups:
        label = "Sub Agents" if part["subagent"] else "Session Models"
        ready = Decimal(part["known_ccost"]) > 0 or part["complete"]
        cost = ccost_amount(Decimal(part["known_ccost"])) if ready else "N/A"
        if ready and ccost_unit() == "credits":
            cost += " Credits"
        models.append((label, f"{part['model']} — {part['effort']}"))
        amounts.append(cost)
        evidence.append(ready)
    if values.get("mini_missing_agents", 0) and ("Sub Agents", "N/A — N/A") not in models:
        models.append(("Sub Agents", "Request usage unavailable"))
        amounts.append("N/A")
        evidence.append(False)
    # Share model/effort text between units. The browser only joins prepared
    # labels and formatted amounts; it never groups, values or rounds requests.
    sections = []
    for label in ("Session Models", "Sub Agents"):
        bullets = [f"• {model} — ({amount})" for (kind, model), amount in zip(models, amounts) if kind == label]
        if bullets:
            sections.append(label + ":\n" + "\n".join(bullets))
    key = "session_cost_help" if values.get("mini_session_cost") else "cost_detail_help"
    return {"mini_cost_models": tuple(models), "mini_cost_amounts": tuple(amounts),
            "mini_cost_ready": tuple(evidence), key: "\n\n".join(sections) or "No model usage recorded"}
