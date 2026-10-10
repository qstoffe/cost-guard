"""Session prompt-block assembly: range/order, coherent Watch deltas and totals."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Mapping, Sequence

from src.analysis.context import ContextEpochs, context_composition, estimate_next_context
from src.analysis.models import RootAnalysisBundle
from src.domain import EventKind, SessionSnapshot
from src.pricing.catalog import PricingCatalog

from .models import PromptProjection, SessionPromptBlock
from .prompt_rows import PromptRowProjector, ThresholdMultiplier, mix_percent


def _coherent_watch_deltas(rows: list[PromptProjection], *, epochs: ContextEpochs,
                           session_id: str, subtask_ids: frozenset[str]) -> list[PromptProjection]:
    """Reconcile adjacent root anchors; moves, unknown compactions and shrinks stay honest.

    Retain the epoch-aware per-prompt estimate when no comparable displayed anchor
    exists; subtasks never reset root state. This changes only Watch delta display,
    not context sizes, warnings, accounting or request attribution.
    """
    last_root: PromptProjection | None = None
    result: list[PromptProjection] = []
    for row in rows:
        if row.event_id in subtask_ids:
            result.append(row)
            continue
        if not row.is_compaction:
            delta = row.watch_delta_context_tokens
            crossed = last_root is not None and epochs.crossed(session_id, last_root.at_ms, row.at_ms + 1)
            anchor = None if last_root is None or crossed else last_root.watch_next_context_tokens
            if anchor:
                next_tokens = row.watch_next_context_tokens
                delta = None if next_tokens is None else next_tokens - anchor
            elif last_root is not None and last_root.is_compaction and not crossed:
                delta = None
            if delta is not None and delta < 0:
                delta = None
            if delta != row.watch_delta_context_tokens:
                row = replace(row, watch_delta_context_tokens=delta)
        result.append(row)
        last_root = row
    return result


def _diagnostic_cost_shares(parts: Sequence[tuple[Decimal | None, Decimal | None]]) -> tuple[str, str]:
    if not parts:
        return "", ""
    if any(ictx is None or extra is None for ictx, extra in parts):
        return "N/A", "N/A"
    ictx_total = sum((ictx for ictx, _ in parts if ictx is not None), Decimal(0))
    extra_total = sum((extra for _, extra in parts if extra is not None), Decimal(0))
    total = ictx_total + extra_total
    if total <= 0:
        return "", ""
    percent = int((ictx_total / total * Decimal(100)).to_integral_value(rounding="ROUND_HALF_UP"))
    return f"{percent}%", f"{100 - percent}%"


def _session_block(*, session_id: str, title: str, rows: list[PromptProjection],
                   projector: PromptRowProjector, mix_values: tuple[int, int, int, int],
                   diagnostic_parts: Sequence[tuple[Decimal | None, Decimal | None]]) -> SessionPromptBlock:
    total_ccost = sum((row.ccost for row in rows), Decimal(0))
    prompt_rows = [row for row in rows if not row.is_compaction]
    total_subagent = sum((row.subagent_ccost for row in prompt_rows), Decimal(0))
    breakdown_known = all(row.breakdown_known for row in prompt_rows) if prompt_rows else True
    ictx_text, extra_text = _diagnostic_cost_shares(diagnostic_parts)
    mix = mix_percent(mix_values)
    latest = next((record for record in reversed(projector.bundle.prompts) if not record.in_progress and not record.aborted), None)
    composition = context_composition(projector.snapshot, latest) if latest is not None else None
    estimate = estimate_next_context(latest, projector.catalog, epochs=projector.epochs) if latest is not None else None
    model_id = latest.last_root_entry.model.model if latest is not None and latest.last_root_entry else ""
    warning = projector.warning(estimate.tokens if estimate else None, model_id)
    return SessionPromptBlock(
        session_id=session_id,
        title=title or session_id,
        rows=tuple(rows),
        total_ccost=total_ccost,
        total_calls=sum(row.calls for row in rows),
        total_ictx_cost_text=ictx_text,
        total_extra_cost_text=extra_text,
        total_mix_text="" if mix is None else "/".join(str(value) for value in mix),
        current_context_tokens=composition.target_tokens if composition else None,
        current_context_sources=composition.category_totals if composition else {},
        next_context_tokens=estimate.tokens if estimate else None,
        next_context_cached_ccost=estimate.cached_ccost if estimate else None,
        next_context_fresh_ccost=estimate.fresh_ccost if estimate else None,
        next_context_warning=warning.text,
        next_context_warning_severity=warning.price_severity,
        next_context_cost_multiplier=projector.multiplier(warning, model_id),
        total_main_ccost=total_ccost - total_subagent,
        total_subagent_ccost=total_subagent,
        total_breakdown_known=breakdown_known,
        total_has_cost_breakdown=bool(breakdown_known and total_subagent > 0),
        total_main_estimated=any(row.main_estimated for row in prompt_rows)
                             or any(row.is_compaction and row.unresolved_cost for row in rows),
        total_subagent_estimated=any(row.subagent_estimated for row in prompt_rows),
        comparison_cost_complete=all(not row.unresolved_cost for row in rows),
        billed_cost=(sum((row.billed_cost for row in rows), Decimal(0))
                     if all(row.billed_cost is not None for row in rows) else None),
    )


def build_prompt_block(
    *, session_id: str, title: str, bundle: RootAnalysisBundle, snapshot: SessionSnapshot,
    catalog: PricingCatalog, config: Mapping[str, object], start_ms: int | None = None,
    end_ms: int | None = None, threshold_multiplier: ThresholdMultiplier | None = None,
) -> SessionPromptBlock:
    projector = PromptRowProjector(snapshot=snapshot, bundle=bundle, catalog=catalog, config=config,
                                   threshold_multiplier=threshold_multiplier)
    event_numbers = {
        event.event_id: index + 1 for index, event in enumerate(sorted(
            (event for event in snapshot.events if event.session_id == session_id
             and event.kind in {EventKind.USER_PROMPT, EventKind.SUBTASK, EventKind.COMPACTION}),
            key=lambda event: (event.created_at_ms, event.event_id),
        ))
    }
    rows: list[PromptProjection] = []
    mix_values = [0, 0, 0, 0]
    diagnostic_parts: list[tuple[Decimal | None, Decimal | None]] = []
    for record in bundle.prompts:
        if start_ms is not None and record.prompt_time_ms < start_ms:
            continue
        if end_ms is not None and record.prompt_time_ms >= end_ms:
            continue
        row = projector.prompt(record)
        rows.append(row)
        if row.token_mix_percent is not None:
            for index, value in enumerate((record.input_tokens, record.cache_read_tokens, record.cache_write_tokens, record.output_tokens)):
                mix_values[index] += value
            diagnostic_parts.append((row.incoming_context_ccost, row.extra_ccost))
    for record in bundle.compactions:
        if start_ms is not None and record.created_at_ms < start_ms:
            continue
        if end_ms is not None and record.created_at_ms >= end_ms:
            continue
        row = projector.compaction(record, event_numbers[record.user_message_id])
        rows.append(row)
        raw_mix = (record.input_tokens, record.cache_read_tokens, record.cache_write_tokens, record.output_tokens)
        if sum(raw_mix) > 0:
            for index, value in enumerate(raw_mix):
                mix_values[index] += value
            diagnostic_parts.append((row.incoming_context_ccost, row.extra_ccost))
    rows.sort(key=lambda row: (row.at_ms, 0 if row.is_compaction else 1, row.prompt_number))
    rows = _coherent_watch_deltas(rows, epochs=projector.epochs, session_id=session_id,
                                 subtask_ids=frozenset(record.prompt_id for record in bundle.prompts if record.prompt_kind == "subtask"))
    return _session_block(session_id=session_id, title=title, rows=rows, projector=projector,
                          mix_values=tuple(mix_values), diagnostic_parts=diagnostic_parts)
