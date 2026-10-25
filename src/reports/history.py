"""Explicit history scopes: discovery selects candidates, analysis establishes usage."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from src.domain import NormalizedSession
from src.domain.session_tree import root_activity
from src.analysis.models import RootAnalysisBundle, TraceEntry
from src.analysis.timezones import local_day_start_ms
from src.analysis.period_ccost import reconcile_usage
from src.sources.base import SessionSource


@dataclass(frozen=True, slots=True)
class HistoryRequirements:
    scope: str
    start_ms: int | None = None
    root_ids: frozenset[str] | None = None
    limit: int | None = None

    def select(self, roots: Sequence[NormalizedSession], activity: Mapping[str, int]) -> tuple[NormalizedSession, ...]:
        candidates = tuple(root for root in roots
                           if (self.root_ids is None or root.session_id in self.root_ids)
                           and (self.start_ms is None or activity.get(root.session_id, root.updated_at_ms) >= self.start_ms))
        return candidates if self.limit is None else candidates[:self.limit]


def daily_roots(sessions: Sequence[NormalizedSession], start_ms: int) -> tuple[NormalizedSession, ...]:
    # Creation is deliberately not a cutoff: old roots with new child/request
    # activity qualify. Hydrated trace entries, never this gate, establish totals.
    activity = root_activity(sessions)
    roots = tuple(item for item in sessions if item.parent_session_id is None)
    return HistoryRequirements("watch-today", start_ms=start_ms).select(roots, activity)


class WatchHistoryAcquisition:
    """Incremental source-backed daily scope; process retention belongs to Watch.

    Only revision-proven stable roots skip reanalysis. A completed plan publishes
    its flattened scope once, not quadratically after every enrichment slice.
    """

    def __init__(self) -> None:
        self.entries_by_root: dict[str, tuple[TraceEntry, ...]] = {}
        self.state: dict[str, tuple[int, str]] = {}
        self.day_start_ms: int | None = None
        self.scope_start_ms: int | None = None
        self.published_start_ms: int | None = None
        self._published_entries: tuple[TraceEntry, ...] = ()
        self._dirty = True
        self._retained: dict[tuple, TraceEntry] = {}
        self._retained_publication: tuple[TraceEntry, ...] = ()
        self._stepped: set[tuple] = set()

    def reset(self) -> None:
        self.entries_by_root.clear()
        self.state.clear()
        self.day_start_ms = None
        self.scope_start_ms = None
        self.published_start_ms = None
        self._dirty = True
        self._retained.clear()
        self._stepped.clear()
        self._retained_publication = ()

    def candidates(self, source: SessionSource, sessions: Sequence[NormalizedSession], *,
                   timezone_id: str, now_ms: int, active_root_ids: Sequence[str] = (),
                   start_ms: int | None = None) -> tuple[tuple[NormalizedSession, ...], Mapping[str, str]]:
        day = local_day_start_ms(timezone_id, now_ms=now_ms)
        start = min(day, start_ms) if start_ms is not None else day
        if self.day_start_ms != day or self.scope_start_ms is None or start < self.scope_start_ms:
            retained = dict(self._retained)
            stepped = set(self._stepped)
            self.reset()
            self._retained = {key: entry for key, entry in retained.items() if start <= entry.completed_at_ms <= now_ms}
            self._stepped = {key[:3] for key in self._retained if key[3] is not None} & stepped
            self.day_start_ms = day
            self.scope_start_ms = start
        roots = daily_roots(sessions, self.scope_start_ms)
        selected = {root.session_id for root in roots}
        active = set(active_root_ids)
        roots += tuple(root for root in sessions if root.parent_session_id is None
                       and root.session_id in active and root.session_id not in selected)
        batch = getattr(source, "get_session_tree_revisions", None)
        revisions = (batch(tuple(root.session_id for root in roots)) if callable(batch)
                     else {root.session_id: source.get_session_tree_revision(root.session_id) for root in roots})
        ids = {root.session_id for root in roots}
        if set(self.entries_by_root) - ids:
            self._dirty = True
        self.entries_by_root = {key: entries for key, entries in self.entries_by_root.items() if key in ids}
        self.state = {key: value for key, value in self.state.items() if key in ids}
        return roots, revisions

    def unchanged(self, root_id: str, revision: str) -> bool:
        return self.state.get(root_id) == (self.day_start_ms, revision)

    def record(self, root_id: str, bundle: RootAnalysisBundle, *, now_ms: int) -> tuple[TraceEntry, ...]:
        assert self.scope_start_ms is not None
        entries = tuple(entry for entry in bundle.trace_entries if self.scope_start_ms <= entry.completed_at_ms <= now_ms)
        self._retain(bundle.trace_entries, now_ms)
        self._dirty = self._dirty or self.entries_by_root.get(root_id) != entries
        self.entries_by_root[root_id] = entries
        if bundle.cacheable and all(entry.completed_at_ms <= now_ms for entry in bundle.trace_entries):
            self.state[root_id] = (self.day_start_ms, bundle.source_revision)
        else:
            self.state.pop(root_id, None)
        return entries

    def _retain(self, entries: Sequence[TraceEntry], now_ms: int) -> None:
        for entry in entries:
            message = entry.message_id or (entry.parent_event_id, entry.sort_order)
            base = entry.source_instance, entry.session_id, message
            if entry.step_part_id:
                self._retained.pop((*base, None), None)
                self._stepped.add(base)
            elif base in self._stepped:
                continue
            identity = (*base, entry.step_part_id)
            if (self.scope_start_ms or 0) <= entry.completed_at_ms <= now_ms:
                self._retained[identity] = reconcile_usage(self._retained.get(identity), entry)
            else:
                self._retained.pop(identity, None)

    def retained_entries(self) -> tuple[TraceEntry, ...]:
        return self._retained_publication

    def entries(self) -> tuple[TraceEntry, ...]:
        self.published_start_ms = self.scope_start_ms
        retained = tuple(self._retained.values())
        if retained != self._retained_publication:
            self._retained_publication = retained
        if self._dirty:
            self._published_entries = tuple(entry for values in self.entries_by_root.values() for entry in values)
            self._dirty = False
        return self._published_entries
