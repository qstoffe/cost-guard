"""Bounded immutable full-state publications with instance-bound replay IDs."""
from collections import deque
import json
from threading import Condition

MAX_EVENT_BYTES = 2 * 1024 * 1024
MAX_REPLAY_BYTES = 8 * 1024 * 1024


class EventHub:
    def __init__(self, instance, *, capacity=32):
        self.instance = instance
        self.capacity = capacity
        self.condition = Condition()
        self.sequence = 0
        self.replay = deque()
        self.bytes = 0
        self.current = {}
        self.closed = False

    def _encode(self, kind, value, sequence):
        return (f"id: {self.instance}:{sequence}\nevent: {kind}\ndata: " +
                json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")) + "\n\n").encode("ascii")

    def publish(self, kind, value):
        value = value.to_json() if hasattr(value, "to_json") else value
        with self.condition:
            if self.closed or self.current.get(kind) == value:
                return
            sequence = self.sequence + 1
            data = self._encode(kind, value, sequence)
            if len(data) > MAX_EVENT_BYTES:
                value = {"state": "result_too_large", "view": None}
                data = self._encode(kind, value, sequence)
            # Store only detached JSON values, never the publisher's mutable dict.
            self.current[kind] = json.loads(json.dumps(value))
            self.sequence = sequence
            self.replay.append((sequence, data))
            self.bytes += len(data)
            while len(self.replay) > self.capacity or self.bytes > MAX_REPLAY_BYTES:
                self.bytes -= len(self.replay.popleft()[1])
            self.condition.notify_all()

    def snapshot(self):
        with self.condition:
            return dict(instance_id=self.instance, sequence=self.sequence,
                        values=json.loads(json.dumps(self.current)))

    def read(self, last_id, *, timeout=0.5):
        with self.condition:
            try:
                instance, raw = last_id.rsplit(":", 1)
                sequence = int(raw)
                if instance != self.instance or sequence < 0 or sequence > self.sequence:
                    raise ValueError("old_instance")
            except (ValueError, AttributeError):
                return self.sequence, (self._encode("resync", {"instance_id": self.instance}, self.sequence),)
            if sequence == self.sequence and not self.closed:
                self.condition.wait(timeout)
            if self.replay and sequence < self.replay[0][0] - 1:
                return self.sequence, (self._encode("resync", {"instance_id": self.instance}, self.sequence),)
            return self.sequence, tuple(data for number, data in self.replay if number > sequence)

    def close(self, reason):
        self.publish("terminal", {"reason": reason, "message": "Host stopped. Run the launcher again."})
        with self.condition:
            self.closed = True
            self.condition.notify_all()
