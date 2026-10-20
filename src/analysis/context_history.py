"""Evidence-backed active-history membership and continuing-context anchors."""
from __future__ import annotations

from bisect import bisect_left, bisect_right
import json
from collections.abc import Mapping
from dataclasses import dataclass

from src.domain import MessageRole, NormalizedMessage, NormalizedPart, SessionSnapshot

from .models import PromptRecord, RootAnalysisBundle, TraceEntry


@dataclass(frozen=True, slots=True)
class ContinuingContext:
    entry: TraceEntry
    tokens: int | None
    cached_tokens: int
    fresh_tokens: int
    active: bool | None


@dataclass(frozen=True, slots=True)
class CompactionContext:
    session_id: str
    message_id: str
    completed_at_ms: int
    tokens: int | None
    provider_id: str
    model_id: str
    variant: str


def _entry_key(entry: TraceEntry) -> tuple[str, str | None, str | None, int, int]:
    return entry.session_id, entry.message_id, entry.step_part_id, entry.completed_at_ms, entry.sort_order


def _text_tokens(text: str) -> int:
    return 0 if not text else (len(text) + 3) // 4


def _object_tokens(value: object) -> int:
    try:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError):
        text = str(value)
    return _text_tokens(text)


def _part_tokens(part: NormalizedPart) -> int:
    data = part.data
    if part.kind in {"text", "reasoning"}:
        return _text_tokens(str(data.get("text") or ""))
    if part.kind == "file":
        label = str(data.get("filename") or "file")
        mime = str(data.get("mime") or "")
        return max(4, _text_tokens(label + " " + mime))
    if part.kind == "compaction":
        return 0
    return _object_tokens(data)


def _tool_result_tokens(part: NormalizedPart) -> int:
    state = part.data.get("state")
    if not isinstance(state, Mapping):
        return 0
    value = state.get("output", state.get("result", state.get("metadata")))
    return _object_tokens(value) if value is not None else 0


def _message_tokens(message: NormalizedMessage) -> int:
    if message.role is MessageRole.ASSISTANT and message.tokens is not None:
        return message.tokens.output + message.tokens.reasoning
    return sum(_part_tokens(part) for part in message.parts)


