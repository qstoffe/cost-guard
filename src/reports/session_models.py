"""Bounded Web Sessions model facts from canonical executed request evidence."""
from dataclasses import dataclass

from src.analysis.effort_defaults import request_effort
from src.analysis.effort import prompt_replies
from src.analysis.valuation import unique_usage
from src.domain.effort import EffortEvidence
from src.domain.model_identity import catalog_display_name
from src.domain.session_tree import root_by_session
from .model_details import executed as _executed, model_identity as _identity, has_model_details, linked_agents, selected_effort
from .prompt_selection import selected_model, selection_name, selection_variant

LIMIT = 64


@dataclass(frozen=True, slots=True)
class SessionModel:
    provider: str
    model: str
    catalog_model: str = ""
    efforts: tuple[EffortEvidence, ...] = ()
    display_model: str = ""


def model_fields(item, catalog):
    """Never hydrate or use saved prompt selections as evidence of execution.

    The latest *prompt* wins, not the latest completed child/compaction request.
    Child roles require same-root ancestry (or positive compact prompt links).
    """
    root = item.session.session_id
    snapshot = item.snapshot
    ancestry = root_by_session(snapshot.sessions) if snapshot is not None else {}
    linked = {sid for prompt in item.bundle.prompts for sid in prompt.linked_session_ids}
    entries = sorted(unique_usage(item.bundle.trace_entries), key=lambda e: (e.completed_at_ms, e.sort_order))
    scoped = [entry for entry in entries if entry.session_id == root
              or ancestry.get(entry.session_id) == root or entry.session_id in linked]
    agents = {sid for prompt in item.bundle.prompts for sid in linked_agents(prompt)}
    agents.update(entry.session_id for entry in scoped if entry.session_id != root and _executed(entry))
    groups = {"main": {}, "subagent": {}}
    identities, accepted = set(), set()
    complete = bool(snapshot is not None and snapshot.complete
        and snapshot.source_revision == item.bundle.source_revision
        and not any(p.in_progress or p.execution_unverified for p in item.bundle.prompts)
        and not any(c.in_progress for c in item.bundle.compactions))
    for entry in entries:
        if not _executed(entry):
            complete = False
            continue
        if entry.session_id != root and not (ancestry.get(entry.session_id) == root or entry.session_id in linked):
            complete = False
            continue
        identity = _identity(entry)
        if identity is None:
            complete = False
            continue
        identities.add(identity)
        if identity not in accepted and len(accepted) >= LIMIT:
            complete = False
            continue
        accepted.add(identity)
        role = "main" if entry.session_id == root else "subagent"
        group = groups[role]
        if identity not in group:
            group[identity] = (entry.model, [])
        efforts = group[identity][1]
        evidence = request_effort(entry)
        if (evidence.selected is not None and (len(evidence.selected) > 64
                or evidence.selected and not evidence.selected.isprintable())
                or any(len(text) > 256 or text and not text.isprintable()
                       for text in (evidence.effective, evidence.source, evidence.revision))):
            complete = False
            continue
        if evidence not in efforts:
            if len(efforts) < 4:
                efforts.append(evidence)
            else:
                complete = False

    latest = None
    prompts = sorted((p for p in item.bundle.prompts if p.session_id == root and p.prompt_kind != "subtask"),
                     key=lambda p: (p.prompt_time_ms, p.prompt_id))
    for prompt in prompts:
        used = [entry for entry in prompt.entries if entry.session_id == root and not entry.summary
                and _executed(entry) and _identity(entry)]
        if used:
            latest = max(used, key=lambda e: (e.completed_at_ms, e.sort_order))
        else:
            complete = False  # A later saved/pending action is not confirmed usage.
    model = "N/A"
    if latest is not None:
        ref = latest.model
        model = catalog_display_name(ref.provider, ref.display_name if ref.resolution and ref.display_name
                                     else catalog.display_name(ref.model, ref.provider))
    if latest is None:
        complete = False

    def parts(role):
        return tuple(SessionModel(provider, model,
            ref.model if ref.resolution and ref.model != model and len(ref.model) <= 256
                and ref.model.isprintable() else "", tuple(efforts), selection_name(ref, catalog))
            for (provider, model), (ref, efforts) in groups[role].items())

    selection = None
    variant = ""
    if (latest is None and prompts and snapshot is not None
            and snapshot.source_revision == item.bundle.source_revision
            and snapshot.root.provenance == item.session.provenance):
        replies = prompt_replies(snapshot)
        selection = selected_model(prompts[-1], replies)
        if selection is not None:
            variant = selection_variant(prompts[-1], replies, selection)
            texts = (selection.provider, f"{selection.provider}/{selection.recorded_model}",
                     selection_name(selection, catalog), variant)
            if any(len(text) > limit or text and not text.isprintable()
                   for text, limit in zip(texts, (128, 256, 256, 64))):
                selection = None
    return dict(model=model, multiple_models=len(identities) > 1,
        selected_display_model=selection_name(selection, catalog) if selection else "",
        selected_model_id=f"{selection.provider}/{selection.recorded_model}" if selection else "",
        selected_effort=variant if selection else "",
        has_model_details=has_model_details(scoped, len(agents)), linked_agent_count=len(agents),
        contributor_models=tuple(sorted(f"{provider}/{model}" for provider, model in accepted)),
        contributor_models_complete=complete, main_models=parts("main"), subagent_models=parts("subagent"),
        model_pending=latest is None and selection is None and any(p.in_progress for p in prompts))


