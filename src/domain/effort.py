"""Presentation evidence only; never a request option, price or grouping identity."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DefaultEffort:
    scope: str
    selected_model: str
    model_id: str
    package: str
    level: str
    source: str
    signature: str


@dataclass(frozen=True, slots=True)
class EffortEvidence:
    # None is unattributable; "" is an omitted variant on a known request.
    selected: str | None
    effective: str = ""
    source: str = "unknown"
    revision: str = ""


def bounded_evidence(values):
    """Keep bounded distinct facts, with an honest overflow marker, not a guess."""
    result = {}
    for value in values:
        result[value] = None
        if len(result) > 24:
            return (*tuple(result)[:23], EffortEvidence(None, source="omitted"))
    return tuple(result)
