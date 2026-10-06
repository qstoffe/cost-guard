"""Provider-neutral integration status values."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IntegrationHealth:
    available: bool
    healthy: bool
    detail: str = ""
