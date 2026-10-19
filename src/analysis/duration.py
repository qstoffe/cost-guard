"""Source-independent execution timing and overlap-safe accumulated duration."""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from src.domain import BackgroundActivity, NormalizedMessage
from .models import PromptReference, TraceEntry


def execution_duration(start_ms: int, end_ms: int | None) -> int | None:
    """Unknown/invalid boundaries are unavailable, never an invented zero."""
    if start_ms <= 0 or end_ms is None or end_ms < start_ms:
        return None
    return end_ms - start_ms


def prompt_duration(
    ref: PromptReference, root_messages: Sequence[NormalizedMessage], latest: NormalizedMessage | None,
    entries: Sequence[TraceEntry], message_index: Mapping[str, NormalizedMessage],
    *, in_progress: bool, now_ms: int, background: Sequence[BackgroundActivity],
) -> int | None:
    """Use existing lifecycle state; metadata/observation cannot end dead work.

    A completed assistant (including a terminal tool-call continuation) supplies
    an activity boundary. Its task/tool ends and owned background work can extend
    that boundary, without borrowing a child's unrelated session metadata.
    """
    start_ms = ref.prompt_time_ms
    if in_progress:
        return execution_duration(start_ms, now_ms)
    if latest is None:
        return None
    end = latest.termination.completed_at_ms if latest.termination else latest.completed_at_ms
    if end is None:
        return None
    child_ids = {entry.message_id for entry in entries if entry.session_id != ref.session_id}
    messages = [*root_messages, *(message_index[mid] for mid in child_ids if mid in message_index)]
    owners = {message.message_id for message in messages}
    if any(item.owner_message_id in owners and not item.running and item.ended_at_ms is None
           and (item.owner_message_id == latest.message_id or end < item.started_at_ms) for item in background):
        return None
    ends = [end]
    for message in messages:
        if message.completed_at_ms is not None:
            ends.append(message.completed_at_ms)
        for part in message.parts:
            if part.updated_at_ms > part.created_at_ms:
                ends.append(part.updated_at_ms)
            state = part.data.get("state")
            timing = state.get("time") if isinstance(state, Mapping) else None
            value = timing.get("end") if isinstance(timing, Mapping) else None
            if isinstance(value, int) and not isinstance(value, bool):
                ends.append(value)
    ends.extend(item.ended_at_ms for item in background
                if item.owner_message_id in owners and item.ended_at_ms is not None)
    return execution_duration(start_ms, max(ends))


def accumulated_duration(intervals: Iterable[tuple[int, int | None]]) -> int | None:
    """Union (start, duration) pairs in O(n log n); any unknown poisons total."""
    resolved: list[tuple[int, int]] = []
    for start, duration in intervals:
        if start <= 0 or duration is None or duration < 0:
            return None
        resolved.append((start, start + duration))
    if not resolved:
        return 0
    resolved.sort()
    left, right = resolved[0]
    total = 0
    for start, end in resolved[1:]:
        if start <= right:
            right = max(right, end)
        else:
            total += right - left
            left, right = start, end
    return total + right - left
