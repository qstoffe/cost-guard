"""Shared historical grouping; provider routes are not publisher identities."""
from src.pricing.identities import reference_identity, unverified_alias
from src.pricing.publishers import model_publisher, token_mix_publisher


UNKNOWN_PUBLISHER = "Unknown / unverified"


def history_model_key(model):
    if unverified_alias(model.model, model.provider):
        return f"{model.provider.lower()}/{reference_identity(model.model)}"
    return reference_identity(model.model) or (model.model or "").lower()


def history_reference_model(model, reference):
    return None if unverified_alias(model.model, model.provider) else reference.resolve_reference(model.model)


def history_publisher(model, matched, *, web):
    name = token_mix_publisher(model, matched) if web else model_publisher(matched)
    return name or UNKNOWN_PUBLISHER


def web_model_label(model, matched):
    if matched:
        return matched.model.display_name or matched.model.model
    if unverified_alias(model.model, model.provider):
        return model.recorded_model
    return model.display_name or model.recorded_model
