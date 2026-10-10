"""Canonical prompt/compaction row projection; no acquisition, ordering or totals."""
from __future__ import annotations

from decimal import Decimal
from typing import Callable, Mapping

from src.analysis.comparisons import compaction_model_timeline_name, effort_model_name
from src.analysis.context import (
    ContextEpochs, NextContextWarningState, build_context_timeline,
    estimate_next_context, next_context_warning_state, watch_context_state,
)
from src.analysis.effort import prompt_effort
from src.analysis.models import CompactionRecord, PromptRecord, RootAnalysisBundle
from src.analysis.valuation import billed_spend, comparison_cost
from src.domain import SessionSnapshot
from src.pricing.catalog import PricingCatalog

from .models import PromptProjection
from .semantics import input_context_above_price_threshold, prompt_has_additional_model

ThresholdMultiplier = Callable[[str, int], Decimal | None]


def mix_percent(values: tuple[int, int, int, int]) -> tuple[int, int, int, int] | None:
    total = sum(values)
    if total <= 0:
        return None
    raw = [Decimal(value) * Decimal(100) / Decimal(total) for value in values]
    rounded = [int(value.to_integral_value(rounding="ROUND_HALF_UP")) for value in raw]
    rounded[-1] += 100 - sum(rounded)
    return tuple(rounded)  # type: ignore[return-value]


def _context_ccost(catalog: PricingCatalog, record: PromptRecord | CompactionRecord) -> Decimal | None:
    if not record.entries:
        return None
    entry = record.entries[0]
    request_input = entry.tokens.input + entry.tokens.cache_read + entry.tokens.cache_write
    if request_input <= 0:
        return None
    return catalog.reference_input_context(
        entry.model, input_tokens=entry.tokens.input, cache_read_tokens=entry.tokens.cache_read,
        cache_write_tokens=entry.tokens.cache_write, request_input_tokens=request_input,
    )


def _extra_ccost(catalog: PricingCatalog, record: PromptRecord | CompactionRecord) -> Decimal | None:
    total = Decimal(0)
    known = True
    for entry in record.entries:
        value = catalog.reference_usage(entry.model, entry.tokens)
        if value is None:
            known = False
            continue
        total += value
    ictx = _context_ccost(catalog, record)
    if not known or ictx is None:
        return None
    return max(Decimal(0), total - ictx)


