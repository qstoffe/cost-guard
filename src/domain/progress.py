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


def observe_work(phase, units=0):
    observer = _work_observer.get()
    if observer is not None:
        observer(phase, units)


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
