"""Observation-based Watch row lifecycle and cap policy."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

from src.domain import EventKind, SessionSnapshot
from src.reports.models import PromptProjection, SessionPromptBlock

from .models import ToolObservation, WatchRow
from .tools import observe_tools


def _event_key(prompt: PromptProjection) -> str:
    """Stable row identity, including projections without a source event ID."""
    return prompt.event_id or f"{prompt.at_ms}:{prompt.prompt_number}:{prompt.label}"


def _marker(prompt: PromptProjection, *, recent_completion: bool, recent_running: bool) -> str:
    if prompt.aborted:
        return "!" if recent_completion else ""
    if prompt.watch_error:
        return "!"
    if prompt.in_progress:
        return "+" if recent_running else ""
    return "✓" if recent_completion else ""


def _activity(snapshot: SessionSnapshot, prompt: PromptProjection, event_id: str, now_ms: int) -> ToolObservation:
    """Final counts remain observable; only live prompts may expose active work."""
    tool = observe_tools(snapshot, event_id, is_compaction=prompt.is_compaction, now_ms=now_ms)
    if not prompt.in_progress:
        return replace(tool, running_tool="", running_ms=0, todo_completed=0, todo_total=0, active_todo="")
    if not prompt.background_kinds:
        return tool
    return replace(tool, background_kinds=prompt.background_kinds,
                   background_ms=max(0, now_ms - prompt.background_started_ms))


@dataclass(slots=True)
class _Observed:
    first_seen_ms: int
    was_running: bool
    completion_seen_ms: int | None = None
    ever_running: bool = False
    last_prompt: PromptProjection | None = None
    session_title: str = ""
    display_time_ms: int = 0
    event_sequence: int = 0
    after_compaction: bool = False
    last_tool: ToolObservation | None = None


class WatchRowTracker:
    def __init__(self, *, started_at_ms: int, recent_seconds: float, max_rows: int, session_scope: bool = False) -> None:
        self.started_at_ms = int(started_at_ms)
        self.recent_ms = max(0, int(float(recent_seconds) * 1000))
        self.max_rows = max(1, int(max_rows))
        self.session_scope = bool(session_scope)
        self._observed: dict[tuple[str, str], _Observed] = {}
        self._final_activity: dict[str, tuple[SessionSnapshot, str, ToolObservation]] = {}

    @staticmethod
    def _event_sequences(snapshot: SessionSnapshot) -> dict[str, int]:
        """Number root prompt/compaction events in canonical timeline order.

        OpenCode V2 can continue the same logical prompt after an automatic
        compaction.  Source timestamps remain useful, but the canonical event
        sequence is the stable tie-breaker when adjacent events share/coarsen a
        timestamp.  Prompt display numbers remain the ordinary user-prompt
        numbers; this sequence is Watch ordering state only.
        """
        root_id = snapshot.root.session_id
        allowed = {EventKind.USER_PROMPT, EventKind.SUBTASK, EventKind.COMPACTION}
        events = [
            (event.created_at_ms, index, event.event_id)
            for index, event in enumerate(snapshot.events)
            if event.session_id == root_id and event.kind in allowed
        ]
        events.sort(key=lambda item: (item[0], item[1], item[2]))
        return {event_id: index + 1 for index, (_at_ms, _source_index, event_id) in enumerate(events)}

    def _recent_completion(self, observed: _Observed, now_ms: int) -> bool:
        return (
            observed.completion_seen_ms is not None
            and self.recent_ms > 0
            and 0 <= now_ms - observed.completion_seen_ms < self.recent_ms
        )

    def _sort_key(self, row: WatchRow) -> tuple[int, int, int, str, str]:
        event_id = _event_key(row.prompt)
        observed = self._observed.get((row.session_id, event_id))
        at_ms = observed.display_time_ms if observed and observed.display_time_ms else row.prompt.at_ms
        sequence = observed.event_sequence if observed else 0
        if row.prompt.is_compaction:
            rank = 0
        elif observed and observed.after_compaction:
            rank = 2
        else:
            rank = 1
        return (at_ms, sequence, rank, row.session_id, event_id)

    @staticmethod
    def _latest_compaction_after(
        prompt: PromptProjection,
        block: SessionPromptBlock,
        sequence_by_event: Mapping[str, int],
    ) -> PromptProjection | None:
        if prompt.is_compaction or not prompt.in_progress:
            return None
        prompt_sequence = sequence_by_event.get(prompt.event_id, 0)
        candidates: list[PromptProjection] = []
        for row in block.rows:
            if not row.is_compaction:
                continue
            compact_sequence = sequence_by_event.get(row.event_id, 0)
            if prompt_sequence and compact_sequence:
                if compact_sequence > prompt_sequence:
                    candidates.append(row)
            elif row.at_ms > prompt.at_ms:
                candidates.append(row)
        if not candidates:
            return None
        return max(candidates, key=lambda row: (row.at_ms, sequence_by_event.get(row.event_id, 0), row.event_id))

    def _row(
        self,
        block: SessionPromptBlock,
        prompt: PromptProjection,
        snapshot: SessionSnapshot,
        now_ms: int,
        *,
        sequence_by_event: Mapping[str, int],
    ) -> WatchRow | None:
        event_id = _event_key(prompt)
        key = (block.session_id, event_id)
        observed = self._observed.get(key)
        if observed and observed.last_prompt and observed.last_prompt.completed_successfully and prompt.aborted:
            # Incomplete refresh reconstruction cannot downgrade an observed
            # final response to an abort for the same event identity.
            prompt = observed.last_prompt
        eligible = prompt.in_progress or prompt.at_ms >= self.started_at_ms or observed is not None
        if not eligible and not self.session_scope:
            return None
        if observed is None:
            observed = _Observed(
                now_ms,
                prompt.in_progress,
                ever_running=prompt.in_progress,
                last_prompt=prompt,
                session_title=block.title,
                display_time_ms=prompt.at_ms,
                event_sequence=sequence_by_event.get(event_id, 0),
            )
            if not prompt.in_progress and prompt.at_ms >= self.started_at_ms:
                observed.completion_seen_ms = now_ms
            self._observed[key] = observed
        else:
            if observed.was_running and not prompt.in_progress:
                observed.completion_seen_ms = now_ms
            observed.was_running = prompt.in_progress
            observed.ever_running = observed.ever_running or prompt.in_progress
            observed.last_prompt = prompt
            observed.session_title = block.title
            if not observed.display_time_ms:
                observed.display_time_ms = prompt.at_ms
            if not observed.event_sequence:
                observed.event_sequence = sequence_by_event.get(event_id, 0)

        continuation_compaction = self._latest_compaction_after(prompt, block, sequence_by_event)
        if continuation_compaction is not None:
            compact_sequence = sequence_by_event.get(continuation_compaction.event_id, 0)
            compact_time = continuation_compaction.at_ms
            if (compact_time, compact_sequence) >= (observed.display_time_ms, observed.event_sequence):
                # The same logical prompt is now a post-compaction continuation.
                # Keep its #N identity but place the live row immediately after
                # the compaction boundary, and retain that placement on completion.
                observed.display_time_ms = compact_time
                observed.event_sequence = compact_sequence
                observed.after_compaction = True

        recent_running = (
            prompt.in_progress
            and self.recent_ms > 0
            and 0 <= now_ms - observed.first_seen_ms < self.recent_ms
        )
        marker = _marker(prompt, recent_completion=self._recent_completion(observed, now_ms),
                         recent_running=recent_running)
        return WatchRow(block.session_id, block.title, prompt, marker)

    def _retained_missing_rows(
        self,
        block: SessionPromptBlock,
        snapshot: SessionSnapshot,
        present_event_ids: set[str],
        now_ms: int,
    ) -> list[WatchRow]:
        """Retain a prompt that disappears from analysis after V2 compaction.

        Current V2 may attribute post-compaction assistant work to the compaction
        checkpoint rather than to the original user message.  A zero-call prompt
        can therefore be visible while the session is active and disappear from
        the stateless report projection as soon as it becomes idle.  Watch has
        already observed the logical prompt identity, so keep that dashboard row
        as completed history instead of deleting it at the transition.
        """
        retained: list[WatchRow] = []
        for (session_id, event_id), observed in self._observed.items():
            if session_id != block.session_id or event_id in present_event_ids:
                continue
            prompt = observed.last_prompt
            if prompt is None or prompt.is_compaction or not observed.ever_running:
                continue
            if observed.was_running:
                observed.was_running = False
                observed.completion_seen_ms = now_ms
                duration = max(prompt.duration_ms or 0, max(0, now_ms - prompt.at_ms))
                prompt = replace(prompt, in_progress=False, duration_ms=duration)
                observed.last_prompt = prompt
            # A retained prompt is never running: was_running tracks last_prompt.
            marker = _marker(prompt, recent_completion=self._recent_completion(observed, now_ms), recent_running=False)
            retained.append(WatchRow(session_id, observed.session_title or block.title, prompt, marker, None))
        return retained

    def _tool_activity(self, row: WatchRow, snapshot: SessionSnapshot, now_ms: int) -> ToolObservation:
        """Stable idle frames reuse projections, not a second history/causal cache."""
        event_id = _event_key(row.prompt)
        cached = self._final_activity.get(row.session_id)
        if not row.prompt.in_progress and cached and cached[0] is snapshot and cached[1] == event_id:
            return cached[2]
        tool = _activity(snapshot, row.prompt, event_id, now_ms)
        observed = self._observed.get((row.session_id, event_id))
        if observed is not None:
            if not tool.tool_count and observed.last_tool and not any(
                message.parent_message_id == event_id for message in snapshot.messages
            ):
                tool = replace(observed.last_tool, running_tool="", running_ms=0, todo_completed=0,
                               todo_total=0, active_todo="", background_kinds=(), background_ms=0)
            observed.last_tool = tool
        if row.prompt.in_progress:
            self._final_activity.pop(row.session_id, None)
        else:
            self._final_activity[row.session_id] = (snapshot, event_id, tool)
        return tool

    def _attach_activity(
        self, rows: list[WatchRow], snapshot: SessionSnapshot, now_ms: int, sequences: Mapping[str, int],
    ) -> list[WatchRow]:
        """Attach final/live observations to the latest canonical prompt per session.

        New zero-usage prompts suppress the old activity even before projection;
        compaction does not transfer a logical prompt's diagnostic ownership.
        """
        if not rows:
            return rows
        prompts = [event for event in snapshot.events if event.session_id == snapshot.root.session_id
                   and event.kind in {EventKind.USER_PROMPT, EventKind.SUBTASK}]
        latest_prompt = max(prompts, key=lambda event: sequences.get(event.event_id, 0)).event_id if prompts else ""
        latest_key = _event_key(rows[-1].prompt)
        result = []
        for row in rows:
            event_id = _event_key(row.prompt)
            tool = None
            if event_id == latest_prompt or (row.prompt.is_compaction and row.prompt.in_progress):
                tool = self._tool_activity(row, snapshot, now_ms)
            result.append(replace(row, tool=tool, is_latest_session_event=event_id == latest_key))
        return result

    def project(
        self,
        blocks: Mapping[str, SessionPromptBlock],
        snapshots: Mapping[str, SessionSnapshot],
        *,
        now_ms: int,
    ) -> tuple[WatchRow, ...]:
        rows: list[WatchRow] = []
        for session_id, block in blocks.items():
            snapshot = snapshots.get(session_id)
            if snapshot is None:
                continue
            sequence_by_event = self._event_sequences(snapshot)
            session_rows: list[WatchRow] = []
            present_event_ids: set[str] = set()
            for prompt in block.rows:
                present_event_ids.add(_event_key(prompt))
                row = self._row(
                    block, prompt, snapshot, now_ms,
                    sequence_by_event=sequence_by_event,
                )
                if row is not None:
                    session_rows.append(row)
            session_rows.extend(self._retained_missing_rows(block, snapshot, present_event_ids, now_ms))

            if self.session_scope and not session_rows and block.rows:
                prompt = block.rows[-1]
                session_rows.append(WatchRow(
                    block.session_id, block.title, prompt,
                    "+" if prompt.in_progress and self.recent_ms > 0 else "",
                    is_latest_session_event=True,
                ))

            session_rows.sort(key=self._sort_key)
            session_rows = self._attach_activity(session_rows, snapshot, now_ms, sequence_by_event)
            rows.extend(session_rows)

        rows.sort(key=self._sort_key)
        protected = [
            row for row in rows
            if row.prompt.in_progress
            or row.marker in {"+", "✓", "!"}
        ]
        protected_keys = {(row.session_id, row.prompt.event_id) for row in protected}
        ordinary = [row for row in rows if (row.session_id, row.prompt.event_id) not in protected_keys]
        room = max(0, self.max_rows - len(protected))
        kept = ordinary[-room:] if room else []
        selected = protected + kept
        selected.sort(key=self._sort_key)
        if self.session_scope:
            return tuple(selected)

        # Group only after the global cap/protection policy has selected rows.
        # Each block retains canonical order; latest visible activity orders
        # blocks chronologically, with session identity breaking timestamp ties.
        by_session: dict[str, list[WatchRow]] = {}
        for row in selected:
            by_session.setdefault(row.session_id, []).append(row)
        ordered_blocks = sorted(
            by_session.values(),
            key=lambda block: (self._sort_key(block[-1])[0], block[-1].session_id),
        )
        return tuple(row for block in ordered_blocks for row in block)
