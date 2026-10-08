"""Strict availability intersection and model-comparison price text."""
from __future__ import annotations

from src.pricing.catalog import PricingCatalog
from src.numbers import reference_rate
from src.sources.model_availability import ModelAvailabilitySource
from src.sources.errors import SourceError
from src.runtime_errors import recoverable, recovered
from src.pricing.tiers import lower_bound, ordered_tiers


def selectable_catalog(
    catalog: PricingCatalog,
    *,
    availability_source: ModelAvailabilitySource | None,
) -> tuple[PricingCatalog, tuple[str, ...]]:
    """Intersect the catalog with global OpenCode availability, never fuzzy prices.

    Availability is deliberately fail-open: if OpenCode cannot provide a
    reliable model list, retain the full
    pricing catalog rather than accidentally hiding a usable model.
    """
    try:
        available_ids = availability_source.available_model_ids() if availability_source else None
    except (SourceError, OSError):
        available_ids = None
    except Exception as exc:
        recoverable(exc, "model-availability")
        return catalog, ("ERROR: Model availability lookup failed internally; showing full pricing catalog.",)
    else:
        recovered("model-availability")
    if available_ids is None:
        return catalog, ("⚠ Could not determine available OpenCode models; showing full pricing catalog.",)

    matches = [catalog.resolve_reference(value) for value in available_ids]
    selected = [model for model in catalog.models if any(match is model for match in matches)]
    warnings = () if selected else ("⚠ No available OpenCode models match the pricing catalog.",)
    return PricingCatalog(
        tuple(selected),
        retrieved_at_ms=catalog.retrieved_at_ms,
        source_revision=catalog.source_revision,
        refresh_not_after_ms=catalog.refresh_not_after_ms,
    ), warnings


def price_summary(catalog: PricingCatalog, model_name: str) -> str:
    model = catalog.resolve_reference(model_name)
    if model is None or model.currency != "USD":
        return "N/A"
    tiers = ordered_tiers(model)
    if not tiers:
        return "N/A"
    parts: list[str] = []
    for index, tier in enumerate(tiers):
        write = tier.per_million_cache_write
        values = (
            reference_rate(tier.per_million_input),
            reference_rate(tier.per_million_cache_read),
            reference_rate(write),
            reference_rate(tier.per_million_output),
        )
        bound = lower_bound(tier, tiers[index - 1]) if index else None
        # Always carry exact numeric boundaries, including with no observed mix.
        suffix = f" ({bound[0]}{bound[1]})" if bound else ""
        parts.append("/".join(values) + suffix)
    return "→".join(parts)
