"""One canonical causal child shared by backend and real cross-view DOM checks."""
from dataclasses import replace

from .session_snapshots import make_uncompacted_snapshot
from src.domain import ModelRef


def model_details_snapshot(case):
    snapshot = make_uncompacted_snapshot()
    child = case in {"child-same", "child-effort", "child-model", "running-child", "unknown-main"}
    messages = tuple(replace(message, parts=()) if message.message_id == "a_sub" and not child
                     else message for message in snapshot.messages if child or message.session_id == "root")
    requests = []
    for request in snapshot.invocations:
        if not child and request.session_id != "root":
            continue
        model, effort = request.model, "high"
        if request.session_id == "child":
            effort = "max" if case == "child-effort" else "high"
            if case == "child-model":
                model = ModelRef("github-copilot", "claude-test")
            if case == "running-child":
                continue
        if request.invocation_id == "i_syn":
            if case == "main-models":
                model = ModelRef("github-copilot", "claude-test")
            if case == "main-efforts":
                effort = "max"
        if case == "separate-efforts" and request.invocation_id == "i_next":
            effort = "max"
        if case == "unknown-main" and request.session_id == "root":
            continue
        requests.append(replace(request, model=model, variant=effort))
    if case == "running-child":
        messages = tuple(replace(message, completed_at_ms=None, finish_reason=None)
                         if message.message_id == "ca" else message for message in messages)
    return replace(snapshot, sessions=snapshot.sessions if child else (snapshot.root,),
        messages=messages, parts=tuple(part for message in messages for part in message.parts),
        events=tuple(replace(event, metadata={**event.metadata,
            "variant": "max" if case == "separate-efforts" and event.event_id == "u_next" else "high"})
            for event in snapshot.events if child or event.session_id == "root"),
        invocations=tuple(requests), source_revision=f"model-details-{case}")


def scoped_snapshot(case, root_id, snapshot=None):
    """Independent histories must not masquerade as deletion of acquired requests."""
    snapshot = snapshot or model_details_snapshot(case)
    ids = {session.session_id: root_id if session.session_id == snapshot.root.session_id else root_id + "-child"
           for session in snapshot.sessions}

    def linked(value):
        if isinstance(value, dict):
            return {key: linked(part) for key, part in value.items()}
        if isinstance(value, list):
            return [linked(part) for part in value]
        return ids.get(value, value) if isinstance(value, str) else value

    def owned(value):
        return replace(value, session_id=ids[value.session_id],
                       provenance=replace(value.provenance, source_session_id=ids[value.session_id]))

    sessions = tuple(replace(owned(session),
        parent_session_id=ids.get(session.parent_session_id)) for session in snapshot.sessions)
    messages = []
    for message in snapshot.messages:
        parts = tuple(replace(owned(part), data=linked(part.data)) for part in message.parts)
        messages.append(replace(owned(message), parts=parts))
    return replace(snapshot, root=sessions[0], sessions=sessions, messages=tuple(messages),
        parts=tuple(part for message in messages for part in message.parts),
        events=tuple(owned(event) for event in snapshot.events),
        invocations=tuple(owned(request) for request in snapshot.invocations))
