"""Bounded Web Sessions model facts from canonical executed request evidence."""
from dataclasses import dataclass

from src.analysis.effort_defaults import request_effort
from src.analysis.valuation import unique_usage
from src.domain.effort import EffortEvidence
from src.domain.model_identity import catalog_display_name
from src.domain.session_tree import root_by_session

LIMIT = 64


@dataclass(frozen=True, slots=True)
class SessionModel:
    provider: str
    model: str
    catalog_model: str = ""
    efforts: tuple[EffortEvidence, ...] = ()


def _identity(entry):
    provider, model = entry.model.provider, entry.model.recorded_model
    if (provider and model and len(provider) <= 128 and len(f"{provider}/{model}") <= 256
            and provider.isprintable() and model.isprintable() and model != "N/A"):
        return provider, model
    return None


def _executed(entry):
    # A failed zero-usage selection alone does not establish a dispatched model.
    return not entry.error_name or entry.tokens.total > 0 or entry.reported_cost > 0


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
                and ref.model.isprintable() else "", tuple(efforts))
            for (provider, model), (ref, efforts) in groups[role].items())

    return dict(model=model, multiple_models=len(identities) > 1,
        contributor_models=tuple(sorted(f"{provider}/{model}" for provider, model in accepted)),
        contributor_models_complete=complete, main_models=parts("main"), subagent_models=parts("subagent"),
        model_pending=latest is None and any(p.in_progress for p in prompts))


def decode_models(values):
    return tuple(SessionModel(part["provider"], part["model"], part["catalog_model"],
        tuple(EffortEvidence(**e) for e in part["efforts"])) for part in values)


def valid_models(values):
    """Reject malformed/old role claims, rather than promote undifferentiated IDs."""
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
                    or len(part.efforts) > 4 or any(
                        e.selected is not None and (not isinstance(e.selected, str) or len(e.selected) > 64
                            or e.selected and not e.selected.isprintable())
                        or any(not isinstance(t, str) or len(t) > 256 or t and not t.isprintable()
                               for t in (e.effective, e.source, e.revision)) for e in part.efforts)):
                return False
            union.add(identity)
    return (tuple(sorted(union)) == values["contributor_models"]
        and values["multiple_models"] == (len(union) > 1)
        and (values["model"] == "N/A" or bool(values["main_models"])))
