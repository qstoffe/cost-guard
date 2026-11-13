"""Compact identity codecs and source-neutral mutable-dependency admission."""
from dataclasses import asdict

from src.domain import ModelRef
from src.domain.model_identity import ModelResolution
from src.domain.effort import DefaultEffort


def encode_model(model):
    value = dict(provider=model.provider, model=model.model, display_name=model.display_name)
    if model.resolution is not None:
        value['resolution'] = asdict(model.resolution)
    if model.effort_default is not None:
        value['effort_default'] = asdict(model.effort_default)
    return value


def decode_model(value):
    value = dict(value)
    resolution = value.pop('resolution', None)
    effort = value.pop('effort_default', None)
    return ModelRef(**value, resolution=ModelResolution(**resolution) if resolution else None,
        effort_default=DefaultEffort(**effort) if effort else None)


def dependencies(entries):
    models = {(entry.model, entry.model.effort_default): entry.model for entry in entries}
    return [encode_model(model) for model in models.values()
             if model.resolution is not None or model.effort_default is not None]


def current(source, models):
    values = tuple(models)
    validate = getattr(source, 'model_identities_current', None)
    return validate(values) if callable(validate) else not any(model.resolution is not None for model in values)


def payload_current(source, values):
    return current(source, (decode_model(value) for value in values))
