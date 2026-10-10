"""Pure V2 message/part/request normalization; no service or catalog acquisition."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any

from src.domain import (
    CostKind, CostObservation, MessageRole, ModelInvocation, ModelRef,
    NormalizedMessage, NormalizedPart, Provenance, TokenUsage,
)

from .errors import SourceDataError
from .opencode_errors import normalize_error_name
from .opencode_tokens import token_usage

ProvenanceFactory = Callable[[str, str | None], Provenance]


def safe_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def optional_positive_int(value: Any) -> int | None:
    parsed = safe_int(value, 0)
    return parsed if parsed > 0 else None


def normalize_token_usage(value: Any, *, context: str) -> TokenUsage | None:
    return token_usage(value, context=context, source="OpenCode V2")


def _cost(value: Any, *, context: str) -> CostObservation | None:
    if value is None:
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise SourceDataError(f"OpenCode V2 {context} contains an invalid numeric value") from exc
    if not amount.is_finite() or amount < 0:
        raise SourceDataError(f"OpenCode V2 {context} contains an invalid numeric value")
    return CostObservation(amount=amount, currency="USD", kind=CostKind.PROVIDER_REPORTED, estimated=False)


def _model_ref(provider: Any, model: Any) -> ModelRef | None:
    provider_text = "" if provider is None else str(provider).strip()
    model_text = "" if model is None else str(model).strip()
    if not provider_text and not model_text:
        return None
    return ModelRef(provider=provider_text, model=model_text)


def _part_semantic_data(data: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(data))
    for key in ("id", "messageID", "sessionID"):
        result.pop(key, None)
    return result


def _part_times(data: Mapping[str, Any], created: int, completed: int | None) -> tuple[int, int]:
    time_value = data.get("time")
    time_map = time_value if isinstance(time_value, Mapping) else {}
    start = safe_int(time_map.get("start"), created)
    end = safe_int(time_map.get("end"), completed or start)
    return start, end


def normalize_message_bundle(
    bundle: Mapping[str, Any], provenance: ProvenanceFactory,
) -> tuple[NormalizedMessage, tuple[NormalizedPart, ...]]:
    info = bundle.get("info")
    raw_parts = bundle.get("parts")
    if not isinstance(info, Mapping) or not isinstance(raw_parts, list):
        raise SourceDataError("OpenCode V2 message payload is invalid")
    message_id = info.get("id")
    session_id = info.get("sessionID")
    if not isinstance(message_id, str) or not isinstance(session_id, str):
        raise SourceDataError("OpenCode V2 message identity is invalid")
    role_text = str(info.get("role", "")).lower()
    role = {"user": MessageRole.USER, "assistant": MessageRole.ASSISTANT}.get(role_text, MessageRole.OTHER)
    time_value = info.get("time")
    time_map = time_value if isinstance(time_value, Mapping) else {}
    created = safe_int(time_map.get("created"))
    completed = optional_positive_int(time_map.get("completed"))

    model: ModelRef | None = None
    variant: str | None = None
    if role is MessageRole.USER:
        nested = info.get("model")
        if isinstance(nested, Mapping):
            model = _model_ref(nested.get("providerID"), nested.get("modelID", nested.get("id")))
            raw_variant = nested.get("variant", info.get("variant"))
            variant = str(raw_variant) if raw_variant not in (None, "") else None
    elif role is MessageRole.ASSISTANT:
        model = _model_ref(info.get("providerID"), info.get("modelID"))
        raw_variant = info.get("variant")
        variant = str(raw_variant) if raw_variant not in (None, "") else None

    parts: list[NormalizedPart] = []
    for raw in raw_parts:
        if not isinstance(raw, Mapping):
            raise SourceDataError("OpenCode V2 message contains an invalid part")
        part_id = raw.get("id")
        if not isinstance(part_id, str):
            raise SourceDataError("OpenCode V2 part identity is invalid")
        part_session = str(raw.get("sessionID") or session_id)
        part_message = str(raw.get("messageID") or message_id)
        part_created, part_updated = _part_times(raw, created, completed)
        parts.append(NormalizedPart(
            part_id=part_id, message_id=part_message, session_id=part_session,
            kind=str(raw.get("type", "other") or "other"),
            created_at_ms=part_created, updated_at_ms=part_updated,
            provenance=provenance(part_session, part_id), data=_part_semantic_data(raw),
        ))
    metadata = {key: deepcopy(info[key]) for key in ("mode", "system", "structured") if key in info}
    message = NormalizedMessage(
        message_id=message_id, session_id=session_id, role=role,
        created_at_ms=created, completed_at_ms=completed,
        parent_message_id=str(info.get("parentID")) if info.get("parentID") not in (None, "") else None,
        model=model, variant=variant,
        agent=str(info.get("agent")) if info.get("agent") not in (None, "") else None,
        summary=bool(info.get("summary", False)),
        finish_reason=str(info.get("finish")) if info.get("finish") not in (None, "") else None,
        error_name=normalize_error_name(info.get("error")),
        tokens=normalize_token_usage(info.get("tokens"), context="message tokens"),
        cost=_cost(info.get("cost"), context="message cost") if "cost" in info else None,
        parts=tuple(parts), provenance=provenance(session_id, message_id), metadata=metadata,
    )
    return message, tuple(parts)


def normalize_invocations(message: NormalizedMessage, provenance: ProvenanceFactory) -> list[ModelInvocation]:
    """Per-step observations replace cumulative message usage, never add to it."""
    if message.role is not MessageRole.ASSISTANT or message.model is None:
        return []
    steps = [part for part in message.parts if part.kind == "step-finish" and isinstance(part.data.get("tokens"), Mapping)]
    if steps:
        result: list[ModelInvocation] = []
        for part in steps:
            tokens = normalize_token_usage(part.data.get("tokens"), context="step tokens")
            if tokens is None:
                continue
            result.append(ModelInvocation(
                invocation_id=f"{message.message_id}:{part.part_id}", session_id=message.session_id,
                created_at_ms=part.created_at_ms or message.created_at_ms,
                completed_at_ms=part.updated_at_ms or message.completed_at_ms,
                model=message.model, tokens=tokens,
                cost=_cost(part.data.get("cost"), context="step cost") if "cost" in part.data else None,
                provenance=provenance(message.session_id, part.part_id),
                initiating_event_id=message.parent_message_id, message_id=message.message_id,
                step_part_id=part.part_id, variant=message.variant, summary=message.summary,
                finish_reason=message.finish_reason, error_name=message.error_name,
            ))
        return result
    if message.tokens is None:
        return []
    request_id = message.metadata.get("provider_request_id") if isinstance(message.metadata, Mapping) else None
    return [ModelInvocation(
        invocation_id=message.message_id, session_id=message.session_id,
        created_at_ms=message.created_at_ms, completed_at_ms=message.completed_at_ms,
        model=message.model, tokens=message.tokens, cost=message.cost, provenance=message.provenance,
        initiating_event_id=message.parent_message_id,
        provider_request_id=str(request_id) if request_id else None, message_id=message.message_id,
        variant=message.variant, summary=message.summary,
        finish_reason=message.finish_reason, error_name=message.error_name,
    )]
