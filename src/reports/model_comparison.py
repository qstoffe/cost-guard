"""Strict availability intersection and model-comparison price text."""
from __future__ import annotations

import threading

from src.analysis.comparisons import model_comparison_rows
from .models import ModelCatalogProjection, ModelComparisonProjection
from .semantics import active_model_promotion, active_promotion_notes, model_is_recent, recent_model_notice_details

from src.pricing.catalog import PricingCatalog
from src.pricing.publishers import model_publisher
from src.numbers import reference_rate
from src.sources.model_availability import ModelAvailabilitySource
from src.sources.errors import SourceError
from src.runtime_errors import recoverable, recovered
from src.pricing.tiers import lower_bound, ordered_tiers


class AvailabilityPrefetch:
    """Start the advisory availability lookup now; consume it later.

    The lookup is I/O (V2 settle polling or the CLI fallback), so it overlaps
    report analysis. Its result or exception is returned/re-raised unchanged
    on the consuming thread, preserving ``selectable_catalog``'s fail-open and
    ERROR semantics.
    """

    def __init__(self, source: ModelAvailabilitySource) -> None:
        self._result: tuple[str, ...] | None = None
        self._error: Exception | None = None
        self._thread = threading.Thread(target=self._run, args=(source,),
                                        name="cost-guard-model-availability", daemon=True)
        self._thread.start()

    def _run(self, source: ModelAvailabilitySource) -> None:
        try:
            self._result = source.available_model_ids()
        except Exception as exc:  # delivered to the consumer's boundary below
            self._error = exc

    def available_model_ids(self) -> tuple[str, ...] | None:
        self._thread.join()
        if self._error is not None:
            raise self._error
        return self._result


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


def web_model_catalog(usage, catalog, selected, *, now_ms, cache_repository, progress=None):
    """Freeze both scopes using one sample and full-catalog denominator; no new I/O."""
    markers, notes = active_promotion_notes(catalog, now_ms)
    candidates = model_comparison_rows(usage, catalog, include_uncomparable=True)
    rows = []
    for index, row in enumerate(candidates):
        rows.append(ModelComparisonProjection(
            row.publisher, row.model_name, row.relative_to_lowest, price_summary(catalog, row.model_name),
            row.release_date, row.model_name in markers, model_is_recent(row.release_date, now_ms=now_ms),
            markers.get(row.model_name), row.relative_levels, row.evidence,
            active_model_promotion(catalog.resolve_reference(row.model_name), now_ms),
            price_help(catalog, row.model_name),
        ))
        if progress is not None:
            progress(index + 1, len(candidates))
    selected_names = {(model_publisher(model) or 'Unknown / unverified',
                       model.model.display_name or model.model.model) for model in selected.models}
    notices = tuple((row.model, recent_model_notice_details(
        PricingCatalog((catalog.resolve_reference(row.model),)), now_ms=now_ms,
        cache_repository=cache_repository)[0]) for row in rows if row.recent)
    return ModelCatalogProjection(tuple(rows), tuple((row.publisher, row.model) for row in rows
        if (row.publisher, row.model) in selected_names), notes, notices)


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


def price_help(catalog: PricingCatalog, model_name: str) -> str:
    """Exact native rates from this comparison snapshot, not amount formatting."""
    model = catalog.resolve_reference(model_name)
    tiers = ordered_tiers(model) if model is not None and model.currency == 'USD' else ()
    lines = ['GitHub Copilot · USD / 1M tokens']
    if not tiers:
        return lines[0] + '\nPublished rates unavailable'
    def rate(value):
        return 'N/A' if value is None else '$' + reference_rate(value)
    for index, tier in enumerate(tiers):
        bound = lower_bound(tier, tiers[index - 1] if index else None)
        if bound:
            lines.append(f'Input context {bound[0]}{bound[1]} tokens:')
        elif len(tiers) > 1:
            lines.append(f'Base context tier (≤{tier.max_input_tokens} tokens):' if tier.max_input_tokens else 'Base context tier:')
        lines.append(f'Input {rate(tier.per_million_input)} · Cached input {rate(tier.per_million_cache_read)}')
        lines.append(f'Cache write {rate(tier.per_million_cache_write)} · Output {rate(tier.per_million_output)}')
    return '\n'.join(lines)
