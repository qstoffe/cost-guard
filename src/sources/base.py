"""Session Source protocols shared by concrete OpenCode generations."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping, Protocol, Sequence

from src.domain import IntegrationHealth, NormalizedSession, SessionCapabilities, SessionSnapshot


@dataclass(frozen=True, slots=True)
class SourceChange:
    """Source-neutral live change hint.

    Change hints are deliberately not treated as durable history.  Watch may use
    them to decide what to refresh, but a stream disconnect always requires a
    fresh snapshot before Cost Guard trusts source state again.
    """

    source_id: str
    event_type: str
    session_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)


class SessionSource(Protocol):
    @property
    def source_id(self) -> str: ...

    @property
    def capabilities(self) -> SessionCapabilities: ...

    def probe(self) -> IntegrationHealth: ...

    def list_sessions(self, since_ms: int | None = None) -> Sequence[NormalizedSession]: ...

    def get_session_tree_revision(self, session_id: str) -> str: ...

    def load_session_snapshot(self, session_id: str) -> SessionSnapshot: ...


class LiveSessionSource(SessionSource, Protocol):
    """A Session Source that can emit non-replayable live change hints."""

    def iter_changes(self) -> Iterator[SourceChange]: ...
