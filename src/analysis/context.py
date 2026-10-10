"""Context/Ictx estimation and chronological state semantics.

This module keeps context diagnostics presentation-only.  It never feeds its
estimates back into authoritative billing.
"""
from __future__ import annotations

import json
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Mapping

from src.domain import MessageRole, NormalizedMessage, NormalizedPart, SessionSnapshot
from src.pricing.catalog import PricingCatalog

from .models import CompactionRecord, PromptRecord, RootAnalysisBundle, TraceEntry


@dataclass(frozen=True, slots=True)
class NextContextEstimate:
    tokens: int | None
    cached_ccost: Decimal | None = None
    fresh_ccost: Decimal | None = None
    complete: bool = False


class PriceWarningSeverity(str, Enum):
    NONE = "none"
    APPROACHING = "approaching"
    EXCEEDED = "exceeded"


@dataclass(frozen=True, slots=True)
class NextContextWarningState:
    text: str = ""
    hard_warning: bool = False
    price_approaching: bool = False
    price_exceeded: bool = False
    price_threshold: int = 0

    @property
    def price_severity(self) -> PriceWarningSeverity:
        if self.price_exceeded:
            return PriceWarningSeverity.EXCEEDED
        if self.price_approaching:
            return PriceWarningSeverity.APPROACHING
        return PriceWarningSeverity.NONE


@dataclass(frozen=True, slots=True)
class ContextSource:
    category: str
    kind: str
    label: str
    detail: str
    tokens: int
    provenance: str = ""


@dataclass(frozen=True, slots=True)
class ContextComposition:
    target_tokens: int | None
    sources: tuple[ContextSource, ...]
    category_totals: Mapping[str, int]
    complete: bool


@dataclass(frozen=True, slots=True)
class ContextTimelineState:
    event_kind: str
    event_id: str
    at_ms: int
    incoming_tokens: int | None
    next_tokens: int | None
    delta_tokens: int | None
    complete: bool


@dataclass(frozen=True, slots=True)
class WatchContextState:
    """Live Watch context values matching the retained v77 session-timeline semantics."""

    next_tokens: int | None
    delta_tokens: int | None
    model_id: str = ""
    last_activity_ms: int = 0
    cached_ccost: Decimal | None = None
    fresh_ccost: Decimal | None = None


def estimate_text_tokens(text: str) -> int:
    return 0 if not text else (len(text) + 3) // 4


def _object_tokens(value: object) -> int:
    try:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError):
        text = str(value)
    return estimate_text_tokens(text)


def _part_context_tokens(part: NormalizedPart) -> tuple[str, str, str, str, int]:
    data = part.data
    if part.kind in {"text", "reasoning"}:
        text = str(data.get("text") or "")
        return "History", "Text", "message", _preview(text), estimate_text_tokens(text)
    if part.kind == "file":
        label = str(data.get("filename") or "file")
        detail = str(data.get("mime") or "")
        return "History", "User prompts", label, detail, max(4, estimate_text_tokens(label + " " + detail))
    if part.kind == "compaction":
        summary = data.get("summary")
        recent = data.get("recent")
        if summary or recent:
            tokens = _object_tokens(summary) + _object_tokens(recent)
            return "History", "Compaction", "Summary", "Durable compacted context", max(1, tokens)
        return "History", "Compaction", "Trigger", "What did we do so far?", estimate_text_tokens("What did we do so far?")
    if part.kind != "tool":
        return "Other", part.kind or "Part", part.kind or "part", "", _object_tokens(data)
    tool = str(data.get("tool") or "tool")
    state = data.get("state") if isinstance(data.get("state"), Mapping) else {}
    input_value = state.get("input") if isinstance(state, Mapping) else None
    output_value = None
    if isinstance(state, Mapping):
        output_value = state.get("output", state.get("result", state.get("metadata")))
    lower = tool.lower()
    if lower == "read":
        category = "Files"
    elif lower in {"grep", "glob", "list", "ls"}:
        category = "Search"
    elif lower == "task":
        category = "Subagents"
    elif lower in {"webfetch", "web_fetch", "websearch", "web_search", "fetch"}:
        category = "Web"
    elif lower in {"bash", "shell", "powershell", "pwsh"}:
        category = "Shell"
    elif lower == "skill":
        category = "Skills"
    else:
        category = "Tooling"
    label = tool
    if isinstance(input_value, Mapping):
        for key in ("filePath", "path", "description", "query", "url", "name", "command"):
            if input_value.get(key):
                label = f"{tool}: {_preview(str(input_value[key]), 70)}"
                break
    tokens = _object_tokens(input_value) + _object_tokens(output_value)
    return category, category, label, "", tokens


