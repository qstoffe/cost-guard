"""Source-specific Watch observation mechanics behind a small common surface."""
from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, Queue
from threading import Event, Thread
from typing import Mapping, Sequence

from src.domain import NormalizedSession
from src.domain.session_tree import root_by_session
from src.sources.base import LiveSessionSource, SessionSource, SourceChange
from src.sources.errors import SourceError, SourceResyncRequiredError
from src.runtime_errors import recoverable, recovered


@dataclass(frozen=True, slots=True)
class CatalogObservation:
    sessions: tuple[NormalizedSession, ...]
    roots: tuple[NormalizedSession, ...]
    root_by_session: Mapping[str, str]
    revisions: Mapping[str, str]


def _root_map(sessions: Sequence[NormalizedSession]) -> tuple[tuple[NormalizedSession, ...], dict[str, str]]:
    mapping = root_by_session(sessions)
    roots = tuple(
        sorted(
            (item for item in sessions if item.parent_session_id is None and item.archived_at_ms is None),
            key=lambda item: (item.updated_at_ms, item.session_id),
            reverse=True,
        )
    )
    return roots, mapping


def _revisions(source: SessionSource, root_ids: Sequence[str]) -> Mapping[str, str]:
    batch = getattr(source, "get_session_tree_revisions", None)
    if callable(batch):
        return dict(batch(root_ids))
    return {root_id: source.get_session_tree_revision(root_id) for root_id in root_ids}


def observe_catalog(source: SessionSource, *, session_id: str | None = None) -> CatalogObservation:
    sessions = tuple(source.list_sessions())
    roots, root_by_session = _root_map(sessions)
    if session_id is not None:
        root_id = root_by_session.get(session_id)
        if root_id is None:
            return CatalogObservation(sessions, (), root_by_session, {})
        roots = tuple(item for item in roots if item.session_id == root_id)
    revisions = _revisions(source, tuple(item.session_id for item in roots))
    return CatalogObservation(sessions, roots, root_by_session, revisions)


@dataclass(frozen=True, slots=True)
class PumpResult:
    change: SourceChange | None = None
    resync_required: bool = False
    error: str = ""
    software_fault: bool = False


class LiveEventPump:
    """Consume one live-only source stream on a daemon thread.

    The pump never treats events as durable truth.  End/failure becomes an
    explicit resync signal; the coordinator owns reconnection after the fresh
    snapshot has completed.
    """

    def __init__(self, source: LiveSessionSource) -> None:
        self.source = source
        self._queue: Queue[PumpResult] = Queue()
        self._stop = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(target=self._run, name="cost-guard-v2-events", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            for change in self.source.iter_changes():
                if self._stop.is_set():
                    return
                recovered("watch-event-observer")
                self._queue.put(PumpResult(change=change))
        except SourceResyncRequiredError as exc:
            if not self._stop.is_set():
                self._queue.put(PumpResult(resync_required=True, error=str(exc)))
        except SourceError as exc:
            if not self._stop.is_set():
                self._queue.put(PumpResult(resync_required=True, error=str(exc)))
        except Exception as exc:
            if self._stop.is_set():
                raise  # Retired pump has no ERROR surface: use the fatal hook.
            # Hints are disposable; only an authoritative snapshot may
            # restore correctness. The coordinator shows ERROR until resync.
            recoverable(exc, "watch-event-observer")
            self._queue.put(PumpResult(resync_required=True, software_fault=True,
                error="ERROR: Watch event observer failed · resynchronizing"))

    def get(self, timeout: float) -> PumpResult | None:
        try:
            return self._queue.get(timeout=max(0.0, timeout))
        except Empty:
            return None

    def stop(self) -> None:
        self._stop.set()
