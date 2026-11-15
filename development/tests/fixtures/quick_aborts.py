"""Two synthetic same-minute cancellations; no private session or picker state."""
from dataclasses import replace

from development.tests.fixtures.session_snapshots import one_request
from src.domain import EventKind, NormalizedEvent
from src.sources.opencode_v2_normalization import normalize_invocations, normalize_message_bundle
from src.sources.opencode_v2_wire import current_union_message_to_legacy_bundle


def quick_aborts(*, generation="v2", second_model=True, assistant_model=False, running=False):
    base = one_request(running=False)
    root = replace(base.root, active=running,
        provenance=replace(base.root.provenance, source_generation=generation))
    provenance = lambda sid, eid=None: replace(root.provenance, source_session_id=sid, source_event_id=eid)
    messages, events = [], []
    for index, at in enumerate((2000, 2400)):
        uid, aid = f"abort-u{index}", f"abort-a{index}"
        selection = dict(providerID="github-copilot", modelID="claude-sonnet-5-5", variant="low") if not index or second_model else {}
        if generation == "v2":
            raw = dict(id=aid, type="assistant", time={"created": at + 1, "completed": at + 100},
                content=[], error={"name": "MessageAbortedError"})
            if assistant_model and selection:
                raw["model"] = dict(providerID=selection["providerID"], id=selection["modelID"], variant="low")
            bundle = current_union_message_to_legacy_bundle(raw, session={"id": root.session_id}, ordinal=index)
            bundle["info"]["parentID"] = uid
        else:
            bundle = dict(info=dict(id=aid, sessionID=root.session_id, parentID=uid, role="assistant",
                time={"created": at + 1, "completed": at + 100}, error={"name": "MessageAbortedError"}), parts=[])
            if assistant_model and selection:
                bundle["info"].update(providerID=selection["providerID"], modelID=selection["modelID"], variant="low")
        if running and index:
            bundle["info"]["time"].pop("completed", None)
            bundle["info"].pop("error", None)
        message, _ = normalize_message_bundle(bundle, provenance)
        messages.append(message)
        events.append(NormalizedEvent(uid, root.session_id, EventKind.USER_PROMPT, at,
            provenance(root.session_id, uid), f"Synthetic prompt {index + 1}",
            metadata=dict(provider_id=selection["providerID"], model_id=selection["modelID"], variant="low") if selection else {}))
    invocations = tuple(inv for message in messages for inv in normalize_invocations(message, provenance))
    return replace(base, root=root, sessions=(root,), messages=tuple(messages), parts=(), events=tuple(events),
        invocations=invocations, complete=True, source_revision=f"quick-{generation}-{second_model}-{assistant_model}-{running}")
