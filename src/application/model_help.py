"""Request identity copy from recorded selectors, never labels or pricing guesses."""
from src.domain.model_identity import CATALOG_ESTIMATE_HELP
from .effort_help import effort_help


def request_model_help(provider, recorded, *, catalog_model=None):
    identities = tuple(sorted({f'{provider}/{model}' for model in recorded if provider and model}))
    text = ', '.join(identities[:64]) or 'Unrecorded model — provider/model identity unavailable'
    if len(identities) > 64:
        text += f'\n{len(identities) - 64} additional recorded selections not shown.'
    if catalog_model:
        text += f'\nCatalog modelID: {catalog_model}\n{CATALOG_ESTIMATE_HELP}'
    return text


def session_model_tokens(values):
    if 'model_help' in values:
        return {'model_help': values['model_help']}
    if 'contributor_models' not in values:
        return {}
    models = values['contributor_models']
    text = '\n'.join(models) or 'Contributing model identities are not available.'
    if not values.get('contributor_models_complete'):
        text += '\nObserved so far; contributing model coverage may be incomplete.'
    return {'model_help': text}


def session_model_help(item):
    sections = []
    remaining = 32_000
    omitted = False
    for heading, models in (("Main models used in session", item.main_models),
                            ("Sub-agents used in session", item.subagent_models)):
        if not models:
            continue
        lines = []
        for part in models:
            text = request_model_help(part.provider, (part.model,), catalog_model=part.catalog_model)
            details = [effort_help(evidence) for evidence in part.efforts if evidence.selected is not None]
            if details:
                text += "\nEffort: " + "; ".join(dict.fromkeys(details))
            bullet = "• " + text.replace("\n", "\n  ")
            if len(bullet) > remaining:
                omitted = True
                continue
            lines.append(bullet)
            remaining -= len(bullet) + 1
        if lines:
            sections.append(heading + "\n" + "\n".join(lines))
    if not item.main_models:
        sections.insert(0, "No attributable executed main-thread model is available.")
    if omitted:
        sections.append("Additional model details omitted at the bounded help limit.")
    if not item.contributor_models_complete or omitted:
        sections.append("Observed so far; contributing model coverage may be incomplete.")
    return "\n\n".join(sections)
