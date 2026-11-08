"""Detached guidance dependencies and pure enrichment; never Earlier proof."""
from dataclasses import asdict, dataclass, replace

from src.analysis.cache import dependency_signature
from src.analysis.comparisons import threshold_cost_multiplier
from src.analysis.context import next_context_warning_state

GUIDANCE_TTL_MS = 900_000
SAMPLING_DEFINITION = 'canonical-comparison-and-token-100-v1'


@dataclass(frozen=True, slots=True)
class GuidanceScope:
    source: tuple[str, str, str]
    semantics: str


@dataclass(frozen=True, slots=True)
class GuidanceBinding:
    scope: GuidanceScope
    catalog: object
    reference_catalog: object


@dataclass(frozen=True, slots=True)
class GuidanceObservation:
    scope: GuidanceScope
    mix: tuple
    started_at_ms: int
    started_monotonic: float


def guidance_semantics(service, catalog, reference_catalog):
    return dependency_signature({
        'configuration': {key: value for key, value in service.config.items() if key != 'webSettings'},
        'analysis': asdict(service._dependencies(catalog)),
        'reference_prices': reference_catalog.analysis_signature,
        'sampling': SAMPLING_DEFINITION,
    })


def cached_guidance_binding(service):
    """Observe local registration and cached prices only; no source/provider scan."""
    source = service.source
    source.refresh_observation_epoch()
    epoch = source.observation_epoch
    instance = source.source_instance
    if not epoch or not instance:
        return None
    catalog = service.pricing_provider.cached_catalog()
    reference = (catalog if service.comparison_pricing_provider is service.pricing_provider
        else service.comparison_pricing_provider.cached_catalog())
    if catalog is None or reference is None:
        return None
    scope = GuidanceScope((service.selection.selected, instance, epoch),
        guidance_semantics(service, catalog, reference))
    return GuidanceBinding(scope, catalog, reference)


def requalify_guidance(context, binding, config):
    """Reprice compact canonical inputs, never relabel old price-derived fields."""
    if context.guidance_signature == binding.scope.semantics:
        return context
    thresholds = config.get('thresholds') or {}
    warning = next_context_warning_state(tokens=context.tokens or 0, model_id=context.model_id,
        catalog=binding.catalog,
        price_approach_percent=float(thresholds.get('nextIctxPriceThresholdWarningPercent', 75)))
    cached, fresh = context.price_basis.costs(binding.catalog) if context.price_basis else (None, None)
    return replace(context, text=warning.text, severity=warning.price_severity,
        price_threshold=warning.price_threshold, multiplier=None, cached_ccost=cached, fresh_ccost=fresh,
        guidance_signature=binding.scope.semantics, guidance_state='pending' if warning.price_threshold else 'ready')


def complete_guidance(context, mix, catalog, semantics):
    if context.guidance_signature != semantics or not context.price_threshold:
        return context
    return replace(context, multiplier=threshold_cost_multiplier(catalog,
        context.model_id, context.price_threshold, mix), guidance_state='ready')
