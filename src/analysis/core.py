"""Composition of source-neutral prompt/billing/compaction analysis."""
from __future__ import annotations

from collections import defaultdict

from src.domain import EventKind, MessageRole, SessionSnapshot

from .billing import CostEstimator, ProviderScope
from .causal import TRACKED_PROVIDER_DEFAULT, build_prompt_records, trace_entries
from .compaction import completed_compactions
from .models import RootAnalysisBundle


def snapshot_is_stable(snapshot: SessionSnapshot) -> bool:
    """Conservatively decide whether derived results may be persisted.

    A stable snapshot has no unfinished assistant message and no visible root
    prompt/compaction awaiting a terminal assistant result.  False negatives
    merely cost performance; false positives could persist incomplete analysis,
    so uncertainty intentionally returns False.
    """
    if any(session.active is True for session in snapshot.sessions):
        return False
    if any(activity.running for activity in snapshot.background):
        return False
    for message in snapshot.messages:
        if message.role is MessageRole.ASSISTANT and message.completed_at_ms is None and not message.error_name:
            return False

    assistant_parents = {
        message.parent_message_id
        for message in snapshot.messages
        if message.role is MessageRole.ASSISTANT and message.parent_message_id
    }
    native_completed_compactions = {
        message.message_id
        for message in snapshot.messages
        if message.role is MessageRole.USER
        and any(
            part.kind == "compaction"
            and str(part.data.get("status") or "completed").lower() == "completed"
            and bool(part.data.get("summary") or part.data.get("recent"))
            for part in message.parts
        )
    }
    for event in snapshot.events:
        if event.session_id != snapshot.root.session_id:
            continue
        if (
            event.kind in {EventKind.USER_PROMPT, EventKind.SUBTASK, EventKind.COMPACTION}
            and event.event_id not in assistant_parents
            and event.event_id not in native_completed_compactions
        ):
            return False

    # A compaction only becomes durable analysis state after a completed summary.
    summary_parents = {
        message.parent_message_id
        for message in snapshot.messages
        if message.role is MessageRole.ASSISTANT
        and message.parent_message_id
        and message.summary
        and message.finish_reason
        and not message.error_name
        and message.completed_at_ms is not None
    }
    for event in snapshot.events:
        if event.session_id == snapshot.root.session_id and event.kind is EventKind.COMPACTION:
            if event.event_id not in summary_parents and event.event_id not in native_completed_compactions:
                return False
    return True


def analyze_snapshot(
    snapshot: SessionSnapshot,
    *,
    tracked_provider: ProviderScope = TRACKED_PROVIDER_DEFAULT,
    estimator: CostEstimator | None = None,
    now_ms: int | None = None,
    subscription_providers: frozenset[str] = frozenset(),
) -> RootAnalysisBundle:
    entries = trace_entries(snapshot, subscription_providers=subscription_providers)
    prompts = build_prompt_records(
        snapshot,
        tracked_provider=tracked_provider,
        estimator=estimator,
        now_ms=now_ms,
        subscription_providers=subscription_providers,
    )
    compactions = completed_compactions(
        snapshot,
        tracked_provider=tracked_provider,
        estimator=estimator,
        subscription_providers=subscription_providers,
    )
    return RootAnalysisBundle(
        root_session_id=snapshot.root.session_id,
        source_revision=snapshot.source_revision,
        trace_entries=entries,
        prompts=prompts,
        compactions=compactions,
        cacheable=snapshot_is_stable(snapshot) and not any(record.in_progress for record in prompts)
        and not any(record.in_progress for record in compactions),
    )
