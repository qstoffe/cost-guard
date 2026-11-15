"""Shared Web marker facts from executed requests and canonical causal links."""
from src.analysis.effort_defaults import request_effort
from src.analysis.valuation import unique_usage


def executed(entry):
    # A failed zero-usage selection alone does not establish dispatched work.
    return not entry.error_name or entry.tokens.total > 0 or entry.reported_cost > 0


def model_identity(entry):
    provider, model = entry.model.provider, entry.model.recorded_model
    if (provider and model and len(provider) <= 128 and len(f"{provider}/{model}") <= 256
            and provider.isprintable() and model.isprintable() and model != "N/A"):
        return provider, model
    return None


def selected_effort(selected):
    if selected is None or len(selected) > 64 or selected and not selected.isprintable():
        return None
    return (selected.strip() or "default").casefold()


def linked_agents(record):
    return set(record.linked_session_ids) | {
        entry.session_id for entry in record.entries[record.root_entry_count:]
        if entry.session_id != record.session_id and executed(entry)}


def has_model_details(entries, agent_count=0):
    identities, efforts = set(), set()
    for entry in unique_usage(entries):
        if not executed(entry):
            continue
        identity = model_identity(entry)
        if identity is not None:
            identities.add(identity)
            effort = selected_effort(request_effort(entry).selected)
            if effort is not None:
                efforts.add(effort)
    return bool(agent_count or len(identities) > 1 or len(efforts) > 1)
