"""Bounded live stop-cause evidence, matched to persisted V2 idle identity/time.

An event supplies only the missing actor, never a terminal outcome or usage.
Evidence stays in this source instance and cannot reconstruct older history.
"""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
import math
from threading import Lock
from typing import Any


class LiveInterruptionReasons:
    MAX_OBSERVATIONS = 1024

    def __init__(self) -> None:
        self._observed: OrderedDict[tuple[str, str], int] = OrderedDict()
        self._lock = Lock()

    def observe(self, event: Mapping[str, Any]) -> None:
        data = event.get("data")
        if event.get("type") != "session.execution.interrupted" or not isinstance(data, Mapping):
            return
        session_id, event_id, at = data.get("sessionID"), event.get("id"), event.get("created")
        if data.get("reason") != "user" or not isinstance(session_id, str) or not 0 < len(session_id) <= 128:
            return
        if not isinstance(event_id, str) or not event_id.startswith("evt_") or not 4 < len(event_id) <= 128:
            return
        if isinstance(at, bool) or not isinstance(at, (int, float)) or not math.isfinite(at) or at <= 0 or at != int(at):
            return
        # OpenCode's Session.Message.ID.fromEvent replaces only the evt_ prefix.
        key = (session_id, "msg_" + event_id[4:])
        with self._lock:
            self._observed[key] = int(at)
            self._observed.move_to_end(key)
            if len(self._observed) > self.MAX_OBSERVATIONS:
                self._observed.popitem(last=False)

    def signature(self, session_id: str) -> tuple[tuple[str, int], ...]:
        """Live evidence invalidates analysis cached before the event arrived."""
        with self._lock:
            return tuple(sorted((message_id, at) for (owner, message_id), at in self._observed.items()
                                if owner == session_id))

    def reason(self, item: Mapping[str, Any], session_id: str) -> str:
        if item.get("type") != "idle" or item.get("outcome") != "interrupted":
            return ""
        message_id, time = item.get("id"), item.get("time")
        if not isinstance(message_id, str) or not isinstance(time, Mapping):
            return ""
        with self._lock:
            at = self._observed.get((session_id, message_id))
        return "user" if at is not None and time.get("created") == at else ""
