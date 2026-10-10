"""Provider-neutral model repricing and model timeline labels."""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Iterable

from src.pricing.catalog import PricingCatalog, normalized_average_token_mix, token_mix_tier_price
from src.pricing.tiers import lower_bound, ordered_tiers

from .models import PromptRecord
from .effort import EffortSelection, interpret_effort

# Sorting only: never exposed as observed usage or a Relative CCost sample.
_DEFAULT_SORT_MIX = (Decimal("0.02"), Decimal("0.96"), Decimal("0.01"), Decimal("0.01"), 1)


@dataclass(frozen=True, slots=True)
class RelativePriceLevel:
    relative_cost: Decimal | None
    threshold_tokens: int | None = None
    threshold_operator: str | None = None


@dataclass(frozen=True, slots=True)
class ModelComparisonRow:
    model_name: str
    publisher: str
    estimated_ccost: Decimal | None
    relative_to_lowest: Decimal | None
    release_date: str | None = None
    promotional: bool = False
    relative_levels: tuple[RelativePriceLevel, ...] = ()



def model_comparison_rows(records: Iterable[PromptRecord], catalog: PricingCatalog) -> tuple[ModelComparisonRow, ...]:
    records = tuple(records)
    mix = normalized_average_token_mix(records)
    sampled = mix[4] > 0
    sorting_mix = mix if sampled else _DEFAULT_SORT_MIX
    rows: list[ModelComparisonRow] = []
    scores: list[tuple[Decimal | None, ...]] = []
    bounds: list[tuple[tuple[str, int] | None, ...]] = []
    for model in catalog.ccost_models:
        tiers = ordered_tiers(model)
        units = tuple(token_mix_tier_price(sorting_mix, tier) for tier in tiers) or (None,)
        unit = units[0]
        if sampled and unit is None:
            continue  # Preserve the observed-mix comparable-model selection.
        # Normalize the shared observed mix to one million tokens.  The absolute
        # number is diagnostic only; relative ordering is the important contract.
        rows.append(ModelComparisonRow(
            model_name=model.model.display_name or model.model.model,
            publisher=str(model.metadata.get("publisher", model.model.provider)),
            estimated_ccost=unit if sampled else None,
            relative_to_lowest=None,
            release_date=model.metadata.get("release_date"),
            promotional=str(model.metadata.get("promotion_active", "false")).lower() == "true",
        ))
        scores.append(units)
        bounds.append(tuple(None if index == 0 else lower_bound(tier, tiers[index - 1])
                            for index, tier in enumerate(tiers)) or (None,))
    if not rows:
        return ()
    lowest = min((units[0] for units in scores if units[0] is not None and units[0] > 0), default=Decimal(0))
    projected = []
    for row, units, thresholds in zip(rows, scores, bounds):
        levels = tuple(RelativePriceLevel(
            value / lowest if sampled and lowest > 0 and value is not None else None,
            bound[1] if bound else None, bound[0] if bound else None,
        ) for value, bound in zip(units, thresholds))
        projected.append(replace(row, relative_to_lowest=levels[0].relative_cost, relative_levels=levels))
    # Use raw shared-mix costs for sorting: dividing by the same positive
    # reference cannot change order, and must not introduce division rounding.
    depth = max(map(len, scores))
    def sort_key(index: int) -> tuple:
        units, thresholds = scores[index], bounds[index]
        key: list = [(units[0] is None, -(units[0] or Decimal(0)))]
        for level in range(1, depth):
            value = units[level] if level < len(units) else units[-1]
            previous = units[level - 1] if level < len(units) else units[-1]
            boundary = thresholds[level] if level < len(thresholds) else None
            increasing = value is not None and previous is not None and value > previous
            # Missing rates stay unknown; absence of a tier means unchanged.
            start = boundary[1] + (boundary[0] == ">") if boundary and increasing else None
            key.extend(((value is None, -(value or Decimal(0))),
                        (start is None, start or 0)))
        return (*key, rows[index].model_name.casefold(), rows[index].model_name)
    return tuple(projected[index] for index in sorted(range(len(rows)), key=sort_key))

def threshold_cost_multiplier(
    catalog: PricingCatalog, model_id: str, threshold: int,
    mix: tuple[Decimal, Decimal, Decimal, Decimal, int],
) -> Decimal | None:
    """Relative CCost after/before one price threshold, exactly as the model table.

    Both Relative CCost levels share the report's comparison mix and lowest
    reference, so their ratio is the tier-price ratio under that mix. Without
    an observed sample the table's hidden sorting mix is used. Only a real
    increase is returned; ``threshold`` is the warning's ``>N`` boundary.
    """
    model = catalog.reference_prices(model_id, exact=False) if model_id and threshold > 0 else None
    if model is None:
        return None
    tiers = ordered_tiers(model)
    shared = mix if mix[4] > 0 else _DEFAULT_SORT_MIX
    for previous, tier in zip(tiers, tiers[1:]):
        if (tier.min_input_tokens or 0) - 1 == threshold:
            before, after = token_mix_tier_price(shared, previous), token_mix_tier_price(shared, tier)
            return after / before if before and after and after > before else None
    return None


def _effort_label(variant: str) -> str:
    value = (variant or "").strip()
    if not value or value.lower() == "default":
        return "Default"
    mapping = {"xhigh": "XHigh", "high": "High", "medium": "Medium", "low": "Low", "minimal": "Minimal"}
    return mapping.get(value.lower(), value[:1].upper() + value[1:])


def _model_display_name(catalog: PricingCatalog, model_id: str) -> str:
    model = catalog.resolve(model_id)
    return (model.model.display_name if model and model.model.display_name else re.sub(r"^github-copilot/", "", model_id or "")) or "N/A"


def effort_model_name(catalog: PricingCatalog, model_id: str, effort: EffortSelection) -> str:
    name = _model_display_name(catalog, model_id)
    return f"{name} ({_effort_label(effort.level)})" if effort.level else name


def model_timeline_name(catalog: PricingCatalog, model_id: str, provider_id: str, variant: str) -> str:
    return effort_model_name(catalog, model_id, interpret_effort(variant, attributable=bool(model_id)))


def watch_model_timeline_name(catalog: PricingCatalog, model_id: str, provider_id: str, variant: str) -> str:
    """Compatibility entry point; Watch and report have identical semantics."""
    return model_timeline_name(catalog, model_id, provider_id, variant)


def compaction_model_timeline_name(catalog: PricingCatalog, model_id: str, variant: str) -> str:
    """A /compact event may display only its own explicit effort."""
    return effort_model_name(catalog, model_id, interpret_effort(
        variant, attributable=bool(model_id), compaction=True,
    ))