def _preview(text: str, limit: int = 68) -> str:
    value = " ".join((text or "").replace("\t", " ").split())
    return value if len(value) <= limit else value[:limit] + "..."


def _message_tokens(message: NormalizedMessage) -> int:
    if message.role is MessageRole.ASSISTANT and message.tokens is not None:
        return message.tokens.output + message.tokens.reasoning
    return sum(_part_context_tokens(part)[4] for part in message.parts)


def _estimate_entry_next_context(entry: TraceEntry, catalog: PricingCatalog) -> NextContextEstimate:
    next_tokens = entry.tokens.total
    if next_tokens <= 0:
        return NextContextEstimate(None)
    model = catalog.resolve(entry.model.model)
    if model is None:
        return NextContextEstimate(next_tokens)
    prior_context = entry.tokens.input + entry.tokens.cache_read + entry.tokens.cache_write
    new_fresh = entry.tokens.output + entry.tokens.reasoning
    # Next-Ictx pricing is a presentation-only range: one end assumes the
    # previously observed input context can be served at the model's cached-input
    # rate, the other prices the same next context as fresh input. Cost Guard does
    # not predict whether a future request receives a provider/runtime cache hit.
    cached = catalog.reference_input_context(
        entry.model,
        input_tokens=new_fresh,
        cache_read_tokens=prior_context,
        cache_write_tokens=0,
        request_input_tokens=next_tokens,
    )
    fresh = catalog.reference_input_context(
        entry.model,
        input_tokens=next_tokens,
        cache_read_tokens=0,
        cache_write_tokens=0,
        request_input_tokens=next_tokens,
    )
    return NextContextEstimate(next_tokens, cached, fresh, cached is not None and fresh is not None)


class ContextEpochs:
    """Session location moves as non-billable context-epoch boundaries.

    A context anchor is retired when a move follows it before the session's next
    real request; that first request after the move establishes the new baseline.
    Earlier anchors that already fed a later same-epoch request stay historical.
    """

    def __init__(self, snapshot: SessionSnapshot, bundle: RootAnalysisBundle) -> None:
        self._boundaries: dict[str, list[int]] = {}
        for item in snapshot.context_boundaries:
            self._boundaries.setdefault(item.session_id, []).append(item.at_ms)
        self._requests: dict[str, list[int]] = {}
        for entry in bundle.trace_entries:
            if entry.session_id in self._boundaries:
                self._requests.setdefault(entry.session_id, []).append(entry.completed_at_ms)
        for values in (*self._boundaries.values(), *self._requests.values()):
            values.sort()

    def crossed(self, session_id: str, start_ms: int, end_ms: int | None) -> bool:
        """Whether a move happened at/after ``start_ms`` and before ``end_ms`` (None: ever)."""
        boundaries = self._boundaries.get(session_id, ())
        index = bisect_left(boundaries, start_ms)
        return index < len(boundaries) and (end_ms is None or boundaries[index] < end_ms)

    def retired(self, session_id: str, anchor_ms: int) -> bool:
        requests = self._requests.get(session_id, ())
        later = bisect_right(requests, anchor_ms)
        # A tie with the move cannot prove that the request followed it.
        return self.crossed(session_id, anchor_ms, requests[later] + 1 if later < len(requests) else None)


def estimate_next_context(record: PromptRecord, catalog: PricingCatalog, *,
                          epochs: ContextEpochs | None = None) -> NextContextEstimate:
    if record.in_progress or record.aborted or record.last_root_entry is None:
        return NextContextEstimate(None)
    if epochs is not None and epochs.retired(record.session_id, record.last_root_entry.completed_at_ms):
        return NextContextEstimate(None)
    return _estimate_entry_next_context(record.last_root_entry, catalog)


def _latest_meaningful_watch_root(record: PromptRecord) -> TraceEntry | None:
    """Return the newest non-zero same-session request attributable to this prompt.

    OpenCode can append an unfinished/terminal zero-usage root step while a prompt
    is still running. v77 ignored such a step as a context anchor and retained the
    newest meaningful root continuation. ``last_root_entry`` alone therefore is
    insufficient for live Watch.
    """
    candidates = [
        entry for entry in record.entries
        if entry.session_id == record.session_id
        and entry.request_input_approx > 0
        and entry.completed_at_ms >= record.prompt_time_ms
    ]
    if (
        record.last_root_entry is not None
        and record.last_root_entry.session_id == record.session_id
        and record.last_root_entry.request_input_approx > 0
        and record.last_root_entry.completed_at_ms >= record.prompt_time_ms
    ):
        candidates.append(record.last_root_entry)
    if not candidates:
        return None
    return max(candidates, key=lambda entry: (entry.completed_at_ms, entry.sort_order))


