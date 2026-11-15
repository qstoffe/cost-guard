"""Display-only prompt-bound selection; never request or contribution evidence."""
from src.domain import ModelRef
from src.domain.model_identity import catalog_display_name


def selected_model(record, replies):
    matches = [message for message in replies.get((record.session_id, record.prompt_id), ())
               if message.model.provider and message.model.recorded_model]
    if matches:
        return max(matches, key=lambda message: (message.created_at_ms, message.message_id)).model
    return ModelRef(record.main_provider_id, record.main_model_id) if record.main_provider_id and record.main_model_id else None


def selection_variant(record, replies, model):
    matches = [message for message in replies.get((record.session_id, record.prompt_id), ())
               if message.model == model]
    latest = max(matches, key=lambda message: (message.created_at_ms, message.message_id), default=None)
    if latest is not None and latest.variant:
        return latest.variant
    return (record.main_variant or "") if (record.main_provider_id, record.main_model_id) == (model.provider, model.model) else ""


def selection_name(model, catalog):
    return catalog_display_name(model.provider, model.display_name if model.resolution and model.display_name
                                else catalog.display_name(model.model, model.provider))
