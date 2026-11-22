"""Bounded Web prompt-detail export and unit-aware copy; no pricing or acquisition."""
from decimal import Decimal

from src.domain.effort import bounded_evidence
from .contracts import record
from .model_help import attribution_label, request_model_help
from .reference_cost import issue_records
from .effort_help import evidence_record, evidence_help
from .mini_costs import mini_groups

MAX_PARTS = 24


def watch_calls(row):
    """Physical request groups, independent of role, price tier and valuation."""
    groups = {}
    for part in row.cost_parts:
        key = (part.provider_id or "Unknown provider", part.model_id or "Unknown model", part.effort or "Unknown")
        groups.setdefault(key, []).append(part)
    lines = []
    for (provider, model, effort), parts in list(groups.items())[:MAX_PARTS]:
        evidence = tuple(evidence_record(value) for value in bounded_evidence(
            value for part in parts for value in part.effort_evidence))
        effort = evidence_help([dict(value.fields) for value in evidence],
            value_cell=True, explicit=effort) if evidence else effort
        count = sum(part.calls for part in parts)
        lines.append(f"{provider}/{model} ({effort.replace(chr(10), ' ')}): {count} calls")
    if len(groups) > MAX_PARTS:
        lines.append("Additional request groups omitted; partial details.")
    observed = sum(part.calls for part in row.cost_parts)
    missing = any(agent.state not in {"usage-observed", "not-executed"} for agent in row.agent_coverage)
    if observed != row.calls or missing or row.linked_agent_count and not row.cost_parts:
        lines.append("Unknown/unattributed requests: partial model/effort evidence.")
    for index, agent in enumerate(row.agent_coverage[:MAX_PARTS], 1):
        if label := attribution_label(agent.attribution):
            lines.append(f"Subagent {index} — {label}")
    return "\n".join(lines) or "Model/effort request details unavailable."


def grouped_parts(parts):
    """Sum unrounded source-owned parts before bounding the exported groups."""
    groups = {}
    for part in parts:
        role = "main" if part.agent == 0 else "subagents"
        key = (role, part.agent, part.provider_id, part.model_id, part.variant, part.price_tier, part.selected_models)
        groups.setdefault(key, []).append(part)
    result = []
    for (role, agent, provider, model_id, variant, tier, _selected), items in groups.items():
        first = items[0]
        categories = tuple(None if any(item.categories[index] is None for item in items) else
            sum((item.categories[index] for item in items), Decimal(0)) for index in range(4))
        evidence = tuple(evidence_record(value) for value in bounded_evidence(
            value for item in items for value in item.effort_evidence))
        optional = {"effort_evidence": evidence} if evidence else {}
        issues = issue_records(issue for item in items for issue in item.unavailable)
        if issues:
            optional["ccost_unavailable"] = issues
        if any(item.catalog_estimate for item in items):
            optional["catalog_estimate"] = True
        result.append(record(role=role, agent=agent, provider_id=provider, model_id=model_id, variant=variant,
            effort=first.effort, price_tier=tier,
            selected_models=tuple(sorted({model for item in items for model in item.selected_models})),
            agent_count=len({item.session_id for item in items if item.agent and item.session_id}),
            prompt_count=len({identity for item in items for identity in item.prompt_ids}),
            prompts_complete=all(item.prompts_complete for item in items),
            calls=sum(item.calls for item in items),
            known_ccost=sum((item.known_ccost for item in items), Decimal(0)),
            priced_requests=sum(item.priced_requests for item in items),
            complete=all(item.complete for item in items), categories=categories, **optional))
    return tuple(result)


def cost_detail(row):
    parts = grouped_parts(row.cost_parts)
    shown = parts[:MAX_PARTS]
    omitted = [dict(part.fields) for part in parts[MAX_PARTS:]]
    missing_agents = max(0, row.linked_agent_count - len({part.session_id for part in row.cost_parts if part.agent}))
    agents = tuple(record(agent=index + 1, state=agent.state)
        for index, agent in enumerate(row.agent_coverage))
    known_agents = {part.agent for part in row.cost_parts}
    missing = tuple(agent for agent in agents if dict(agent.fields)["agent"] not in known_agents
                    or dict(agent.fields)["state"] not in {"usage-observed", "not-executed"})
    attributed = tuple(record(agent=index, label=attribution_label(agent.attribution))
        for index, agent in enumerate(row.agent_coverage, 1) if agent.attribution != "verified")
    by_agent = {}
    for part in parts:
        value = dict(part.fields)
        total = by_agent.setdefault(value["agent"], dict(known_ccost=Decimal(0), complete=True, groups=0))
        total["known_ccost"] += Decimal(value["known_ccost"])
        total["complete"] = total["complete"] and value["complete"]
        total["groups"] += 1
    totals = tuple(record(agent=agent, **total) for agent, total in sorted(by_agent.items())
        if total["groups"] > 1)[:MAX_PARTS]
    observed_calls = sum(part.calls for part in row.cost_parts)
    return record(parts=shown,
        omitted_parts=len(omitted), omitted_ccost=sum((Decimal(part["known_ccost"]) for part in omitted), Decimal(0)),
        omitted_complete=all(part["complete"] for part in omitted),
        omitted_calls=sum(part["calls"] for part in omitted),
        model_count=len({(part.provider_id, part.model_id) for part in row.cost_parts
            if part.provider_id and part.model_id}),
        group_count=len(parts), observed_calls=observed_calls,
        calls_complete=bool(parts) and observed_calls == row.calls and
            (bool(agents) and all(agent.state in {"usage-observed", "not-executed"} for agent in row.agent_coverage)
             or not agents and not missing_agents),
        agents_without_usage=missing_agents,
        missing_agents=missing[:MAX_PARTS], omitted_agents=max(0, len(missing) - MAX_PARTS),
        agent_totals=totals,
        attributed_agents=attributed[:MAX_PARTS],
        linked_agent_count=row.linked_agent_count)


