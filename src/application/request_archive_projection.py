"""Project independent physical usage and causal ownership from one acquisition."""
from decimal import Decimal

from src.analysis.billing import billing_request_fingerprint
from src.analysis.cache import dependency_signature
from src.analysis.valuation import physical_usage_key
from src.cache.display_prompts import DisplayPrompt
from src.cache.display_requests import DisplayRequest, RequestRoster, ROOT_WRITE_LIMIT, TOKEN_FIELDS
from src.domain import CostDisposition
from src.reports.prompts import build_prompt_block
from src.reports.token_mix_history import history_prompt_keys


def _key(value):
    return bytes.fromhex(dependency_signature(value))


def _account(entry):
    if entry.account_ref is None:
        return None
    try:
        return _key(entry.account_ref.key)
    except ValueError:  # An unbound label is never attribution evidence.
        return None


def display_prompt(row, kind):
    if row.in_progress or row.execution_unverified:
        outcome = "unverified"  # No live state can survive process restart.
    elif row.watch_error:
        outcome = "failed"
    elif row.aborted:
        outcome = "aborted"
    elif row.completed_successfully:
        outcome = "finished"
    else:
        outcome = "unknown"
    cost = row.ccost if row.comparison_cost.observed_requests or not row.unresolved_cost else None
    mix = ",".join(map(str, row.token_mix_percent)) if row.token_mix_percent is not None else None
    return DisplayPrompt(
        row.event_id, row.at_ms or None, row.completed_at_ms, row.duration_ms, kind, row.prompt_number,
        next((name for name in (row.watch_model, row.model_effort) if name and name != "N/A"), None),
        row.watch_effort if row.watch_effort and row.watch_effort != "N/A" else None,
        row.calls, row.incoming_context_tokens, cost, not row.unresolved_cost,
        row.incoming_context_ccost if row.incoming_context_ccost_known else None,
        row.extra_ccost if row.extra_ccost_known else None, mix, outcome,
    )


def _qualified_tree_members(snapshot):
    """Only an observed path from a top-level root qualifies a fork tree."""
    root = snapshot.root
    if root.parent_session_id is not None:
        return set()
    children = {}
    for session in snapshot.sessions:
        if session.parent_session_id is not None:
            children.setdefault(session.parent_session_id, []).append(session.session_id)
    members = {root.session_id}
    pending = [root.session_id]
    while pending:
        for child in children.get(pending.pop(), ()):
            if child not in members:
                members.add(child)
                pending.append(child)
    return members


def request_roster(snapshot, bundle, reference, *, config=None):
    """Reject unstable or unidentifiable acquisitions, never infer retractions."""
    prompt_count = len(bundle.prompts) + len(bundle.compactions) if config is not None else 0
    if (not snapshot.complete or not bundle.cacheable or snapshot.source_revision != bundle.source_revision
            or snapshot.root.session_id != bundle.root_session_id
            or len(bundle.trace_entries) + prompt_count > ROOT_WRITE_LIMIT):
        return None
    prompts = history_prompt_keys(bundle)
    chosen, keys = {}, {}
    for entry in bundle.trace_entries:
        identity = physical_usage_key(entry)
        if identity is None:
            return None
        key = keys[entry] = _key(identity)
        # Repeated capture within one tree does not make another request.
        previous = chosen.get(key)
        if previous is None or (len(entry.tokens.known_fields), entry.completed_at_ms) >= (
                len(previous.tokens.known_fields), previous.completed_at_ms):
            chosen[key] = entry

    attributed = set()
    for prompt in bundle.prompts:
        for entry in prompt.entries:
            identity = physical_usage_key(entry)
            key = keys.get(entry) or (_key(identity) if identity is not None else None)
            if key not in chosen:  # Copied or missing evidence is not a physical request.
                return None
            attributed.add((key, prompt.prompt_id))
            if len(chosen) + len(attributed) + prompt_count > ROOT_WRITE_LIMIT:
                return None

    tree_members = _qualified_tree_members(snapshot)
    requests = []
    for key, entry in chosen.items():
        known = sum(1 << index for index, name in enumerate(TOKEN_FIELDS) if name in entry.tokens.known_fields)
        amounts = (Decimal(0),) * 4 if known & 0b1111 == 0b1111 and not entry.tokens.total else (
            reference.reference_category_valuation(entry.model, entry.tokens))
        if amounts is not None and (len(amounts) != 4 or any(not value.is_finite() or value < 0 for value in amounts)):
            return None
        fingerprint = billing_request_fingerprint(entry)
        executing_prompt = prompts.get(entry)
        has_billing = (entry.cost_disposition in {CostDisposition.BILLED, CostDisposition.INCLUDED_SUBSCRIPTION}
                       and entry.reported_cost_currency is not None)
        requests.append(DisplayRequest(
            key, entry.completed_at_ms if entry.completed_at_ms > 0 else None,
            _key((entry.source_instance, fingerprint)) if fingerprint else None, entry.session_id,
            executing_prompt[1] if executing_prompt is not None else None,
            entry.model.provider, entry.model.model, entry.model.recorded_model, _account(entry),
            tuple(getattr(entry.tokens, field) for field in TOKEN_FIELDS), known,
            entry.reported_cost if has_billing else None, entry.reported_cost_currency if has_billing else None,
            entry.cost_disposition.value, amounts, entry.selected_effort or entry.variant, entry.summary,
            snapshot.root.session_id if entry.session_id in tree_members else None,
            entry.sort_order,
        ))
    detail = () if config is not None else None
    if config is not None and prompt_count:
        block = build_prompt_block(session_id=snapshot.root.session_id, title=snapshot.root.title,
                                   bundle=bundle, snapshot=snapshot, catalog=reference, config=config)
        kinds = {row.prompt_id: row.prompt_kind for row in bundle.prompts}
        detail = tuple(display_prompt(row, "compaction" if row.is_compaction else kinds.get(row.event_id, "prompt"))
                       for row in block.rows)
        if any(not row.event_id for row in detail) or len({row.event_id for row in detail}) != len(detail):
            return None
    return RequestRoster(reference.analysis_signature, tuple(requests), tuple(sorted(attributed)), detail)
