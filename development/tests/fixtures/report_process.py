"""Controlled owned-process exit and IPC, without spawning or OS side effects."""
from collections import deque
from unittest.mock import Mock


class ReportProcess:
    def __init__(self, *, messages=(), exit_after_join=None):
        self.messages = deque(messages)
        self.alive = True
        self.exit_after_join = exit_after_join
        self.process = Mock()
        self.process.is_alive.side_effect = lambda: self.alive
        self.process.join.side_effect = self.join
        self.receiver = Mock()
        self.receiver.poll.side_effect = lambda: bool(self.messages)
        self.receiver.recv.side_effect = self.messages.popleft
        self.sender = Mock()
        self.context = Mock()
        self.context.Pipe.return_value = self.receiver, self.sender
        self.context.Process.return_value = self.process

    def join(self, *, timeout):
        if self.exit_after_join is not None and self.process.join.call_count >= self.exit_after_join:
            self.alive = False
