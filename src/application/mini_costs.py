"""Mini-only grouping of canonical unrounded costs; no valuation or acquisition."""
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
    session = values.get("mini_session_cost", False)
    main_count = sum(not part["subagent"] for part in groups)
    counters = {False: 0, True: 0}
    sections = []
    for part in groups:
        child = part["subagent"]
        counters[child] += 1
        label = ("Sub Agent " + str(counters[child]) if child else
                 "Session Model " + str(counters[child]) if session else
                 "Main Model" + (" " + str(counters[child]) if main_count > 1 else ""))
        cost = (ccost_amount(Decimal(part["known_ccost"]), unresolved=not part["complete"])
                if part["priced_requests"] else "N/A")
        if cost != "N/A" and ccost_unit() == "credits":
            cost += " Credits"
        sections.append(f"{label}: {part['model']} — {part['effort']}\n{label} CCost: {cost}")
    if not main_count:
        label = "Session Model 1" if session else "Main Model"
        sections.insert(0, f"{label}: N/A — N/A\n{label} CCost: N/A")
    for index in range(values.get("mini_missing_agents", 0)):
        label = "Sub Agent " + str(counters[True] + index + 1)
        sections.append(f"{label}: N/A — N/A\n{label} CCost: N/A")
    return {"mini_cost_help": "\n\n".join(sections)}
