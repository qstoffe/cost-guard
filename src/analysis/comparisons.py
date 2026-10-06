"""Provider-neutral model repricing and model timeline labels."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from src.pricing.catalog import PricingCatalog, canonical_model_name, normalized_average_token_mix, token_mix_unit_price

from .models import PromptRecord
from .effort import EffortSelection, interpret_effort

# Sorting only: never exposed as observed usage or a Rel CCost sample.
_DEFAULT_SORT_MIX = (Decimal("0.02"), Decimal("0.96"), Decimal("0.01"), Decimal("0.01"), 1)


@dataclass(frozen=True, slots=True)
class ModelComparisonRow:
    model_name: str
    publisher: str
    estimated_ccost: Decimal | None
    relative_to_lowest: Decimal | None
    release_date: str | None = None
    promotional: bool = False



def model_comparison_rows(records: Iterable[PromptRecord], catalog: PricingCatalog) -> tuple[ModelComparisonRow, ...]:
    records = tuple(records)
    mix = normalized_average_token_mix(records)
    sampled = mix[4] > 0
    sorting_mix = mix if sampled else _DEFAULT_SORT_MIX
    rows: list[ModelComparisonRow] = []
    scores: dict[ModelComparisonRow, Decimal | None] = {}
    for model in catalog.ccost_models:
        unit = token_mix_unit_price(sorting_mix, model)
        if sampled and unit is None:
            continue
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
        scores[rows[-1]] = unit
    if not rows:
        return ()
    if not sampled:
        return tuple(sorted(
            rows,
            key=lambda row: (
                scores[row] is None,
                -(scores[row] or Decimal(0)),
                row.model_name.lower(),
            ),
        ))
    lowest = min(row.estimated_ccost for row in rows if row.estimated_ccost is not None and row.estimated_ccost > 0) if any(row.estimated_ccost is not None and row.estimated_ccost > 0 for row in rows) else Decimal(0)
    return tuple(sorted((
        ModelComparisonRow(
            row.model_name, row.publisher, row.estimated_ccost,
            (row.estimated_ccost / lowest) if lowest > 0 and row.estimated_ccost is not None else None,
            row.release_date, row.promotional,
        ) for row in rows
    ), key=lambda row: (-(row.estimated_ccost or Decimal(0)), row.model_name.lower())))



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
