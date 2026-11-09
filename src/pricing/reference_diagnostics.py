"""Explain failed reference valuation using the exact acquired catalog only."""
from src.domain.reference_cost import ReferenceCostIssue
from .identities import CONTEXT_MODELS, reference_identity

_RECOGNIZED = CONTEXT_MODELS | {"claude-sonnet-4", "claude-opus-4"}
_CATEGORIES = (("input", "input"), ("cache_read", "cached input"),
               ("cache_write", "cache write"), ("output", "output"))


def reference_issue(catalog, model, tokens):
    missing = [label for name, label in _CATEGORIES if name not in tokens.known_fields]
    if missing:
        return ReferenceCostIssue("usage", detail=", ".join(missing))
    if not catalog.retrieved_at_ms or not catalog.source_revision or catalog.reference_stale:
        return ReferenceCostIssue("catalog")
    native = catalog.resolve_reference(model.model)
    if native is None:
        if model.model not in catalog._issue_identity_memo:
            catalog._issue_identity_memo[model.model] = unmatched_issue(catalog, model.model)
        return catalog._issue_identity_memo[model.model]
    prices = catalog.reference_prices(model.model)
    tier = prices.selected_tier(tokens.input + tokens.cache_read + tokens.cache_write)
    if tier is None:
        return ReferenceCostIssue("rate", detail="selected tier")
    missing_rates = [label for name, label in (("input", "input"), ("cache_read", "cached input"), ("output", "output"))
                     if getattr(tier, "per_million_" + name) is None]
    return ReferenceCostIssue("rate", detail=", ".join(missing_rates)) if missing_rates else ReferenceCostIssue("unknown")


def unmatched_issue(catalog, model_id):
    # Only recognized, explicit version identities can prove list absence.
    # Unknown aliases/variants and duplicate catalog matches remain uncertain.
    raw = model_id.split("/", 1)[-1].lower()
    identity = reference_identity(raw)
    candidates = [item for item in catalog.models if identity in {
        reference_identity(item.model.model), reference_identity(item.model.display_name or "")}]
    if raw in _RECOGNIZED and not candidates:
        label = raw.replace("claude-", "Claude ").replace("sonnet-", "Sonnet ").replace("opus-", "Opus ").replace("haiku-", "Haiku ")
        return ReferenceCostIssue("model_absent", label.replace("-", "."))
    return ReferenceCostIssue("identity")
