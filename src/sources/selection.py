"""Select one OpenCode generation and report migration gaps without merging history."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from src.domain import IntegrationHealth, NormalizedSession

from .base import SessionSource
from .errors import SourceError, SourceUnavailableError
from .opencode_v1 import OpenCodeV1Source
from .opencode_v2 import OpenCodeV2Source


@dataclass(frozen=True, slots=True)
class MigrationGapDiagnostic:
    inspected: bool
    missing_in_v2: tuple[str, ...] = ()
    newer_in_v1: tuple[str, ...] = ()
    detail: str = ""

    @property
    def has_gap(self) -> bool:
        return bool(self.missing_in_v2 or self.newer_in_v1)

    def warning(self) -> str | None:
        if not self.has_gap:
            return None
        pieces: list[str] = []
        if self.missing_in_v2:
            pieces.append(f"{len(self.missing_in_v2)} legacy V1 session(s) are missing from V2")
        if self.newer_in_v1:
            pieces.append(f"{len(self.newer_in_v1)} legacy V1 session(s) are newer than their V2 copy")
        return (
            "OpenCode V1 contains history that may not be represented in the selected V2 source: "
            + "; ".join(pieces)
            + ". Cost Guard will not merge sources automatically; set openCode.source to v1 to inspect legacy history."
        )


@dataclass(frozen=True, slots=True)
class SourceSelection:
    source: SessionSource
    selected: str
    warnings: tuple[str, ...]
    selected_health: IntegrationHealth
    migration_gap: MigrationGapDiagnostic | None = None


def _session_map(values: Sequence[NormalizedSession]) -> dict[str, NormalizedSession]:
    return {value.session_id: value for value in values}


def inspect_v1_v2_migration_gap(v1: SessionSource, v2: SessionSource) -> MigrationGapDiagnostic:
    """Compare session metadata only; never hydrate or reconcile source payloads."""

    try:
        v1_health = v1.probe()
    except SourceError as exc:
        return MigrationGapDiagnostic(False, detail=f"V1 metadata could not be inspected: {exc}")
    if not v1_health.healthy:
        return MigrationGapDiagnostic(False, detail="V1 metadata source is not healthy")
    try:
        legacy = _session_map(v1.list_sessions())
        modern = _session_map(v2.list_sessions())
    except SourceError as exc:
        return MigrationGapDiagnostic(False, detail=f"migration metadata could not be compared: {exc}")
    missing = sorted(session_id for session_id in legacy if session_id not in modern)
    newer = sorted(
        session_id
        for session_id, legacy_session in legacy.items()
        if session_id in modern and legacy_session.updated_at_ms > modern[session_id].updated_at_ms
    )
    return MigrationGapDiagnostic(True, tuple(missing), tuple(newer), "metadata-only session comparison complete")


class SourceSelector:
    """Resolve ``auto|v1|v2`` to exactly one active Session Source."""

    def __init__(
        self,
        *,
        v1_factory: Callable[[], SessionSource] = OpenCodeV1Source,
        v2_factory: Callable[[], SessionSource] = OpenCodeV2Source,
    ):
        self._v1_factory = v1_factory
        self._v2_factory = v2_factory

    @staticmethod
    def _probe(source: SessionSource) -> IntegrationHealth:
        try:
            return source.probe()
        except SourceError as exc:
            return IntegrationHealth(available=True, healthy=False, detail=str(exc))

    @staticmethod
    def _failure(label: str, health: IntegrationHealth) -> SourceUnavailableError:
        detail = health.detail or "source is unavailable"
        return SourceUnavailableError(f"OpenCode {label.upper()} was requested but is not usable: {detail}")

    def _selection_for_v2(
        self,
        v2: SessionSource,
        health: IntegrationHealth,
        *,
        warnings: list[str] | None = None,
    ) -> SourceSelection:
        result_warnings = list(warnings or ())
        gap: MigrationGapDiagnostic | None = None
        # Gap inspection is explicitly best-effort and metadata-only.  It can
        # never switch the selected source or fail an otherwise healthy V2 run.
        try:
            v1 = self._v1_factory()
            gap = inspect_v1_v2_migration_gap(v1, v2)
            warning = gap.warning()
            if warning:
                result_warnings.append(warning)
        except (SourceError, OSError, ValueError):
            gap = MigrationGapDiagnostic(False, detail="legacy V1 migration-gap inspection was unavailable")
        return SourceSelection(v2, "v2", tuple(result_warnings), health, gap)

    def select(self, requested: str = "auto") -> SourceSelection:
        mode = requested.strip().lower()
        if mode not in {"auto", "v1", "v2"}:
            raise ValueError("OpenCode source must be auto, v1, or v2")

        if mode == "v2":
            v2 = self._v2_factory()
            health = self._probe(v2)
            if not health.healthy:
                raise self._failure("v2", health)
            return self._selection_for_v2(v2, health)

        if mode == "v1":
            v1 = self._v1_factory()
            health = self._probe(v1)
            if not health.healthy:
                raise self._failure("v1", health)
            return SourceSelection(v1, "v1", (), health)

        v2 = self._v2_factory()
        v2_health = self._probe(v2)
        if v2_health.healthy:
            return self._selection_for_v2(v2, v2_health)

        v1 = self._v1_factory()
        v1_health = self._probe(v1)
        if v1_health.healthy:
            warnings: list[str] = []
            if v2_health.available:
                warnings.append(
                    "OpenCode V2 was detected but is not healthy; Cost Guard selected V1 instead. "
                    + (v2_health.detail or "")
                )
            return SourceSelection(v1, "v1", tuple(warnings), v1_health)

        detail = (
            f"V2: {v2_health.detail or 'unavailable'}; "
            f"V1: {v1_health.detail or 'unavailable'}"
        )
        raise SourceUnavailableError("No supported healthy OpenCode source is available. " + detail)