def _latest_completed_compaction_before(snapshot: SessionSnapshot, before_ms: int) -> tuple[NormalizedMessage, NormalizedMessage] | None:
    by_id = {message.message_id: message for message in snapshot.messages}
    candidates: list[tuple[int, NormalizedMessage, NormalizedMessage]] = []
    for message in snapshot.messages:
        completed = message.completed_at_ms or message.created_at_ms
        if completed <= 0 or completed >= before_ms:
            continue
        # Legacy V1/V2 shape: user compaction trigger + billed assistant summary.
        if (
            message.role is MessageRole.ASSISTANT and message.summary and message.finish_reason
            and not message.error_name and message.parent_message_id
        ):
            parent = by_id.get(message.parent_message_id)
            if parent is not None and parent.role is MessageRole.USER and any(part.kind == "compaction" for part in parent.parts):
                candidates.append((completed, parent, message))
                continue
        # Current V2 shape: one completed compaction checkpoint contains the
        # projected summary/recent context itself.
        if message.role is MessageRole.USER:
            part = next((part for part in message.parts if part.kind == "compaction"), None)
            if part is not None and (part.data.get("summary") or part.data.get("recent")):
                candidates.append((completed, message, message))
    if not candidates:
        return None
    _, parent, summary = max(candidates, key=lambda item: item[0])
    return parent, summary


def _active_messages(snapshot: SessionSnapshot, target: TraceEntry) -> tuple[NormalizedMessage, ...]:
    target_message = next((m for m in snapshot.messages if m.message_id == target.message_id), None)
    cutoff = target_message.created_at_ms if target_message is not None else target.completed_at_ms
    compaction = _latest_completed_compaction_before(snapshot, cutoff)
    ordered = sorted(snapshot.messages, key=lambda m: (m.created_at_ms, m.message_id))
    if compaction is None:
        return tuple(m for m in ordered if m.created_at_ms < cutoff and m.message_id != target.message_id)
    parent, summary = compaction
    tail_start = None
    for part in parent.parts:
        if part.kind == "compaction":
            tail_start = part.data.get("tail_start_id", part.data.get("tailStartId"))
            break
    result: list[NormalizedMessage] = [summary]
    tail_started = tail_start is None
    for message in ordered:
        if message.created_at_ms <= (summary.completed_at_ms or summary.created_at_ms):
            continue
        if message.created_at_ms >= cutoff or message.message_id == target.message_id:
            continue
        if not tail_started and message.message_id == str(tail_start):
            tail_started = True
        if tail_started:
            result.append(message)
    return tuple(result)


def context_composition(snapshot: SessionSnapshot, record: PromptRecord) -> ContextComposition:
    entry = record.last_root_entry
    if entry is None or entry.request_input_approx <= 0:
        return ContextComposition(None, (), {}, False)
    messages = _active_messages(snapshot, entry)
    raw: list[ContextSource] = []
    for message in messages:
        if message.role is MessageRole.USER:
            label = "User prompt"
        elif message.summary:
            label = "Compaction summary"
        else:
            label = "Assistant response"
        for part in message.parts:
            category, kind, part_label, detail, tokens = _part_context_tokens(part)
            if tokens <= 0:
                continue
            if part.kind in {"text", "reasoning"}:
                part_label = label
            raw.append(ContextSource(category, kind, part_label, detail, tokens))
    raw_total = sum(item.tokens for item in raw)
    target = entry.request_input_approx
    if raw_total <= 0:
        return ContextComposition(target, (), {}, False)
    scale = target / raw_total
    scaled: list[ContextSource] = []
    remaining = target
    for index, item in enumerate(raw):
        tokens = remaining if index == len(raw) - 1 else max(1, round(item.tokens * scale))
        remaining -= tokens
        scaled.append(ContextSource(item.category, item.kind, item.label, item.detail, tokens, item.provenance))
    totals: dict[str, int] = {}
    for item in scaled:
        totals[item.category] = totals.get(item.category, 0) + item.tokens
    return ContextComposition(target, tuple(scaled), totals, True)


