"""Prompt/session report projection from canonical analysis state."""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from src.analysis.comparisons import compaction_model_timeline_name, effort_model_name
from src.analysis.effort import prompt_effort
from src.analysis.context import (
    ContextEpochs,
    NextContextWarningState,
    build_context_timeline,
    context_composition,
    estimate_next_context,
    next_context_warning_state,
    watch_context_state,
)
from src.analysis.models import CompactionRecord, RootAnalysisBundle
from src.analysis.valuation import billed_spend, comparison_cost
from src.domain import EventKind, SessionSnapshot
from src.pricing.catalog import PricingCatalog

from .models import PromptProjection, SessionPromptBlock
from .semantics import input_context_above_price_threshold, prompt_has_additional_model


def _mix_percent(values: tuple[int, int, int, int]) -> tuple[int, int, int, int] | None:
    total = sum(values)
    if total <= 0:
        return None
    raw = [Decimal(value) * Decimal(100) / Decimal(total) for value in values]
    rounded = [int(value.to_integral_value(rounding="ROUND_HALF_UP")) for value in raw]
    rounded[-1] += 100 - sum(rounded)
    return tuple(rounded)  # type: ignore[return-value]


def _prompt_context_ccost(catalog: PricingCatalog, record) -> Decimal | None:
    if not record.entries:
        return None
    entry = record.entries[0]
    request_input = entry.tokens.input + entry.tokens.cache_read + entry.tokens.cache_write
    if request_input <= 0:
        return None
    return catalog.reference_input_context(
        entry.model,
        input_tokens=entry.tokens.input,
        cache_read_tokens=entry.tokens.cache_read,
        cache_write_tokens=entry.tokens.cache_write,
        request_input_tokens=request_input,
    )


def _prompt_extra_ccost(catalog: PricingCatalog, record) -> Decimal | None:
    total = Decimal(0)
    known = True
    for entry in record.entries:
        value = catalog.reference_usage(entry.model, entry.tokens)
        if value is None:
            known = False
            continue
        total += value
    ictx = _prompt_context_ccost(catalog, record)
    if not known or ictx is None:
        return None
    return max(Decimal(0), total - ictx)


def _compaction_projection(record: CompactionRecord, catalog: PricingCatalog, timeline, number: int) -> PromptProjection:
    mix = _mix_percent((record.input_tokens, record.cache_read_tokens, record.cache_write_tokens, record.output_tokens))
    state = timeline.get(record.user_message_id)
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
        incoming_context_ccost=_prompt_context_ccost(catalog, record),
        extra_ccost=_prompt_extra_ccost(catalog, record),
        token_mix_percent=mix,
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


