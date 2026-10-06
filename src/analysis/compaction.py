"""Explicit completed /compact event analysis."""
from __future__ import annotations

from decimal import Decimal

from src.domain import EventKind, MessageRole, SessionSnapshot

from .billing import CostEstimator, ProviderScope, actual_entry_cost, provider_matches
from .causal import TRACKED_PROVIDER_DEFAULT, active_compaction_event, trace_entries
from .context import estimate_text_tokens
from .models import CompactionRecord


def completed_compactions(
    snapshot: SessionSnapshot,
    *,
    since_ms: int = 0,
    before_ms: int = 0,
    tracked_provider: ProviderScope = TRACKED_PROVIDER_DEFAULT,
    estimator: CostEstimator | None = None,
    subscription_providers: frozenset[str] = frozenset(),
) -> tuple[CompactionRecord, ...]:
    events = {
        event.event_id: event
        for event in snapshot.events
        if event.session_id == snapshot.root.session_id
        and event.kind is EventKind.COMPACTION
        and event.created_at_ms >= since_ms
        and (before_ms <= 0 or event.created_at_ms < before_ms)
    }
    active = active_compaction_event(snapshot)
    if not events:
        return ()
    entries = trace_entries(snapshot, subscription_providers=subscription_providers)
    result: list[CompactionRecord] = []
    handled_events: set[str] = set()
    for message in snapshot.messages:
        if (
            message.session_id != snapshot.root.session_id
            or message.role is not MessageRole.ASSISTANT
            or not message.parent_message_id
            or message.parent_message_id not in events
            or not message.summary
            or not message.finish_reason
            or message.error_name
        ):
            continue
        event = events[message.parent_message_id]
        message_entries = tuple(sorted(
            (
                entry for entry in entries
                if entry.message_id == message.message_id and provider_matches(entry.model.provider, tracked_provider)
            ),
            key=lambda entry: (entry.completed_at_ms, entry.sort_order),
        ))
        cost = Decimal("0")
        estimated = unresolved = 0
        direct = read = write = output = 0
        for entry in message_entries:
            billing = actual_entry_cost(entry, estimator)
            cost += billing.dollars
            estimated += int(billing.estimated)
            unresolved += int(billing.unresolved)
            direct += entry.tokens.input
            read += entry.tokens.cache_read
            write += entry.tokens.cache_write
            output += entry.tokens.output + entry.tokens.reasoning
        first = next((entry for entry in message_entries if entry.request_input_approx > 0), None)
        model_id = first.model.model if first else (message.model.model if message.model else "")
        provider_id = first.model.provider if first else (message.model.provider if message.model else "")
        handled_events.add(event.event_id)
        result.append(CompactionRecord(
            session_id=snapshot.root.session_id,
            user_message_id=event.event_id,
            summary_message_id=message.message_id,
            created_at_ms=event.created_at_ms,
            completed_at_ms=message.completed_at_ms or event.created_at_ms,
            automatic=event.metadata.get("auto", "false").lower() == "true",
            model_id=model_id,
            provider_id=provider_id,
            variant=first.variant if first and first.variant else (message.variant or event.metadata.get("variant", "")),
            entries=message_entries,
            cost=cost,
            estimated_fallback_requests=estimated,
            unresolved_fallback_requests=unresolved,
            input_context_tokens=first.request_input_approx if first else 0,
            input_tokens=direct,
            cache_read_tokens=read,
            cache_write_tokens=write,
            output_tokens=output,
        ))
    # Current V2 projects a completed compaction as one durable `compaction`
    # message containing the summary/recent context. It has no separate billed
    # assistant-summary message, so preserve it as an explicit /compact boundary
    # with billing cells intentionally blank at presentation time.
    messages_by_id = {message.message_id: message for message in snapshot.messages}
    for event_id, event in events.items():
        if event_id in handled_events:
            continue
        message = messages_by_id.get(event_id)
        if message is None or message.role is not MessageRole.USER:
            continue
        compaction_part = next((part for part in message.parts if part.kind == "compaction"), None)
        if compaction_part is None:
            continue
        data = compaction_part.data
        status = str(data.get("status") or "completed").lower()
        if status != "completed":
            continue
        if not data.get("summary") and not data.get("recent"):
            continue
        tokens = data.get("tokens") if isinstance(data.get("tokens"), dict) else {}
        cache = tokens.get("cache") if isinstance(tokens.get("cache"), dict) else {}
        direct = int(tokens.get("input") or 0)
        read = int(cache.get("read") or 0)
        write = int(cache.get("write") or 0)
        output = int(tokens.get("output") or 0) + int(tokens.get("reasoning") or 0)
        incoming = direct + read + write
        recent = str(data.get("recent") or "")
        result_context = output + estimate_text_tokens(recent)
        model = data.get("model") if isinstance(data.get("model"), dict) else {}
        provider_context = data.get("providerContext") if isinstance(data.get("providerContext"), dict) else {}
        provenance = provider_context.get("provenance") if isinstance(provider_context.get("provenance"), dict) else {}
        model_id = str(model.get("id") or model.get("modelID") or provenance.get("modelID") or event.metadata.get("model_id", ""))
        provider_id = str(model.get("providerID") or provenance.get("providerID") or event.metadata.get("provider_id", ""))
        result.append(CompactionRecord(
            session_id=snapshot.root.session_id,
            user_message_id=event.event_id,
            summary_message_id=message.message_id,
            created_at_ms=event.created_at_ms,
            completed_at_ms=message.completed_at_ms or message.created_at_ms or event.created_at_ms,
            automatic=event.metadata.get("auto", "false").lower() == "true",
            model_id=model_id,
            provider_id=provider_id,
            variant=event.metadata.get("variant", ""),
            entries=(),
            cost=Decimal("0"),
            estimated_fallback_requests=0,
            unresolved_fallback_requests=0,
            input_context_tokens=incoming,
            input_tokens=direct,
            cache_read_tokens=read,
            cache_write_tokens=write,
            output_tokens=output,
            result_context_tokens=result_context or None,
        ))
    if active is not None and active.event_id in events and active.event_id not in handled_events and not any(
        record.user_message_id == active.event_id for record in result
    ):
        result.append(CompactionRecord(
            session_id=snapshot.root.session_id,
            user_message_id=active.event_id,
            summary_message_id=active.event_id,
            created_at_ms=active.created_at_ms,
            completed_at_ms=active.created_at_ms,
            automatic=active.metadata.get("auto", "false").lower() == "true",
            model_id=active.metadata.get("model_id", ""),
            provider_id=active.metadata.get("provider_id", ""),
            variant=active.metadata.get("variant", ""),
            entries=(), cost=Decimal(0), estimated_fallback_requests=0,
            unresolved_fallback_requests=0, input_context_tokens=0,
            input_tokens=0, cache_read_tokens=0, cache_write_tokens=0,
            output_tokens=0, in_progress=True,
        ))
    return tuple(sorted(result, key=lambda item: (item.created_at_ms, item.summary_message_id)))
