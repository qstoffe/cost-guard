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
        self.admitted = False
        self.free = False

    def admit(self):
        """Pre-acquisition handshake; before the grant the host may replace this startup."""
        if self.admitted:
            return
        self.connection.send(('admit', None))
        self._resume(self.connection.recv())
        self.admitted = True

    def _resume(self, grant):
        # 'run' parks after every quantum (background pacing); 'free' parks only
        # when the host has requested a yield for waiting equal/higher-priority work.
        if grant not in ('run', 'free'):
            raise RuntimeError('invalid_worker_control')
        self.free = grant == 'free'
        self.started = self.clock()

    def admit_read(self):
        if current_thread() is self.owner:
            self.checkpoint()
        else:
            self.permit.wait()

    def checkpoint(self):
        if not self.admitted:
            self.admit()
            return
        if self.clock() - self.started < self.seconds:
            return
        if self.free:
            if not self.connection.poll():
                self.started = self.clock()
                return
            if self.connection.recv() != 'yield':
                raise RuntimeError('invalid_worker_control')
        self.permit.clear()
        self.connection.send(('yield', None))
        self._resume(self.connection.recv())
        self.permit.set()
