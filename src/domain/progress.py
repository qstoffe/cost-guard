"""Source-neutral startup work observations; also usable by plain text sinks."""
from __future__ import annotations


class WorkProgress(str):
    """A stage label with optional completed/total work, never a global percentage."""
    def __new__(cls, label: str, phase: str, completed: int = 0, total: int | None = None):
        value = super().__new__(cls, label)
        value.phase = phase
        value.completed = max(0, completed)
        value.total = total if total is not None and total > 0 else None
        return value
