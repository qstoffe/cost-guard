"""Request identity copy from recorded selectors, never labels or pricing guesses."""
from src.domain.model_identity import CATALOG_ESTIMATE_HELP


def request_model_help(provider, recorded, *, catalog_model=None):
    identities = tuple(sorted({f'{provider}/{model}' for model in recorded if provider and model}))
    text = ', '.join(identities[:64]) or 'Unrecorded model — provider/model identity unavailable'
    if len(identities) > 64:
        text += f'\n{len(identities) - 64} additional recorded selections not shown.'
    if catalog_model:
        text += f'\nCatalog modelID: {catalog_model}\n{CATALOG_ESTIMATE_HELP}'
    return text


def session_model_tokens(values):
    if 'contributor_models' not in values:
        return {}
    models = values['contributor_models']
    text = '\n'.join(models) or 'Contributing model identities are not available.'
    if not values.get('contributor_models_complete'):
        text += '\nObserved so far; contributing model coverage may be incomplete.'
    return {'model_help': text}
