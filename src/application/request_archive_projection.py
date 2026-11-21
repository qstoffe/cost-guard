"""Project independent physical usage and causal ownership from one acquisition."""
from decimal import Decimal

from src.analysis.billing import billing_request_fingerprint
from src.analysis.cache import dependency_signature
from src.analysis.valuation import physical_usage_key
from src.cache.display_requests import DisplayRequest, RequestRoster, ROOT_WRITE_LIMIT, TOKEN_FIELDS
from src.domain import CostDisposition
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


def request_roster(snapshot, bundle, reference):
    """Reject unstable or unidentifiable acquisitions, never infer retractions."""
    if (not snapshot.complete or not bundle.cacheable or snapshot.source_revision != bundle.source_revision
            or snapshot.root.session_id != bundle.root_session_id or len(bundle.trace_entries) > ROOT_WRITE_LIMIT):
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
            if len(chosen) + len(attributed) > ROOT_WRITE_LIMIT:
                return None

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
            _key(fingerprint) if fingerprint else None, entry.session_id,
            executing_prompt[1] if executing_prompt is not None else None,
            entry.model.provider, entry.model.model, entry.model.recorded_model, _account(entry),
            tuple(getattr(entry.tokens, field) for field in TOKEN_FIELDS), known,
            entry.reported_cost if has_billing else None, entry.reported_cost_currency if has_billing else None,
            entry.cost_disposition.value, amounts, entry.selected_effort or entry.variant, entry.summary,
        ))
    return RequestRoster(reference.analysis_signature, tuple(requests), tuple(sorted(attributed)))
