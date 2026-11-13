"""Bounded selected-effort facts from actual session-tree request contributors."""
from collections import Counter
from dataclasses import dataclass

from src.analysis.effort_defaults import request_effort
from src.analysis.valuation import unique_usage
from src.domain.effort import EffortEvidence


@dataclass(frozen=True, slots=True)
class SessionEffort:
    provider: str
    model: str
    evidence: EffortEvidence
    requests: int


def effort_name(selected):
    return {"xhigh": "XHigh"}.get(selected, selected.capitalize())


def effort_fields(item):
    groups, selections = Counter(), set()
    unknown = False
    for entry in unique_usage(item.bundle.trace_entries):
        if not entry.tokens.total:
            continue  # Saved/failed zero-usage selections are not executed usage.
        evidence = request_effort(entry)
        selected = evidence.selected
        if (selected is None or not entry.model.provider or not entry.model.recorded_model
                or len(selected) > 64 or not selected.isprintable() and selected):
            unknown = True
            continue
        selections.add((selected.strip() or "default").casefold())
        groups[entry.model.provider, entry.model.recorded_model, evidence] += 1
    selected = next(iter(selections)) if len(selections) == 1 else "multiple" if selections else None
    qualified = item.snapshot is not None and item.snapshot.complete
    key = None if unknown or not qualified else selected
    contributors = tuple(SessionEffort(provider[:128], model[:256], evidence, count)
        for (provider, model, evidence), count in groups.items())[:24]
    return dict(effort="N/A" if key is None else "Multiple efforts" if key == "multiple" else effort_name(key),
        effort_key=key, effort_contributors=contributors, effort_details_complete=len(groups) <= 24 and not unknown,
        effort_qualified=qualified,
        effort_pending=not item.bundle.trace_entries and any(record.in_progress for record in item.bundle.prompts))