class ContextHistory:
    """Track only active persisted history; request usage remains outside this owner."""

    def __init__(self, snapshot: SessionSnapshot, bundle: RootAnalysisBundle,
                 compactions: tuple[CompactionContext, ...] = ()) -> None:
        self._snapshot = snapshot
        self._messages = {(item.session_id, item.message_id): item for item in snapshot.messages}
        self._message_times = {(item.session_id, item.message_id): item.created_at_ms for item in snapshot.messages}
        self._active = {item.session_id: frozenset(item.message_ids) for item in snapshot.active_contexts}
        self._event_sessions = {record.prompt_id: record.session_id for record in bundle.prompts}
        self._event_sessions.update({record.user_message_id: record.session_id for record in bundle.compactions})
        self._next_prompt: dict[tuple[str, str, int], int] = {}
        self._set_next_prompts(bundle)
        self._activity_messages = self._index_activity_messages(snapshot)
        self._compaction_starts: dict[str, list[int]] = {}
        self._compaction_entry_keys = {
            _entry_key(entry) for item in bundle.compactions for entry in item.entries
        }
        for item in bundle.compactions:
            if not item.in_progress and item.created_at_ms > 0:
                self._compaction_starts.setdefault(item.session_id, []).append(item.created_at_ms)
        for values in self._compaction_starts.values():
            values.sort()
        self._unknown_growth: dict[str, list[int]] = {}
        self._growth = self._growth_index(snapshot, bundle)
        self._anchors: dict[tuple[str, str | None, str | None, int, int], TraceEntry | None] = {}
        self._temporary: set[tuple[str, str | None, str | None, int, int]] = set()
        self._temporary_from_compaction: dict[tuple[str, str | None, str | None, int, int], CompactionContext] = {}
        self._uncertain: set[tuple[str, str | None, str | None, int, int]] = set()
        self._build_anchors(snapshot, bundle, compactions)

    @staticmethod
    def _index_activity_messages(snapshot: SessionSnapshot) -> dict[str, tuple[list[int], list[tuple[int, str]]]]:
        grouped: dict[str, list[tuple[int, int, str]]] = {}
        for message in snapshot.messages:
            updated = max((part.updated_at_ms for part in message.parts), default=message.created_at_ms)
            activity = max(message.completed_at_ms or message.created_at_ms, updated)
            grouped.setdefault(message.session_id, []).append((message.created_at_ms, activity, message.message_id))
        result: dict[str, tuple[list[int], list[tuple[int, str]]]] = {}
        for session_id, values in grouped.items():
            values.sort()
            result[session_id] = ([item[0] for item in values], [(item[1], item[2]) for item in values])
        return result

    def _set_next_prompts(self, bundle: RootAnalysisBundle) -> None:
        records: dict[str, list[PromptRecord]] = {}
        for record in bundle.prompts:
            records.setdefault(record.session_id, []).append(record)
        for session_records in records.values():
            session_records.sort(key=lambda item: (item.prompt_time_ms, item.prompt_number))
            for current, following in zip(session_records, session_records[1:]):
                key = (current.session_id, current.prompt_id, current.prompt_time_ms)
                self._next_prompt[key] = following.prompt_time_ms

    def _growth_index(self, snapshot: SessionSnapshot, bundle: RootAnalysisBundle) -> dict[str, tuple[list[int], list[int]]]:
        if not any(self._active.values()):
            return {}
        events: dict[str, list[tuple[int, int]]] = {}
        request_messages = self._request_messages(bundle)
        self._request_growth(events, bundle)
        self._message_growth(events, snapshot, request_messages)
        return self._prefix_growth(events)

    @staticmethod
    def _request_messages(bundle: RootAnalysisBundle) -> dict[tuple[str, str], list[TraceEntry]]:
        result: dict[tuple[str, str], list[TraceEntry]] = {}
        for entry in bundle.trace_entries:
            if entry.message_id:
                result.setdefault((entry.session_id, entry.message_id), []).append(entry)
        return result

    def _request_growth(self, events: dict[str, list[tuple[int, int]]], bundle: RootAnalysisBundle) -> None:
        for entry in bundle.trace_entries:
            if _entry_key(entry) in self._compaction_entry_keys:
                continue
            active = self._active.get(entry.session_id)
            if active is None or not entry.message_id or entry.message_id not in active:
                continue
            output = self._entry_output_tokens(entry)
            if output is None:
                self._unknown_growth.setdefault(entry.session_id, []).append(entry.completed_at_ms)
            elif output > 0 and "output" in entry.tokens.known_fields:
                events.setdefault(entry.session_id, []).append((entry.completed_at_ms, output))

    def _message_growth(self, events: dict[str, list[tuple[int, int]]], snapshot: SessionSnapshot,
                        request_messages: dict[tuple[str, str], list[TraceEntry]]) -> None:
        for message in snapshot.messages:
            active = self._active.get(message.session_id)
            if active is None or message.message_id not in active:
                continue
            if message.role is MessageRole.ASSISTANT:
                self._assistant_growth(events, message, request_messages)
                continue
            tokens = sum(_part_tokens(part) for part in message.parts)
            if tokens > 0:
                events.setdefault(message.session_id, []).append((message.created_at_ms, tokens))

    @staticmethod
    def _assistant_growth(events: dict[str, list[tuple[int, int]]], message: NormalizedMessage,
                          request_messages: dict[tuple[str, str], list[TraceEntry]]) -> None:
        requests = request_messages.get((message.session_id, message.message_id), ())
        output_known = any("output" in entry.tokens.known_fields for entry in requests)
        if not requests or not output_known:
            tokens = (sum(_part_tokens(part) for part in message.parts if part.kind in {"text", "reasoning"})
                      if requests else _message_tokens(message))
            if tokens > 0:
                events.setdefault(message.session_id, []).append((message.completed_at_ms or message.created_at_ms, tokens))
        for part in message.parts:
            if part.kind == "tool" and (tokens := _tool_result_tokens(part)) > 0:
                events.setdefault(message.session_id, []).append((part.updated_at_ms or part.created_at_ms, tokens))

    def _prefix_growth(self, events: dict[str, list[tuple[int, int]]]) -> dict[str, tuple[list[int], list[int]]]:
        result: dict[str, tuple[list[int], list[int]]] = {}
        for session_id, values in events.items():
            values.sort()
            times: list[int] = []
            totals = [0]
            for at_ms, tokens in values:
                times.append(at_ms)
                totals.append(totals[-1] + tokens)
            result[session_id] = times, totals
        for values in self._unknown_growth.values():
            values.sort()
        return result

    def _growth_between(self, session_id: str, after_ms: int, through_ms: int) -> int:
        index = self._growth.get(session_id)
        if index is None or through_ms <= after_ms:
            return 0
        times, totals = index
        first, last = bisect_right(times, after_ms), bisect_right(times, through_ms)
        return totals[last] - totals[first]

    def _entry_output_tokens(self, entry: TraceEntry) -> int | None:
        if "output" in entry.tokens.known_fields:
            return entry.tokens.output + entry.tokens.reasoning
        message = self._messages.get((entry.session_id, entry.message_id))
        if message is None:
            return None
        text = sum(_part_tokens(part) for part in message.parts if part.kind in {"text", "reasoning"})
        return text + max(0, entry.tokens.reasoning) if text > 0 else None

    def _entry_context_tokens(self, entry: TraceEntry) -> int | None:
        if not {"input", "cache_read", "cache_write"}.issubset(entry.tokens.known_fields):
            return None
        output = self._entry_output_tokens(entry)
        if output is None:
            return None
        return entry.request_input_approx + output

    def _has_unknown_growth(self, session_id: str, after_ms: int, through_ms: int) -> bool:
        times = self._unknown_growth.get(session_id, ())
        return bisect_right(times, after_ms) < bisect_right(times, through_ms)

    def _build_anchors(self, snapshot: SessionSnapshot, bundle: RootAnalysisBundle,
                       compactions: tuple[CompactionContext, ...]) -> None:
        events = self._anchor_events(snapshot, bundle, compactions)
        anchors: dict[str, TraceEntry | None] = {}
        compacted: dict[str, CompactionContext | None] = {}
        for _at_ms, _priority, kind, value in events:
            if kind == "boundary":
                self._clear_anchor(str(value), anchors, compacted)
                continue
            if kind == "compaction":
                item = value
                assert isinstance(item, CompactionContext)
                self._start_compaction_epoch(item, anchors, compacted)
                continue
            entry = value
            assert isinstance(entry, TraceEntry)
            self._anchor_request(entry, anchors, compacted)

    def _anchor_events(self, snapshot: SessionSnapshot, bundle: RootAnalysisBundle,
                       compactions: tuple[CompactionContext, ...]) -> list[tuple[int, int, str, object]]:
        events = [(entry.completed_at_ms, 2, "request", entry) for entry in bundle.trace_entries
                  if entry.request_input_approx > 0 and _entry_key(entry) not in self._compaction_entry_keys]
        events.extend((item.completed_at_ms, 1, "compaction", item) for item in compactions
                      if item.completed_at_ms > 0)
        events.extend((item.at_ms, 0, "boundary", item.session_id) for item in snapshot.context_boundaries)
        events.sort(key=lambda item: (item[0], item[1]))
        return events

    @staticmethod
    def _clear_anchor(session_id: str, anchors: dict[str, TraceEntry | None],
                      compacted: dict[str, CompactionContext | None]) -> None:
        anchors[session_id] = None
        compacted[session_id] = None

    def _start_compaction_epoch(self, item: CompactionContext, anchors: dict[str, TraceEntry | None],
                                compacted: dict[str, CompactionContext | None]) -> None:
        anchors[item.session_id] = None
        usable = item.tokens is not None and item.tokens > 0
        active = self.active_message(item.session_id, item.message_id)
        compacted[item.session_id] = item if usable and active is not False else None

    def _anchor_request(self, entry: TraceEntry, anchors: dict[str, TraceEntry | None],
                        compacted: dict[str, CompactionContext | None]) -> None:
        key = _entry_key(entry)
        if self.active_entry(entry) is False:
            self._clear_anchor(entry.session_id, anchors, compacted)
            self._anchors[key] = None
            return
        anchor = anchors.get(entry.session_id)
        checkpoint = compacted.get(entry.session_id)
        if anchor is None and self._temporary_after_compaction(entry, checkpoint, compacted):
            return
        if anchor is not None and self._same_model(anchor, entry):
            if self._temporary_after_request(entry, anchor, anchors, compacted):
                return
        anchors[entry.session_id] = entry
        compacted[entry.session_id] = None
        self._anchors[key] = entry

    def _temporary_after_compaction(self, entry: TraceEntry, checkpoint: CompactionContext | None,
                                   compacted: dict[str, CompactionContext | None]) -> bool:
        if checkpoint is None or not self._same_compaction_model(checkpoint, entry):
            return False
        expected = self._expected_input(checkpoint.tokens, checkpoint.completed_at_ms, entry)
        if expected is None:
            self._mark_uncertain(entry, None)
            compacted[entry.session_id] = None
            return True
        if entry.request_input_approx >= expected:
            return False
        self._temporary_from_compaction[_entry_key(entry)] = checkpoint
        self._anchors[_entry_key(entry)] = None
        return True

    def _temporary_after_request(self, entry: TraceEntry, anchor: TraceEntry,
                                 anchors: dict[str, TraceEntry | None],
                                 compacted: dict[str, CompactionContext | None]) -> bool:
        anchor_tokens = self._entry_context_tokens(anchor)
        expected = None if anchor_tokens is None else self._expected_input(anchor_tokens, anchor.completed_at_ms, entry)
        if expected is None:
            self._mark_uncertain(entry, anchors)
            compacted[entry.session_id] = None
            return True
        if entry.request_input_approx >= expected:
            return False
        if self.active_entry(entry) is True and self.active_entry(anchor) is True:
            self._anchors[_entry_key(entry)] = anchor
            self._temporary.add(_entry_key(entry))
        else:
            self._mark_uncertain(entry, anchors)
            compacted[entry.session_id] = None
        return True

    def _mark_uncertain(self, entry: TraceEntry, anchors: dict[str, TraceEntry | None] | None) -> None:
        key = _entry_key(entry)
        self._anchors[key] = None
        self._uncertain.add(key)
        if anchors is not None:
            anchors[entry.session_id] = None

    @staticmethod
    def _same_model(left: TraceEntry, right: TraceEntry) -> bool:
        return left.model == right.model and left.variant == right.variant

    @staticmethod
    def _same_compaction_model(left: CompactionContext, right: TraceEntry) -> bool:
        return (left.provider_id == right.model.provider and left.model_id == right.model.model
                and left.variant == (right.variant or ""))

    def _request_start(self, entry: TraceEntry) -> int:
        return self._message_times.get((entry.session_id, entry.message_id), entry.completed_at_ms)

    def _expected_input(self, baseline: int, baseline_at_ms: int, entry: TraceEntry) -> int | None:
        start = self._request_start(entry)
        if start > baseline_at_ms:
            return baseline + self._growth_between(entry.session_id, baseline_at_ms, start)
        output = self._entry_output_tokens(entry)
        if output is None:
            return None
        growth = self._growth_between(entry.session_id, baseline_at_ms, entry.completed_at_ms)
        return baseline + max(0, growth - output)

    def active_entry(self, entry: TraceEntry) -> bool | None:
        active = self._active.get(entry.session_id)
        if active is None:
            return None
        return bool(entry.message_id and entry.message_id in active)

    def active_message(self, session_id: str, message_id: str) -> bool | None:
        active = self._active.get(session_id)
        return None if active is None else message_id in active

    def active_prompt(self, record: PromptRecord) -> bool | None:
        active = self._active.get(record.session_id)
        if active is None:
            return None
        if record.prompt_id in active:
            return True
        return any(self.active_entry(entry) is True for entry in record.entries
                   if entry.session_id == record.session_id)

    def session_for_event(self, event_id: str) -> str | None:
        return self._event_sessions.get(event_id)

    def comparable_selection(self, previous: TraceEntry, current: TraceEntry) -> bool:
        """A selection alone is not a rewrite, but current membership must prove continuity.

        Only the same provider/model with complete retained history and nondecreasing
        observed input supports this comparison. Effort may differ. Missing history
        or telemetry never proves that an earlier epoch remains comparable.
        """
        active = self._active.get(current.session_id)
        if active is None or previous.model != current.model:
            return False
        fields = {"input", "cache_read", "cache_write", "output"}
        if not all(fields.issubset(entry.tokens.known_fields) for entry in (previous, current)):
            return False
        before = self._entry_context_tokens(previous)
        after = self._entry_context_tokens(current)
        if before is None or after is None or current.request_input_approx < before:
            return False
        messages = [message for message in self._snapshot.messages
                    if message.session_id == current.session_id
                    and message.created_at_ms <= self._request_start(current)]
        return bool(messages) and all(message.message_id in active for message in messages)

    def _activity_end(self, record: PromptRecord, entry: TraceEntry) -> int:
        end = max(record.prompt_time_ms, record.last_request_time_ms, record.terminal_time_ms, entry.completed_at_ms)
        limit = self._next_prompt.get((record.session_id, record.prompt_id, record.prompt_time_ms))
        for boundary in self._snapshot.context_boundaries:
            if boundary.session_id == record.session_id and boundary.at_ms > record.prompt_time_ms:
                limit = boundary.at_ms if limit is None else min(limit, boundary.at_ms)
        for compaction in self._compaction_starts.get(record.session_id, ()):
            if compaction > record.prompt_time_ms:
                limit = compaction if limit is None else min(limit, compaction)
        activity = self._activity_messages.get(record.session_id)
        if activity is None:
            return min(end, limit) if limit is not None else end
        starts, values = activity
        first = bisect_left(starts, record.prompt_time_ms)
        last = len(starts) if limit is None else bisect_left(starts, limit)
        for activity_ms, message_id in values[first:last]:
            if self.active_message(record.session_id, message_id) is False:
                continue
            end = max(end, activity_ms)
        return min(end, limit) if limit is not None else end

    def continuing(self, record: PromptRecord, candidate: TraceEntry | None = None) -> ContinuingContext:
        entry = candidate or record.last_root_entry
        if entry is None or entry.request_input_approx <= 0:
            return ContinuingContext(entry, None, 0, 0, None)
        active = self.active_entry(entry)
        if active is False:
            tokens = self._entry_context_tokens(entry)
            if tokens is None:
                return ContinuingContext(entry, None, 0, 0, False)
            return ContinuingContext(entry, tokens, entry.request_input_approx,
                                     self._entry_output_tokens(entry), False)
        key = _entry_key(entry)
        if key in self._temporary_from_compaction:
            compacted = self._temporary_from_compaction[key]
            end = self._activity_end(record, entry)
            if self._has_unknown_growth(entry.session_id, compacted.completed_at_ms, end):
                return ContinuingContext(entry, None, 0, 0, active)
            tokens = compacted.tokens + self._growth_between(entry.session_id, compacted.completed_at_ms, end)
            return ContinuingContext(entry, tokens, compacted.tokens,
                                     max(0, tokens - compacted.tokens), active)
        if key in self._uncertain:
            return ContinuingContext(entry, None, 0, 0, active)
        anchor = self._anchors.get(key, entry)
        if anchor is None:
            return ContinuingContext(entry, None, 0, 0, active)
        end = self._activity_end(record, entry)
        if key in self._temporary:
            anchor_tokens = self._entry_context_tokens(anchor)
            if anchor_tokens is None or self._has_unknown_growth(anchor.session_id, anchor.completed_at_ms, end):
                return ContinuingContext(anchor, None, 0, 0, active)
            tokens = anchor_tokens + self._growth_between(anchor.session_id, anchor.completed_at_ms, end)
            cached = anchor.request_input_approx
            return ContinuingContext(anchor, tokens, cached, max(0, tokens - cached), active)
        growth = self._growth_between(entry.session_id, entry.completed_at_ms, end)
        entry_tokens = self._entry_context_tokens(entry)
        if entry_tokens is None or self._has_unknown_growth(entry.session_id, entry.completed_at_ms, end):
            return ContinuingContext(entry, None, 0, 0, active)
        output = self._entry_output_tokens(entry)
        return ContinuingContext(entry, entry_tokens + growth, entry.request_input_approx, output + growth, active)