def build_prompt_block(
    *,
    session_id: str,
    title: str,
    bundle: RootAnalysisBundle,
    snapshot: SessionSnapshot,
    catalog: PricingCatalog,
    config: Mapping[str, object],
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> SessionPromptBlock:
    timeline_values = build_context_timeline(snapshot, bundle, catalog)
    timeline = {state.event_id: state for state in timeline_values}
    epochs = ContextEpochs(snapshot, bundle)
    event_numbers = {
        event.event_id: index + 1
        for index, event in enumerate(sorted(
            (event for event in snapshot.events if event.session_id == session_id
             and event.kind in {EventKind.USER_PROMPT, EventKind.SUBTASK, EventKind.COMPACTION}),
            key=lambda event: (event.created_at_ms, event.event_id),
        ))
    }
    thresholds = config.get("thresholds") if isinstance(config.get("thresholds"), Mapping) else {}
    approach = float(thresholds.get("nextIctxPriceThresholdWarningPercent", 75))
    running_warning_ccost = Decimal(str(config.get("runningPromptWarningCCost", 1800)))
    rows: list[PromptProjection] = []
    total_mix_values = [0, 0, 0, 0]
    diagnostic_cost_parts: list[tuple[Decimal | None, Decimal | None]] = []
    for record in bundle.prompts:
        if start_ms is not None and record.prompt_time_ms < start_ms:
            continue
        if end_ms is not None and record.prompt_time_ms >= end_ms:
            continue
        state = timeline.get(record.prompt_id)
        watch_state = watch_context_state(snapshot, bundle, record, catalog, epochs)
        next_estimate = estimate_next_context(record, catalog, epochs=epochs)
        warning = NextContextWarningState()
        if next_estimate.tokens and record.last_root_entry:
            warning = next_context_warning_state(
                tokens=next_estimate.tokens,
                model_id=record.last_root_entry.model.model,
                catalog=catalog,
                price_approach_percent=approach,
            )
        watch_warning = NextContextWarningState()
        if watch_state.next_tokens and watch_state.model_id:
            watch_warning = next_context_warning_state(
                tokens=watch_state.next_tokens,
                model_id=watch_state.model_id,
                catalog=catalog,
                price_approach_percent=approach,
            )
        mix = None if record.in_progress else _mix_percent(
            (record.input_tokens, record.cache_read_tokens, record.cache_write_tokens, record.output_tokens)
        )
        ictx_ccost = None if record.in_progress else _prompt_context_ccost(catalog, record)
        extra_ccost = None if record.in_progress else _prompt_extra_ccost(catalog, record)
        if mix is not None:
            total_mix_values[0] += record.input_tokens
            total_mix_values[1] += record.cache_read_tokens
            total_mix_values[2] += record.cache_write_tokens
            total_mix_values[3] += record.output_tokens
            diagnostic_cost_parts.append((ictx_ccost, extra_ccost))
        valuation = comparison_cost(record.entries, catalog.reference_valuation)
        main = comparison_cost(record.entries[:record.root_entry_count], catalog.reference_valuation)
        subagent = comparison_cost(record.entries[record.root_entry_count:], catalog.reference_valuation)
        model_label = effort_model_name(catalog, record.main_model_id, prompt_effort(record, snapshot))
        rows.append(PromptProjection(
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
            next_context_tokens=next_estimate.tokens,
            next_context_cached_ccost=next_estimate.cached_ccost,
            next_context_fresh_ccost=next_estimate.fresh_ccost,
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
            running_cost_warning=bool(record.in_progress and running_warning_ccost > 0 and valuation.known_ccost >= running_warning_ccost),
            ictx_price_threshold=input_context_above_price_threshold(catalog, record.main_model_id, record.input_context_tokens),
            watch_delta_context_tokens=watch_state.delta_tokens,
            watch_next_context_tokens=watch_state.next_tokens,
            watch_next_context_cached_ccost=watch_state.cached_ccost,
            watch_next_context_fresh_ccost=watch_state.fresh_ccost,
            watch_next_context_warning=watch_warning.text,
            watch_next_context_warning_severity=watch_warning.price_severity,
        ))
    for compaction in bundle.compactions:
        if start_ms is not None and compaction.created_at_ms < start_ms:
            continue
        if end_ms is not None and compaction.created_at_ms >= end_ms:
            continue
        projection = _compaction_projection(compaction, catalog, timeline, event_numbers[compaction.user_message_id])
        rows.append(projection)
        raw_mix = (compaction.input_tokens, compaction.cache_read_tokens, compaction.cache_write_tokens, compaction.output_tokens)
        if sum(raw_mix) > 0:
            for index, value in enumerate(raw_mix):
                total_mix_values[index] += value
            diagnostic_cost_parts.append((projection.incoming_context_ccost, projection.extra_ccost))
    rows.sort(key=lambda row: (row.at_ms, 0 if row.is_compaction else 1, row.prompt_number))

    total_ccost = sum((row.ccost for row in rows), Decimal(0))
    total_calls = sum(row.calls for row in rows)
    prompt_rows = [row for row in rows if not row.is_compaction]
    total_subagent = sum((row.subagent_ccost for row in prompt_rows), Decimal(0))
    total_breakdown_known = all(row.breakdown_known for row in prompt_rows) if prompt_rows else True
    total_main = total_ccost - total_subagent
    total_has_breakdown = bool(total_breakdown_known and total_subagent > 0)
    total_main_estimated = any(row.main_estimated for row in prompt_rows) or any(
        row.is_compaction and row.unresolved_cost for row in rows
    )
    total_subagent_estimated = any(row.subagent_estimated for row in prompt_rows)

    total_ictx_cost_text = total_extra_cost_text = ""
    if diagnostic_cost_parts:
        if any(ictx is None or extra is None for ictx, extra in diagnostic_cost_parts):
            total_ictx_cost_text = total_extra_cost_text = "N/A"
        else:
            ictx_total = sum((ictx for ictx, _extra in diagnostic_cost_parts if ictx is not None), Decimal(0))
            extra_total = sum((extra for _ictx, extra in diagnostic_cost_parts if extra is not None), Decimal(0))
            diagnostic_total = ictx_total + extra_total
            if diagnostic_total > 0:
                ictx_percent = int((ictx_total / diagnostic_total * Decimal(100)).to_integral_value(rounding="ROUND_HALF_UP"))
                total_ictx_cost_text = f"{ictx_percent}%"
                total_extra_cost_text = f"{100 - ictx_percent}%"
    total_mix = _mix_percent(tuple(total_mix_values))
    total_mix_text = "" if total_mix is None else "/".join(str(value) for value in total_mix)

    latest_prompt = next((record for record in reversed(bundle.prompts) if not record.in_progress and not record.aborted), None)
    current_context_tokens = None
    current_sources: Mapping[str, int] = {}
    next_tokens = None
    next_cached = next_fresh = None
    next_warning = NextContextWarningState()
    if latest_prompt is not None:
        composition = context_composition(snapshot, latest_prompt)
        current_context_tokens = composition.target_tokens
        current_sources = composition.category_totals
        estimate = estimate_next_context(latest_prompt, catalog, epochs=epochs)
        next_tokens = estimate.tokens
        next_cached = estimate.cached_ccost
        next_fresh = estimate.fresh_ccost
        if estimate.tokens and latest_prompt.last_root_entry:
            next_warning = next_context_warning_state(
                tokens=estimate.tokens,
                model_id=latest_prompt.last_root_entry.model.model,
                catalog=catalog,
                price_approach_percent=approach,
            )
    return SessionPromptBlock(
        session_id=session_id,
        title=title or session_id,
        rows=tuple(rows),
        total_ccost=total_ccost,
        total_calls=total_calls,
        total_ictx_cost_text=total_ictx_cost_text,
        total_extra_cost_text=total_extra_cost_text,
        total_mix_text=total_mix_text,
        current_context_tokens=current_context_tokens,
        current_context_sources=current_sources,
        next_context_tokens=next_tokens,
        next_context_cached_ccost=next_cached,
        next_context_fresh_ccost=next_fresh,
        next_context_warning=next_warning.text,
        next_context_warning_severity=next_warning.price_severity,
        total_main_ccost=total_main,
        total_subagent_ccost=total_subagent,
        total_breakdown_known=total_breakdown_known,
        total_has_cost_breakdown=total_has_breakdown,
        total_main_estimated=total_main_estimated,
        total_subagent_estimated=total_subagent_estimated,
        comparison_cost_complete=all(not row.unresolved_cost for row in rows),
        billed_cost=(sum((row.billed_cost for row in rows), Decimal(0))
                     if all(row.billed_cost is not None for row in rows) else None),
    )
