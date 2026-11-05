"""Bounded Web prompt-detail export and unit-aware copy; no pricing or acquisition."""
from decimal import Decimal

from src.numbers import ccost_amount
from .contracts import record

MAX_PARTS = 24


def cost_detail(row):
    parts = row.cost_parts
    shown = parts[:MAX_PARTS]
    omitted = parts[MAX_PARTS:]
    return record(parts=tuple(record(**{name: getattr(part, name) for name in (
        "session_id", "agent", "provider_id", "model_id", "variant", "model", "effort",
        "calls", "known_ccost", "priced_requests", "complete", "categories")}) for part in shown),
        omitted_parts=len(omitted), omitted_ccost=sum((part.known_ccost for part in omitted), Decimal(0)),
        omitted_complete=all(part.complete for part in omitted),
        omitted_calls=sum(part.calls for part in omitted),
        agents_without_usage=max(0, row.linked_agent_count - len({part.agent for part in parts if part.agent})),
        linked_agent_count=row.linked_agent_count)


def detail_tokens(values):
    detail = values.get("cost_detail")
    if detail is None:
        return {}
    detail = dict(detail.fields)
    sections, models, calls, agents = [], [], [], {}
    for part in detail["parts"]:
        part = dict(part.fields)
        owner = "Main prompt" if part["agent"] == 0 else f"Subagent {part['agent']}"
        identity = part["model"] or part["model_id"] or "Unrecorded model"
        if part["effort"] and part["effort"] != "N/A":
            identity += " · " + part["effort"]
        heading = owner + " — " + identity
        models.append(heading + f"\n  {part['provider_id']}/{part['model_id']}")
        calls.append(f"{heading}: {part['calls']}")
        agents.setdefault(owner, []).append(part)
        if not part["priced_requests"]:
            sections.append(heading + "\nCost unavailable — no reference price for recorded usage.")
            continue
        lines = [heading]
        for label, amount in zip(("Input", "Cached input", "Cache write", "Output"), part["categories"]):
            if amount is not None:
                lines.append(f"• {label}: {ccost_amount(Decimal(amount))}")
        lines.append("Subtotal: " + ccost_amount(Decimal(part["known_ccost"]), unresolved=not part["complete"]))
        if any(amount is None for amount in part["categories"]):
            lines.append("Some category amounts are unavailable; subtotal includes known priced usage.")
        if not part["complete"]:
            lines.append("Partial pricing — unpriced requests are not included.")
        sections.append("\n".join(lines))
    for owner, parts in agents.items():
        if len(parts) > 1:
            scope = " (shown model/effort groups)" if detail["omitted_parts"] else ""
            amount = sum((Decimal(part["known_ccost"]) for part in parts), Decimal(0))
            sections.append(owner + " total" + scope + ": " + ccost_amount(amount,
                unresolved=not all(part["complete"] for part in parts)))
    if detail["omitted_parts"]:
        note = f"{detail['omitted_parts']} additional agent/model groups not shown"
        sections.append(note + "\nKnown subtotal: " + ccost_amount(Decimal(detail["omitted_ccost"]),
            unresolved=not detail["omitted_complete"]))
        models.append(note)
        calls.append(note + f": {detail.get('omitted_calls', 0)} calls")
    linked = detail["linked_agent_count"]
    if detail.get("agents_without_usage"):
        note = f"{detail['agents_without_usage']} linked subagent(s) have no recorded request usage."
        sections.append(note)
        models.append(note)
    model_help = (f"* Linked subagents participated ({linked}).\n\n" if linked else "") + "\n\n".join(models)
    if sections:
        total = values.get("ccost")
        sections.append("Total CCost: " + ccost_amount(None if total is None else Decimal(total),
            unresolved=values.get("unresolved_cost", False)) + "\nAmounts are independently rounded.")
    return {"cost_detail_help": "\n\n".join(sections),
            "model_detail_help": model_help if linked or len(models) > 1 else "",
            "calls_help": "\n".join(calls) if linked and calls else ""}