def decode_models(values):
    return tuple(SessionModel(part["provider"], part["model"], part["catalog_model"],
        tuple(EffortEvidence(**e) for e in part["efforts"]), part["display_model"]) for part in values)


def valid_models(values):
    """Reject malformed/old role claims, rather than promote undifferentiated IDs."""
    selection = values["selected_display_model"]
    identity = values["selected_model_id"]
    effort = values["selected_effort"]
    if (any(not isinstance(text, str) or len(text) > limit or text and not text.isprintable()
            for text, limit in ((selection, 256), (identity, 256), (effort, 64)))
            or bool(selection) != bool(identity)
            or identity and (not all(identity.partition("/")[::2]) or values["model"] != "N/A")
            or effort and not identity):
        return False
    union = set()
    for role in ("main_models", "subagent_models"):
        parts = values[role]
        identities = [(part.provider, part.model) for part in parts]
        if len(parts) > LIMIT or len(set(identities)) != len(parts):
            return False
        for part in parts:
            identity = f"{part.provider}/{part.model}"
            if (not part.provider or not part.model or len(part.provider) > 128 or len(identity) > 256
                    or not identity.isprintable() or part.model == "N/A"
                    or not isinstance(part.catalog_model, str) or len(part.catalog_model) > 256
                    or part.catalog_model and not part.catalog_model.isprintable()
                    or not isinstance(part.display_model, str) or len(part.display_model) > 256
                    or part.display_model and not part.display_model.isprintable()
                    or len(part.efforts) > 4 or any(
                        e.selected is not None and (not isinstance(e.selected, str) or len(e.selected) > 64
                            or e.selected and not e.selected.isprintable())
                        or any(not isinstance(t, str) or len(t) > 256 or t and not t.isprintable()
                               for t in (e.effective, e.source, e.revision)) for e in part.efforts)):
                return False
            union.add(identity)
    return (tuple(sorted(union)) == values["contributor_models"]
        and values["multiple_models"] == (len(union) > 1)
        and type(values["linked_agent_count"]) is int and values["linked_agent_count"] >= 0
        and values["has_model_details"] == bool(values["linked_agent_count"] or len(union) > 1 or len({
            selected_effort(e.selected) for role in ("main_models", "subagent_models")
            for part in values[role] for e in part.efforts if selected_effort(e.selected) is not None}) > 1)
        and (values["model"] == "N/A" or bool(values["main_models"])))