def mini_cost_detail(row):
    missing = sum(agent.state not in {"usage-observed", "not-executed"} for agent in row.agent_coverage)
    if not row.agent_coverage:
        missing = max(0, row.linked_agent_count - len({part.session_id for part in row.cost_parts if part.agent}))
    return (("mini_cost_groups", mini_groups(row.cost_parts, complete=not row.unresolved_cost,
            attribution={index: attribution_label(agent.attribution)
                         for index, agent in enumerate(row.agent_coverage, 1)})),
            ("mini_missing_agents", missing))


def detail_tokens(values):
    detail = values.get("cost_detail")
    if detail is None:
        return {}
    detail = dict(detail.fields)
    attributed_agents = (dict(value.fields) for value in detail.get("attributed_agents", ()))
    attribution = {agent["agent"]: agent["label"] for agent in attributed_agents}
    models, calls, main_models, efforts = [], [], [], []
    for part in detail["parts"]:
        part = dict(part.fields)
        owner = "Main prompt" if part["role"] == "main" else f"Subagent {part['agent']}"
        if label := attribution.get(part["agent"]):
            owner += f" ({label})"
        identity_help = request_model_help(part['provider_id'], part['selected_models'] or (part['model_id'],),
            catalog_model=part['model_id'] if part.get('catalog_estimate') else None)
        identity, _, note = identity_help.partition('\n')
        evidence = [dict(value.fields) for value in part.get("effort_evidence", ())]
        effort = evidence_help(evidence, explicit=part["effort"]) if evidence else part["effort"]
        if effort and effort != "N/A":
            identity += " · " + effort
        if part['role'] == 'main':
            main_models.append('Main model: ' + identity + ('\n' + note if note else ''))
            efforts.append(evidence_help(evidence, value_cell=True, explicit=part["effort"]) if evidence else effort)
        heading = owner + " — " + identity
        call_heading = heading + (" · " + part["price_tier"] if part["price_tier"] else "")
        models.append(heading + ('\n' + note if note else '') +
            ("\n  Effort unreported" if part["effort"] in {None, "", "N/A"} else ""))
        if part['role'] == 'subagents':
            main_models.append(models[-1])
        calls.append(f"{call_heading}: {part['calls']}" + ('\n' + note if note else ''))
    if detail["omitted_parts"]:
        note = f"{detail['omitted_parts']} additional role/model/effort groups not shown"
        models.append(note + f" ({detail['model_count']} distinct models overall)")
        calls.append(note + f": {detail.get('omitted_calls', 0)} calls")
    if not detail['parts'] and values.get('recorded_selections'):
        selection = 'Selected model · no request usage recorded'
        selection += '\n' + '\n'.join('Recorded selection: ' + value for value in values['recorded_selections'])
        selection += '\nUsage unavailable; cost unknown. Selection is not executed-model or contribution proof.'
        models.append(selection)
        main_models.append(selection)
        calls.append(selection + '\nNo request usage recorded; no model calls inferred.')
    for agent in detail.get("missing_agents", ()):
        agent = dict(agent.fields)
        state = {"not-executed": "No model request recorded in complete child history.",
            "pending": "Request acquisition pending; usage and cost unknown.",
            "acquisition-pending": "Partial source acquisition; request usage unavailable."}.get(
                agent["state"], "Request usage unavailable; model/effort unknown.")
        note = f"Subagent {agent['agent']} — {state}"
        models.append(note)
    if detail.get("omitted_agents"):
        note = f"{detail['omitted_agents']} additional linked agents without request evidence not shown."
        models.append(note)
    # Legacy/custom rows may carry only a count. Never invent private identities.
    if detail.get("agents_without_usage") and not detail.get("missing_agents"):
        note = f"{detail['agents_without_usage']} additional linked agents — request usage unavailable; cost unknown."
        models.append(note)
    model_help = "\n\n".join(models)
    if calls:
        calls.append(("Total Calls: " if detail["calls_complete"] else "Observed Calls (incomplete request evidence): ")
            + str(detail["observed_calls"]))
    return {"model_detail_help": model_help,
            "main_model_help": '\n\n'.join(dict.fromkeys(main_models)) or 'Main model identity unrecorded',
            "effort_help": '\n\n'.join(dict.fromkeys(efforts)) or values.get("watch_effort") or "N/A",
            "effort_tooltip": '\n'.join(dict.fromkeys(
                evidence_help([dict(value.fields) for value in dict(part.fields).get("effort_evidence", ())],
                    explicit=dict(part.fields)["effort"]) for part in detail["parts"]
                if dict(part.fields)["role"] == "main")) or values.get("watch_effort") or "N/A",
            "calls_help": "\n".join(calls)}
