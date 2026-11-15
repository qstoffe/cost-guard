"""AI Stats presentation only: friendly models and selected-effort contributions."""
import re

from src.domain.model_identity import catalog_display_name, unverified_alias
from .effort_defaults import request_effort

EFFORT_ORDER = ('Default', 'Low', 'Medium', 'High', 'XHigh', 'Max', 'Other')


def catalog_label(item, catalog):
    name = item.model.display_name or readable_model(item.model.model)
    collisions = [other for other in catalog.models
                  if other.model.display_name == name and other.model.model != item.model.model]
    if collisions:
        # Catalog release/manufacturer words, not transport routes or hash suffixes.
        return readable_model(item.model.model)
    return name


def readable_model(identity):
    label = identity.split('/')[-1].removesuffix(' (version unverified)')
    label = re.sub(r'(?:[ ·_-]+)?[a-f0-9]{12,}$', '', label, flags=re.I)
    if re.fullmatch(r'[a-f0-9-]{32,}', label, re.I):
        return 'Other model'
    match = re.fullmatch(r'claude-(sonnet|opus|haiku|fable)-(\d+(?:[.-]\d+)*)', label, re.I)
    if match:
        return f'Claude {match[1].title()} {match[2].replace("-", ".")}'
    return label.strip(' ·_-') or 'Other model'


def friendly_model(model, catalog=None):
    recorded = model.recorded_model
    alias = unverified_alias(recorded, model.provider)
    # A recorded release always wins over a mutable source catalog estimate.
    identity = model.model if alias and model.resolution else recorded
    if catalog:
        exact = catalog.resolve_reference(identity)
        if exact:
            return catalog_label(exact, catalog)
        family = re.fullmatch(r'(?:claude-)?(sonnet|opus|haiku|fable)(?:-latest)?(?:\[1m\])?',
                              recorded.lower()) if alias else None
        if family and alias.startswith('Claude '):
            candidates = [item for item in catalog.models if re.fullmatch(
                rf'claude-{family[1]}-\d+(?:[.-]\d+)*', item.model.model, re.I)]
            if candidates:
                latest = max(candidates, key=lambda item: (
                    tuple(map(int, re.findall(r'\d+', item.model.model))), item.model.model))
                return catalog_label(latest, catalog)
    if alias and identity == recorded:
        return alias.removesuffix(' (version unverified)')
    label = catalog_display_name(model.provider, model.display_name) if model.display_name else identity
    # Unknown selections get a compact family/name, never source scope or hashes.
    return readable_model(label)


def model_key(entry):
    return friendly_model(entry.model)


def selected_effort(entry):
    selected = request_effort(entry).selected
    if selected is None:
        return 'Other'
    value = selected.strip().lower()
    if not value or value == 'default':
        return 'Default'
    return {'xhigh': 'XHigh', 'x-high': 'XHigh'}.get(value, value.title())


def effort_values(values):
    """Sort on unrounded metric values; readable order breaks ties."""
    return tuple(sorted(values.items(), key=lambda item: (
        -item[1], EFFORT_ORDER.index(item[0]) if item[0] in EFFORT_ORDER else len(EFFORT_ORDER), item[0])))


def providers(entries):
    return ' + '.join(sorted({entry.model.provider for entry in entries}))
