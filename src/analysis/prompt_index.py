"""Snapshot-local causal lookups; preserve strict timestamp prompt windows."""
from bisect import bisect_left, bisect_right

from src.domain import EventKind, MessageRole
from .billing import provider_matches


class PromptIndex:
    def __init__(self, snapshot, entries, visible, tracked_provider):
        self.assistants = {}
        self.message_order = {message.message_id: index for index, message in enumerate(snapshot.messages)}
        for message in snapshot.messages:
            if message.session_id == snapshot.root.session_id and message.role is MessageRole.ASSISTANT:
                self.assistants.setdefault(message.parent_message_id, []).append(message)
        self.entries = {}
        meaningful = []
        for entry in entries:
            if entry.session_id == snapshot.root.session_id and provider_matches(entry.model.provider, tracked_provider):
                self.entries.setdefault(entry.parent_event_id, []).append(entry)
                if entry.request_input_approx > 0:
                    meaningful.append(entry)
        self.meaningful = meaningful
        self.times = [entry.completed_at_ms for entry in meaningful]
        self.keys = [(entry.completed_at_ms, entry.sort_order) for entry in meaningful]
        self.windows = {event.event_id: {event.event_id} for event in visible}
        by_time = {}
        for event in visible:
            by_time.setdefault(event.created_at_ms, []).append(event)
        times = sorted(by_time)
        for event in snapshot.events:
            if event.session_id != snapshot.root.session_id or event.kind not in {
                    EventKind.BACKGROUND_COMPLETION, EventKind.OTHER, EventKind.SYNTHETIC_CONTINUATION}:
                continue
            index = bisect_left(times, event.created_at_ms) - 1
            if index < 0 or (index + 1 < len(times) and times[index + 1] == event.created_at_ms):
                continue
            for parent in by_time[times[index]]:
                if event.kind is not EventKind.SYNTHETIC_CONTINUATION or parent.kind is EventKind.SUBTASK:
                    self.windows[parent.event_id].add(event.event_id)

    def before_prompt(self, at_ms):
        index = bisect_right(self.times, at_ms) - 1
        return self.meaningful[index] if index >= 0 else None

    def before_entry(self, entry):
        index = bisect_left(self.keys, (entry.completed_at_ms, entry.sort_order)) - 1
        return self.meaningful[index] if index >= 0 else None