def _post_compaction_tokens(snapshot: SessionSnapshot, record: CompactionRecord) -> int | None:
    if record.result_context_tokens is not None:
        return record.result_context_tokens
    summary = next((message for message in snapshot.messages if message.message_id == record.summary_message_id), None)
    parent = next((message for message in snapshot.messages if message.message_id == record.user_message_id), None)
    if summary is None or parent is None:
        return None
    summary_tokens = _message_tokens(summary)
    tail_start = None
    for part in parent.parts:
        if part.kind == "compaction":
            tail_start = part.data.get("tail_start_id", part.data.get("tailStartId"))
            break
    if tail_start is None:
        return summary_tokens if summary_tokens > 0 else None
    ordered = sorted(snapshot.messages, key=lambda m: (m.created_at_ms, m.message_id))
    started = False
    tail_tokens = 0
    for message in ordered:
        if message.message_id == str(tail_start):
            started = True
        if not started or message.created_at_ms >= record.created_at_ms:
            continue
        tail_tokens += _message_tokens(message)
    total = summary_tokens + tail_tokens
    return total if total > 0 else None


def watch_context_state(
    snapshot: SessionSnapshot,
    bundle: RootAnalysisBundle,
    record: PromptRecord,
    catalog: PricingCatalog | None = None,
    epochs: ContextEpochs | None = None,
) -> WatchContextState:
    """Return v77-style live session delta/Next-Ictx values for Watch.

    Watch compares the current prompt's latest meaningful root request with the
    session context immediately *before that prompt*.  A completed compaction
    checkpoint wins over an older root request.  Unlike the ordinary report
    estimator this deliberately permits a still-running prompt to expose the
    latest completed root step, which is what made the v77 dashboard useful
    while tools/continuations were still executing.
    """
    if record.prompt_kind == "subtask" or record.watch_error:
        return WatchContextState(None, None)

    # Anchors from before a location move belong to a retired context epoch.
    epochs = epochs or ContextEpochs(snapshot, bundle)
    prior_entry = record.pre_prompt_entry
    prior_tokens: int | None = None
    prior_time = 0
    if (
        prior_entry is not None
        and prior_entry.session_id == record.session_id
        and prior_entry.request_input_approx > 0
        and prior_entry.completed_at_ms < record.prompt_time_ms
        and not epochs.retired(record.session_id, prior_entry.completed_at_ms)
    ):
        value = prior_entry.tokens.total
        if value > 0:
            prior_tokens = value
            prior_time = prior_entry.completed_at_ms

    prior_compaction = max(
        (
            item for item in bundle.compactions
            if item.session_id == record.session_id
            and not item.in_progress
            and item.completed_at_ms > 0
            and item.completed_at_ms < record.prompt_time_ms
            and not epochs.retired(record.session_id, item.completed_at_ms)
        ),
        key=lambda item: (item.completed_at_ms, item.created_at_ms, item.user_message_id),
        default=None,
    )
    if prior_compaction is not None and prior_compaction.completed_at_ms >= prior_time:
        compacted = _post_compaction_tokens(snapshot, prior_compaction)
        if compacted is not None and compacted > 0:
            prior_tokens = compacted
            prior_time = prior_compaction.completed_at_ms
        else:
            # The newer compaction checkpoint supersedes any older root request.
            # If its resulting size is unknown, retaining the pre-compaction value
            # would manufacture a misleading live delta.
            prior_tokens = None
            prior_time = prior_compaction.completed_at_ms

    current_tokens: int | None = None
    current_entry = _latest_meaningful_watch_root(record)
    if current_entry is not None and epochs.retired(record.session_id, current_entry.completed_at_ms):
        current_entry = None  # wait for the first real request after the move
    if current_entry is not None and current_entry.tokens.total > 0:
        current_tokens = current_entry.tokens.total

    # A running prompt may cross a compaction boundary.  Until a newer root
    # request exists after that rewrite, the old pre-compaction request is not a
    # meaningful live Next-Ictx anchor.
    if record.in_progress:
        latest_live_compaction = max(
            (
                item for item in bundle.compactions
                if item.session_id == record.session_id
                and not item.in_progress
                and item.completed_at_ms >= record.prompt_time_ms
            ),
            key=lambda item: (item.completed_at_ms, item.created_at_ms, item.user_message_id),
            default=None,
        )
        if (
            latest_live_compaction is not None
            and (current_entry is None or latest_live_compaction.completed_at_ms > current_entry.completed_at_ms)
        ):
            current_tokens = None

    # If OpenCode persisted the new user prompt but has not produced a root
    # request yet, retain the v77 provisional baseline+prompt estimate.
    if current_tokens is None and (record.in_progress or record.aborted):
        if prior_tokens is not None and prior_tokens > 0 and record.prompt_context_tokens_approx > 0:
            current_tokens = prior_tokens + record.prompt_context_tokens_approx

    if current_tokens is None or current_tokens <= 0:
        return WatchContextState(None, None)

    baseline = prior_tokens
    first_ms = min((entry.completed_at_ms for entry in record.entries), default=0)
    mixed = current_entry is not None and epochs.crossed(record.session_id, first_ms, current_entry.completed_at_ms)
    if (baseline is None or baseline <= 0) and not mixed:
        baseline = record.input_context_tokens if record.input_context_tokens > 0 else None
    delta = current_tokens - baseline if baseline is not None and baseline > 0 else None
    model_id = current_entry.model.model if current_entry is not None else record.main_model_id
    last_activity_ms = current_entry.completed_at_ms if current_entry is not None else record.prompt_time_ms
    estimate = _estimate_entry_next_context(current_entry, catalog) if current_entry is not None and catalog is not None else None
    return WatchContextState(
        current_tokens, delta, model_id, last_activity_ms,
        estimate.cached_ccost if estimate is not None else None,
        estimate.fresh_ccost if estimate is not None else None,
    )