class PromptRowProjector:
    """Share one timeline/epoch/config scope across every row and session summary."""

    def __init__(self, *, snapshot: SessionSnapshot, bundle: RootAnalysisBundle,
                 catalog: PricingCatalog, config: Mapping[str, object],
                 threshold_multiplier: ThresholdMultiplier | None = None) -> None:
        self.snapshot = snapshot
        self.bundle = bundle
        self.catalog = catalog
        self.timeline = {state.event_id: state for state in build_context_timeline(snapshot, bundle, catalog)}
        self.epochs = ContextEpochs(snapshot, bundle)
        thresholds = config.get("thresholds") if isinstance(config.get("thresholds"), Mapping) else {}
        self.approach = float(thresholds.get("nextIctxPriceThresholdWarningPercent", 75))
        self.running_warning_ccost = Decimal(str(config.get("runningPromptWarningCCost", 1800)))
        self.threshold_multiplier = threshold_multiplier

    def multiplier(self, state: NextContextWarningState, model_id: str) -> Decimal | None:
        if self.threshold_multiplier is None or not state.price_threshold or not model_id:
            return None
        return self.threshold_multiplier(model_id, state.price_threshold)

    def warning(self, tokens: int | None, model_id: str | None) -> NextContextWarningState:
        if not tokens or not model_id:
            return NextContextWarningState()
        return next_context_warning_state(tokens=tokens, model_id=model_id, catalog=self.catalog,
                                          price_approach_percent=self.approach)

    def prompt(self, record: PromptRecord) -> PromptProjection:
        catalog = self.catalog
        state = self.timeline.get(record.prompt_id)
        watch_state = watch_context_state(self.snapshot, self.bundle, record, catalog, self.epochs)
        estimate = estimate_next_context(record, catalog, epochs=self.epochs)
        model_id = record.last_root_entry.model.model if record.last_root_entry else ""
        warning = self.warning(estimate.tokens, model_id)
        watch_warning = self.warning(watch_state.next_tokens, watch_state.model_id)
        mix = None if record.in_progress else mix_percent(
            (record.input_tokens, record.cache_read_tokens, record.cache_write_tokens, record.output_tokens))
        ictx_ccost = None if record.in_progress else _context_ccost(catalog, record)
        extra_ccost = None if record.in_progress else _extra_ccost(catalog, record)
        valuation = comparison_cost(record.entries, catalog.reference_valuation)
        main = comparison_cost(record.entries[:record.root_entry_count], catalog.reference_valuation)
        subagent = comparison_cost(record.entries[record.root_entry_count:], catalog.reference_valuation)
        model_label = effort_model_name(catalog, record.main_model_id, prompt_effort(record, self.snapshot))
        return PromptProjection(
            at_ms=record.prompt_time_ms,
            prompt_number=record.prompt_number,
            label="prompt",
            preview=" ".join(record.prompt_text.split())[:120],
            model_effort=model_label,
            watch_model_effort=model_label,
            ccost=valuation.known_ccost,
            comparison_cost=valuation,
            billed_cost=billed_spend(record.entries),
            cost_estimated=False,
            unresolved_cost=not valuation.complete,
            calls=record.model_calls,
            incoming_context_tokens=record.input_context_tokens or None,
            incoming_context_ccost=ictx_ccost,
            extra_ccost=extra_ccost,
            token_mix_percent=mix,
            in_progress=record.in_progress,
            aborted=record.aborted,
            delta_context_tokens=state.delta_tokens if state else None,
            next_context_tokens=estimate.tokens,
            next_context_cached_ccost=estimate.cached_ccost,
            next_context_fresh_ccost=estimate.fresh_ccost,
            next_context_warning=warning.text,
            next_context_warning_severity=warning.price_severity,
            event_id=record.prompt_id,
            duration_ms=record.duration_ms,
            watch_error=record.watch_error,
            main_ccost=main.known_ccost,
            subagent_ccost=subagent.known_ccost,
            breakdown_known=record.breakdown_known,
            has_cost_breakdown=bool(record.breakdown_known and subagent.observed_requests),
            main_estimated=not main.complete,
            subagent_estimated=not subagent.complete,
            has_additional_model=prompt_has_additional_model(record),
            abort_at_ms=record.abort_time_ms,
            completed_successfully=record.completed_successfully,
            running_cost_warning=bool(record.in_progress and self.running_warning_ccost > 0
                                      and valuation.known_ccost >= self.running_warning_ccost),
            ictx_price_threshold=input_context_above_price_threshold(catalog, record.main_model_id, record.input_context_tokens),
            watch_delta_context_tokens=watch_state.delta_tokens,
            watch_next_context_tokens=watch_state.next_tokens,
            watch_next_context_cached_ccost=watch_state.cached_ccost,
            watch_next_context_fresh_ccost=watch_state.fresh_ccost,
            watch_next_context_warning=watch_warning.text,
            watch_next_context_warning_severity=watch_warning.price_severity,
            next_context_cost_multiplier=self.multiplier(warning, model_id),
            watch_next_context_cost_multiplier=self.multiplier(watch_warning, watch_state.model_id or ""),
            background_kinds=record.background_kinds,
            background_started_ms=record.background_started_ms,
            background_only=record.background_only,
        )

    def compaction(self, record: CompactionRecord, number: int) -> PromptProjection:
        catalog = self.catalog
        state = self.timeline.get(record.user_message_id)
        label = compaction_model_timeline_name(catalog, record.model_id, record.variant)
        valuation = comparison_cost(record.entries, catalog.reference_valuation)
        return PromptProjection(
            at_ms=record.created_at_ms,
            prompt_number=number,
            label="/compact" + (" (auto)" if record.automatic else ""),
            preview="",
            model_effort=label,
            watch_model_effort=label,
            ccost=valuation.known_ccost,
            comparison_cost=valuation,
            billed_cost=billed_spend(record.entries),
            cost_estimated=False,
            unresolved_cost=not valuation.complete,
            calls=record.model_calls,
            incoming_context_tokens=record.input_context_tokens or None,
            incoming_context_ccost=_context_ccost(catalog, record),
            extra_ccost=_extra_ccost(catalog, record),
            token_mix_percent=mix_percent((record.input_tokens, record.cache_read_tokens, record.cache_write_tokens, record.output_tokens)),
            is_compaction=True,
            in_progress=record.in_progress,
            delta_context_tokens=state.delta_tokens if state else None,
            next_context_tokens=state.next_tokens if state else None,
            event_id=record.user_message_id,
            duration_ms=max(0, record.completed_at_ms - record.created_at_ms),
            ictx_price_threshold=input_context_above_price_threshold(catalog, record.model_id, record.input_context_tokens),
            watch_delta_context_tokens=state.delta_tokens if state else None,
            watch_next_context_tokens=state.next_tokens if state else None,
        )
