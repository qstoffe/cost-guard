"""Conservative manufacturer identity from catalog metadata, never account routes."""
from src.domain import ModelPricing, ModelRef
from .catalog import PricingCatalog

_ALIASES = {
    "openai": "OpenAI", "open ai": "OpenAI", "openai, inc.": "OpenAI",
    "anthropic": "Anthropic", "anthropic pbc": "Anthropic",
    "google": "Google", "google deepmind": "Google", "deepmind": "Google",
    "xai": "xAI", "x.ai": "xAI", "meta": "Meta", "meta ai": "Meta",
    "mistral": "Mistral AI", "mistral ai": "Mistral AI",
    "deepseek": "DeepSeek", "alibaba": "Alibaba", "moonshot ai": "Moonshot AI",
}


def model_publisher(model: ModelPricing | None) -> str | None:
    if model is None:
        return None
    # Catalog publisher/manufacturer fields are authoritative, unlike a request's
    # provider route. Normalize known aliases; do not accept service labels.
    values = [str(model.metadata[key]).strip().casefold()
              for key in ("publisher", "manufacturer") if model.metadata.get(key)]
    routes = {"github-copilot", "github copilot", "copilot", "github", "claude code", "opencode",
              "unknown", "n/a", "openrouter", "azure", "amazon bedrock"}
    names = {None if value in routes else _ALIASES.get(value, value.title()) for value in values}
    return next(iter(names)) if len(names) == 1 and None not in names else None


def publisher_for(catalog: PricingCatalog, model_id: str) -> str | None:
    return model_publisher(catalog.resolve_reference(model_id))


def token_mix_publisher(model: ModelRef, matched: ModelPricing | None) -> str | None:
    """Web history only: manufacturer knowledge never supplies a rate or release."""
    if matched is not None:
        return model_publisher(matched)  # Retain catalog authority, including unresolved conflicts.
    return {"openai": "OpenAI", "claude-agent": "Anthropic"}.get(model.provider)