def build_context_timeline(
    snapshot: SessionSnapshot,
    bundle: RootAnalysisBundle,
    catalog: PricingCatalog,
) -> tuple[ContextTimelineState, ...]:
    events: list[tuple[int, str, object]] = []
    events.extend((record.prompt_time_ms, "prompt", record) for record in bundle.prompts)
    events.extend((record.created_at_ms, "compaction", record) for record in bundle.compactions)
    events.extend((item.at_ms, "boundary", item) for item in snapshot.context_boundaries
                  if item.session_id == bundle.root_session_id)
    events.sort(key=lambda item: (item[0], 0 if item[1] == "prompt" else 1))
    epochs = ContextEpochs(snapshot, bundle)
    states: list[ContextTimelineState] = []
    previous_next: int | None = None
    for at_ms, kind, record in events:
        if kind == "boundary":
            previous_next = None  # a moved session's next request starts a new baseline
            continue
        if kind == "prompt":
            assert isinstance(record, PromptRecord)
            incoming = record.input_context_tokens if record.input_context_tokens > 0 else None
            estimate = estimate_next_context(record, catalog, epochs=epochs)
            next_tokens = estimate.tokens
            event_id = record.prompt_id
        else:
            assert isinstance(record, CompactionRecord)
            incoming = record.input_context_tokens if record.input_context_tokens > 0 else None
            next_tokens = None if record.in_progress else _post_compaction_tokens(snapshot, record)
            event_id = record.user_message_id
        baseline = previous_next if previous_next is not None else incoming
        delta = next_tokens - baseline if next_tokens is not None and baseline is not None else None
        states.append(ContextTimelineState(kind, event_id, at_ms, incoming, next_tokens, delta, next_tokens is not None))
        if next_tokens is not None:
            previous_next = next_tokens
    return tuple(states)


def input_context_above_price_threshold(tokens: int, model_id: str, catalog: PricingCatalog) -> bool:
    if tokens <= 0 or not model_id:
        return False
    model = catalog.resolve(model_id)
    if model is None:
        return False
    return any(tier.min_input_tokens is not None and tier.min_input_tokens > 0 and tokens >= tier.min_input_tokens for tier in model.tiers)


def next_context_warning_state(
    *,
    tokens: int,
    model_id: str,
    catalog: PricingCatalog,
    price_approach_percent: float = 75.0,
) -> NextContextWarningState:
    if tokens <= 0 or not model_id:
        return NextContextWarningState()
    approach = min(100.0, max(0.0, float(price_approach_percent)))
    model = catalog.resolve(model_id)
    if model is None:
        return NextContextWarningState()

    parts: list[str] = []
    crossed = 0
    approaching = 0
    for tier in model.tiers:
        minimum = tier.min_input_tokens or 0
        if minimum <= 0:
            continue
        boundary = minimum - 1
        if tokens >= minimum:
            crossed = max(crossed, boundary)
            continue
        if crossed <= 0 and approach > 0 and tokens >= minimum * (approach / 100.0):
            if approaching <= 0 or boundary < approaching:
                approaching = boundary

    def compact(value: int) -> str:
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M"
        if value >= 1_000:
            return f"{value / 1_000:.1f}K"
        return str(value)

    if crossed > 0:
        parts.append(f"Price threshold >{compact(crossed)} exceeded")
    elif approaching > 0:
        parts.append(f"Approaching price threshold >{compact(approaching)}")

    return NextContextWarningState(
        text="[" + "; ".join(parts) + "]" if parts else "",
        hard_warning=crossed > 0,
        price_approaching=approaching > 0 and crossed <= 0,
        price_exceeded=crossed > 0,
        price_threshold=crossed or approaching,
    )
