"""Immutable, JSON-ready report boundary values, not native source objects."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import TypeAlias


JsonScalar: TypeAlias = str | int | bool | None
JsonValue: TypeAlias = "JsonScalar | tuple[JsonValue, ...] | ObjectValue"


@dataclass(frozen=True, slots=True)
class ObjectValue:
    """An immutable record; export produces a detached JSON dictionary."""

    fields: tuple[tuple[str, JsonValue], ...]

    def to_json(self) -> dict:
        return {key: export(value) for key, value in self.fields}


def export(value: JsonValue):
    if isinstance(value, ObjectValue):
        return value.to_json()
    if isinstance(value, tuple):
        return [export(item) for item in value]
    return value


def record(**values) -> ObjectValue:
    return ObjectValue(tuple((key, freeze(value)) for key, value in values.items()))


def freeze(value) -> JsonValue:
    """Only boundary primitives; never introspect dataclasses/provider objects."""
    if isinstance(value, Enum):
        return freeze(value.value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Non-finite boundary decimal")
        return str(value)
    if value is None or type(value) in (str, int, bool) or isinstance(value, ObjectValue):
        return value
    if isinstance(value, (tuple, list)):
        return tuple(freeze(item) for item in value)
    raise TypeError("Unapproved boundary value")


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    phase: str
    completed: int = 0
    total: int | None = None

    def to_json(self) -> dict:
        return {"phase": self.phase, "completed": self.completed, "total": self.total}


@dataclass(frozen=True, slots=True)
class ReportError:
    code: str
    retryable: bool = False

    def to_json(self) -> dict:
        return {"code": self.code, "retryable": self.retryable}


@dataclass(frozen=True, slots=True)
class ReportResult:
    instance_id: str
    sequence: int
    observed_at_ms: int
    scope: ObjectValue
    source: ObjectValue
    view: ObjectValue | None = None
    error: ReportError | None = None
    schema_version: int = 1

    def to_json(self) -> dict:
        return {
            "schema_version": self.schema_version, "instance_id": self.instance_id,
            "sequence": self.sequence, "observed_at_ms": self.observed_at_ms,
            "scope": self.scope.to_json(), "source": self.source.to_json(),
            "view": self.view.to_json() if self.view is not None else None,
            "error": self.error.to_json() if self.error is not None else None,
        }
