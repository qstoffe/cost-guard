"""Select one OpenCode generation and report migration gaps without merging history."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from src.domain import IntegrationHealth, NormalizedSession

from .base import SessionSource
from .errors import SourceError, SourceUnavailableError
from .opencode_v1 import OpenCodeV1Source
from .opencode_v2 import OpenCodeV2Source


MISSING_IN_V2 = "missing_in_v2"
NEWER_IN_V1 = "newer_in_v1"


@dataclass(frozen=True, slots=True)
class MigrationGapSession:
    """Normalized V1 activity window that the selected V2 history may lack.

    ``first_ms``/``last_ms`` bound the possibly unrepresented activity: a whole
    missing session, or only V1 activity after its V2 copy's last update.
    """

    session_id: str
    root_session_id: str
    kind: str
    first_ms: int
    last_ms: int

    def overlaps(self, start_ms: int, end_ms: int | None = None) -> bool:
        return self.last_ms >= start_ms and (end_ms is None or self.first_ms < end_ms)


@dataclass(frozen=True, slots=True)
class MigrationGapDiagnostic:
    inspected: bool
    missing_in_v2: tuple[str, ...] = ()
    newer_in_v1: tuple[str, ...] = ()
    detail: str = ""
    sessions: tuple[MigrationGapSession, ...] = ()

    @property
    def has_gap(self) -> bool:
        return bool(self.missing_in_v2 or self.newer_in_v1)


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
    evidence = tuple(
        MigrationGapSession(
            session_id, _legacy_root(legacy, session_id), MISSING_IN_V2,
            min(legacy[session_id].created_at_ms, legacy[session_id].updated_at_ms),
            _last_activity_ms(legacy[session_id]),
        )
        for session_id in missing
    ) + tuple(
        MigrationGapSession(
            session_id, _legacy_root(legacy, session_id), NEWER_IN_V1,
            modern[session_id].updated_at_ms, _last_activity_ms(legacy[session_id]),
        )
        for session_id in newer
    )
    return MigrationGapDiagnostic(
        True, tuple(missing), tuple(newer), "metadata-only session comparison complete", evidence,
    )


def _last_activity_ms(session: NormalizedSession) -> int:
    return max(session.created_at_ms, session.updated_at_ms, session.archived_at_ms or 0)


def _legacy_root(legacy: dict[str, NormalizedSession], session_id: str) -> str:
    current = legacy[session_id]
    seen = {session_id}
    while current.parent_session_id and current.parent_session_id not in seen:
        parent = legacy.get(current.parent_session_id)
        if parent is None:
            # An unlisted parent is still the best available causal-root identity.
            return current.parent_session_id
        seen.add(parent.session_id)
        current = parent
    return current.session_id


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
        # It is evidence, not a source warning: reports decide scope relevance
        # and Watch never shows it.
        try:
            v1 = self._v1_factory()
            gap = inspect_v1_v2_migration_gap(v1, v2)
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
