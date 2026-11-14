"""Revision-owned historical activity over the detail lane's existing snapshot.

Only safe detached values cross HTTP. No source reads on expansion, no Watch
card retention/caps, and no totals inferred from a partially transferred table.
"""
from collections.abc import Mapping

from src.domain.progress import observe_work
from src.reports.session_history import SessionHistory
from src.watch.invocation import terminal_invocation
from src.watch.tools import classified_name, observe_tools, session_calls, tool_outcome
from src.watch.tool_contracts import (
    is_skill_tool, skill_tool_id, verified_skill_origin,
)
from .projection import identity

PAGE_SIZE = 25


class ActivityHistory(SessionHistory):
    """Application-owned safe projection cache, invalidated by canonical identity."""
    def __init__(self):
        super().__init__()
        self.activity_snapshot = None
        self.activity = None

    def activity_for(self, source, rows):
        if self.snapshot is not self.activity_snapshot:
            self.activity = build_activity(self.snapshot, source, rows)
            self.activity_snapshot = self.snapshot
        return self.activity


def build_activity(snapshot, source, rows=()):
    if snapshot is None:
        return None
    physical = session_calls(snapshot)
    lookup = getattr(source, "skill_origins_for_session", None)
    origins = {}
    for part in physical:
        if callable(lookup) and is_skill_tool(part.data) and skill_tool_id(part.data):
            if part.session_id not in origins:
                origins[part.session_id] = lookup(part.session_id)
    observation = observe_tools(snapshot, "", session_wide=True, skill_origins_by_session=origins)
    owners = {(message.session_id, message.message_id): message.parent_message_id for message in snapshot.messages}
    events = {(event.session_id, event.event_id) for event in snapshot.events}
    numbers = {row.event_id: row.prompt_number for row in rows}
    records, unavailable = [], 0
    for part in physical:
        outcome = tool_outcome(part)
        if outcome not in {"error", "cancelled"}:
            continue
        name = classified_name(part, origins)
        detail = terminal_invocation(name, "failed" if outcome == "error" else outcome,
                                     part, snapshot.root.provenance)
        if detail is None:
            unavailable += 1
        else:
            parent = owners.get((part.session_id, part.message_id))
            # IDs, not previews/titles or arbitrary source labels, identify owners.
            detail["owner"] = ("Root agent" if part.session_id == snapshot.root.session_id else "Linked agent")
            detail["agent_id"] = identity((part.session_id,))
            detail["prompt_id"] = (identity((part.session_id, parent))
                                   if (part.session_id, parent) in events else None)
            detail["prompt_number"] = numbers.get(parent) if part.session_id == snapshot.root.session_id else None
            state = part.data.get("state")
            status = str(state.get("status") or "").lower() if isinstance(state, Mapping) else ""
            detail["recorded_status"] = status if status in {"error", "completed", "cancelled", "interrupted"} else "unavailable"
            records.append(detail)
        observe_work("publishing", 1)
    return dict(scope=identity((snapshot.root.provenance.source_type,
        snapshot.root.provenance.source_generation, snapshot.root.provenance.source_instance,
        getattr(source, "observation_epoch", None), snapshot.root.session_id)), complete=snapshot.complete,
        counts=observation.tool_counts, failed_count=observation.failed_count,
        failed_or_cancelled_count=observation.failed_or_cancelled_count,
        outcomes=tuple(dict(tool_name=item.tool_name, outcome=item.outcome, count=item.count)
                       for item in observation.tool_outcomes),
        skills=tuple(dict(skill_id=item.skill_id, failed_count=item.failed_count) for item in observation.skills),
        skills_partial=any(is_skill_tool(part.data) and
            not verified_skill_origin(origins.get(part.session_id, {}).get(skill_tool_id(part.data)))
            for part in physical),
        failures=tuple(records), unavailable=unavailable)


def activity_page(activity, offset=0):
    if activity is None:
        return None
    return dict(offset=offset, total=len(activity["failures"]),
                failures=activity["failures"][offset:offset + PAGE_SIZE])


def activity_summary(activity):
    if activity is None:
        return None
    return {**{key: value for key, value in activity.items() if key != "failures"},
            **activity_page(activity)}
