"""Bounded Web prompt-detail export and unit-aware copy; no pricing or acquisition."""
from decimal import Decimal

from src.numbers import ccost_amount
from .contracts import record
from .reference_cost import issue_records, unavailable_help

MAX_PARTS = 24


def grouped_parts(parts):
    """Sum unrounded source-owned parts before bounding the exported groups."""
    groups, identities = {}, {}
    for part in parts:
        role = "main" if part.agent == 0 else "subagents"
        key = (role, part.provider_id, part.model_id, part.variant, part.price_tier)
        groups.setdefault(key, []).append(part)
        identities.setdefault(part.model or part.model_id, set()).add((part.provider_id, part.model_id))
    result = []
    for (role, provider, model_id, variant, tier), items in groups.items():
        first = items[0]
        categories = tuple(None if any(item.categories[index] is None for item in items) else
            sum((item.categories[index] for item in items), Decimal(0)) for index in range(4))
        result.append(record(role=role, provider_id=provider, model_id=model_id, variant=variant,
            model=first.model, effort=first.effort, price_tier=tier,
            qualify_model=len(identities[first.model or model_id]) > 1,
            agent_count=len({item.session_id for item in items if item.agent and item.session_id}),
            prompt_count=len({identity for item in items for identity in item.prompt_ids}),
            prompts_complete=all(item.prompts_complete for item in items),
            calls=sum(item.calls for item in items),
            known_ccost=sum((item.known_ccost for item in items), Decimal(0)),
            priced_requests=sum(item.priced_requests for item in items),
            complete=all(item.complete for item in items), categories=categories,
            ccost_unavailable=issue_records(issue for item in items for issue in item.unavailable)))
    return tuple(result)


def cost_detail(row):
    parts = grouped_parts(row.cost_parts)
    shown = parts[:MAX_PARTS]
    omitted = [dict(part.fields) for part in parts[MAX_PARTS:]]
    missing_agents = max(0, row.linked_agent_count - len({part.session_id for part in row.cost_parts if part.agent}))
    observed_calls = sum(part.calls for part in row.cost_parts)
    return record(parts=shown,
        omitted_parts=len(omitted), omitted_ccost=sum((Decimal(part["known_ccost"]) for part in omitted), Decimal(0)),
        omitted_complete=all(part["complete"] for part in omitted),
        omitted_calls=sum(part["calls"] for part in omitted),
        model_count=len({(part.provider_id, part.model_id) for part in row.cost_parts
            if part.provider_id and part.model_id}),
        group_count=len(parts), observed_calls=observed_calls,
        calls_complete=bool(parts) and observed_calls == row.calls and not missing_agents,
        agents_without_usage=missing_agents,
        linked_agent_count=row.linked_agent_count)


def detail_tokens(values):
    detail = values.get("cost_detail")
    if detail is None:
        return {}
    detail = dict(detail.fields)
    sections, models, calls = [], [], []
    for part in detail["parts"]:
        part = dict(part.fields)
        owner = "Main prompt" if part["role"] == "main" else "Subagents"
        identity = part["model"] or part["model_id"] or "Unrecorded model"
        if part["qualify_model"]:
            identity += f" [{part['provider_id']}/{part['model_id']}]"
        if part["effort"] and part["effort"] != "N/A":
            identity += " · " + part["effort"]
        heading = owner + " — " + identity
        call_heading = heading + (" · " + part["price_tier"] if part["price_tier"] else "")
        if part["role"] == "subagents" and part["agent_count"]:
            agents = f" ({part['agent_count']} agent{'s' if part['agent_count'] != 1 else ''})"
            heading += agents
            call_heading += agents
        models.append(heading + (f"\n  {part['provider_id']}/{part['model_id']}" if part['provider_id'] and part['model_id'] else
            "\n  Provider/model identity unrecorded") + ("\n  Effort unreported" if part["effort"] in {None, "", "N/A"} else ""))
        calls.append(f"{call_heading}: {part['calls']}")
        lines = [heading]
        if part["role"] == "subagents":
            count = str(part["prompt_count"]) if part["prompts_complete"] else (
                f"at least {part['prompt_count']} observed (incomplete boundaries)" if part["prompt_count"] else
                "N/A — prompt boundaries unrecorded")
            lines.append("• Number of prompts: " + count)
        if not part["priced_requests"]:
            sections.append("\n".join(lines) + "\n" + unavailable_help(part["ccost_unavailable"]) + "\n"
                + "\n".join(f"• {label}: N/A" for label in ("Input", "Cached input", "Cache write", "Output"))
                + "\nSubtotal: N/A")
            continue
        for label, amount in zip(("Input", "Cached input", "Cache write", "Output"), part["categories"]):
            lines.append(f"• {label}: {ccost_amount(None if amount is None else Decimal(amount))}")
        lines.append("Subtotal: " + ccost_amount(Decimal(part["known_ccost"]), unresolved=not part["complete"]))
        if any(amount is None for amount in part["categories"]):
            lines.append("Some category amounts are unavailable; subtotal includes known priced usage.")
        if not part["complete"]:
            lines.append("Partial pricing — unpriced requests are not included.")
        sections.append("\n".join(lines))
    if detail["omitted_parts"]:
        note = f"{detail['omitted_parts']} additional role/model/effort groups not shown"
        sections.append(note + "\nKnown subtotal: " + ccost_amount(Decimal(detail["omitted_ccost"]),
            unresolved=not detail["omitted_complete"]))
        models.append(note + f" ({detail['model_count']} distinct models overall)")
        calls.append(note + f": {detail.get('omitted_calls', 0)} calls")
    linked = detail["linked_agent_count"]
    if not detail["parts"] and values.get("calls", 0):
        sections.append("Detailed request attribution unavailable; no per-model costs can be established.")
    if detail.get("agents_without_usage"):
        note = f"{detail['agents_without_usage']} linked subagent(s) have no recorded request usage."
        sections.append(note)
        models.append(note)
        calls.append(note)
    model_help = (f"* Linked subagents participated ({linked}).\n\n" if linked else "") + "\n\n".join(models)
    if sections:
        total = values.get("ccost")
        sections.append("Total CCost: " + ccost_amount(None if total is None else Decimal(total),
            unresolved=values.get("unresolved_cost", False)) + "\nAmounts are independently rounded.")
    if calls:
        calls.append(("Total Calls: " if detail["calls_complete"] else "Observed Calls (incomplete request evidence): ")
            + str(detail["observed_calls"]))
    return {"cost_detail_help": "\n\n".join(sections),
            "model_detail_help": model_help if detail["model_count"] > 1 or linked else "",
            "calls_help": "\n".join(calls) if detail["group_count"] > 1 or linked and calls else ""}
