"""Source-neutral startup work observations; also usable by plain text sinks."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar


_work_observer = ContextVar('work_observer', default=None)


@contextmanager
def observing_work(observer):
    """Opt-in scalar work checkpoints; no source identities or content escape."""
    token = _work_observer.set(observer)
    try:
        yield
    finally:
        _work_observer.reset(token)


def observe_work(phase, units=0, *, completed=None, total=None):
    observer = _work_observer.get()
    if observer is not None:
        if completed is None and total is None:
            observer(phase, units)
        else:
            observer(phase, units, completed=completed, total=total)


class DetailProgress:
    """Source-owned milestones, not a fraction of heterogeneous work or time.

    Only explicit phase entry or a known local denominator advances the plan.
    Nested scalar checkpoints feed liveness, never imply a new stage. The
    final source point (70) belongs to accepted publication, outside the child.
    """
    bands = dict(selecting=(3, 10), verifying=(10, 15), reading=(15, 40),
        analyzing=(40, 55), projecting=(55, 65), publishing=(65, 69))
    phases = ('queued', *bands)

    def __init__(self):
        self.phase, self.percent = 'selecting', 3
        self.completed = self.total = None

    def observe(self, phase, units=0, *, completed=None, total=None):
        if phase not in self.bands or units and completed is None:
            return
        start, end = self.bands[phase]
        self.phase = phase
        valid = (isinstance(completed, int) and isinstance(total, int)
            and 0 <= completed <= total and total > 0)
        self.completed, self.total = (completed, total) if valid else (None, None)
        point = start + (end - start) * completed // total if valid else start
        self.percent = max(self.percent, point)


class WorkProgress(str):
    """A stage label with optional completed/total work, never a global percentage."""
    def __new__(cls, label: str, phase: str, completed: int = 0, total: int | None = None,
                *, stage: str | None = None):
        value = super().__new__(cls, label)
        value.phase = phase
        value.completed = max(0, completed)
        value.total = total if total is not None and total > 0 else None
        value.stage = stage
        return value
