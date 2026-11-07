"""Cooperative finite-worker quanta; parked work retains its private Python stack.

Only the host grants another quantum. No OS suspension, shared source object or
extra acquisition thread is involved. The exact-parent sentinel remains active
while a child is parked, and shutdown still forcibly reaps owned children.
"""
from dataclasses import dataclass
import time
from threading import Event, current_thread

from src.reports import ReportRequest


@dataclass(frozen=True, slots=True)
class ManagedReport(ReportRequest):
    source_identity: str = ''
    quantum_seconds: float = 0.1
    observation_ms: int = 0
    history_batch_size: int = 64


class Quantum:
    def __init__(self, connection, seconds, *, clock=time.monotonic):
        self.connection = connection
        self.seconds = seconds
        self.clock = clock
        self.started = clock()
        self.owner = current_thread()
        self.permit = Event()
        self.permit.set()

    def admit_read(self):
        if current_thread() is self.owner:
            self.checkpoint()
        else:
            self.permit.wait()

    def checkpoint(self):
        if self.clock() - self.started < self.seconds:
            return
        self.permit.clear()
        self.connection.send(('yield', None))
        if self.connection.recv() != 'run':
            raise RuntimeError('invalid_worker_control')
        self.started = self.clock()
        self.permit.set()
